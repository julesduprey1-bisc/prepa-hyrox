"""Calcule l'indice d'efficacité d'un run sur son bloc principal et l'ajoute à data.json.

Usage : python3 outils/indice_ef.py --id ID --perf perf.json [--streams streams.json] [--note "…"]

perf.json    : réponse Strava « get_activity_performance » (laps, FC).
streams.json : réponse « get_activity_streams » (time, distance, heart_rate), utilisée
               seulement si le run n'a qu'un tour.
Bloc principal = échauffement et retour au calme exclus :
  - plusieurs tours : on retire le premier s'il fait 15 min ou moins et le dernier
    s'il fait 10 min ou moins, puis on garde les tours qui restent ; s'il reste un vrai
    bloc (10 min ou plus), les tours de moins de 3 min (lignes droites et leurs
    récupérations, séance découpée sur la montre depuis le 28/10) sont écartés ;
  - un seul tour : on retire les 5 premières et les 3 dernières minutes des streams.
Indice = vitesse (m/s) ÷ FC moyenne × 1000.
"""
import argparse
import json
import pathlib

RACINE = pathlib.Path(__file__).resolve().parent.parent
DATA = RACINE / "data.json"


def bloc_tours(laps):
    laps = [l for l in laps if l.get("moving_time") and l.get("distance")]
    if len(laps) >= 3:
        if laps[0]["moving_time"] <= 900:
            laps = laps[1:]
        if laps[-1]["moving_time"] <= 600:
            laps = laps[:-1]
    elif len(laps) == 2:
        a, b = laps
        if b["moving_time"] <= 600 and b["moving_time"] < a["moving_time"]:
            laps = [a]
        elif a["moving_time"] <= 900 and a["moving_time"] < b["moving_time"]:
            laps = [b]
    if any(l["moving_time"] >= 600 for l in laps):
        laps = [l for l in laps if l["moving_time"] >= 180]
    if not laps or any(l.get("avg_hr") is None for l in laps):
        return None
    t = sum(l["moving_time"] for l in laps)
    d = sum(l["distance"] for l in laps)
    fc = sum(l["avg_hr"] * l["moving_time"] for l in laps) / t
    return d, t, fc, len(laps)


def bloc_streams(s, debut=300, fin=180):
    T, D, H = s.get("time"), s.get("distance"), s.get("heart_rate")
    if not (T and D and H) or T[-1] - debut - fin < 600:
        return None
    a, b = debut, T[-1] - fin
    idx = [i for i, x in enumerate(T) if a <= x <= b]
    if len(idx) < 3:
        return None
    i0, i1 = idx[0], idx[-1]
    hr = sum(H[i] * (T[i + 1] - T[i]) for i in range(i0, i1)) / (T[i1] - T[i0])
    return D[i1] - D[i0], T[i1] - T[i0], hr, 1


def allure(v):
    s = round(1000 / v)
    return f"{s // 60}:{s % 60:02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--perf", required=True)
    ap.add_argument("--streams")
    ap.add_argument("--note", default="")
    args = ap.parse_args()

    data = json.loads(DATA.read_text())
    act = next((x for x in data["strava"]["items"] if x["id"] == args.id), None)
    if not act:
        raise SystemExit(f"Activité {args.id} absente de data.json : lancer maj_strava.py d'abord.")

    perf = json.loads(pathlib.Path(args.perf).read_text())
    res = bloc_tours(perf.get("laps") or [])
    if (res is None or res[3] == 1 and len(perf.get("laps") or []) == 1) and args.streams:
        res = bloc_streams(json.loads(pathlib.Path(args.streams).read_text())) or res
    if res is None:
        raise SystemExit("Pas de FC exploitable : indice non calculé.")

    d, t, fc, _ = res
    v = d / t
    ind = round(v / fc * 1000, 2)
    zone = "récup" if fc < 130 else "EF" if fc <= 142 else "endurance active"
    point = {"id": args.id, "d": act["d"], "allure": allure(v), "fc": round(fc, 1), "ind": ind, "zone": zone,
             "note": args.note or f"bloc principal {round(t / 60)}'"}

    pts = [p for p in data["ef"]["points"] if p.get("id") != args.id]
    pts.append(point)
    pts.sort(key=lambda p: p["d"])
    data["ef"]["points"] = pts
    data["ef"]["maj"] = act["d"]
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(point, ensure_ascii=False))


if __name__ == "__main__":
    main()
