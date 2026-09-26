#!/usr/bin/env python3
"""Bulk historical Player Wordle import from the public Transfermarkt dataset.
Only senior players with 25+ recorded first-team appearances and complete
profile data are promoted. Safe to rerun: players are upserted by club/name.
"""
import csv, sqlite3, re, datetime, shutil, os
from collections import defaultdict

DB="/var/lib/clubdailyfive/player-wordle/game.sqlite3"
PERF="/var/tmp/player_wordle_performances.csv"
PROFILES="/var/tmp/player_wordle_profiles.csv"
CLUBS={
"bournemouth":"AFC Bournemouth","arsenal":"Arsenal FC","aston-villa":"Aston Villa","brentford":"Brentford FC",
"brighton":"Brighton & Hove Albion","chelsea":"Chelsea FC","coventry":"Coventry City","crystal-palace":"Crystal Palace",
"everton":"Everton FC","fulham":"Fulham FC","hull":"Hull City","ipswich":"Ipswich Town","leeds":"Leeds United",
"liverpool":"Liverpool FC","man-city":"Manchester City","man-utd":"Manchester United","newcastle":"Newcastle United",
"nottingham-forest":"Nottingham Forest","sunderland":"Sunderland AFC","tottenham":"Tottenham Hotspur"}
EUROPE={"Albania","Austria","Belgium","Bosnia-Herzegovina","Bosnia and Herzegovina","Bulgaria","Croatia","Cyprus","Czech Republic","Czechoslovakia","Denmark","England","Estonia","Finland","France","Germany","Greece","Hungary","Iceland","Ireland","Italy","Kosovo","Latvia","Lithuania","Luxembourg","Malta","Montenegro","Netherlands","North Macedonia","Northern Ireland","Norway","Poland","Portugal","Romania","Russia","Scotland","Serbia","Slovakia","Slovenia","Soviet Union","Spain","Sweden","Switzerland","Turkey","Ukraine","Wales","Yugoslavia"}
AFRICA={"Algeria","Angola","Benin","Burkina Faso","Burundi","Cameroon","Cape Verde","Central African Republic","Chad","Congo","Cote d'Ivoire","DR Congo","Egypt","Equatorial Guinea","Eritrea","Ethiopia","Gabon","Gambia","The Gambia","Ghana","Guinea","Guinea-Bissau","Kenya","Liberia","Libya","Madagascar","Mali","Mauritania","Mauritius","Morocco","Mozambique","Namibia","Niger","Nigeria","Rwanda","Senegal","Sierra Leone","South Africa","Sudan","Tanzania","Togo","Tunisia","Uganda","Zambia","Zimbabwe"}
ASIA={"Afghanistan","Bahrain","China","Georgia","India","Indonesia","Iran","Iraq","Israel","Japan","Jordan","Kazakhstan","Kuwait","Kyrgyzstan","Lebanon","Malaysia","North Korea","Oman","Pakistan","Palestine","Philippines","Qatar","Saudi Arabia","South Korea","Syria","Tajikistan","Thailand","Turkmenistan","United Arab Emirates","Uzbekistan","Vietnam"}
N_AMERICA={"Antigua and Barbuda","Aruba","Bahamas","Barbados","Belize","Bermuda","Canada","Costa Rica","Cuba","Curacao","Curaçao","Dominica","Dominican Republic","El Salvador","Grenada","Guadeloupe","Guatemala","Guyana","Haiti","Honduras","Jamaica","Martinique","Mexico","Montserrat","Nicaragua","Panama","Puerto Rico","Saint Kitts and Nevis","Saint Lucia","Suriname","Trinidad and Tobago","United States","US Virgin Islands"}
S_AMERICA={"Argentina","Bolivia","Brazil","Chile","Colombia","Ecuador","Paraguay","Peru","Uruguay","Venezuela"}
OCEANIA={"Australia","Fiji","New Caledonia","New Zealand","Papua New Guinea","Samoa","Solomon Islands","Tahiti","Tonga","Vanuatu"}

def integer(v):
    try: return int(float(v))
    except: return 0

def season_year(s):
    m=re.match(r"(\d{2,4})",s or "")
    if not m: return None
    y=int(m.group(1))
    return 2000+y if y<40 else (1900+y if y<100 else y)

def clean_name(v):
    return re.sub(r" \(\d+\)$","",v or "").strip()

def first_country(v):
    parts=re.split(r"\s{2,}|\s*/\s*|,",v or "")
    n=(parts[0] if parts else "").strip()
    return {"Ireland":"Republic of Ireland","United States":"USA","Cote d'Ivoire":"Ivory Coast"}.get(n,n)

def continent(n):
    raw={"Republic of Ireland":"Ireland","USA":"United States","Ivory Coast":"Cote d'Ivoire","Türkiye":"Turkey","Korea":"South Korea","St. Kitts & Nevis":"Saint Kitts and Nevis","St. Lucia":"Saint Lucia"}.get(n,n)
    if raw in {"Armenia","Belarus","Faroe Islands","Jersey"}:return "Europe"
    if raw=="French Guiana":return "South America"
    if raw=="Seychelles":return "Africa"
    if raw in EUROPE:return "Europe"
    if raw in AFRICA:return "Africa"
    if raw in ASIA:return "Asia"
    if raw in N_AMERICA:return "North America"
    if raw in S_AMERICA:return "South America"
    if raw in OCEANIA:return "Oceania"
    return "Other"

def senior(team):
    t=team.lower()
    return not any(x in t for x in (" u18"," u19"," u20"," u21"," u23"," youth"," reserves"," ii"," b team"))

def main():
    if not os.path.exists(PERF) or not os.path.exists(PROFILES):
        raise SystemExit("dataset files missing")
    reverse={v:k for k,v in CLUBS.items()}
    clubstats={}
    history=defaultdict(list)
    with open(PERF,encoding="utf-8-sig",newline="") as f:
        for r in csv.DictReader(f):
            pid=r["player_id"]; team=r["team_name"]; y=season_year(r["season_name"])
            if y and senior(team): history[pid].append((y,team))
            slug=reverse.get(team)
            if not slug: continue
            key=(slug,pid)
            d=clubstats.setdefault(key,{"apps":0,"first":9999})
            d["apps"]+=integer(r["nb_on_pitch"])
            if y:d["first"]=min(d["first"],y)
    wanted={pid for (slug,pid),d in clubstats.items() if d["apps"]>=25 and d["first"]<9999}
    profiles={}
    with open(PROFILES,encoding="utf-8-sig",newline="") as f:
        for r in csv.DictReader(f):
            if r["player_id"] in wanted: profiles[r["player_id"]]=r
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup=DB+".bak.pre-historical-"+stamp
    shutil.copy2(DB,backup)
    con=sqlite3.connect(DB)
    clubs={slug:cid for cid,slug in con.execute("select id,slug from clubs")}
    before={slug:con.execute("select count(*) from players where club_id=?",(cid,)).fetchone()[0] for slug,cid in clubs.items()}
    inserted=updated=skipped=0
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    for (slug,pid),d in clubstats.items():
        if d["apps"]<25 or d["first"]>=9999 or slug not in clubs: continue
        p=profiles.get(pid)
        if not p: skipped+=1; continue
        name=clean_name(p.get("player_name"))
        dobtxt=p.get("date_of_birth","")
        nat=first_country(p.get("citizenship",""))
        mainpos=p.get("main_position","")
        if not name or not dobtxt or not nat or not mainpos: skipped+=1; continue
        try: dob=datetime.date.fromisoformat(dobtxt)
        except: skipped+=1; continue
        debut_year=d["first"]
        approx_date=datetime.date(debut_year,7,1)
        age=debut_year-dob.year-((approx_date.month,approx_date.day)<(dob.month,dob.day))
        if age<15 or age>45: skipped+=1; continue
        pos={"Attack":"Forward","Midfield":"Midfielder","Defender":"Defender","Goalkeeper":"Goalkeeper"}.get(mainpos)
        if not pos: skipped+=1; continue
        cont=continent(nat)
        earlier={team for y,team in history[pid] if y<=debut_year and team!=CLUBS[slug] and senior(team)}
        prior=len(earlier)
        source=f"https://www.transfermarkt.com/{p.get('player_slug','player')}/profil/spieler/{pid}"
        cid=clubs[slug]
        old=con.execute("select id from players where club_id=? and name=?",(cid,name)).fetchone()
        con.execute("""insert into players(club_id,name,debut_age,position,position_rank,nationality,continent,appearances,prior_clubs,source_url,source_updated_at,debut_year)
        values(?,?,?,?,?,?,?,?,?,?,?,?)
        on conflict(club_id,name) do update set debut_age=excluded.debut_age,position=excluded.position,position_rank=excluded.position_rank,
        nationality=excluded.nationality,continent=excluded.continent,appearances=max(players.appearances,excluded.appearances),
        prior_clubs=excluded.prior_clubs,source_url=excluded.source_url,source_updated_at=excluded.source_updated_at,debut_year=excluded.debut_year""",
        (cid,name,age,pos,{"Goalkeeper":0,"Defender":1,"Midfielder":2,"Forward":3}[pos],nat,cont,d["apps"],prior,source,now,debut_year))
        con.execute("""insert into player_candidates(club_id,name,discovered_at,source_url,status) values(?,?,?,?,?)
          on conflict(club_id,name) do update set source_url=excluded.source_url,status='approved'""",(cid,name,now,source,"approved"))
        con.execute("""insert into enrichment_queue(club_id,player_name,status,attempts,last_attempt) values(?,?,?,?,?)
          on conflict(club_id,player_name) do update set status='approved',last_attempt=excluded.last_attempt""",(cid,name,"approved",1,now))
        if old: updated+=1
        else: inserted+=1
    con.commit()
    integrity=con.execute("pragma integrity_check").fetchone()[0]
    after={slug:con.execute("select count(*) from players where club_id=?",(cid,)).fetchone()[0] for slug,cid in clubs.items()}
    invalid=con.execute("""select count(*) from players where debut_year is null or debut_year<1850 or debut_year>2026
       or debut_age<15 or debut_age>45 or position not in ('Goalkeeper','Defender','Midfielder','Forward')
       or nationality='' or continent=''""").fetchone()[0]
    print("backup",backup)
    print("inserted",inserted,"updated",updated,"skipped",skipped,"total",sum(after.values()),"integrity",integrity,"invalid",invalid)
    for slug in sorted(after): print(slug,before.get(slug,0),"->",after[slug])

if __name__=="__main__":main()
