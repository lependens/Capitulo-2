"""Estudio 01, paso 2: que input de Open-Meteo introduce el error en la ET0.

1. Compara cada input de Open-Meteo con el medido en SIAR (sesgo, RMSE, MAE, correlacion).
2. Recalcula PM FAO-56 sustituyendo los inputs del sensor por los de Open-Meteo, de uno en uno y todos a la vez,
   y mide el error frente a PM_FAO56_V1 (con los 4 inputs de sensor la PM recalculada coincide con la referencia
   a ~1e-6 mm/dia: es el control del experimento).

Viento: Open-Meteo da viento a 10 m; se convierte a 2 m con el factor FAO-56 (0,748). SIAR se toma como 2 m
(convencion de Capitulo-1, no verificada estacion a estacion).

Uso:
    PYTHONPATH=src python studies/01_et0_vs_pm/diagnose_inputs.py
"""

import argparse
import csv
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from openmeteo_et0 import metrics  # noqa: E402
from openmeteo_et0.pm import WIND_10M_TO_2M, et0_pm  # noqa: E402
from openmeteo_et0.stations import load_stations  # noqa: E402


def num(v):
    try:
        return float(v) if v not in ("", None) else None
    except ValueError:
        return None


def corr(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    sab = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    saa = sum((x - ma) ** 2 for x in a)
    sbb = sum((y - mb) ** 2 for y in b)
    return sab / math.sqrt(saa * sbb) if saa and sbb else float("nan")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", type=Path, default=ROOT / "data/reference/reference_2020_2025.csv")
    ap.add_argument("--inputs", type=Path, default=ROOT / "data/reference/siar_inputs_2020_2025.csv")
    ap.add_argument("--openmeteo", type=Path, default=ROOT / "data/processed/openmeteo_archive.csv")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "results" / "inputs_2020_2025")
    a = ap.parse_args(argv)

    stations = {s.code: s for s in load_stations()}
    ref = {}
    with open(a.reference, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            v = num(r["ET0_PM_FAO56_V1"])
            if v is not None:
                ref[(r["station_code"], r["date"])] = v
    om = {}
    with open(a.openmeteo, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            om[(r["station_code"], r["date"])] = r

    rows = []  # cohorte: todos los inputs (SIAR y Open-Meteo) presentes + referencia
    with open(a.inputs, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            k = (r["station_code"], r["date"])
            if k[0] not in stations or k not in ref or k not in om:
                continue
            o = om[k]
            s = {"tmax": num(r["TempMax"]), "tmin": num(r["TempMin"]), "rhmax": num(r["HumedadMax"]),
                 "rhmin": num(r["HumedadMin"]), "rhmean": num(r["HumedadMedia"]), "u2": num(r["VelViento"]),
                 "rs": num(r["Radiacion"])}
            w10 = num(o["wind10_mean_ms"])
            m = {"tmax": num(o["tmax_c"]), "tmin": num(o["tmin_c"]), "rhmax": num(o["rh_max_pct"]),
                 "rhmin": num(o["rh_min_pct"]), "rhmean": num(o["rh_mean_pct"]),
                 "u2": None if w10 is None else w10 * WIND_10M_TO_2M, "rs": num(o["shortwave_sum_mj_m2"])}
            if any(v is None for v in s.values()) or any(v is None for v in m.values()):
                continue
            rows.append((k, s, m, ref[k], num(o["et0_om_mm"])))

    a.out.mkdir(parents=True, exist_ok=True)
    n = len(rows)

    # 1) inputs: Open-Meteo - SIAR
    labels = {"tmax": "Tmax (C)", "tmin": "Tmin (C)", "rhmax": "HRmax (%)", "rhmin": "HRmin (%)",
              "rhmean": "HRmedia (%)", "u2": "Viento a 2 m (m/s)", "rs": "Radiacion (MJ/m2/dia)"}
    in_rows = []
    for key, label in labels.items():
        d = [m[key] - s[key] for _, s, m, _, _ in rows]
        xs = [s[key] for _, s, _, _, _ in rows]
        ys = [m[key] for _, _, m, _, _ in rows]
        in_rows.append({"variable": label, "n": n, "media_siar": sum(xs) / n, "media_openmeteo": sum(ys) / n,
                        "sesgo": sum(d) / n, "rmse": math.sqrt(sum(x * x for x in d) / n),
                        "mae": sum(abs(x) for x in d) / n, "correlacion": corr(xs, ys)})
    # rango diurno (Tmax - Tmin)
    d = [(m["tmax"] - m["tmin"]) - (s["tmax"] - s["tmin"]) for _, s, m, _, _ in rows]
    in_rows.append({"variable": "Rango diurno Tmax-Tmin (C)", "n": n,
                    "media_siar": sum(s["tmax"] - s["tmin"] for _, s, _, _, _ in rows) / n,
                    "media_openmeteo": sum(m["tmax"] - m["tmin"] for _, _, m, _, _ in rows) / n,
                    "sesgo": sum(d) / n, "rmse": math.sqrt(sum(x * x for x in d) / n),
                    "mae": sum(abs(x) for x in d) / n, "correlacion": ""})
    with open(a.out / "inputs_comparison.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(in_rows[0]))
        w.writeheader()
        w.writerows(in_rows)

    # 2) sustitucion de inputs en PM
    groups = {"T": ("tmax", "tmin"), "HR": ("rhmax", "rhmin"), "viento": ("u2",), "Rs": ("rs",)}
    scenarios = [("control: todos del sensor", ()),
                 ("solo T de Open-Meteo", ("T",)), ("solo HR de Open-Meteo", ("HR",)),
                 ("solo viento de Open-Meteo", ("viento",)), ("solo Rs de Open-Meteo", ("Rs",)),
                 ("T + Rs de Open-Meteo", ("T", "Rs")), ("T + HR de Open-Meteo", ("T", "HR")),
                 ("todos de Open-Meteo (PM propia)", ("T", "HR", "viento", "Rs"))]
    out_rows, summary = [], []
    for name, swap in scenarios:
        recs = []
        for (st, d), s, m, pm_ref, _ in rows:
            vals = dict(s)
            for g in swap:
                for v in groups[g]:
                    vals[v] = m[v]
            lat, alt = stations[st].latitude, stations[st].altitude_m
            e = et0_pm(vals["tmax"], vals["tmin"], vals["rhmax"], vals["rhmin"], vals["u2"], vals["rs"], lat, alt, d)
            recs.append({"station_code": st, "date": d, "pred": e, "ref": pm_ref})
        gm = metrics.compute([(r["pred"], r["ref"]) for r in recs])
        summary.append((name, gm))
        for r in metrics.group_metrics(recs):
            if r["group"] in ("global", "station", "season"):
                out_rows.append({"scenario": name, **r})
    recs = [{"station_code": k[0], "date": k[1], "pred": o, "ref": r} for k, _, _, r, o in rows if o is not None]
    gm = metrics.compute([(r["pred"], r["ref"]) for r in recs])
    summary.append(("ET0 nativa de Open-Meteo (referencia)", gm))
    for r in metrics.group_metrics(recs):
        if r["group"] in ("global", "station", "season"):
            out_rows.append({"scenario": "ET0 nativa de Open-Meteo", **r})
    fields = ["scenario", "group", "key", "n", "mae", "rmse", "bias", "r2", "r2_status"]
    with open(a.out / "et0_substitution.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out_rows)

    lines = ["# Diagnostico de inputs (2020-2025, 9 estaciones)", "",
             f"Cohorte: {n} dias con inputs completos en SIAR y Open-Meteo y referencia PM_FAO56_V1; "
             f"SHA256 de claves `{metrics.cohort_hash([{'station_code': k[0], 'date': k[1]} for k, *_ in rows])}`.",
             f"Viento de Open-Meteo convertido de 10 m a 2 m (x{WIND_10M_TO_2M:.3f}).", "",
             "## Inputs: Open-Meteo menos SIAR", "",
             "| Variable | Media SIAR | Media Open-Meteo | Sesgo | RMSE | Correlacion |", "|---|---:|---:|---:|---:|---:|"]
    for r in in_rows:
        c = f"{r['correlacion']:.3f}" if r["correlacion"] != "" else ""
        lines.append(f"| {r['variable']} | {r['media_siar']:.2f} | {r['media_openmeteo']:.2f} | {r['sesgo']:+.2f} | {r['rmse']:.2f} | {c} |")
    lines += ["", "## ET0 recalculada con PM sustituyendo inputs (frente a PM_FAO56_V1)", "",
              "| Escenario | RMSE | Sesgo | R2 |", "|---|---:|---:|---:|"]
    for name, gm in summary:
        lines.append(f"| {name} | {gm['rmse']:.3f} | {gm['bias']:+.3f} | {gm['r2']:.3f} |")
    (a.out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
