"""Exploratorio (2026-11-27, no es resultado de ningun estudio): balance hidrico FAO-56 simple con cada fuente de ET0.

Usa las predicciones F1 (estacion no vista) del estudio 03.2 y la lluvia SIAR de la propia estacion, comun a
todas las fuentes, para aislar el efecto de la ET0. Kc unico por cultivo, cubeta de agua util (TAW), riego que
rellena la cubeta cuando el agotamiento supera RAW = 0,5 TAW. Sin escorrentia ni percolacion explicita.

Uso:
    python -I studies/05_balance_hidrico/exploratorio/balance_rapido.py --pp-dir <carpeta con IBxx_datos_completos.csv de Capitulo-1>
"""
import argparse
import glob
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
FUENTES = {
    "PM SIAR (referencia)": "pm",
    "Open-Meteo crudo": "OM_crudo",
    "OM + AHC mensual transferido": "OM_AHC_mensual_medio_entrenamiento",
    "PM estacion mas cercana": "PM_estacion_mas_cercana_mismo_dia",
    "IDW mismo dia": "PM_IDW_estaciones_entrenamiento_mismo_dia",
    "HGB-S0 (sin sensor)": "S0|HGB",
    "HGB-S2 (+T, HR)": "S2|HGB",
    "HGB-L2 (solo sensor T, HR)": "L2|HGB",
}
CULTIVOS = {
    "Cesped (Kc 0,8 todo el anio, TAW 100 mm)": (lambda m: 0.8, 100),
    "Almendro (Kc 0,4-0,9 abr-oct, TAW 150 mm)": (lambda m: {4: .4, 5: .6, 6: .85, 7: .9, 8: .9, 9: .7, 10: .5}.get(m, 0), 150),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pp-dir", required=True, type=Path)
    a = ap.parse_args()
    d = pd.read_csv(ROOT / "studies/03_loso_openmeteo_ml/results/predictions_test.csv.gz")
    d = d[d.fold.astype(str).str.startswith("F1")] if d.fold.astype(str).str.startswith("F1").any() else d
    pp = pd.concat(pd.read_csv(f, usecols=["Fecha", "Precipitacion", "Estacion"]) for f in glob.glob(str(a.pp_dir / "IB*_datos_completos.csv")))
    pp = pp.rename(columns={"Fecha": "date", "Estacion": "station_code", "Precipitacion": "P"})
    d = d.merge(pp, on=["station_code", "date"], how="left")
    d["P"] = d.P.fillna(0)
    rows = []
    for cultivo, (kc, taw) in CULTIVOS.items():
        raw = 0.5 * taw
        for s, g in d.sort_values("date").groupby("station_code"):
            mes = g.date.str[5:7].astype(int).values
            for nombre, col in FUENTES.items():
                et = g[col].fillna(g.pm).clip(lower=0).values
                dr, riego = 0.0, 0.0
                for i in range(len(g)):
                    dr = max(dr - g.P.values[i], 0) + kc(mes[i]) * et[i]
                    if dr > raw:
                        riego += dr
                        dr = 0.0
                rows.append((cultivo, s, nombre, riego))
    t = pd.DataFrame(rows, columns=["cultivo", "estacion", "fuente", "riego_mm"]).pivot_table(index=["cultivo", "estacion"], columns="fuente", values="riego_mm")
    res = []
    for c, g in t.groupby(level=0):
        ref = g["PM SIAR (referencia)"]
        for f in FUENTES:
            p = (g[f] / ref - 1) * 100
            res.append((c, f, round(g[f].mean() / 6), round(p.mean(), 1), round(p.abs().mean(), 1), round(p.abs().max(), 1)))
    print(pd.DataFrame(res, columns=["cultivo", "fuente", "riego_mm_anio", "sesgo_pct", "error_abs_medio_pct_por_estacion", "peor_estacion_pct"]).to_string(index=False))


if __name__ == "__main__":
    main()
