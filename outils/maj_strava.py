"""Fusionne des réponses Strava « list_activities » dans data.json, au format de l'app.

Usage : python3 outils/maj_strava.py --depuis AAAA-MM-JJ page1.json [page2.json …]

La kiné (enregistrée par la montre en « Entraînement aux poids ») est reconnue par
l'app d'après le programme réel du jour, déplacements compris (depuis le 27/10) :
le script ne renomme plus les séances du mardi et du jeudi matin. Une activité
renommée « Kiné » sur Strava est reprise comme telle.

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
    if (a.get("sport_type") or "") not in ("WeightTraining", "Workout"):
        return None
    n = (a.get("name") or "").lower()
    if "push" in n:
        return "push"
    if "pull" in n:
        return "pull"
    if re.search(r"jambe|legs|squat|[ée]paule", n):
        return "legs"
    return None


COURSE = re.compile(r"\brun\b|running|\bcourse\b|🏃", re.I)
NAVETTE = re.compile(r"shuttle|navette", re.I)
TOURS = re.compile(r"(\d+)\s*(?:rounds?|tours?|sets?|séries)\b", re.I)
DIST = re.compile(r"(\d{1,2}[ \u202f\u00a0.]\d{3}(?!\d)|\d+(?:[.,]\d+)?)\s*(km|m)\b", re.I)
FOIS = re.compile(r"(\d+)\s*[x×]\s*$", re.I)


def km_wod(a):
    """Km courus pendant une box / un WOD (demande de Jules, 27/10), lus dans la description (à défaut le titre).
    Chaque ligne qui parle de course (run, course, 🏃) et donne une distance compte, multipliée par le nombre
    de tours annoncé plus haut (« 3 tours », « 2 rounds », « × 2 sets ») ou sur la ligne (« 4 × 400 m run »).
    Distances non fixées (shuttle run, navettes) ignorées. Rien de lisible : None (Jules corrige dans l'app)."""
    if (a.get("sport_type") or "") not in ("HighIntensityIntervalTraining", "Crossfit"):
        return None
    texte = (a.get("description") or "").strip() or (a.get("name") or "")
    total, tours = 0.0, 1
    for ligne in texte.splitlines():
        course = COURSE.search(ligne)
        t = TOURS.search(ligne)
        if t and not course:
            tours = int(t.group(1))
            continue
        if not course or NAVETTE.search(ligne):
            continue
        for d in DIST.finditer(ligne):
            v = float(re.sub(r"[ \u202f\u00a0.]", "", d.group(1)) if re.fullmatch(r"\d{1,2}[ \u202f\u00a0.]\d{3}", d.group(1)) else d.group(1).replace(",", "."))
            km = v if d.group(2).lower() == "km" else v / 1000
            f = FOIS.search(ligne[:d.start()])
            total += km * (int(f.group(1)) if f else tours)
    total = round(total, 1)
    return total if 0 < total <= 15 else None


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
        **({"kb": kb} if (kb := km_wod(a)) else {}),
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

    items = sorted(fusion.values(), key=lambda x: (x["d"], x["h"]), reverse=True)
    maj = datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Paris")).strftime("%Y-%m-%dT%H:%M")
    data["strava"]["items"] = items
    data["strava"]["maj"] = maj
    data["maj"] = maj
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")

    print(json.dumps({"maj": maj, "nouveaux": nouveaux, "supprimes": supprimes}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
