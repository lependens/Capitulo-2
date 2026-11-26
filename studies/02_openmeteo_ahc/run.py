"""Estudio 02: ET0 de Open-Meteo + ajuste tipo AHC (OLS por el origen) frente a V2.

Ajuste con DESARROLLO (<=2019-12-31) por estacion; evaluacion en TEST 2020-2025 sobre la cohorte common_core de V2.
Uso (desde la raiz):  python studies/02_openmeteo_ahc/run.py
"""
import csv, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from openmeteo_et0.metrics import compute, season_key, SEASONS, cohort_hash  # noqa: E402

OUT = ROOT / "studies/02_openmeteo_ahc/results"
RES = ["annual", "seasonal", "monthly"]
FAMS = ["HS_RA_V1", "HG_RS_V1", "VALIANTZAS_V1"]
METHODS = ["FORMULA", "AHC", "ML", "ANN_A", "ANN_E"]
stations = [r["station_code"] for r in csv.DictReader(open(ROOT / "config/stations.csv"))]


def fnum(s):
    return float(s) if s not in ("", None) else None


om = {(r["station_code"], r["date"]): fnum(r["et0_om_mm"]) for r in csv.DictReader(open(ROOT / "data/processed/openmeteo_archive.csv"))}

# --- DESARROLLO: pares (x=OM, y=PM) ---
dev = []
for r in csv.DictReader(open(ROOT / "data/reference/reference_2004_2019.csv")):
    if r["station_code"] not in stations or r["evaluated_PM"] != "true":
        continue
    y, x = fnum(r["ET0_PM_FAO56_V1"]), om.get((r["station_code"], r["date"]))
    if y is None or x is None:
        continue
    dev.append((r["station_code"], r["date"], x, y))


def group(res, date):
    m = int(date[5:7])
    return "all" if res == "annual" else (SEASONS[m] if res == "seasonal" else f"{m:02d}")


coef, ncoef = {}, {}
for res in RES:
    sxy, sxx, n = {}, {}, {}
    for st, d, x, y in dev:
        k = (st, group(res, d))
        sxy[k] = sxy.get(k, 0) + x * y
        sxx[k] = sxx.get(k, 0) + x * x
        n[k] = n.get(k, 0) + 1
    for k in sxy:
        coef[(res, *k)] = sxy[k] / sxx[k]
        ncoef[(res, *k)] = n[k]

OUT.mkdir(parents=True, exist_ok=True)
with open(OUT / "coefficients.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["resolution", "station_code", "group", "coef_a", "n_dev"])
    for k in sorted(coef):
        w.writerow([*k, f"{coef[k]:.6f}", ncoef[k]])

# --- TEST ---
metrics_rows, strows, pred_out = [], [], []
cmp_rows = []
for res in RES:
    v2 = list(csv.DictReader(open(ROOT / f"data/v2/et0_v2_{res}_2020_2025.csv")))
    coh = [r for r in v2 if r["common_core"] == "1"]
    recs = {"OM_RAW": [], "OM_AHC": []}
    v2recs = {f"{f}_{m}": [] for f in FAMS for m in METHODS}
    missing = 0
    for r in coh:
        st, d = r["station_id"], r["date"]
        x, y = om.get((st, d)), float(r["reference_value"])
        a = coef.get((res, st, group(res, d)))
        if x is None or a is None:
            missing += 1
            continue
        base = {"station_code": st, "date": d, "ref": y}
        recs["OM_RAW"].append({**base, "pred": x})
        recs["OM_AHC"].append({**base, "pred": a * x})
        pred_out.append([res, st, d, y, x, a * x])
        for f in FAMS:
            for m in METHODS:
                p = fnum(r[f"{f}_{m}"])
                if p is not None:
                    v2recs[f"{f}_{m}"].append({**base, "pred": p})
    print(res, "cohorte", len(coh), "sin OM/coef", missing, "cohort_hash", cohort_hash(recs["OM_AHC"])[:12])
    allrecs = {**recs, **v2recs}
    for name, rr in allrecs.items():
        m = compute([(x["pred"], x["ref"]) for x in rr])
        metrics_rows.append({"resolution": res, "method": name, **m})
        for st in stations:
            s = compute([(x["pred"], x["ref"]) for x in rr if x["station_code"] == st])
            strows.append({"resolution": res, "method": name, "station_code": st, **s})

with open(OUT / "predictions_openmeteo_2020_2025.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["resolution", "station_code", "date", "pm_ref", "om_et0", "om_ahc"])
    for r in pred_out:
        w.writerow([r[0], r[1], r[2], f"{r[3]:.6f}", f"{r[4]:.4f}", f"{r[5]:.6f}"])
for name, rows in (("metrics_global.csv", metrics_rows), ("metrics_by_station.csv", strows)):
    with open(OUT / name, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in r.items()})

# --- comparaciones A y B (criterios congelados en config/thresholds_v2.json) ---
g = {(r["resolution"], r["method"]): r for r in metrics_rows}
s = {(r["resolution"], r["method"], r["station_code"]): r["rmse"] for r in strows}
lines = ["| Granularidad | Comparador | RMSE comp. | RMSE OM+AHC | Sesgo comp. | Sesgo OM+AHC | Estaciones donde gana OM+AHC | Veredicto |", "|---|---|---|---|---|---|---|---|"]
for res in RES:
    o = g[(res, "OM_AHC")]
    for blk, names in (("A", [f"{f}_{m}" for m in ("FORMULA", "AHC") for f in FAMS]),
                       ("B", [f"{f}_{m}" for m in ("ML", "ANN_A", "ANN_E") for f in FAMS])):
        for nm in names:
            c = g[(res, nm)]
            wins = sum(1 for st in stations if s[(res, "OM_AHC", st)] != "" and s[(res, nm, st)] != "" and s[(res, "OM_AHC", st)] < s[(res, nm, st)])
            if blk == "A":
                ver = "A: OM+AHC mejora" if o["rmse"] < c["rmse"] else "A: no mejora"
            else:
                ver = "B: ventaja nuestra" if c["rmse"] < o["rmse"] else "B: OM+AHC iguala/supera"
            lines.append(f"| {res} | {nm} | {c['rmse']:.3f} | {o['rmse']:.3f} | {c['bias']:+.3f} | {o['bias']:+.3f} | {wins}/9 | {ver} |")
(OUT / "comparison.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
print("\nGLOBAL")
for res in RES:
    for nm in ("OM_RAW", "OM_AHC"):
        r = g[(res, nm)]
        print(res, nm, r["n"], f"rmse {r['rmse']:.4f} bias {r['bias']:+.4f} mae {r['mae']:.4f} r2 {r['r2']:.4f}")
print("dev pares", len(dev))
