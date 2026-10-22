"""Bilan d'un jour : prévu / fait, charge (effort relatif Strava), retour par séance, conseil du lendemain.

Usage : python3 outils/bilan_jour.py [AAAA-MM-JJ]   (par défaut : aujourd'hui, heure de Paris)

Ouvre l'app dans Chromium headless et réutilise sa propre logique (programme,
séances, détection des activités), pour que le bilan dise exactement ce que
l'app affiche. Les reports et annulations faits sur le téléphone ne sont pas
visibles ici : une séance « non trouvée » a peut-être été reportée.
"""
import datetime
import functools
import http.server
import json
import pathlib
import sys
import threading
import zoneinfo

from playwright.sync_api import sync_playwright

RACINE = pathlib.Path(__file__).resolve().parent.parent

JS = """(date)=>{
 const A=acts();
 const out={date,charge:charge(A,date),conseil_jour:conseil(date,A),conseil_demain:conseil(addD(date,1),A),
  retours:A.filter(a=>a.d===date).map(a=>({nom:a.n,type:a.k,effort:a.re,retour:retourSeance(a,A)})),
  jours_sans:Object.fromEntries(["run","box","muscu"].map(k=>[k,(x=>x?diff(x,date):null)(lastOf(k,A.filter(a=>a.d<=date)))]))};
 const w=WEEKS.find(w=>date>=w.start&&date<=addD(w.start,6));
 if(!w)return {...out,hors_programme:true};
 const d=effDays(w).find(x=>x.date===date),st=weekStat(w,A);
 return {...out,semaine:"S"+w.s+" · "+w.tag,
  prevu:d.items.filter(i=>i.k!=="repos").map(i=>({seance:i.t,type:i.k,fixe:!!i.lock,fait:doneOn(date,i.k,A)})),
  semaine_course_km:Math.round(st.km*10)/10,semaine_objectif_km:w.km,
  semaine_runs:st.runs,semaine_box:st.box,semaine_kine:st.kine,semaine_muscu:st.muscu};
}"""


def main():
    jour = sys.argv[1] if len(sys.argv) > 1 else datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Paris")).strftime("%Y-%m-%d")
    class Silencieux(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    handler = functools.partial(Silencieux, directory=str(RACINE))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            nav = p.chromium.launch()
            page = nav.new_page()
            page.goto(f"http://127.0.0.1:{srv.server_port}/index.html")
            page.wait_for_function("typeof SNAP!=='undefined' && SNAP!==null", timeout=15000)
            print(json.dumps(page.evaluate(JS, jour), ensure_ascii=False, indent=1))
            nav.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    main()
