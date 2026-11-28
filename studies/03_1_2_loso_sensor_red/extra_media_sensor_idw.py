"""Analisis POST HOC del 03.1.2 (no planificado, sin veredicto): media simple de un modelo de sensor y la IDW del dia.

Sin entrenar nada: lee results/predictions_test.csv.gz del propio estudio. Para cada familia de sensor (HGB, escenario B):
  media_S_IDW   = (HGB con solo el sensor + IDW del dia) / 2
  media_S3_IDW  = (HGB sensor + 3 vecinas (S+R3) + IDW del dia) / 2
y las compara con la IDW, con el sensor solo y con S+R1. Mismo bootstrap que el informe (2.000 replicas, semilla 20261126,
bloques estacion-ano). Es el analogo con sensor de la media HGB-S0 + IDW del 03.2/03.3 (0,377, post hoc).

Salidas: results/extra_media_sensor_idw.csv (global por familia y particion) y
results/extra_media_sensor_idw_por_estacion.csv. Uso: python studies/03_1_2_loso_sensor_red/extra_media_sensor_idw.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import report as r
from design import lc

RES = r.RES
FAM_NAMES = {"VALIANTZAS": "Valiantzas", "HS_RA": "HS-Ra", "HG_RS": "HG-Rs"}


def scope(t: pd.DataFrame, name: str) -> pd.DataFrame:
    return t[t.scheme == "F1_loso"] if name == "F1" else t[t.fold == name]


def delta(a: pd.Series, b: pd.Series, t: pd.DataFrame):
    bi, _ = lc.block_index(t.station_code, t.date)
    draws = lc.boot_draws(bi.max() + 1)
    return r.boot_delta(a.to_numpy(), b.to_numpy(), t.pm.to_numpy(), bi, draws)


def rmse(x: pd.Series, t: pd.DataFrame) -> float:
    return float(np.sqrt(((x - t.pm) ** 2).mean()))


def main() -> None:
    P = pd.read_csv(RES / "predictions_test.csv.gz")
    B = P[P.scenario == "B"].copy()
    glob, st = [], []
    for fam, lab in FAM_NAMES.items():
        B[f"m_S|{fam}"] = (B[f"B|S|{fam}|HGB"] + B["B|IDW"]) / 2
        B[f"m_S3|{fam}"] = (B[f"B|S_R3|{fam}|HGB"] + B["B|IDW"]) / 2
        for sc in ["F1", "F2_Ibiza", "F2_Menorca", "F2_Mallorca_informativo"]:
            t = scope(B, sc)
            s, s1, s3, idw = (t[f"B|S|{fam}|HGB"], t[f"B|S_R1|{fam}|HGB"], t[f"B|S_R3|{fam}|HGB"], t["B|IDW"])
            m, m3 = t[f"m_S|{fam}"], t[f"m_S3|{fam}"]
            d_idw, d_s, d_s1 = delta(m, idw, t), delta(m, s, t), delta(m, s1, t)
            glob.append({"familia": lab, "particion": sc, "n": len(t), "rmse_S": rmse(s, t), "rmse_S_R1": rmse(s1, t),
                         "rmse_S_R3": rmse(s3, t), "rmse_IDW": rmse(idw, t), "rmse_media_S_IDW": rmse(m, t),
                         "rmse_media_S3_IDW": rmse(m3, t),
                         "corr_errores_S_IDW": float(np.corrcoef(s - t.pm, idw - t.pm)[0, 1]),
                         "d_media_vs_IDW": d_idw[0], "d_media_vs_IDW_lo95": d_idw[1], "d_media_vs_IDW_hi95": d_idw[2],
                         "d_media_vs_S": d_s[0], "d_media_vs_S_lo95": d_s[1], "d_media_vs_S_hi95": d_s[2],
                         "d_media_vs_S_R1": d_s1[0], "d_media_vs_S_R1_lo95": d_s1[1], "d_media_vs_S_R1_hi95": d_s1[2]})
            for stn, g in t.groupby("station_code"):
                st.append({"familia": lab, "particion": sc, "station_code": stn, "rmse_IDW": rmse(g["B|IDW"], g),
                           "rmse_S": rmse(g[f"B|S|{fam}|HGB"], g), "rmse_S_R1": rmse(g[f"B|S_R1|{fam}|HGB"], g),
                           "rmse_media_S_IDW": rmse(g[f"m_S|{fam}"], g)})
    pd.DataFrame(glob).round(5).to_csv(RES / "extra_media_sensor_idw.csv", index=False)
    pd.DataFrame(st).round(5).to_csv(RES / "extra_media_sensor_idw_por_estacion.csv", index=False)
    print(pd.DataFrame(glob).round(3).to_string())


if __name__ == "__main__":
    main()
