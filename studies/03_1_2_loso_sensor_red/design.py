"""Filas, inputs y seleccion de modelos del estudio 03.1.2 (escenarios B, C, B-ayer y A).

Todo lo que no es nuevo se importa del 03.1 (loso_common, loso_models), sin copiarlo:
- datos, Ra, vector de la familia (base_inputs), particiones, distancias, cohorte, metricas y bootstrap: loso_common;
- rejillas, estimadores (Ridge, HGB, ANN M con sus 5 semillas), desempate y recorte de negativos: loso_models.

Lo unico nuevo es la validacion interna con la red recalculada por pliegue: loso_models.select_and_fit recibe una X
fija y no puede quitar la estacion de validacion del pool de las demas filas, como exigen los criterios. Por eso
`select_and_fit_net` repite literalmente su logica (misma rejilla, mismos pliegues por estacion, misma metrica, mismo
desempate TIE, mismo ajuste final) pero con una X distinta en cada pliegue interno.
"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
S031 = HERE.parent / "03_1_loso_inputs_siar"
sys.path.insert(0, str(S031))
sys.path.insert(0, str(HERE))
import loso_common as lc  # noqa: E402
import loso_models as lm  # noqa: E402
import network as nw  # noqa: E402

SCENARIOS = ["B", "C", "Bayer", "A"]
SETS = {"B": ["S_R1", "S_R3", "R"], "C": ["S", "S_R1", "S_R3", "R"], "Bayer": ["S_R1", "R"], "A": ["S_costa"]}
MODELS = {"B": ["Ridge", "HGB", "ANN_M"], "C": ["Ridge", "HGB", "ANN_M"], "Bayer": ["Ridge", "HGB"],
          "A": ["Ridge", "HGB"]}
NOFAM = "NONE"   # el conjunto R no depende de la familia
NET_SETS = {"S_R1", "S_R3", "R"}
SENSOR = ["TempMin", "TempMax", "HumedadMedia", "Radiacion", "Ra"]
COAST_CSV = lc.ROOT / "config/stations_coast.csv"


def families_for(iset):
    return [NOFAM] if iset == "R" else lc.FAMILIES


def all_cells(scenarios=None, models=None, families=None, sets=None):
    out = []
    for sc in scenarios or SCENARIOS:
        for iset in SETS[sc]:
            if sets and iset not in sets:
                continue
            for fam in families_for(iset):
                if families and fam != NOFAM and fam not in families:
                    continue
                for m in MODELS[sc]:
                    if models and m not in models:
                        continue
                    out.append((sc, iset, fam, m))
    return out


# ---------------------------------------------------------------- datos en cache (una vez por proceso)
@lru_cache(maxsize=1)
def panel():
    return lc.load_panel()


@lru_cache(maxsize=1)
def pmw():
    return nw.pm_wide(panel())


@lru_cache(maxsize=1)
def dist():
    return lc.distances()


def _shift(dates, days):
    return (pd.to_datetime(pd.Series(dates)) + pd.Timedelta(days=days)).dt.strftime("%Y-%m-%d").to_numpy()


@lru_cache(maxsize=4)
def scenario_frame(scen):
    """Una fila por (estacion, fecha objetivo). Columnas: station_code, date (objetivo), pm, target_ok, month, sensor
    (SENSOR, del dia de los inputs de sensor), Ra_next (solo C), net_date, dev_ok (entrenable), cohort (TEST)."""
    df = panel()
    cohort = (df.period == "TEST") & (df.common_core == 1)
    base = pd.DataFrame({"station_code": df.station_code, "date": df.date, "pm": df.ET0_PM_FAO56_V1,
                         "target_ok": df.target_ok, "month": df.month, "dev": df.period == "DEV",
                         "cohort": cohort} | {c: df[c] for c in SENSOR})
    if scen in ("B", "A"):
        f = base.copy()
        f["net_date"] = f.date
    elif scen == "Bayer":
        f = base.copy()
        f["net_date"] = _shift(f.date, -1)
    elif scen == "C":
        prev = base[["station_code", "date", "dev", "cohort"] + SENSOR].copy()
        prev["date"] = _shift(prev.date, +1)            # fila del dia d, re-etiquetada con su objetivo d+1
        prev = prev.rename(columns={"dev": "dev_prev", "cohort": "cohort_prev"} |
                                   {c: c + "_d" for c in SENSOR})
        f = base.merge(prev, on=["station_code", "date"], how="inner", validate="one_to_one")
        f["Ra_next"] = f["Ra"]                           # Ra(d+1), astronomica
        for c in SENSOR:
            f[c] = f[c + "_d"]                           # inputs de sensor del dia d (incluida Ra(d))
        f["dev"] = f.dev & f.dev_prev                    # par (d, d+1) entero en DESARROLLO
        f["cohort"] = f.cohort & f.cohort_prev           # d y d+1 en la cohorte comun (criterios)
        f["net_date"] = _shift(f.date, -1)               # red del dia d
        f = f.drop(columns=[c + "_d" for c in SENSOR] + ["dev_prev", "cohort_prev"])
    else:
        raise KeyError(scen)
    return f.sort_values(["date", "station_code"]).reset_index(drop=True)


@lru_cache(maxsize=1)
def coast_km():
    if not COAST_CSV.exists():
        raise FileNotFoundError("falta config/stations_coast.csv (ejecutar coast.py)")
    c = pd.read_csv(COAST_CSV, comment="#")
    return dict(zip(c.station_code, c.coast_km))


# ---------------------------------------------------------------- inputs
def features(rows, scen, iset, fam, net=None):
    """Matriz de inputs. Orden de columnas: vector de la familia (03.1), luego red, costa y, en C, Ra(d+1)."""
    parts = []
    if iset != "R":
        parts.append(lc.base_inputs(fam, rows))
    if iset == "S_R1":
        parts.append(net[nw.R1_COLS].to_numpy())
    elif iset == "S_R3":
        parts.append(net[nw.R3_COLS].to_numpy())
    elif iset == "R":
        parts.append(np.column_stack([net[nw.R3_COLS].to_numpy(), rows["Ra"].to_numpy(), net["IDW_PM"].to_numpy()]))
    elif iset == "S_costa":
        ck = coast_km()
        parts.append(np.log1p(rows.station_code.map(ck).to_numpy(dtype=float))[:, None])
    if scen == "C":
        parts.append(rows["Ra_next"].to_numpy()[:, None])
    return np.column_stack(parts).astype(float)


def build_X(rows, scen, iset, fam, pool, exclude=()):
    """X y columnas de red de las filas, con el pool de la particion menos la propia estacion y `exclude`."""
    net = None
    if iset in NET_SETS:
        net = nw.network_features(rows.station_code.to_numpy(), rows.net_date.to_numpy(), pool, pmw(), dist(),
                                  exclude=exclude)
    return features(rows, scen, iset, fam, net), net


# ---------------------------------------------------------------- seleccion con la red recalculada por pliegue
def _predict(model, params, X, y, Xp):
    if model in ("ANN_S", "ANN_M"):
        sp, warn = lm._fit_predict_mlp(model, params, X, y, Xp)
        return sp, warn
    return lm._fit_predict_simple(model, params, X, y, Xp), 0


def select_and_fit_net(model, X_full, X_inner, groups, y, Xtest):
    """Misma logica que loso_models.select_and_fit (Ridge, HGB, ANN_S/M), con X_inner[s] = inputs de TODAS las filas
    de entrenamiento con la estacion s fuera del pool. Filas con NaN en un pliegue (pool vacio) no entran en ese pliegue.
    """
    stations = sorted(np.unique(groups))
    cv, dropped = [], {}
    for p in lm.GRIDS[model]:
        fold_rmse = []
        for s in stations:
            X = X_inner[s]
            fin = np.isfinite(X).all(1)
            dropped[s] = int((~fin).sum())
            tr, va = (groups != s) & fin, (groups == s) & fin
            pr, _ = _predict(model, p, X[tr], y[tr], X[va])
            if model in ("ANN_S", "ANN_M"):
                pr = pr.mean(0)
            fold_rmse.append(float(np.sqrt(np.mean((pr - y[va]) ** 2))))
        cv.append({"params": p, "mean_rmse": float(np.mean(fold_rmse)), "sd_rmse": float(np.std(fold_rmse)),
                   "fold_rmse": dict(zip(stations, fold_rmse)), "epochs_by_fold": []})
    best = min(c["mean_rmse"] for c in cv)
    chosen = [c for c in cv if c["mean_rmse"] - best <= lm.TIE][0]
    res = {"params": chosen["params"], "cv": cv, "inner_rows_dropped": dropped, "warnings": 0}
    pr, res["warnings"] = _predict(model, chosen["params"], X_full, y, Xtest)
    if model in ("ANN_S", "ANN_M"):
        res["seed_preds"], res["pred"] = pr, pr.mean(0)
    else:
        res["pred"] = pr
    return res
