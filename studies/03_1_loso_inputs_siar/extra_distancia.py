"""Analisis EXPLORATORIO posterior (post hoc) del estudio 03.1: el error frente a la distancia a la estacion de entrenamiento mas cercana.

Responde a: que aporta el comparador H2 (PM de la estacion mas cercana) y como cambia el error de cada metodo cuando
el vecino esta mas lejos (F1: 10-93 km; F2: 93-130 km). Descriptivo, sin IC: solo 9 estaciones y 3 con vecino lejano.
No modifica hipotesis, comparadores congelados ni la regla de decision.

Salidas: results/extra_distancia.csv (por estacion y esquema: distancia al vecino de entrenamiento mas cercano, RMSE) y
results/extra_distancia_bandas.csv (media de RMSE entre estaciones por banda de distancia).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
COLS = {"PM_vecina": "PM_estacion_mas_cercana_mismo_dia", "IDW": "PM_IDW_estaciones_entrenamiento_mismo_dia",
        "OM_AHC_mensual": "OM_AHC_mensual_medio_entrenamiento",
        "HGB_HS-Ra": "HS_RA|principal|HGB", "HGB_Valiantzas": "VALIANTZAS|principal|HGB", "HGB_HG-Rs": "HG_RS|principal|HGB"}


def haversine(a, b):
    la1, lo1, la2, lo2 = map(np.radians, [a[0], a[1], b[0], b[1]])
    h = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return float(12742 * np.arcsin(np.sqrt(h)))


def main():
    st = pd.read_csv(ROOT / "config" / "stations.csv").set_index("station_code")
    ll = {k: (st.latitude_deg[k], st.longitude_deg_derived[k]) for k in st.index}
    folds = json.load(open(HERE / "results" / "folds.json"))["folds"]
    pred = pd.read_csv(HERE / "results" / "predictions_test.csv.gz")
    rows = []
    for f in folds:
        for s in f["test"]:
            g = pred[(pred.scheme == f["scheme"]) & (pred.station_code == s)].dropna(subset=["pm"] + list(COLS.values()))
            near = min(f["train"], key=lambda t: (haversine(ll[s], ll[t]), t))
            row = {"esquema": f["scheme"], "estacion": s, "vecina_entrenamiento": near,
                   "distancia_km": round(haversine(ll[s], ll[near]), 1), "n": len(g)}
            for k, c in COLS.items():
                row[k] = round(float(np.sqrt(np.mean((g[c] - g.pm) ** 2))), 4)
            rows.append(row)
    df = pd.DataFrame(rows).sort_values(["esquema", "distancia_km", "estacion"])
    df.to_csv(HERE / "results" / "extra_distancia.csv", index=False)
    f1 = df[df.esquema == "F1_loso"]
    print(df.to_string(index=False))
    df["banda"] = np.where(df.esquema == "F1_loso", np.where(df.distancia_km < 25, "F1 10-22 km", np.where(df.distancia_km < 50, "F1 32 km", "F1 93 km")), "F2 93-130 km")
    res = df.groupby("banda")[list(COLS)].mean().round(3)
    res.insert(0, "n_estaciones", df.groupby("banda").size())
    res.to_csv(HERE / "results" / "extra_distancia_bandas.csv")
    print(res.to_string())
    print("correlacion distancia vs RMSE de PM_vecina (F1, 9 puntos):", round(f1.distancia_km.corr(f1.PM_vecina), 2))


if __name__ == "__main__":
    main()
