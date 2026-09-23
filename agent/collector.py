#!/usr/bin/env python3
"""Player Wordle autonomous collector.
Uses public, non-OpenAI web sources. It never deletes validated history.
Current-squad discovery is sourced from the official Premier League squad-list page.
Detailed historical enrichment is a separate adapter so failures never corrupt live data.
"""
import urllib.request,re,html,sqlite3,datetime,os
from zoneinfo import ZoneInfo
DB="/var/lib/predictioncomp/player-wordle/game.sqlite3"
PL="https://www.premierleague.com/en/news/4706139/see-all-the-202627-premier-league-squad-lists"
TZ=ZoneInfo("Europe/London")
def fetch(url):
 r=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; PlayerWordle/1.0)"})
 return urllib.request.urlopen(r,timeout=30).read().decode("utf-8","ignore")
def clean(x): return re.sub(r"\s+"," ",html.unescape(re.sub("<[^>]+>"," ",x))).strip()
def main():
 con=sqlite3.connect(DB); now=datetime.datetime.now(TZ).isoformat()
 raw=fetch(PL); txt=clean(raw)
 clubs=con.execute("select id,slug,name from clubs where active=1 order by name").fetchall()
 found=0
 for n,(cid,slug,name) in enumerate(clubs):
  starts=[txt.find(name)]
  aliases={"AFC Bournemouth":"AFC Bournemouth","Brighton & Hove Albion":"Brighton & Hove Albion","Hull City":"Hull City"}
  start=txt.find(aliases.get(name,name))
  if start<0: continue
  ends=[txt.find(c[2],start+len(name)) for c in clubs if txt.find(c[2],start+len(name))>start]
  end=min(ends) if ends else min(len(txt),start+12000)
  # Preserve line breaks from the source squad list so names remain separable.
  raw_start=raw.find(name)
  raw_ends=[raw.find(c[2],raw_start+len(name)) for c in clubs if raw.find(c[2],raw_start+len(name))>raw_start]
  raw_end=min(raw_ends) if raw_ends else min(len(raw),raw_start+30000)
  sec=raw[raw_start:raw_end]
  m=re.search(r"25 Squad players.*?</strong>(.*?)</p>.*?U21 players",sec,re.S)
  if not m: continue
  block=re.sub(r"<br\s*/?>","\n",m.group(1),flags=re.I)
  block=html.unescape(re.sub("<[^>]+>","",block))
  names=[re.sub(r"\s+"," ",x).strip(" *") for x in block.splitlines() if len(re.sub(r"\s+"," ",x).strip(" *"))>2]
  # Record discovery queue. Full eligibility + attributes are enriched before promotion to live players.
  con.execute("""CREATE TABLE IF NOT EXISTS player_candidates(id INTEGER PRIMARY KEY,club_id INTEGER,name TEXT,discovered_at TEXT,
    source_url TEXT,status TEXT NOT NULL DEFAULT 'pending',UNIQUE(club_id,name))""")
  for player in names:
   con.execute("INSERT OR IGNORE INTO player_candidates(club_id,name,discovered_at,source_url) VALUES(?,?,?,?)",(cid,player,now,PL)); found+=1
 con.execute("insert into agent_runs(ran_at,status,details) values(?,?,?)",(now,"collector",f"candidate rows seen={found}"))
 con.commit()
 print("collector complete candidates_seen",found,"stored",con.execute("select count(*) from player_candidates").fetchone()[0])
if __name__=="__main__": main()
