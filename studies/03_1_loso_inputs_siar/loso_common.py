"""Piezas comunes de los estudios 03.1 y 03.2 (LOSO / leave-one-island-out).

Contiene: carga de datos, Ra y formulas de V2 (HS-Ra, HG-Rs, Valiantzas), particiones (folds.json), AHC transferido
y de vecino, comparadores PM de la estacion mas cercana e IDW, metricas con las definiciones de V2 y el bootstrap de
bloques estacion-anio. El 03.2 importa este modulo para reutilizar exactamente las mismas piezas.

Definiciones (identicas a V2 / src/openmeteo_et0/metrics.py): error = prediccion - PM; RMSE, MAE, sesgo, R2 = 1 - SSE/SST.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
STATIONS = ["IB01", "IB02", "IB03", "IB04", "IB05", "IB06", "IB08", "IB10", "IB11"]
DEV = ("2004-01-01", "2019-12-31")
TEST = ("2020-01-01", "2025-12-31")
BOOT_REPS, BOOT_SEED = 2000, 20261126
FAMILIES = ["HS_RA", "VALIANTZAS", "HG_RS"]
V2_FAMILY = {"HS_RA": "HS_RA_V1", "VALIANTZAS": "VALIANTZAS_V1", "HG_RS": "HG_RS_V1"}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- Ra y formulas (copia literal de Capitulo-1 V2)
def ra_fao56(lat_deg, doy):
    """Ra [MJ m-2 dia-1], FAO-56 ec. 21-25; denominador 365 tambien en bisiestos (como Capitulo-1 solar.py)."""
    phi = np.radians(lat_deg)
    dr = 1 + 0.033 * np.cos(2 * np.pi * doy / 365)
    delta = 0.409 * np.sin(2 * np.pi * doy / 365 - 1.39)
    ws = np.arccos(np.clip(-np.tan(phi) * np.tan(delta), -1, 1))
    ra = 24 * 60 / np.pi * 0.0820 * dr * (ws * np.sin(phi) * np.sin(delta) + np.cos(phi) * np.cos(delta) * np.sin(ws))
    return np.maximum(0.0, ra)


def formula(fam, d):
    tmin, tmax = d["TempMin"], d["TempMax"]
    tmean = (tmin + tmax) / 2
    if fam == "HS_RA":
        return 0.0023 * 0.408 * d["Ra"] * (tmean + 17.8) * np.sqrt(tmax - tmin)
    if fam == "HG_RS":
        return 0.0135 * 0.408 * d["Radiacion"] * (tmean + 17.8)
    if fam == "VALIANTZAS":
        rs = 0.338 * d["Ra"] * (tmax - tmin) ** 0.3 * (1.001 - d["HumedadMedia"] / 100) ** 0.2
        return 0.408 * 0.0135 * rs * (tmean + 17.8)
    raise KeyError(fam)


def base_inputs(fam, d):
    """Vector de entrada anual de V2 (Capitulo-1 et0_v2.py::_inputs), mismo orden."""
    if fam == "HS_RA":
        return np.column_stack([d["TempMin"], d["TempMax"], d["Ra"]])
    if fam == "VALIANTZAS":
        return np.column_stack([d["TempMin"], d["TempMax"], d["HumedadMedia"], d["Ra"]])
    if fam == "HG_RS":
        return np.column_stack([(d["TempMin"] + d["TempMax"]) / 2, d["Radiacion"]])
    raise KeyError(fam)


def calendar_inputs(d):
    """sin/cos del dia del anio (periodo 365,25) + altitud: variante secundaria del 03.1 y parte de S0 del 03.2."""
    ang = 2 * np.pi * d["doy"] / 365.25
    return np.column_stack([np.sin(ang), np.cos(ang), d["altitude_m"]])


# ---------------------------------------------------------------- datos
def load_stations():
    st = pd.read_csv(ROOT / "config/stations.csv")
    return st.set_index("station_code").loc[STATIONS]


def load_panel():
    """Panel diario 2004-2025 de las 9 estaciones: PM, inputs SIAR, Open-Meteo, Ra, calendario y cohorte V2."""
    ref = pd.concat([pd.read_csv(ROOT / f"data/reference/reference_{p}.csv") for p in ("2004_2019", "2020_2025")])
    inp = pd.concat([pd.read_csv(ROOT / f"data/reference/siar_inputs_{p}.csv") for p in ("2004_2019", "2020_2025")])
    inp = inp.drop(columns=["quality_status"])
    om = pd.read_csv(ROOT / "data/processed/openmeteo_archive.csv").drop(columns=["product", "fetched_at_utc"])
    df = ref.merge(inp, on=["station_code", "date"], how="left", validate="one_to_one")
    df = df[df.station_code.isin(STATIONS)]
    df = df.merge(om, on=["station_code", "date"], how="left", validate="one_to_one")
    st = load_stations()
    df["lat"] = df.station_code.map(st.latitude_deg)
    df["lon"] = df.station_code.map(st.longitude_deg_derived)
    df["altitude_m"] = df.station_code.map(st.altitude_m).astype(float)
    dt = pd.to_datetime(df.date)
    df["doy"] = dt.dt.dayofyear
    df["month"] = dt.dt.month
    df["year"] = dt.dt.year
    df["Ra"] = ra_fao56(df.lat.to_numpy(), df.doy.to_numpy())
    pm = df["ET0_PM_FAO56_V1"]
    # objetivo exactamente como V2 (Capitulo-1 et0_v2.py: target = PM si finita y >= 0; no usa evaluated_PM).
    # Con esta regla los coeficientes AHC locales reproducen los congelados de V2 (p. ej. IB01 HS-Ra 0,893456, n=5512).
    df["target_ok"] = pm.notna() & np.isfinite(pm) & (pm >= 0)
    df["period"] = np.where(df.date <= DEV[1], "DEV", "TEST")
    v2 = pd.read_csv(ROOT / "data/v2/et0_v2_annual_2020_2025.csv")[["station_id", "date", "common_core"]]
    df = df.merge(v2.rename(columns={"station_id": "station_code"}), on=["station_code", "date"], how="left")
    df["common_core"] = df["common_core"].fillna(0).astype(int)
    return df.sort_values(["date", "station_code"]).reset_index(drop=True)


def test_cohort(df):
    t = df[(df.period == "TEST") & (df.common_core == 1)].copy()
    assert len(t) == 19251, len(t)
    return t


# ---------------------------------------------------------------- particiones
def build_folds():
    """Particiones identicas a config/thresholds_v3.json (las mismas en 03.1 y 03.2)."""
    cfg = json.loads((ROOT / "config/thresholds_v3.json").read_text(encoding="utf-8"))["protocol"]["folds"]
    folds = []
    for s in cfg["F1_loso"]:
        folds.append({"id": f"F1_{s}", "scheme": "F1_loso", "test": [s], "criterio": True})
    for name, sts in cfg["F2_island"].items():
        folds.append({"id": f"F2_{name}", "scheme": "F2_island", "test": list(sts),
                      "criterio": not name.endswith("informativo")})
    for f in folds:
        f["train"] = [s for s in STATIONS if s not in f["test"]]
        f["train_period"], f["test_period"] = list(DEV), list(TEST)
    return folds


def write_folds(path, folds):
    payload = {"_comment": "Particiones de los estudios 03.1 y 03.2 (identicas). Entrenamiento: solo DESARROLLO y solo "
                           "estaciones 'train'; evaluacion: TEST en las estaciones 'test', cohorte common_core==1.",
               "source": "config/thresholds_v3.json -> protocol.folds", "folds": folds}
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- geografia
def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi, dl = p2 - p1, np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


def distances():
    st = load_stations()
    return {(a, b): float(haversine_km(st.latitude_deg[a], st.longitude_deg_derived[a],
                                       st.latitude_deg[b], st.longitude_deg_derived[b]))
            for a in STATIONS for b in STATIONS}


def neighbours(target, train, dist):
    return sorted(train, key=lambda s: (dist[(target, s)], s))


# ---------------------------------------------------------------- AHC (OLS por el origen, como V2 y estudio 02)
def ahc_coefficients(x, y, groups):
    """c_g = sum(x*y)/sum(x^2) por grupo."""
    out = {}
    for g in np.unique(groups):
        m = groups == g
        out[g] = float(np.sum(x[m] * y[m]) / np.sum(x[m] ** 2))
    return out


def ahc_by_station(dev, xcol, granularity):
    """{estacion: {grupo: coef}} con DESARROLLO; granularity 'annual' o 'monthly'."""
    res = {}
    for s, g in dev.groupby("station_code"):
        grp = np.zeros(len(g), int) if granularity == "annual" else g["month"].to_numpy()
        res[s] = ahc_coefficients(g[xcol].to_numpy(), g["ET0_PM_FAO56_V1"].to_numpy(), grp)
    return res


def apply_ahc(test, xcol, coefs, granularity):
    grp = np.zeros(len(test), int) if granularity == "annual" else test["month"].to_numpy()
    return test[xcol].to_numpy() * np.array([coefs[g] for g in grp])


def mean_coefs(per_station, train):
    groups = per_station[train[0]].keys()
    return {g: float(np.mean([per_station[s][g] for s in train])) for g in groups}


# ---------------------------------------------------------------- comparadores PM del mismo dia
def pm_nearest_and_idw(df, test_rows, train, dist, power=2.0):
    """PM de la estacion de entrenamiento mas cercana con PM valida ese dia (si falta, la siguiente) e IDW (p=2)
    sobre las estaciones de entrenamiento con PM valida ese dia. Devuelve (nearest, idw, n_fallback)."""
    pm = df[df.target_ok & df.station_code.isin(train)].pivot(index="date", columns="station_code",
                                                               values="ET0_PM_FAO56_V1")
    near, idw, fb = np.full(len(test_rows), np.nan), np.full(len(test_rows), np.nan), 0
    for i, (s, d) in enumerate(zip(test_rows.station_code, test_rows.date)):
        row = pm.loc[d] if d in pm.index else None
        if row is None:
            continue
        order = neighbours(s, train, dist)
        avail = [t for t in order if t in row.index and not np.isnan(row[t])]
        if not avail:
            continue
        near[i] = row[avail[0]]
        fb += avail[0] != order[0]
        w = np.array([1 / dist[(s, t)] ** power for t in avail])
        idw[i] = float(np.sum(w * row[avail].to_numpy()) / w.sum())
    return near, idw, fb


# ---------------------------------------------------------------- metricas y bootstrap
def metrics(pred, ref):
    pred, ref = np.asarray(pred, float), np.asarray(ref, float)
    e = pred - ref
    sse = float(np.sum(e ** 2))
    sst = float(np.sum((ref - ref.mean()) ** 2))
    return {"n": int(len(e)), "mae": float(np.mean(np.abs(e))), "rmse": math.sqrt(sse / len(e)),
            "bias": float(np.mean(e)), "r2": 1 - sse / sst if sst > 0 else float("nan")}


def season_label(dates):
    m = dates.str[5:7].astype(int)
    y = dates.str[:4].astype(int) + (m == 12)
    s = m.map({12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM", 6: "JJA", 7: "JJA", 8: "JJA",
               9: "SON", 10: "SON", 11: "SON"})
    return y.astype(str) + "-" + s


def block_index(stations, dates):
    """Indice de bloque estacion-anio (natural) para el bootstrap; 54 bloques en la cohorte TEST."""
    keys = pd.Series(stations).astype(str).to_numpy() + "|" + pd.Series(dates).str[:4].to_numpy()
    uniq, inv = np.unique(keys, return_inverse=True)
    return inv, uniq


def boot_draws(n_blocks, reps=BOOT_REPS, seed=BOOT_SEED):
    """Mismos remuestreos (numeros aleatorios comunes) para todas las comparaciones: generador nuevo con semilla fija."""
    return np.random.default_rng(seed).integers(0, n_blocks, size=(reps, n_blocks))


def paired_delta_ci(pred_a, pred_b, ref, blocks, draws):
    """RMSE(a) - RMSE(b) en la misma cohorte, IC 95 % percentil por bootstrap de bloques estacion-anio."""
    ea, eb = (np.asarray(pred_a) - ref) ** 2, (np.asarray(pred_b) - ref) ** 2
    nb = blocks.max() + 1
    n = np.bincount(blocks, minlength=nb).astype(float)
    sa, sb = np.bincount(blocks, ea, nb), np.bincount(blocks, eb, nb)
    d0 = math.sqrt(sa.sum() / n.sum()) - math.sqrt(sb.sum() / n.sum())
    # cada fila de draws es un remuestreo de bloques con reemplazo
    N, A, B = n[draws].sum(1), sa[draws].sum(1), sb[draws].sum(1)
    d = np.sqrt(A / N) - np.sqrt(B / N)
    lo, hi = np.percentile(d, [2.5, 97.5])
    return float(d0), float(lo), float(hi)
