"""Estudio 02c: diferencia de RMSE pareada con intervalo de confianza (bootstrap por bloques estacion-anio).

Para cada granularidad y familia: RMSE(ANN_A V2) - RMSE(Open-Meteo + AHC) sobre la misma cohorte; negativo = gana la ANN.
Bloques = (estacion, anio) -> 54 bloques; 5000 remuestreos, semilla fija. El IC refleja la variabilidad entre estaciones y anios,
no la incertidumbre del entrenamiento (un solo ajuste/entrenamiento por celda).
"""
import csv
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "studies/02_openmeteo_ahc/results"
pred = {}
for r in csv.DictReader(open(RES / "predictions_openmeteo_2020_2025.csv")):
    pred[(r["resolution"], r["station_code"], r["date"])] = (float(r["pm_ref"]), float(r["om_ahc"]))
rng = np.random.default_rng(20261126)
out = []
for res in ("annual", "seasonal", "monthly"):
    rows = [r for r in csv.DictReader(open(ROOT / f"data/v2/et0_v2_{res}_2020_2025.csv")) if r["common_core"] == "1"]
    for fam in ("HS_RA_V1", "HG_RS_V1", "VALIANTZAS_V1"):
        for meth in ("ANN_A", "ML"):
            blocks = {}
            for r in rows:
                if r[f"{fam}_{meth}"] == "":
                    continue
                y, om = pred[(res, r["station_id"], r["date"])]
                a = float(r[f"{fam}_{meth}"])
                b = blocks.setdefault((r["station_id"], r["date"][:4]), [0, 0.0, 0.0])
                b[0] += 1; b[1] += (a - y) ** 2; b[2] += (om - y) ** 2
            B = np.array(list(blocks.values()))
            n, sa, so = B[:, 0], B[:, 1], B[:, 2]
            d0 = np.sqrt(sa.sum() / n.sum()) - np.sqrt(so.sum() / n.sum())
            idx = rng.integers(0, len(B), size=(5000, len(B)))
            d = np.sqrt(sa[idx].sum(1) / n[idx].sum(1)) - np.sqrt(so[idx].sum(1) / n[idx].sum(1))
            lo, hi = np.percentile(d, [2.5, 97.5])
            verdict = "ANN gana" if hi < 0 else ("OM+AHC gana" if lo > 0 else "empate (IC incluye 0)")
            out.append([res, fam, meth, int(n.sum()), f"{d0:+.4f}", f"{lo:+.4f}", f"{hi:+.4f}", verdict])
with open(RES / "paired_ci.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["resolution", "family", "method", "n", "delta_rmse_vs_OM_AHC", "ci95_lo", "ci95_hi", "verdict"]); w.writerows(out)
print("| Granularidad | Familia | Método | ΔRMSE (V2 − OM+AHC) | IC 95 % | Veredicto |\n|---|---|---|---|---|---|")
for o in out:
    print(f"| {o[0]} | {o[1]} | {o[2]} | {o[4]} | [{o[5]}, {o[6]}] | {o[7]} |")
