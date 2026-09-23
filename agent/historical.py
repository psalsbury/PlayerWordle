#!/usr/bin/env python3
"""Historical discovery for Player Wordle using API-Football.
No OpenAI dependency. Discovers Premier League club players season-by-season,
queues candidates, and records evidence. Resume-safe and quota-aware.
"""
import sys,os,sqlite3,datetime,time
from zoneinfo import ZoneInfo
sys.path.insert(0,"/opt/predictioncomp/bin")
from api_football import get,DailyQuotaExceeded
DB="/var/lib/predictioncomp/player-wordle/game.sqlite3"; TZ=ZoneInfo("Europe/London")
TEAM_ALIASES={"AFC Bournemouth":"Bournemouth","Brighton & Hove Albion":"Brighton","Manchester City":"Manchester City","Manchester United":"Manchester United","Nottingham Forest":"Nottingham Forest","Tottenham Hotspur":"Tottenham"}
def main():
 c=sqlite3.connect(DB); now=datetime.datetime.now(TZ).isoformat()
 c.executescript("""CREATE TABLE IF NOT EXISTS discovery_evidence(
 id INTEGER PRIMARY KEY,club_id INTEGER,player_name TEXT,season INTEGER,appearances INTEGER DEFAULT 0,
 reason TEXT,source TEXT,UNIQUE(club_id,player_name,season,reason));
 CREATE TABLE IF NOT EXISTS collector_state(k TEXT PRIMARY KEY,v TEXT);""")
 clubs=c.execute("select id,name from clubs where active=1 order by id").fetchall()
 # 2025 = last season; walk backwards 10 seasons for the 25-appearance rule.
 seasons=list(range(2025,2015,-1))
 calls=0
 try:
  for cid,name in clubs:
   teamname=TEAM_ALIASES.get(name,name)
   state=f"teamid:{teamname}"
   row=c.execute("select v from collector_state where k=?",(state,)).fetchone()
   if row: tid=int(row[0])
   else:
    d=get("/teams",{"search":teamname}); calls+=1
    choices=d.get("response",[])
    eng=[x for x in choices if x.get("team",{}).get("country")=="England"]
    if not eng: continue
    tid=int(eng[0]["team"]["id"]); c.execute("insert or replace into collector_state values(?,?)",(state,str(tid))); c.commit()
   for season in seasons:
    key=f"done:{cid}:{season}"
    if c.execute("select 1 from collector_state where k=?",(key,)).fetchone(): continue
    d=get("/players",{"team":tid,"season":season}); calls+=1
    for item in d.get("response",[]):
     p=item.get("player",{}); stats=item.get("statistics",[])
     apps=sum(int((s.get("games",{}).get("appearences") or 0)) for s in stats)
     pname=p.get("name")
     if not pname: continue
     c.execute("""CREATE TABLE IF NOT EXISTS player_candidates(id INTEGER PRIMARY KEY,club_id INTEGER,name TEXT,discovered_at TEXT,
       source_url TEXT,status TEXT NOT NULL DEFAULT 'pending',UNIQUE(club_id,name))""")
     c.execute("insert or ignore into player_candidates(club_id,name,discovered_at,source_url) values(?,?,?,?)",(cid,pname,now,"API-Football"))
     c.execute("insert or ignore into discovery_evidence(club_id,player_name,season,appearances,reason,source) values(?,?,?,?,?,?)",
       (cid,pname,season,apps,"season_roster","API-Football"))
    c.execute("insert or replace into collector_state values(?,?)",(key,now)); c.commit()
 except DailyQuotaExceeded as e:
  print("quota pause",e)
 c.execute("insert into agent_runs(ran_at,status,details) values(?,?,?)",(now,"historical",f"api calls this run={calls}")); c.commit()
 print("historical discovery calls",calls,"candidates",c.execute("select count(*) from player_candidates").fetchone()[0])
if __name__=="__main__": main()
