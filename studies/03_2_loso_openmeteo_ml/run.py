"""Estudio 03.2: Open-Meteo corregido con ML en estaciones no vistas (LOSO / fuera de isla).

Uso (desde la raiz del repo):
    python studies/03_2_loso_openmeteo_ml/run.py fit    [--models HGB,Ridge] [--scenarios S0,S2] [--folds F1_loso]
                                                      [--workers N] [--max-hours H] [--list]
    python studies/03_2_loso_openmeteo_ml/run.py report

`fit` ajusta un modelo por celda (particion x escenario x modelo) y guarda cada celda en results/cells/
(gzip, escritura atomica). Las celdas ya hechas se saltan, asi que se puede interrumpir y reanudar.
`report` une las celdas, calcula comparadores, metricas, IC pareados, veredictos, figuras y manifiesto.
Criterios: config/thresholds_v3.json (congelado al fusionar el PR #8). Los filtros solo eligen celdas.

loso_common.py y loso_models.py son copia literal de studies/03_1_loso_inputs_siar/ (commit 76d4aa8): mismas
particiones, baselines, metricas, bootstrap y seleccion de hiperparametros que el 03.1. Se cargan con nombres de
modulo propios para no chocar con los del 03.1 cuando ambos estudios conviven en el mismo proceso (tests).
"""
from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent


def _load(name):
    key = f"estudio03_2_{name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


lc = _load("loso_common")
lm = _load("loso_models")

RES = HERE / "results"
CELLS = Path(os.environ.get("LOSO_CELLS_DIR", RES / "cells"))  # LOSO_CELLS_DIR solo para pruebas
MODELS = ["Ridge", "HGB", "RF", "ANN_S", "ANN_M"]
HEAVY = ["RF", "ANN_S", "ANN_M"]
SCENARIOS = ["S0", "S1", "S2", "L1", "L2", "S0_coord"]

# Open-Meteo diario: et0, tmax, tmin, radiacion, viento medio y maximo, HR media/max/min (thresholds_v3 S0)
OM_COLS = ["et0_om_mm", "tmax_c", "tmin_c", "shortwave_sum_mj_m2", "wind10_mean_ms", "wind10_max_ms",
           "rh_mean_pct", "rh_max_pct", "rh_min_pct"]


def feature_names(scen):
    cal = ["doy_sin", "doy_cos", "Ra", "altitude_m"]
    if scen == "S0":
        return OM_COLS + cal
    if scen == "S1":
        return OM_COLS + cal + ["TempMax", "TempMin"]
    if scen == "S2":
        return OM_COLS + cal + ["TempMax", "TempMin", "HumedadMedia"]
    if scen == "L1":
        return ["TempMax", "TempMin"] + cal
    if scen == "L2":
        return ["TempMax", "TempMin", "HumedadMedia"] + cal
    if scen == "S0_coord":
        return OM_COLS + cal + ["lat", "lon"]
    raise KeyError(scen)


def features(scen, d):
    """Matriz de entrada del escenario. sin/cos del dia del anio con periodo 365,25 (lc.calendar_inputs)."""
    cal = lc.calendar_inputs(d)  # sin, cos, altitud
    cols = {"doy_sin": cal[:, 0], "doy_cos": cal[:, 1], "altitude_m": cal[:, 2]}
    return np.column_stack([cols[c] if c in cols else d[c].to_numpy(dtype=float) for c in feature_names(scen)])


def cell_path(fold_id, scen, model):
    return CELLS / f"{fold_id}__{scen}__{model}.json.gz"


def env_info():
    import platform
    import pandas
    import sklearn
    return {"python": platform.python_version(), "numpy": np.__version__, "pandas": pandas.__version__,
            "scikit-learn": sklearn.__version__, "platform": platform.platform(),
            "cpu": platform.processor() or platform.machine(), "cpus": os.cpu_count()}


def train_test(fold, scen, df=None):
    """Filas de entrenamiento (DEV, objetivo valido, estaciones train, inputs finitos) y de TEST (cohorte comun)."""
    df = lc.load_panel() if df is None else df
    dev = df[(df.period == "DEV") & df.target_ok & df.station_code.isin(fold["train"])]
    X = features(scen, dev)
    ok = np.isfinite(X).all(1)
    dev, X = dev[ok], X[ok]
    test = lc.test_cohort(df)
    test = test[test.station_code.isin(fold["test"])]
    Xt = features(scen, test)
    assert np.isfinite(Xt).all(), f"inputs no finitos en la cohorte TEST ({scen})"
    assert not (set(dev.station_code) & set(fold["test"])), "estacion de prueba en el entrenamiento"
    assert dev.date.max() <= lc.DEV[1] and test.date.min() >= lc.TEST[0]
    return dev, X, test, Xt


def fit_cell(fold, scen, model, deadline=None):
    if deadline is not None and time.time() > deadline:
        return "OMITIDA (limite de horas)", 0.0
    t0 = time.time()
    dev, X, test, Xt = train_test(fold, scen)
    r = lm.select_and_fit(model, X, dev["ET0_PM_FAO56_V1"].to_numpy(), dev.station_code.to_numpy(),
                          dev.date.to_numpy(), Xt)
    pred, nneg = lm.clip_negative(r["pred"])
    out = {"study": "03.2", "fold": fold["id"], "scenario": scen, "model": model, "features": feature_names(scen),
           "n_train": int(len(dev)), "train_stations": fold["train"], "params": r["params"], "cv": r["cv"],
           "negatives_clipped": nneg, "convergence_warnings": r.get("warnings", 0),
           "station_code": test.station_code.tolist(), "date": test.date.tolist(), "pred": pred.tolist(),
           "seconds": round(time.time() - t0, 1), "env": env_info()}
    if "seed_preds" in r:
        out["seed_preds"] = np.maximum(r["seed_preds"], 0).tolist()
    p = cell_path(fold["id"], scen, model)
    tmp = p.with_name(p.name + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(out, f, default=lambda o: list(o) if isinstance(o, tuple) else str(o))
    tmp.replace(p)
    return p.name, out["seconds"]


def _split(v):
    return [x for x in (v or "").split(",") if x]


def select_cells(models, scenarios=None, fold_ids=None):
    folds = lc.build_folds()
    if fold_ids:
        folds = [f for f in folds if f["id"] in fold_ids or f["scheme"] in fold_ids]
    return [(f, s, m) for m in models for f in folds for s in (scenarios or SCENARIOS)]


def cmd_fit(models, workers, scenarios, fold_ids, max_hours, list_only):
    CELLS.mkdir(parents=True, exist_ok=True)
    lc.write_folds(RES / "folds.json", lc.build_folds())
    allc = select_cells(models, scenarios, fold_ids)
    todo = [a for a in allc if not cell_path(a[0]["id"], a[1], a[2]).exists()]
    print(f"celdas seleccionadas: {len(allc)}; ya hechas: {len(allc) - len(todo)}; pendientes: {len(todo)}", flush=True)
    if list_only:
        return
    deadline = time.time() + max_hours * 3600 if max_hours else None
    if workers <= 1:
        for args in todo:
            print(*fit_cell(*args, deadline), flush=True)
        return
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(fit_cell, *a, deadline) for a in todo]
        for fu in as_completed(futs):
            print(*fu.result(), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["fit", "report"])
    ap.add_argument("--models", default=",".join(MODELS))
    ap.add_argument("--scenarios", default="", help="S0,S1,S2,L1,L2,S0_coord (vacio = todos)")
    ap.add_argument("--folds", default="", help="ids de particion o esquema (F1_loso, F2_island); vacio = todas")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--max-hours", type=float, default=0.0,
                    help="no empezar celdas nuevas pasadas estas horas (las ya empezadas terminan)")
    ap.add_argument("--list", action="store_true", help="solo cuenta celdas pendientes")
    a = ap.parse_args()
    if a.stage == "fit":
        cmd_fit(_split(a.models), a.workers, _split(a.scenarios), _split(a.folds), a.max_hours, a.list)
    else:
        _load("report").main()
