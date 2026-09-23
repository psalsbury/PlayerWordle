#!/usr/bin/env python3
"""Nightly maintenance. Runtime has no ChatGPT/OpenAI dependency.
Imports validated player rows from /etc/predictioncomp/player-wordle-players.csv when present.
The collector boundary is intentionally separate so a permitted football-data source can be swapped without changing the game.
"""
import csv, sqlite3, os, datetime, random
from zoneinfo import ZoneInfo
DB="/var/lib/predictioncomp/player-wordle/game.sqlite3"
CSV="/etc/predictioncomp/player-wordle-players.csv"
TZ=ZoneInfo("Europe/London")
RANK={"Goalkeeper":0,"Defender":1,"Midfielder":2,"Forward":3,"Striker":3}
CONT={"England":"Europe","Scotland":"Europe","Wales":"Europe","Northern Ireland":"Europe","Republic of Ireland":"Europe",
"France":"Europe","Spain":"Europe","Germany":"Europe","Italy":"Europe","Portugal":"Europe","Netherlands":"Europe","Belgium":"Europe",
"Norway":"Europe","Sweden":"Europe","Denmark":"Europe","Poland":"Europe","Croatia":"Europe","Serbia":"Europe","Switzerland":"Europe",
"Brazil":"South America","Argentina":"South America","Uruguay":"South America","Colombia":"South America","Ecuador":"South America",
"USA":"North America","United States":"North America","Canada":"North America","Mexico":"North America",
"Japan":"Asia","South Korea":"Asia","Australia":"Oceania","New Zealand":"Oceania","Ghana":"Africa","Nigeria":"Africa","Senegal":"Africa",
"Morocco":"Africa","Algeria":"Africa","Egypt":"Africa","Cameroon":"Africa","Ivory Coast":"Africa","Côte d'Ivoire":"Africa"}
def main():
    con=sqlite3.connect(DB); now=datetime.datetime.now(TZ)
    added=0; updated=0
    if os.path.exists(CSV):
      clubs={s:i for i,s in con.execute("SELECT id,slug FROM clubs")}
      with open(CSV,encoding="utf-8-sig",newline="") as f:
       for r in csv.DictReader(f):
        cid=clubs.get(r["club_slug"].strip())
        if not cid: continue
        pos=r["position"].strip(); nat=r["nationality"].strip()
        vals=(cid,r["name"].strip(),int(r["debut_age"]),int(r["debut_year"]),pos,RANK.get(pos,2),nat,r.get("continent","").strip() or CONT.get(nat,"Other"),
              int(r["appearances"]),int(r["prior_clubs"]),r.get("source_url",""),now.isoformat())
        before=con.total_changes
        con.execute("""INSERT INTO players(club_id,name,debut_age,debut_year,position,position_rank,nationality,continent,appearances,prior_clubs,source_url,source_updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(club_id,name) DO UPDATE SET debut_age=excluded.debut_age,debut_year=excluded.debut_year,position=excluded.position,
        position_rank=excluded.position_rank,nationality=excluded.nationality,continent=excluded.continent,appearances=excluded.appearances,
        prior_clubs=excluded.prior_clubs,source_url=excluded.source_url,source_updated_at=excluded.source_updated_at""",vals)
        added += con.total_changes-before
    # On an empty/new database make today's game available immediately; also prepare tomorrow.
    today=now.date().isoformat()
    if con.execute("SELECT COUNT(*) FROM daily_game").fetchone()[0] == 0:
      for cid, in con.execute("SELECT id FROM clubs WHERE active=1"):
        ids=[x[0] for x in con.execute("SELECT id FROM players WHERE club_id=?",(cid,))]
        if ids: con.execute("INSERT OR IGNORE INTO daily_game(game_date,club_id,player_id) VALUES(?,?,?)",(today,cid,random.choice(ids)))
    day=(now.date()+datetime.timedelta(days=1)).isoformat()
    for cid, in con.execute("SELECT id FROM clubs WHERE active=1"):
      ids=[x[0] for x in con.execute("SELECT id FROM players WHERE club_id=?",(cid,))]
      if not ids: continue
      prev=con.execute("SELECT player_id FROM daily_game WHERE club_id=? ORDER BY game_date DESC LIMIT 1",(cid,)).fetchone()
      pool=[x for x in ids if not prev or x!=prev[0]] or ids
      con.execute("INSERT OR IGNORE INTO daily_game(game_date,club_id,player_id) VALUES(?,?,?)",(day,cid,random.choice(pool)))
    con.execute("INSERT INTO agent_runs(ran_at,status,details) VALUES(?,?,?)",(now.isoformat(),"ok",f"player rows processed={added}"))
    con.commit(); print("nightly complete",day,"rows",added)
if __name__=="__main__": main()
