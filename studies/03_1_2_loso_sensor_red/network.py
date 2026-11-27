"""Columnas de red SIAR del estudio 03.1.2 (R1 y R3), con las dos reglas de construccion de los criterios.

Reglas (config/thresholds_v3_1_2.json -> network_features):
1. Exclusion de la propia estacion: para una fila de la estacion t, t nunca esta en el pool. En la validacion interna,
   la estacion de validacion se pasa en `exclude` y sale del pool de TODAS las filas (entrenamiento y validacion).
2. Ordenacion por cercania: PM_1..PM_3 y d1..d3 son la 1.a, 2.a y 3.a estacion DISPONIBLE ese dia mas cercana a la
   fila (d1 <= d2 <= d3), nunca columnas indexadas por el nombre de la estacion. Empates de distancia: por codigo,
   igual que loso_common.neighbours.

Pool de un dia: estaciones de `pool` con PM valida ese dia (target_ok), menos la propia y las de `exclude`.
IDW: potencia 2 sobre todo el pool disponible (mismo calculo que loso_common.pm_nearest_and_idw).
Pool con menos de 3 estaciones: R3 repite la ultima disponible (PM y distancia). Pool vacio: todo NaN (la fila no
entra; se cuenta fuera).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

R1_COLS = ["IDW_PM", "d1_km"]
R3_COLS = ["PM_1", "PM_2", "PM_3", "d1_km", "d2_km", "d3_km"]
ALL_COLS = ["IDW_PM", "PM_1", "PM_2", "PM_3", "d1_km", "d2_km", "d3_km", "n_pool"]


def pm_wide(df):
    """Tabla fecha x estacion con la PM valida (target_ok); NaN donde no hay PM valida."""
    d = df[df.target_ok]
    return d.pivot(index="date", columns="station_code", values="ET0_PM_FAO56_V1")


def ordered_pool(station, pool, dist, exclude=()):
    """Estaciones candidatas para una fila de `station`, sin ella misma ni `exclude`, ordenadas por (distancia, codigo)."""
    cand = [s for s in pool if s != station and s not in set(exclude)]
    return sorted(cand, key=lambda s: (dist[(station, s)], s))


def network_features(stations, net_dates, pool, pmw, dist, exclude=(), power=2.0):
    """Columnas de red para filas (estacion, fecha de red). Devuelve DataFrame con ALL_COLS, alineado con la entrada.

    stations, net_dates: secuencias de la misma longitud (codigo de estacion de la fila y fecha cuya red se usa: d en B
    y C, d-1 en B-ayer). pool: estaciones de entrenamiento de la particion. pmw: salida de pm_wide.
    """
    stations = np.asarray(stations, dtype=object)
    net_dates = np.asarray(net_dates, dtype=object)
    n = len(stations)
    out = {c: np.full(n, np.nan) for c in ALL_COLS}
    out["n_pool"] = np.zeros(n)
    for s in pd.unique(stations):
        rows = np.flatnonzero(stations == s)
        cand = ordered_pool(s, pool, dist, exclude)
        if not cand:
            continue
        dk = np.array([dist[(s, t)] for t in cand])
        M = pmw.reindex(index=net_dates[rows], columns=cand).to_numpy(dtype=float)
        avail = np.isfinite(M)
        navail = avail.sum(1)
        ok = navail > 0
        w = np.where(avail, 1.0 / dk ** power, 0.0)
        num = np.where(avail, w * np.nan_to_num(M), 0.0).sum(1)
        den = w.sum(1)
        out["IDW_PM"][rows[ok]] = num[ok] / den[ok]
        out["n_pool"][rows] = navail
        cum = np.cumsum(avail, axis=1)
        for j in (1, 2, 3):
            r = np.minimum(j, navail)                          # rango efectivo: si faltan, la ultima disponible
            hit = avail & (cum == r[:, None])
            idx = hit.argmax(1)
            pm_j = M[np.arange(len(rows)), idx]
            d_j = dk[idx]
            out[f"PM_{j}"][rows[ok]] = pm_j[ok]
            out[f"d{j}_km"][rows[ok]] = d_j[ok]
    return pd.DataFrame(out)
