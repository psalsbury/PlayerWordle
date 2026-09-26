#!/usr/bin/env python3
import sqlite3,urllib.request,urllib.parse,json,re,datetime,time
from zoneinfo import ZoneInfo
DB="/var/lib/clubdailyfive/player-wordle/game.sqlite3"; TZ=ZoneInfo("Europe/London")
CONT={"England":"Europe","Scotland":"Europe","Wales":"Europe","Northern Ireland":"Europe","Republic of Ireland":"Europe","France":"Europe","Spain":"Europe","Portugal":"Europe","Germany":"Europe","Netherlands":"Europe","Belgium":"Europe","Italy":"Europe","Denmark":"Europe","Norway":"Europe","Sweden":"Europe","Switzerland":"Europe","Austria":"Europe","Greece":"Europe","Ukraine":"Europe","Poland":"Europe","Serbia":"Europe","Croatia":"Europe","Slovenia":"Europe","Bosnia and Herzegovina":"Europe","Czech Republic":"Europe","Hungary":"Europe","Turkey":"Europe","Israel":"Asia","Brazil":"South America","Argentina":"South America","Uruguay":"South America","Colombia":"South America","Chile":"South America","Ecuador":"South America","Paraguay":"South America","Nigeria":"Africa","Ghana":"Africa","Morocco":"Africa","Senegal":"Africa","Cote d'Ivoire":"Africa","Mali":"Africa","Algeria":"Africa","Cameroon":"Africa","Guinea":"Africa","Mozambique":"Africa","Burkina Faso":"Africa","DR Congo":"Africa","Democratic Republic of Congo":"Africa","United States":"North America","Canada":"North America","Jamaica":"North America","Japan":"Asia","Uzbekistan":"Asia","Australia":"Oceania","New Zealand":"Oceania"}
def getjson(url):
 r=urllib.request.Request(url,headers={"User-Agent":"PlayerWordle/1.0 contact: admin@predictioncomp.com","Accept":"application/json"})
 return json.load(urllib.request.urlopen(r,timeout=15))
def rank(pos):
 p=pos.lower()
 if "goal" in p:return 0
 if "defend" in p:return 1
 if "midfield" in p:return 2
 return 3
def main():
 c=sqlite3.connect(DB); now=datetime.datetime.now(TZ).isoformat(); rows=c.execute("select club_id,player_name from enrichment_queue where status='pending' limit 445").fetchall(); ok=0
 for cid,name in rows:
  try:
   q=urllib.parse.quote(name+" footballer")
   d=getjson("https://www.wikidata.org/w/api.php?action=wbsearchentities&search="+q+"&language=en&format=json&limit=1")
   if not d.get("search"): continue
   qid=d["search"][0]["id"]; ent=getjson("https://www.wikidata.org/wiki/Special:EntityData/"+qid+".json")["entities"][qid]; cl=ent.get("claims",{})
   def val(prop):
    try:return cl[prop][0]["mainsnak"]["datavalue"]["value"]
    except:return None
   dob=val("P569")
   if isinstance(dob,dict): dob=dob.get("time","")[1:11]
   natid=val("P27"); nat=None
   if isinstance(natid,dict):
    nid=natid.get("id")
    if nid:
     ne=getjson("https://www.wikidata.org/wiki/Special:EntityData/"+nid+".json")["entities"][nid]
     nat=ne.get("labels",{}).get("en",{}).get("value")
   if dob:c.execute("insert or replace into player_facts(club_id,player_name,fact,value,source_url,checked_at) values(?,?,?,?,?,?)",(cid,name,"dob",dob,"Wikidata:"+qid,now))
   if nat:c.execute("insert or replace into player_facts(club_id,player_name,fact,value,source_url,checked_at) values(?,?,?,?,?,?)",(cid,name,"nationality",nat,"Wikidata:"+qid,now))
   c.execute("update enrichment_queue set attempts=attempts+1,last_attempt=? where club_id=? and player_name=?",(now,cid,name)); c.commit(); ok+=1
   time.sleep(.15)
  except Exception as e: pass
 print("wikidata enriched",ok,"facts",c.execute("select count(*) from player_facts").fetchone()[0])
if __name__=="__main__":main()
