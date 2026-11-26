"""Estudio 03.1: modelos de pocos inputs SIAR en estaciones no vistas (LOSO / fuera de isla).

Uso (desde la raiz del repo):
    python studies/03_1_loso_inputs_siar/run.py fit    [--models HGB,Ridge,...] [--workers N]
    python studies/03_1_loso_inputs_siar/run.py report

`fit` ajusta los modelos conjuntos por celda (particion x familia x variante x modelo) y guarda un punto de control
por celda en results/cells/ (se puede interrumpir y reanudar). `report` calcula formulas, AHC, comparadores, metricas,
IC pareados, figuras y el manifiesto. Criterios: config/thresholds_v3_1.json (congelado).
"""
from __future__ import annotations

import argparse
import gzip
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
sys.path.insert(0, str(HERE))
import loso_common as lc  # noqa: E402
import loso_models as lm  # noqa: E402

RES = HERE / "results"
CELLS = Path(os.environ.get("LOSO_CELLS_DIR", RES / "cells"))  # LOSO_CELLS_DIR solo para pruebas
MODELS = ["Ridge", "HGB", "RF", "ANN_S", "ANN_M", "ANN_V2like"]
VARIANTS = ["principal", "secundaria"]


def features(fam, variant, d):
    X = lc.base_inputs(fam, d)
    return X if variant == "principal" else np.column_stack([X, lc.calendar_inputs(d)])


def cell_path(fold_id, fam, variant, model):
    return CELLS / f"{fold_id}__{fam}__{variant}__{model}.json.gz"


def env_info():
    import platform
    import pandas
    import sklearn
    return {"python": platform.python_version(), "numpy": np.__version__, "pandas": pandas.__version__,
            "scikit-learn": sklearn.__version__, "platform": platform.platform(),
            "cpu": platform.processor() or platform.machine()}


def fit_cell(fold, fam, variant, model, deadline=None):
    if deadline is not None and time.time() > deadline:
        return "OMITIDA (limite de horas)", 0.0
    t0 = time.time()
    df = lc.load_panel()
    dev = df[(df.period == "DEV") & df.target_ok & df.station_code.isin(fold["train"])]
    X = features(fam, variant, dev)
    ok = np.isfinite(X).all(1)
    dev, X = dev[ok], X[ok]
    test = lc.test_cohort(df)
    test = test[test.station_code.isin(fold["test"])]
    Xt = features(fam, variant, test)
    assert np.isfinite(Xt).all(), "inputs no finitos en la cohorte TEST"
    r = lm.select_and_fit(model, X, dev["ET0_PM_FAO56_V1"].to_numpy(), dev.station_code.to_numpy(),
                          dev.date.to_numpy(), Xt)
    pred, nneg = lm.clip_negative(r["pred"])
    out = {"fold": fold["id"], "family": fam, "variant": variant, "model": model,
           "n_train": int(len(dev)), "train_stations": fold["train"], "params": r["params"], "cv": r["cv"],
           "negatives_clipped": nneg, "convergence_warnings": r.get("warnings", 0),
           "final_epochs": r.get("final_epochs"), "station_code": test.station_code.tolist(),
           "date": test.date.tolist(), "pred": pred.tolist(), "seconds": round(time.time() - t0, 1),
           "env": env_info()}
    if "seed_preds" in r:
        out["seed_preds"] = np.maximum(r["seed_preds"], 0).tolist()
    p = cell_path(fold["id"], fam, variant, model)
    tmp = p.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(out, f, default=lambda o: list(o) if isinstance(o, tuple) else str(o))
    tmp.replace(p)
    return p.name, out["seconds"]


def _split(v):
    return [x for x in (v or "").split(",") if x]


def cmd_fit(models, workers, families, fold_ids, variants, max_hours, list_only):
    CELLS.mkdir(parents=True, exist_ok=True)
    folds = lc.build_folds()
    lc.write_folds(RES / "folds.json", folds)
    if fold_ids:
        folds = [f for f in folds if f["id"] in fold_ids or f["scheme"] in fold_ids]
    fams = families or lc.FAMILIES
    vars_ = variants or VARIANTS
    allc = [(f, fam, v, m) for m in models for f in folds for fam in fams for v in vars_]
    todo = [a for a in allc if not cell_path(a[0]["id"], a[1], a[2], a[3]).exists()]
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
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--families", default="", help="HS_RA,VALIANTZAS,HG_RS (vacio = todas)")
    ap.add_argument("--folds", default="", help="ids de particion o esquema (F1_loso, F2_island); vacio = todas")
    ap.add_argument("--variants", default="", help="principal,secundaria (vacio = ambas)")
    ap.add_argument("--max-hours", type=float, default=0.0,
                    help="no empezar celdas nuevas pasadas estas horas (las ya empezadas terminan)")
    ap.add_argument("--list", action="store_true", help="solo cuenta celdas pendientes")
    a = ap.parse_args()
    if a.stage == "fit":
        cmd_fit(_split(a.models), a.workers, _split(a.families), _split(a.folds), _split(a.variants),
                a.max_hours, a.list)
    else:
        import report
        report.main()
