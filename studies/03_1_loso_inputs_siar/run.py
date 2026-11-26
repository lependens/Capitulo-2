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
CELLS = RES / "cells"
MODELS = ["Ridge", "HGB", "RF", "ANN_S", "ANN_M", "ANN_V2like"]
VARIANTS = ["principal", "secundaria"]


def features(fam, variant, d):
    X = lc.base_inputs(fam, d)
    return X if variant == "principal" else np.column_stack([X, lc.calendar_inputs(d)])


def cell_path(fold_id, fam, variant, model):
    return CELLS / f"{fold_id}__{fam}__{variant}__{model}.json.gz"


def fit_cell(fold, fam, variant, model):
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
           "date": test.date.tolist(), "pred": pred.tolist(), "seconds": round(time.time() - t0, 1)}
    if "seed_preds" in r:
        out["seed_preds"] = np.maximum(r["seed_preds"], 0).tolist()
    p = cell_path(fold["id"], fam, variant, model)
    tmp = p.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(out, f, default=lambda o: list(o) if isinstance(o, tuple) else str(o))
    tmp.replace(p)
    return p.name, out["seconds"]


def cmd_fit(models, workers):
    CELLS.mkdir(parents=True, exist_ok=True)
    folds = lc.build_folds()
    lc.write_folds(RES / "folds.json", folds)
    todo = [(f, fam, v, m) for m in models for f in folds for fam in lc.FAMILIES for v in VARIANTS
            if not cell_path(f["id"], fam, v, m).exists()]
    print(f"celdas pendientes: {len(todo)}", flush=True)
    if workers <= 1:
        for args in todo:
            print(*fit_cell(*args), flush=True)
        return
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(fit_cell, *a) for a in todo]
        for fu in as_completed(futs):
            print(*fu.result(), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["fit", "report"])
    ap.add_argument("--models", default=",".join(MODELS))
    ap.add_argument("--workers", type=int, default=1)
    a = ap.parse_args()
    if a.stage == "fit":
        cmd_fit([m for m in a.models.split(",") if m], a.workers)
    else:
        import report
        report.main()
