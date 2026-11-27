"""Distancia a la costa de las 9 estaciones (variante A del 03.1.2) y diagnostico previo sin entrenar.

    python studies/03_1_2_loso_sensor_red/coast.py compute --geojson RUTA/ne_10m_coastline.geojson
    python studies/03_1_2_loso_sensor_red/coast.py compute --download      # Kaggle u otro equipo con red
    python studies/03_1_2_loso_sensor_red/coast.py diag

Linea de costa: Natural Earth 1:10m `ne_10m_coastline` (dominio publico), en GeoJSON del repositorio oficial de
Natural Earth (github.com/nvkelso/natural-earth-vector). Se guarda en config/stations_coast.csv con la URL, el nombre
del fichero y su SHA256. Nunca se estima a mano.

Metodo: para cada estacion, distancia minima a todos los segmentos de la linea de costa. El punto mas cercano de cada
segmento se busca en una proyeccion plana local centrada en la estacion (equirectangular; en distancias de pocos km el
error de esta aproximacion es despreciable frente a la resolucion de la escala 1:10m) y la distancia final se calcula
con haversine (esfera R = 6371 km, la misma que loso_common.haversine_km) desde la estacion hasta ese punto.

`diag` (sin entrenar nada): sesgo por estacion del 03.1 (HGB principal de las tres familias y Open-Meteo + AHC mensual
transferido), anual y de verano (JJA), frente a log1p(distancia a la costa); correlacion de Spearman con n = 9
(indicativa). Salidas: results/coast_diagnostic.csv, results/coast_diagnostic.json y figures/00_diagnostico_costa.png.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "03_1_loso_inputs_siar"))
import loso_common as lc  # noqa: E402

URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_coastline.geojson")
OUT = lc.ROOT / "config/stations_coast.csv"
R_EARTH = 6371.0
S031_RES = HERE.parent / "03_1_loso_inputs_siar/results"


def _lines(geo):
    for ft in geo["features"]:
        g = ft["geometry"]
        if g is None:
            continue
        if g["type"] == "LineString":
            yield np.asarray(g["coordinates"], float)[:, :2]
        elif g["type"] == "MultiLineString":
            for part in g["coordinates"]:
                yield np.asarray(part, float)[:, :2]


def min_distance_km(lat, lon, lines, box_deg=3.0):
    """Distancia minima (km) del punto a un conjunto de polilineas [lon, lat]."""
    best, best_pt = np.inf, None
    k = np.cos(np.radians(lat))
    for ln in lines:
        if len(ln) < 2:
            continue
        near = (np.abs(ln[:, 1] - lat) < box_deg) & (np.abs(ln[:, 0] - lon) < box_deg / max(k, 1e-6))
        if not near.any():
            continue
        x = (ln[:, 0] - lon) * k          # grados "de este" escalados (plano local)
        y = ln[:, 1] - lat
        ax, ay, bx, by = x[:-1], y[:-1], x[1:], y[1:]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        t = np.where(L2 > 0, np.clip(-(ax * dx + ay * dy) / np.where(L2 > 0, L2, 1), 0, 1), 0)
        px, py = ax + t * dx, ay + t * dy
        d2 = px * px + py * py
        i = int(np.argmin(d2))
        if d2[i] < best:
            best, best_pt = d2[i], (lat + py[i], lon + px[i] / k)
    if best_pt is None:
        return np.nan
    return float(lc.haversine_km(lat, lon, best_pt[0], best_pt[1]))


def compute(geojson_path=None, download=False):
    if download:
        dst = Path("ne_10m_coastline.geojson")
        urllib.request.urlretrieve(URL, dst)
        geojson_path = dst
    raw = Path(geojson_path).read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    lines = list(_lines(json.loads(raw)))
    st = lc.load_stations()
    rows = []
    for s in lc.STATIONS:
        km = min_distance_km(st.latitude_deg[s], st.longitude_deg_derived[s], lines)
        rows.append({"station_code": s, "coast_km": round(km, 3), "log1p_coast_km": round(float(np.log1p(km)), 5)})
    df = pd.DataFrame(rows)
    head = (f"# Distancia minima a la linea de costa (km). Fuente: Natural Earth 1:10m ne_10m_coastline (dominio publico)\n"
            f"# url: {URL}\n# fichero: {Path(geojson_path).name}  sha256: {sha}\n"
            f"# metodo: studies/03_1_2_loso_sensor_red/coast.py (punto mas cercano en plano local + haversine R=6371)\n")
    OUT.write_text(head + df.to_csv(index=False), encoding="utf-8")
    print(head + df.to_string(index=False))


def _spearman(a, b):
    ra, rb = pd.Series(a).rank().to_numpy(), pd.Series(b).rank().to_numpy()
    return float(np.corrcoef(ra, rb)[0, 1])


def diag():
    """Diagnostico sin entrenar: sesgo por estacion del 03.1 frente a la distancia a la costa (F1, TEST, cohorte)."""
    coast = pd.read_csv(OUT, comment="#").set_index("station_code")
    p = pd.read_csv(S031_RES / "predictions_test.csv.gz")
    p = p[p.scheme == "F1_loso"]
    methods = {f"{f}|principal|HGB": f"HGB {f}" for f in lc.FAMILIES} | \
              {"OM_AHC_mensual_medio_entrenamiento": "OM + AHC mensual", "PM_IDW_estaciones_entrenamiento_mismo_dia": "IDW"}
    jja = p.date.str[5:7].isin(["06", "07", "08"])
    rows = []
    for m, lab in methods.items():
        e = p[m] - p.pm
        for s in lc.STATIONS:
            k = p.station_code == s
            rows.append({"method": m, "label": lab, "station_code": s, "coast_km": coast.coast_km[s],
                         "log1p_coast_km": coast.log1p_coast_km[s], "bias": float(e[k].mean()),
                         "bias_JJA": float(e[k & jja].mean()),
                         "rmse": float(np.sqrt(np.mean(e[k] ** 2)))})
    d = pd.DataFrame(rows)
    res = {"_comment": "Diagnostico previo de la variante A, sin entrenar (03.1.2, Parte II). n = 9 estaciones: "
                       "solo indicativo, sin IC ni contraste.", "spearman": {}}
    for m, g in d.groupby("method"):
        res["spearman"][m] = {c: round(_spearman(g.log1p_coast_km, g[c]), 3) for c in ("bias", "bias_JJA", "rmse")}
    (HERE / "results").mkdir(exist_ok=True)
    d.round(4).to_csv(HERE / "results/coast_diagnostic.csv", index=False)
    (HERE / "results/coast_diagnostic.json").write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n",
                                                        encoding="utf-8")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    (HERE / "figures").mkdir(exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharex=True)
    for ax, col, tit in zip(axes, ("bias", "bias_JJA"), ("Sesgo medio (TEST)", "Sesgo de verano (JJA)")):
        for m, g in d.groupby("method", sort=False):
            ax.plot(g.coast_km, g[col], "o", label=f"{g.label.iloc[0]} (ρ={res['spearman'][m][col]:+.2f})")
        for s, x, y in d[d.method == "OM_AHC_mensual_medio_entrenamiento"][["station_code", "coast_km", col]].values:
            ax.annotate(s, (x, y), fontsize=7, xytext=(3, 3), textcoords="offset points")
        ax.axhline(0, color="0.6", lw=0.8)
        ax.set_xscale("symlog", linthresh=1)
        ax.set_xlabel("Distancia a la costa (km, Natural Earth 1:10m)")
        ax.set_ylabel("mm/día")
        ax.set_title(tit)
    axes[1].legend(fontsize=7)
    fig.suptitle("Diagnóstico de costa (sin entrenar): sesgo por estación del 03.1, F1, n = 9 (indicativo)")
    fig.tight_layout()
    fig.savefig(HERE / "figures/00_diagnostico_costa.png", dpi=150)
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["compute", "diag"])
    ap.add_argument("--geojson", default="")
    ap.add_argument("--download", action="store_true")
    a = ap.parse_args()
    if a.stage == "compute":
        if not a.geojson and not a.download:
            raise SystemExit("indicar --geojson RUTA o --download")
        compute(a.geojson or None, a.download)
    else:
        diag()
