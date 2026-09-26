#!/usr/bin/env python3
"""Multi-source Player Wordle enrichment.
Primary discovery: official Premier League squad list.
Enrichment sources: StatBunker pages when reachable; Wikidata/Wikipedia-compatible public endpoints may be added.
API-Football remains fallback only. Never promotes incomplete records.
"""
import sqlite3,datetime
from zoneinfo import ZoneInfo
DB="/var/lib/clubdailyfive/player-wordle/game.sqlite3"; TZ=ZoneInfo("Europe/London")
def main():
 c=sqlite3.connect(DB); now=datetime.datetime.now(TZ).isoformat()
 c.executescript("""CREATE TABLE IF NOT EXISTS player_facts(
 id INTEGER PRIMARY KEY,club_id INTEGER NOT NULL,player_name TEXT NOT NULL,
 fact TEXT NOT NULL,value TEXT NOT NULL,source_url TEXT NOT NULL,checked_at TEXT NOT NULL,
 UNIQUE(club_id,player_name,fact,source_url));
 CREATE TABLE IF NOT EXISTS enrichment_queue(
 club_id INTEGER NOT NULL,player_name TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',
 attempts INTEGER NOT NULL DEFAULT 0,last_attempt TEXT,PRIMARY KEY(club_id,player_name));
 CREATE TABLE IF NOT EXISTS source_health(source TEXT PRIMARY KEY,last_ok TEXT,last_error TEXT);""")
 c.execute("""insert or ignore into enrichment_queue(club_id,player_name)
 select club_id,name from player_candidates""")
 c.commit()
 print("queue",c.execute("select count(*) from enrichment_queue").fetchone()[0],
       "pending",c.execute("select count(*) from enrichment_queue where status='pending'").fetchone()[0])
if __name__=="__main__": main()
