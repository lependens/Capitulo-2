"""Diagnóstico posterior (sin veredicto) del fallo de las ANN en F1: extrapolación de inputs estáticos.

No forma parte de la regla de decisión ni cambia ningún criterio. Lee las predicciones ya calculadas
(`results/predictions_test.csv.gz`, `results/cells/`) y escribe:

- results/diagnostico_rango_inputs_estaticos.csv: por estación dejada fuera, si su altitud, latitud o
  longitud caen fuera del rango de las 8 estaciones de entrenamiento.
- results/diagnostico_sin_IB01.csv: F1 sin IB01 (8 estaciones), ΔRMSE con IC 95 % (mismo bootstrap de
  bloques estación-año, mismas funciones que report.py) y RMSE por semilla de las ANN.

    python studies/03_loso_openmeteo_ml/diagnostico_ann_altitud.py
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import CELLS, RES, lc  # noqa: E402

MODELS = ["Ridge", "HGB", "RF", "ANN_S", "ANN_M"]
SCEN = ["S0", "S1", "S2", "L1", "L2", "S0_coord"]
COMP = ["OM_AHC_mensual_medio_entrenamiento", "PM_estacion_mas_cercana_mismo_dia",
        "PM_IDW_estaciones_entrenamiento_mismo_dia"]


def static_ranges():
    st = lc.load_stations().rename(columns={"latitude_deg": "lat", "longitude_deg_derived": "lon"})
    rows = []
    for c in st.index:
        o = st.drop(c)
        row = {"station_code": c}
        for k in ("altitude_m", "lat", "lon"):
            row[k] = float(st.loc[c, k])
            row[f"{k}_train_min"], row[f"{k}_train_max"] = float(o[k].min()), float(o[k].max())
            row[f"{k}_fuera_de_rango"] = not (o[k].min() <= st.loc[c, k] <= o[k].max())
        rows.append(row)
    return pd.DataFrame(rows)


def without(pred, station="IB01"):
    q = pred[pred.fold.str.startswith("F1") & (pred.station_code != station)].reset_index(drop=True)
    bi, _ = lc.block_index(q.station_code, q.date)
    draws = lc.boot_draws(bi.max() + 1)
    rows = []

    def add(kind, a, b):
        d0, lo, hi = lc.paired_delta_ci(q[a].to_numpy(), q[b].to_numpy(), q.pm.to_numpy(), bi, draws)
        rows.append({"kind": kind, "A": a, "B": b, "n": len(q), "n_blocks": int(bi.max() + 1),
                     "rmse_A": lc.metrics(q[a], q.pm)["rmse"], "rmse_B": lc.metrics(q[b], q.pm)["rmse"],
                     "delta_rmse": d0, "ci95_lo": lo, "ci95_hi": hi})

    for s in SCEN:
        for m in MODELS:
            if m != "HGB":
                add("modelo_vs_HGB", f"{s}|{m}", f"{s}|HGB")
    for m in MODELS:
        for c in COMP:
            add("S0_vs_comparador", f"S0|{m}", c)
    add("hipotesis_H1_sin_IB01", "S0|HGB", COMP[0])
    add("hipotesis_H2_sin_IB01", "S0|HGB", COMP[1])
    add("hipotesis_H3_sin_IB01", "S2|HGB", "S0|HGB")
    return pd.DataFrame(rows)


def seed_rmse(pred, station="IB01"):
    rows = []
    f1 = pred[pred.fold.str.startswith("F1")]
    for m in ("ANN_S", "ANN_M"):
        for s in SCEN:
            for excl in (False, True):
                err = [[] for _ in range(5)]
                for f in sorted(CELLS.glob(f"F1_*__{s}__{m}.json.gz")):
                    c = json.load(gzip.open(f))
                    if excl and station in c["fold"]:
                        continue
                    ref = f1[f1.fold == c["fold"]].pm.to_numpy()
                    for i, sp in enumerate(c["seed_preds"]):
                        err[i].append(np.asarray(sp) - ref)
                r = [float(np.sqrt(np.mean(np.concatenate(e) ** 2))) for e in err]
                rows.append({"model": m, "scenario": s, "sin": station if excl else "", "rmse_seeds": r,
                             "rmse_seed_min": min(r), "rmse_seed_max": max(r), "rmse_seed_sd": float(np.std(r, ddof=1))})
    return pd.DataFrame(rows)


def main():
    pred = pd.read_csv(RES / "predictions_test.csv.gz")
    static_ranges().to_csv(RES / "diagnostico_rango_inputs_estaticos.csv", index=False)
    without(pred).to_csv(RES / "diagnostico_sin_IB01.csv", index=False, float_format="%.6f")
    seed_rmse(pred).to_csv(RES / "diagnostico_semillas_ann.csv", index=False, float_format="%.6f")
    print("escrito: diagnostico_rango_inputs_estaticos.csv, diagnostico_sin_IB01.csv, diagnostico_semillas_ann.csv")


if __name__ == "__main__":
    main()
