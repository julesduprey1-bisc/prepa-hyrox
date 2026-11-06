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
  - un seul tour : on retire les 5 premières et les 3 dernières minutes des streams, les
    arrêts (trou de mesure ou moins de 0,5 m/s) et, s'il y en a, la série de lignes droites
    de la fin avec leurs récupérations (bloc arrêté 20 s avant : 3 accélérations ou plus en
    moins de 8 min, au-dessus de 1,3 × la vitesse médiane du début du bloc et de 2,9 m/s ;
    demande de Jules du 06/11 après l'EF du 04/11). Streams à demander en resolution 1000
    (une mesure toutes les 3-4 s) : à 100, les lignes droites ne se voient plus.
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
    if not (T and D and H) or len(T) < 3:
        return None
    n = len(T)
    dts = sorted(T[i] - T[i - 1] for i in range(1, n) if T[i] > T[i - 1])
    pas = dts[len(dts) // 2] if dts else 1
    trou = max(10, 3 * pas)          # au-delà : arrêt (pause automatique de la montre)
    a, b = debut, T[-1] - fin
    if pas <= 5:                     # assez de mesures pour voir des accélérations de 15 s
        k = max(1, round(3 / pas))

        def vit(i):
            u, w = max(0, i - k), min(n - 1, i + k)
            dt = T[w] - T[u]
            return (D[w] - D[u]) / dt if dt > 0 else 0

        V = [vit(i) for i in range(n)]
        base = sorted(V[i] for i in range(n) if a <= T[i] <= a + 600 and V[i] > 0.5)
        if base:
            seuil = max(2.9, 1.3 * base[len(base) // 2])
            acc, run, deb = [], 0, None
            for i in range(1, n):
                if T[i] < a + 600:
                    continue
                if V[i] >= seuil and T[i] - T[i - 1] <= trou:
                    if run == 0:
                        deb = T[i - 1]
                    run += T[i] - T[i - 1]
                else:
                    if run >= 4:
                        acc.append(deb)
                    run = 0
            if run >= 4:
                acc.append(deb)
            for j, t0 in enumerate(acc):
                if sum(1 for t in acc[j:] if t - t0 <= 480) >= 3:
                    b = min(b, t0 - 20)
                    break
    dist = tps = hs = 0
    for i in range(1, n):
        if T[i - 1] < a or T[i] > b:
            continue
        dt, dd = T[i] - T[i - 1], D[i] - D[i - 1]
        if dt <= 0 or dt > trou or dd / dt < 0.5:
            continue
        dist += dd
        tps += dt
        hs += (H[i] + H[i - 1]) / 2 * dt
    if tps < 600:
        return None
    return dist, tps, hs / tps, 1


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
