"""Estudio 02b: variantes mas justas de Open-Meteo (misma informacion que las formulas V2).

Mismo protocolo que run.py (AHC por estacion, ajuste <=2019, test 2020-2025 en la cohorte V2) pero cambiando QUE se
ajusta con AHC:
  OM_NATIVA    : ET0 nativa de Open-Meteo (todas las entradas + calculo propio).
  PM_OM_TODO   : PM FAO-56 propia con T, HR, Rs y viento de Open-Meteo (viento 10 m -> 2 m).
  PM_OM_U2=2   : igual, pero viento fijo 2 m/s (sin informacion de viento; OM aporta T, HR y Rs).
  HS_RA_OM     : Hargreaves-Samani con Tmin/Tmax de Open-Meteo y Ra (misma formula e inputs que HS_RA_V1; la
                 implementacion reproduce HS_RA_V1 con las T del sensor a 4e-6 mm/dia).
Comparador directo de HS_RA_OM: HS_RA_V1 (T de SIAR) FORMULA y AHC de V2.
"""
import csv, math, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from openmeteo_et0.metrics import compute, SEASONS  # noqa: E402
from openmeteo_et0.pm import et0_pm, extraterrestrial_radiation, WIND_10M_TO_2M  # noqa: E402
from openmeteo_et0.stations import load_stations  # noqa: E402

OUT = ROOT / "studies/02_openmeteo_ahc/results"
RES = ["annual", "seasonal", "monthly"]
ST = {s.code: s for s in load_stations()}


def f(v):
    return float(v) if v not in ("", None) else None


def variants(r, s):
    t = {k: f(r[c]) for k, c in (("tx", "tmax_c"), ("tn", "tmin_c"), ("hx", "rh_max_pct"), ("hn", "rh_min_pct"),
                                 ("rs", "shortwave_sum_mj_m2"), ("w", "wind10_mean_ms"), ("et", "et0_om_mm"))}
    d = r["date"]
    out = {"OM_NATIVA": t["et"]}
    if None in (t["tx"], t["tn"]):
        return out
    ra = extraterrestrial_radiation(s.latitude, d)
    out["HS_RA_OM"] = 0.0023 * ((t["tx"] + t["tn"]) / 2 + 17.8) * math.sqrt(max(t["tx"] - t["tn"], 0)) * ra * 0.408
    if None not in (t["hx"], t["hn"], t["rs"]):
        out["PM_OM_U2=2"] = et0_pm(t["tx"], t["tn"], t["hx"], t["hn"], 2.0, t["rs"], s.latitude, s.altitude_m, d)
        if t["w"] is not None:
            out["PM_OM_TODO"] = et0_pm(t["tx"], t["tn"], t["hx"], t["hn"], t["w"] * WIND_10M_TO_2M, t["rs"], s.latitude, s.altitude_m, d)
    return out


X = {}
for r in csv.DictReader(open(ROOT / "data/processed/openmeteo_archive.csv")):
    if r["station_code"] in ST:
        X[(r["station_code"], r["date"])] = variants(r, ST[r["station_code"]])
NAMES = ["OM_NATIVA", "PM_OM_TODO", "PM_OM_U2=2", "HS_RA_OM"]


def grp(res, d):
    m = int(d[5:7])
    return "all" if res == "annual" else (SEASONS[m] if res == "seasonal" else f"{m:02d}")


dev = []
for r in csv.DictReader(open(ROOT / "data/reference/reference_2004_2019.csv")):
    k = (r["station_code"], r["date"])
    if k[0] in ST and r["evaluated_PM"] == "true" and r["ET0_PM_FAO56_V1"] != "" and k in X:
        dev.append((k, float(r["ET0_PM_FAO56_V1"])))

rows, byst = [], []
for res in RES:
    v2 = [r for r in csv.DictReader(open(ROOT / f"data/v2/et0_v2_{res}_2020_2025.csv")) if r["common_core"] == "1"]
    for nm in NAMES:
        sxy, sxx = {}, {}
        for (st, d), y in dev:
            x = X[(st, d)].get(nm)
            if x is None:
                continue
            g = (st, grp(res, d))
            sxy[g] = sxy.get(g, 0) + x * y
            sxx[g] = sxx.get(g, 0) + x * x
        a = {g: sxy[g] / sxx[g] for g in sxy}
        for kind in ("RAW", "AHC"):
            prs, per = [], {}
            for r in v2:
                st, d = r["station_id"], r["date"]
                x = X[(st, d)].get(nm)
                if x is None:
                    continue
                p = x if kind == "RAW" else a[(st, grp(res, d))] * x
                y = float(r["reference_value"])
                prs.append((p, y))
                per.setdefault(st, []).append((p, y))
            rows.append({"resolution": res, "variant": f"{nm}_{kind}", **compute(prs)})
            for st, pp in per.items():
                byst.append({"resolution": res, "variant": f"{nm}_{kind}", "station_code": st, **compute(pp)})
    for nm in ("HS_RA_V1_FORMULA", "HS_RA_V1_AHC"):
        pp = [(float(r[nm]), float(r["reference_value"])) for r in v2 if r[nm] != ""]
        rows.append({"resolution": res, "variant": nm + "  [V2, T de SIAR]", **compute(pp)})

with open(OUT / "fair_variants_metrics.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    for r in rows:
        w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in r.items()})
with open(OUT / "fair_variants_by_station.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(byst[0]))
    w.writeheader()
    for r in byst:
        w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in r.items()})
print(f"{'variante':42s}" + "".join(f"{x:>22s}" for x in RES))
for v in dict.fromkeys(r["variant"] for r in rows):
    print(f"{v:42s}" + "".join(
        "{:>22s}".format("{:.3f} / {:+.3f} (n={})".format(r["rmse"], r["bias"], r["n"]))
        for res in RES for r in rows if r["variant"] == v and r["resolution"] == res))
