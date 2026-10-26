"""Fusionne des réponses Strava « list_activities » dans data.json, au format de l'app.

Usage : python3 outils/maj_strava.py --depuis AAAA-MM-JJ page1.json [page2.json …]

Les séances « poids » du mardi et du jeudi entre 9h45 et 11h45 sont la kiné
(tous les mardis et jeudis à 10h30) : renommées « Kiné », elles ne comptent pas en muscu.

--depuis est la date de début de la requête Strava : une activité de data.json
datée de ce jour ou après, absente des réponses, a été supprimée sur Strava et
est retirée. Les noms liés à la santé sont neutralisés (dépôt public).
"""
import argparse
import datetime
import json
import pathlib
import re
import zoneinfo

RACINE = pathlib.Path(__file__).resolve().parent.parent
DATA = RACINE / "data.json"
SANTE = re.compile(r"kin[ée]|kin[ée]sith|r[ée][ée]duc|physio|m[ée]decin|douleur|bless", re.I)


def nom(a):
    n = (a.get("name") or "").strip().split("\n")[0].strip()
    t = a.get("sport_type") or ""
    if t == "PhysicalTherapy" or SANTE.search(n):
        return "Kiné"
    if t == "Hike":
        return "Randonnée"
    return n[:80] or t


def salle(a):
    """Type de séance de salle lu dans le titre Strava (seul le type est gardé, pas le titre)."""
    n = (a.get("name") or "").lower()
    if "push" in n:
        return "push"
    if "pull" in n:
        return "pull"
    if re.search(r"jambe|legs|squat|[ée]paule", n):
        return "legs"
    return None


def kine_du_matin(x):
    """Kiné tous les mardis et jeudis à 10h30 (Jules, 14/10) : la montre l'enregistre en « poids ».
    Une séance titrée Push / Pull / Jambes sur Strava reste de la muscu (Push du jeudi 15/10 à 10h36)."""
    if x["t"] not in ("WeightTraining", "Workout") or not x["d"] or x.get("s"):
        return False
    jour = datetime.date.fromisoformat(x["d"]).weekday()  # 1 = mardi, 3 = jeudi
    return jour in (1, 3) and "09:45" <= x["h"] <= "11:45"


def item(a):
    s = a.get("summary") or {}
    st = a.get("start_local") or ""
    return {
        "id": str(a["id"]), "n": nom(a), "t": a.get("sport_type") or "",
        "d": st[:10], "h": st[11:16],
        "km": round((s.get("distance") or 0) / 1000, 2),
        "min": round((s.get("moving_time") or 0) / 60, 1),
        "re": s.get("relative_effort"),
        "s": salle(a),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--depuis", required=True)
    ap.add_argument("pages", nargs="+")
    args = ap.parse_args()

    recus = {}
    for p in args.pages:
        rep = json.loads(pathlib.Path(p).read_text())
        for a in rep.get("activities", []):
            recus[str(a["id"])] = item(a)

    data = json.loads(DATA.read_text())
    avant = {x["id"]: x for x in data["strava"]["items"]}
    nouveaux = [x for i, x in recus.items() if i not in avant]
    supprimes = [x for i, x in avant.items() if x["d"] >= args.depuis and i not in recus]

    fusion = dict(avant)
    for i in [x["id"] for x in supprimes]:
        del fusion[i]
    for i, x in recus.items():
        if i in fusion:
            ancien = fusion[i]["n"]
            # Garde le nom déjà nettoyé, sauf si Jules l'a renommée « Kiné » sur Strava (kiné hors mardi/jeudi),
            # ou si une séance classée kiné porte en fait un titre Push / Pull / Jambes.
            if x["n"] != "Kiné" and not (ancien == "Kiné" and x.get("s")):
                x["n"] = ancien
        fusion[i] = x

    for x in fusion.values():
        if kine_du_matin(x):
            x["n"] = "Kiné"
    items = sorted(fusion.values(), key=lambda x: (x["d"], x["h"]), reverse=True)
    maj = datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Paris")).strftime("%Y-%m-%dT%H:%M")
    data["strava"]["items"] = items
    data["strava"]["maj"] = maj
    data["maj"] = maj
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")

    print(json.dumps({"maj": maj, "nouveaux": nouveaux, "supprimes": supprimes}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
