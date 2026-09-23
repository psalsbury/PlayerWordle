#!/usr/bin/env python3
import sqlite3, os
DB="/var/lib/predictioncomp/player-wordle/game.sqlite3"
CLUBS=[
("bournemouth","AFC Bournemouth"),("arsenal","Arsenal"),("aston-villa","Aston Villa"),("brentford","Brentford"),("brighton","Brighton & Hove Albion"),
("chelsea","Chelsea"),("coventry","Coventry City"),("crystal-palace","Crystal Palace"),("everton","Everton"),("fulham","Fulham"),
("hull","Hull City"),("ipswich","Ipswich Town"),("leeds","Leeds United"),("liverpool","Liverpool"),("man-city","Manchester City"),
("man-utd","Manchester United"),("newcastle","Newcastle United"),("nottingham-forest","Nottingham Forest"),("sunderland","Sunderland"),("tottenham","Tottenham Hotspur")]
os.makedirs(os.path.dirname(DB),exist_ok=True)
con=sqlite3.connect(DB)
con.executescript("""
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
CREATE TABLE IF NOT EXISTS clubs(id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS players(
 id INTEGER PRIMARY KEY, club_id INTEGER NOT NULL REFERENCES clubs(id), name TEXT NOT NULL, debut_age INTEGER NOT NULL, debut_year INTEGER NOT NULL,
 position TEXT NOT NULL, position_rank INTEGER NOT NULL, nationality TEXT NOT NULL, continent TEXT NOT NULL,
 appearances INTEGER NOT NULL, prior_clubs INTEGER NOT NULL, source_url TEXT, source_updated_at TEXT,
 UNIQUE(club_id,name));
CREATE INDEX IF NOT EXISTS idx_players_club_name ON players(club_id,name);
CREATE TABLE IF NOT EXISTS daily_game(
 game_date TEXT NOT NULL, club_id INTEGER NOT NULL REFERENCES clubs(id), player_id INTEGER NOT NULL REFERENCES players(id),
 PRIMARY KEY(game_date,club_id));
CREATE TABLE IF NOT EXISTS aggregate_stats(
 stat_date TEXT NOT NULL, club_id INTEGER NOT NULL REFERENCES clubs(id), started INTEGER NOT NULL DEFAULT 0,
 completed INTEGER NOT NULL DEFAULT 0, won INTEGER NOT NULL DEFAULT 0, guesses_total INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(stat_date,club_id));
CREATE TABLE IF NOT EXISTS agent_runs(id INTEGER PRIMARY KEY, ran_at TEXT NOT NULL, status TEXT NOT NULL, details TEXT);
""")
con.executemany("INSERT INTO clubs(slug,name) VALUES(?,?) ON CONFLICT(slug) DO UPDATE SET name=excluded.name,active=1",CLUBS)
con.commit(); print("database ready",DB)
