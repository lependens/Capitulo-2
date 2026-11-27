"""Estudio 03.1.2: sensor local + red SIAR en una estacion no vista.

Uso (desde la raiz del repo):
    python studies/03_1_2_loso_sensor_red/run.py fit [--scenarios B,C] [--models HGB] [--workers N] [--folds ...]
    python studies/03_1_2_loso_sensor_red/run.py report

Una celda = particion x escenario x conjunto x familia x modelo. Se guarda entera en results/cells/ al acabar
(reanudable). El conjunto S de B NO se ajusta aqui: se reutilizan las celdas del 03.1. Criterios:
config/thresholds_v3_1_2.json (congelado). Los filtros solo seleccionan celdas; no cambian modelos ni criterios.
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
import design as ds  # noqa: E402
from design import lc, lm  # noqa: E402

RES = HERE / "results"
CELLS = Path(os.environ.get("LOSO_CELLS_DIR", RES / "cells"))   # LOSO_CELLS_DIR solo para pruebas


def cell_path(fold_id, scen, iset, fam, model):
    return CELLS / f"{fold_id}__{scen}__{iset}__{fam}__{model}.json.gz"


def env_info():
    import platform
    import pandas
    import sklearn
    return {"python": platform.python_version(), "numpy": np.__version__, "pandas": pandas.__version__,
            "scikit-learn": sklearn.__version__, "platform": platform.platform(),
            "cpu": platform.processor() or platform.machine()}


def _q(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return {k: float(v) for k, v in zip(("min", "p25", "p50", "p75", "max"), np.percentile(x, [0, 25, 50, 75, 100]))} \
        if len(x) else None


def prepare(fold, scen, iset, fam, max_train_rows=None):
    """Filas y matrices de una celda (sin ajustar nada). max_train_rows solo para pruebas rapidas."""
    fr = ds.scenario_frame(scen)
    tr = fr[fr.dev & fr.target_ok & fr.station_code.isin(fold["train"])]
    X0, net0 = ds.build_X(tr, scen, iset, fam, fold["train"])
    keep = np.isfinite(X0).all(1)
    n_drop_train = int((~keep).sum())
    tr, X0 = tr[keep].reset_index(drop=True), X0[keep]
    net0 = net0[keep].reset_index(drop=True) if net0 is not None else None
    if max_train_rows and len(tr) > max_train_rows:
        idx = np.sort(np.random.default_rng(0).choice(len(tr), max_train_rows, replace=False))
        tr, X0 = tr.iloc[idx].reset_index(drop=True), X0[idx]
        net0 = net0.iloc[idx].reset_index(drop=True) if net0 is not None else None
    groups = tr.station_code.to_numpy()
    if iset in ds.NET_SETS:
        X_inner = {s: ds.build_X(tr, scen, iset, fam, fold["train"], exclude=(s,))[0] for s in sorted(set(groups))}
    else:
        X_inner = {s: X0 for s in sorted(set(groups))}
    te = fr[fr.cohort & fr.station_code.isin(fold["test"])]
    Xt, nett = ds.build_X(te, scen, iset, fam, fold["train"])
    okt = np.isfinite(Xt).all(1)
    if iset not in ds.NET_SETS:
        assert okt.all(), "inputs de sensor no finitos en la cohorte TEST"
    te, Xt = te[okt].reset_index(drop=True), Xt[okt]
    nett = nett[okt].reset_index(drop=True) if nett is not None else None
    return {"train": tr, "X": X0, "X_inner": X_inner, "groups": groups, "y": tr.pm.to_numpy(), "net_train": net0,
            "test": te, "Xt": Xt, "net_test": nett, "n_drop_train": n_drop_train, "n_drop_test": int((~okt).sum())}


def fit_cell(fold, scen, iset, fam, model, deadline=None, max_train_rows=None):
    if deadline is not None and time.time() > deadline:
        return "OMITIDA (limite de horas)", 0.0
    t0 = time.time()
    P = prepare(fold, scen, iset, fam, max_train_rows)
    r = ds.select_and_fit_net(model, P["X"], P["X_inner"], P["groups"], P["y"], P["Xt"])
    pred, nneg = lm.clip_negative(r["pred"])
    te = P["test"]
    out = {"fold": fold["id"], "scenario": scen, "input_set": iset, "family": fam, "model": model,
           "n_features": int(P["X"].shape[1]), "n_train": int(len(P["y"])), "train_stations": fold["train"],
           "rows_dropped_train_empty_pool": P["n_drop_train"], "rows_dropped_test_empty_pool": P["n_drop_test"],
           "inner_rows_dropped": r["inner_rows_dropped"], "params": r["params"], "cv": r["cv"],
           "negatives_clipped": nneg, "convergence_warnings": r.get("warnings", 0),
           "station_code": te.station_code.tolist(), "date": te.date.tolist(), "pred": pred.tolist(),
           "seconds": round(time.time() - t0, 1), "env": env_info(), "test_run": bool(max_train_rows)}
    if P["net_test"] is not None:
        out["d1_km_test"] = np.round(P["net_test"].d1_km.to_numpy(), 3).tolist()
        out["d1_km_train_quantiles"] = _q(P["net_train"].d1_km)
        out["n_pool_test_quantiles"] = _q(P["net_test"].n_pool)
    if "seed_preds" in r:
        out["seed_preds"] = np.maximum(r["seed_preds"], 0).tolist()
    p = cell_path(fold["id"], scen, iset, fam, model)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(out, f, default=lambda o: list(o) if isinstance(o, tuple) else str(o))
    tmp.replace(p)
    return p.name, out["seconds"]


def _split(v):
    return [x for x in (v or "").split(",") if x]


def cmd_fit(scen, models, families, sets, fold_ids, workers, max_hours, list_only, max_train_rows):
    folds = lc.build_folds()
    if fold_ids:
        folds = [f for f in folds if f["id"] in fold_ids or f["scheme"] in fold_ids]
    cells = ds.all_cells(scen or None, models or None, families or None, sets or None)
    if "A" in (scen or ds.SCENARIOS) and not ds.COAST_CSV.exists():
        print("AVISO: falta config/stations_coast.csv; se omiten las celdas de A")
        cells = [c for c in cells if c[0] != "A"]
    allc = [(f, *c) for c in cells for f in folds]
    todo = [a for a in allc if not cell_path(a[0]["id"], *a[1:]).exists()]
    print(f"celdas seleccionadas: {len(allc)}; ya hechas: {len(allc) - len(todo)}; pendientes: {len(todo)}", flush=True)
    if list_only:
        return
    deadline = time.time() + max_hours * 3600 if max_hours else None
    if workers <= 1:
        for a in todo:
            print(*fit_cell(*a, deadline, max_train_rows), flush=True)
        return
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(fit_cell, *a, deadline, max_train_rows) for a in todo]
        for fu in as_completed(futs):
            print(*fu.result(), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["fit", "report"])
    ap.add_argument("--scenarios", default="", help="B,C,Bayer,A (vacio = todos)")
    ap.add_argument("--models", default="", help="Ridge,HGB,ANN_M (vacio = los de cada escenario)")
    ap.add_argument("--families", default="", help="HS_RA,VALIANTZAS,HG_RS (R no tiene familia y siempre entra)")
    ap.add_argument("--sets", default="", help="S,S_R1,S_R3,R,S_costa (vacio = todos)")
    ap.add_argument("--folds", default="", help="ids de particion o esquema (F1_loso, F2_island)")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--max-hours", type=float, default=0.0,
                    help="no empezar celdas nuevas pasadas estas horas (las ya empezadas terminan)")
    ap.add_argument("--list", action="store_true", help="solo cuenta celdas pendientes")
    ap.add_argument("--max-train-rows", type=int, default=0,
                    help="SOLO PRUEBAS: submuestra el entrenamiento (las celdas quedan marcadas test_run)")
    a = ap.parse_args()
    if a.stage == "fit":
        if a.max_train_rows and "LOSO_CELLS_DIR" not in os.environ:
            raise SystemExit("--max-train-rows solo con LOSO_CELLS_DIR apuntando fuera de results/")
        cmd_fit(_split(a.scenarios), _split(a.models), _split(a.families), _split(a.sets), _split(a.folds),
                a.workers, a.max_hours, a.list, a.max_train_rows)
    else:
        import report
        report.main()
