#!/usr/bin/env python3
"""Fill historical Player Wordle coverage gaps from Wikidata club statements.
Requires 25+ recorded senior appearances and complete DOB/nationality/position/
club-start data. Existing players are preserved. Safe to rerun.
"""
import urllib.request,urllib.parse,json,time,sqlite3,re,datetime,shutil,unicodedata
from collections import defaultdict

DB="/var/lib/clubdailyfive/player-wordle/game.sqlite3"
CLUBS={
"bournemouth":"Q19568","arsenal":"Q9617","aston-villa":"Q18711","brentford":"Q19571",
"brighton":"Q19453","chelsea":"Q9616","coventry":"Q19580","crystal-palace":"Q19467",
"everton":"Q5794","fulham":"Q18708","hull":"Q19477","ipswich":"Q9653","leeds":"Q1128631",
"liverpool":"Q1130849","man-city":"Q50602","man-utd":"Q18656","newcastle":"Q18716",
"nottingham-forest":"Q19490","sunderland":"Q18739","tottenham":"Q18741"}
UA="PlayerWordle/1.0 admin@predictioncomp.com"
CONTINENTS={
"Europe":{"Albania","Armenia","Austria","Belarus","Belgium","Bosnia and Herzegovina","Bulgaria","Croatia","Cyprus","Czech Republic","Denmark","England","Estonia","Faroe Islands","Finland","France","Georgia","Germany","Greece","Hungary","Iceland","Ireland","Italy","Jersey","Kosovo","Latvia","Lithuania","Luxembourg","Malta","Moldova","Montenegro","Netherlands","North Macedonia","Northern Ireland","Norway","Poland","Portugal","Republic of Ireland","Romania","Russia","Scotland","Serbia","Slovakia","Slovenia","Spain","Sweden","Switzerland","Turkey","Türkiye","Ukraine","Wales"},
"Africa":{"Algeria","Angola","Benin","Burkina Faso","Burundi","Cameroon","Cape Verde","Central African Republic","Chad","Congo","Democratic Republic of the Congo","DR Congo","Egypt","Equatorial Guinea","Eritrea","Ethiopia","Gabon","Gambia","Ghana","Guinea","Guinea-Bissau","Ivory Coast","Côte d'Ivoire","Kenya","Liberia","Libya","Madagascar","Mali","Mauritania","Mauritius","Morocco","Mozambique","Namibia","Niger","Nigeria","Rwanda","Senegal","Seychelles","Sierra Leone","South Africa","Sudan","Tanzania","Togo","Tunisia","Uganda","Zambia","Zimbabwe"},
"Asia":{"Afghanistan","Bahrain","China","India","Indonesia","Iran","Iraq","Israel","Japan","Jordan","Kazakhstan","Kuwait","Kyrgyzstan","Lebanon","Malaysia","North Korea","Oman","Pakistan","Palestine","Philippines","Qatar","Saudi Arabia","South Korea","Syria","Tajikistan","Thailand","Turkmenistan","United Arab Emirates","Uzbekistan","Vietnam"},
"North America":{"Antigua and Barbuda","Aruba","Bahamas","Barbados","Belize","Bermuda","Canada","Costa Rica","Cuba","Curaçao","Dominica","Dominican Republic","El Salvador","Grenada","Guadeloupe","Guatemala","Guyana","Haiti","Honduras","Jamaica","Martinique","Mexico","Montserrat","Nicaragua","Panama","Puerto Rico","Saint Kitts and Nevis","Saint Lucia","Suriname","Trinidad and Tobago","United States"},
"South America":{"Argentina","Bolivia","Brazil","Chile","Colombia","Ecuador","French Guiana","Paraguay","Peru","Uruguay","Venezuela"},
"Oceania":{"Australia","Fiji","New Caledonia","New Zealand","Papua New Guinea","Samoa","Solomon Islands","Tahiti","Tonga","Vanuatu"}}

def fetch_json(url,tries=5,timeout=120):
    last=None
    for i in range(tries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)
        except Exception as e:
            last=e; time.sleep(2**i)
    raise last

def sparql(club):
    q=f"""SELECT ?player ?apps ?start WHERE {{
      ?player p:P54 ?st. ?st ps:P54 wd:{club}; pq:P1350 ?apps.
      OPTIONAL {{?st pq:P580 ?start}}
    }}"""
    u="https://query.wikidata.org/sparql?"+urllib.parse.urlencode({"query":q,"format":"json"})
    return fetch_json(u,timeout=180)["results"]["bindings"]

def entities(ids,props="labels|claims"):
    out={}
    ids=list(dict.fromkeys(ids))
    for i in range(0,len(ids),50):
        u="https://www.wikidata.org/w/api.php?"+urllib.parse.urlencode({
          "action":"wbgetentities","ids":"|".join(ids[i:i+50]),"props":props,"languages":"en","format":"json"})
        out.update(fetch_json(u,timeout=60).get("entities",{})); time.sleep(.1)
    return out

def qid_from_uri(v):return v.rsplit("/",1)[-1]
def claim_qids(ent,prop):
    out=[]
    for c in ent.get("claims",{}).get(prop,[]):
        try:out.append(c["mainsnak"]["datavalue"]["value"]["id"])
        except:pass
    return out
def claim_time(claim,prop):
    try:return claim["qualifiers"][prop][0]["datavalue"]["value"]["time"][1:11]
    except:return None
def dob(ent):
    try:return ent["claims"]["P569"][0]["mainsnak"]["datavalue"]["value"]["time"][1:11]
    except:return None
def label(ent,qid):
    return ent.get("labels",{}).get("en",{}).get("value",qid)
def norm(s):
    s=unicodedata.normalize("NFKD",s or "").encode("ascii","ignore").decode().lower()
    return re.sub(r"[^a-z0-9]","",s)
def continent(n):
    aliases={"Ireland":"Republic of Ireland","United States of America":"United States","Cote d'Ivoire":"Ivory Coast","Korea, South":"South Korea"}
    n=aliases.get(n,n)
    for c,vals in CONTINENTS.items():
        if n in vals:return c
    return None
def pos_from_labels(labels):
    s=" ".join(labels).lower()
    if "goalkeeper" in s:return "Goalkeeper"
    if any(x in s for x in ("defender","back","centre-back","full-back")):return "Defender"
    if "midfielder" in s or "midfield" in s:return "Midfielder"
    if any(x in s for x in ("forward","striker","winger","attack")):return "Forward"
    return None
def senior(s):
    t=s.lower()
    return not any(x in t for x in ("under-","under "," u18"," u19"," u20"," u21"," u23","youth","academy","reserve"))

def main():
    raw={}
    def discover(item):
        slug,club=item
        print("discover",slug,flush=True)
        rows=sparql(club)
        agg=defaultdict(lambda:{"apps":0,"starts":[]})
        for r in rows:
            pid=qid_from_uri(r["player"]["value"])
            try:a=int(float(r["apps"]["value"]))
            except:continue
            agg[pid]["apps"]+=a
            if "start" in r:agg[pid]["starts"].append(r["start"]["value"][:10])
        return slug,{pid:{"apps":d["apps"],"start":min(d["starts"])} for pid,d in agg.items() if d["apps"]>=25 and d["starts"]}
    from concurrent.futures import ThreadPoolExecutor,as_completed
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(discover,item) for item in CLUBS.items()]
        for future in as_completed(futures):
            slug,found=future.result()
            for pid,d in found.items():raw[(slug,pid)]=d
            print("complete",slug,len(found),flush=True)
    all_pids={pid for slug,pid in raw}
    # Fetch names cheaply first, then load full claims only for genuine gaps.
    names=entities(all_pids,props="labels")
    check=sqlite3.connect(DB)
    clubids_pre={s:i for i,s in check.execute("select id,slug from clubs")}
    existing_pre={slug:{norm(n) for n, in check.execute("select name from players where club_id=?",(cid,))} for slug,cid in clubids_pre.items()}
    missing_keys={(slug,pid) for slug,pid in raw if norm(label(names.get(pid,{}),pid)) not in existing_pre.get(slug,set())}
    raw={k:v for k,v in raw.items() if k in missing_keys}
    missing_pids={pid for slug,pid in raw}
    print("genuine gaps",len(raw),"players",len(missing_pids),flush=True)
    people=entities(missing_pids)
    related=set()
    for p in people.values():
        related.update(claim_qids(p,"P27")); related.update(claim_qids(p,"P413"))
        for st in p.get("claims",{}).get("P54",[]):
            try:related.add(st["mainsnak"]["datavalue"]["value"]["id"])
            except:pass
    rel=entities(related)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup=DB+".bak.pre-wikidata-gaps-"+stamp; shutil.copy2(DB,backup)
    c=sqlite3.connect(DB); clubids={s:i for i,s in c.execute("select id,slug from clubs")}
    existing={slug:{norm(n) for n, in c.execute("select name from players where club_id=?",(cid,))} for slug,cid in clubids.items()}
    added=skipped=0; reasons=defaultdict(int); now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    added_by=defaultdict(int)
    for (slug,pid),d in raw.items():
        ent=people.get(pid,{})
        name=label(ent,pid).strip()
        if norm(name) in existing.get(slug,set()):continue
        birth=dob(ent)
        nations=claim_qids(ent,"P27"); positions=claim_qids(ent,"P413")
        if not birth or not nations or not positions:reasons["missing_profile"]+=1;skipped+=1;continue
        nat=label(rel.get(nations[0],{}),nations[0]); cont=continent(nat)
        pos=pos_from_labels([label(rel.get(x,{}),x) for x in positions])
        if not cont or not pos:reasons["unmapped"]+=1;skipped+=1;continue
        try:
            bd=datetime.date.fromisoformat(birth); sy=int(d["start"][:4]); approx=datetime.date(sy,7,1)
            age=sy-bd.year-((approx.month,approx.day)<(bd.month,bd.day))
        except:reasons["bad_date"]+=1;skipped+=1;continue
        if not 15<=age<=45:reasons["bad_age"]+=1;skipped+=1;continue
        prior=set()
        for st in ent.get("claims",{}).get("P54",[]):
            try:team=st["mainsnak"]["datavalue"]["value"]["id"]
            except:continue
            if team==CLUBS[slug]:continue
            end=claim_time(st,"P582"); start=claim_time(st,"P580")
            if (end and end[:4]<=str(sy)) or (start and start[:4]<str(sy)):
                tl=label(rel.get(team,{}),team)
                if senior(tl):prior.add(team)
        cid=clubids[slug]; source="https://www.wikidata.org/wiki/"+pid
        c.execute("""insert into players(club_id,name,debut_age,position,position_rank,nationality,continent,appearances,prior_clubs,source_url,source_updated_at,debut_year)
          values(?,?,?,?,?,?,?,?,?,?,?,?)""",(cid,name,age,pos,{"Goalkeeper":0,"Defender":1,"Midfielder":2,"Forward":3}[pos],nat,cont,d["apps"],len(prior),source,now,sy))
        c.execute("""insert into player_candidates(club_id,name,discovered_at,source_url,status) values(?,?,?,?,?)
          on conflict(club_id,name) do update set status='approved',source_url=excluded.source_url""",(cid,name,now,source,"approved"))
        c.execute("""insert into enrichment_queue(club_id,player_name,status,attempts,last_attempt) values(?,?,?,?,?)
          on conflict(club_id,player_name) do update set status='approved',last_attempt=excluded.last_attempt""",(cid,name,"approved",1,now))
        existing[slug].add(norm(name));added+=1;added_by[slug]+=1
    c.commit()
    print("backup",backup)
    print("added",added,"skipped",skipped,"reasons",dict(reasons),"total",c.execute("select count(*) from players").fetchone()[0])
    print("integrity",c.execute("pragma integrity_check").fetchone()[0])
    for slug in sorted(CLUBS):print(slug,"added",added_by[slug],"total",c.execute("select count(*) from players where club_id=?",(clubids[slug],)).fetchone()[0])
    print("brian",c.execute("""select p.name,p.appearances,p.debut_year,p.debut_age,p.prior_clubs from players p join clubs cl on cl.id=p.club_id where cl.slug='man-utd' and lower(p.name) like '%mcclair%'""").fetchall())

if __name__=="__main__":main()
