"""Estudio 03.3: Open-Meteo + ML + red SIAR del dia (L3) y objetivo residual con control de dominio (L5).

Uso (desde la raiz del repo):
    python studies/03_3_om_red_residual/run.py fit [--arms S0+R1,S0_res] [--models HGB,Ridge] [--folds F1_loso]
                                                   [--workers N] [--max-hours H] [--list]
    python studies/03_3_om_red_residual/run.py report

Una celda = particion x brazo x modelo (results/cells/, gzip, escritura atomica, reanudable). Ademas, por particion,
una celda por estacion de entrenamiento s con el HGB-S0 anidado (entrenado SIN s ni las evaluadas, con su propia
seleccion de hiperparametros) que da los residuos de `residuo_IDW` y las predicciones fuera de muestra con las que
se elige w en `media_ponderada`. HGB-S0, HGB-S2 y ANN_M-S0 NO se ajustan aqui: se toman del 03.2.

Criterios: config/thresholds_v3_3.json (congelado). Los filtros solo eligen celdas; no cambian nada del protocolo.

Codigo importado sin copiar ni modificar: loso_common, loso_models y run.py (feature_names/features de S0 y S2) del
03.2, y network.py del 03.1.2. Lo unico nuevo de modelado es `select_and_fit_net`: repite literalmente la logica de
loso_models.select_and_fit (rejilla, pliegues por estacion, metrica, desempate TIE, ajuste final) pero con la red
recalculada en cada pliegue interno, sacando la estacion de validacion del pool de TODAS las filas.
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
from functools import lru_cache
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
S032 = HERE.parent / "03_2_loso_openmeteo_ml"
S0312 = HERE.parent / "03_1_2_loso_sensor_red"


def _load(key, path):
    """Carga un modulo con nombre propio (el mismo que usa el 03.2 para los suyos: se comparten si ya estan)."""
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


lc = _load("estudio03_2_loso_common", S032 / "loso_common.py")
lm = _load("estudio03_2_loso_models", S032 / "loso_models.py")
r32 = _load("estudio03_2_run", S032 / "run.py")
nw = _load("estudio03_1_2_network", S0312 / "network.py")

RES = Path(os.environ.get("LOSO_RES_DIR", HERE / "results"))      # LOSO_RES_DIR solo para pruebas
CELLS = Path(os.environ.get("LOSO_CELLS_DIR", RES / "cells"))   # LOSO_CELLS_DIR solo para pruebas
THR = json.loads((lc.ROOT / "config/thresholds_v3_3.json").read_text(encoding="utf-8"))

# brazo -> modelos (thresholds_v3_3.json -> methods). HGB: todos los brazos con modelo; Ridge: S0+R1 y S0_res;
# ANN_M: S0_res, S0_sin_alt, S0_res_sin_alt.
ARMS = {
    "S0+R1": ["Ridge", "HGB"],
    "S2+R1": ["HGB"],
    "S0+R1_ayer": ["HGB"],
    "S0_res": ["Ridge", "HGB", "ANN_M"],
    "S0_sin_alt": ["HGB", "ANN_M"],
    "S0_alt_recortada": ["HGB"],
    "S0_res_sin_alt": ["HGB", "ANN_M"],
}
NESTED = "anidado"          # celdas F?__anidado_<s>__HGB
NET_ARMS = {"S0+R1", "S2+R1", "S0+R1_ayer"}
RES_ARMS = {"S0_res", "S0_res_sin_alt"}
W_GRID = [round(0.1 * i, 1) for i in range(11)]          # media_ponderada: w en {0, 0.1, ..., 1}
ALT = "altitude_m"


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


def shift_dates(dates, days):
    return (pd.to_datetime(pd.Series(np.asarray(dates))) + pd.Timedelta(days=days)).dt.strftime("%Y-%m-%d").to_numpy()


def net_dates(arm, rows):
    """Fecha cuya red se usa: el mismo dia (R1) o el anterior (R1_ayer)."""
    d = rows.date.to_numpy()
    return shift_dates(d, -1) if arm == "S0+R1_ayer" else d


# ---------------------------------------------------------------- inputs
def base_scenario(arm):
    return "S2" if arm.startswith("S2") else "S0"


def feature_names(arm):
    names = list(r32.feature_names(base_scenario(arm)))
    if "sin_alt" in arm:
        names.remove(ALT)
    if arm in NET_ARMS:
        names += list(nw.R1_COLS)
    return names


def network(rows, arm, pool, exclude=(), table=None):
    """Columnas de red (network.py) para las filas, con la fecha de red del brazo; `table` = otra tabla fecha x
    estacion en lugar de la PM (se usa para la IDW de residuos)."""
    return nw.network_features(rows.station_code.to_numpy(), net_dates(arm, rows), pool,
                               pmw() if table is None else table, dist(), exclude=exclude)


def alt_range(fold):
    alt = lc.load_stations().altitude_m.astype(float)
    a = alt.loc[fold["train"]]
    return float(a.min()), float(a.max())


def arm_X(arm, rows, net=None, alt_clip=None):
    """Matriz de inputs del brazo. S0/S2 = run.py del 03.2 (identicos); sin altitud = se quita la columna; altitud
    recortada = np.clip al rango [min, max] de las estaciones de entrenamiento; R1 = IDW_PM y d1_km al final."""
    scen = base_scenario(arm)
    X = r32.features(scen, rows)
    names = list(r32.feature_names(scen))
    j = names.index(ALT)
    if arm == "S0_alt_recortada":
        assert alt_clip is not None, "falta el rango de altitud de la particion"
        X = X.copy()
        X[:, j] = np.clip(X[:, j], *alt_clip)
    if "sin_alt" in arm:
        X = np.delete(X, j, axis=1)
    if arm in NET_ARMS:
        X = np.column_stack([X, net[nw.R1_COLS].to_numpy(dtype=float)])
    return X.astype(float)


def target(arm, rows):
    """Objetivo: PM, o PM - ET0_OM en los brazos residuales (prediccion final = ET0_OM + modelo)."""
    pm = rows["ET0_PM_FAO56_V1"].to_numpy(dtype=float)
    return pm - rows["et0_om_mm"].to_numpy(dtype=float) if arm in RES_ARMS else pm


def to_pm(arm, rows, pred_model):
    """Regla (d): prediccion = ET0_OM + modelo en los brazos residuales; identidad en los demas."""
    pred_model = np.asarray(pred_model, float)
    return rows["et0_om_mm"].to_numpy(dtype=float) + pred_model if arm in RES_ARMS else pred_model


# ---------------------------------------------------------------- seleccion con la red recalculada por pliegue
def _predict(model, params, X, y, Xp):
    if model in ("ANN_S", "ANN_M"):
        return lm._fit_predict_mlp(model, params, X, y, Xp)
    return lm._fit_predict_simple(model, params, X, y, Xp), 0


def select_and_fit_net(model, X_full, X_inner, groups, y, Xtest):
    """Logica literal de loso_models.select_and_fit (Ridge, HGB, ANN_S/M) con X_inner[s] = inputs de TODAS las filas
    de entrenamiento con s fuera del pool. Filas sin red en un pliegue (pool vacio) no entran en ese pliegue."""
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


# ---------------------------------------------------------------- filas de una celda
def _subsample(n, k):
    return np.sort(np.random.default_rng(0).choice(n, k, replace=False))


def prepare(fold, arm, max_train_rows=None):
    """Filas y matrices de una celda (sin ajustar). Entrenamiento: DESARROLLO, objetivo valido, estaciones de
    entrenamiento, inputs finitos (con red: pool no vacio). TEST: cohorte comun de las estaciones evaluadas; las filas
    sin red quedan con prediccion NaN (el informe las quita de TODOS los metodos y las cuenta)."""
    df = panel()
    assert not (set(fold["train"]) & set(fold["test"]))
    tr = df[(df.period == "DEV") & df.target_ok & df.station_code.isin(fold["train"])].reset_index(drop=True)
    clip = alt_range(fold)
    net0 = network(tr, arm, fold["train"]) if arm in NET_ARMS else None
    X0 = arm_X(arm, tr, net0, clip)
    keep = np.isfinite(X0).all(1)
    n_drop_train = int((~keep).sum())
    tr, X0 = tr[keep].reset_index(drop=True), X0[keep]
    if max_train_rows and len(tr) > max_train_rows:
        idx = _subsample(len(tr), max_train_rows)
        tr, X0 = tr.iloc[idx].reset_index(drop=True), X0[idx]
    groups = tr.station_code.to_numpy()
    if arm in NET_ARMS:   # regla (b): la estacion de validacion sale del pool de todas las filas
        X_inner = {s: arm_X(arm, tr, network(tr, arm, fold["train"], exclude=(s,)), clip) for s in sorted(set(groups))}
    else:
        X_inner = None
    te = lc.test_cohort(df)
    te = te[te.station_code.isin(fold["test"])].reset_index(drop=True)
    nett = network(te, arm, fold["train"]) if arm in NET_ARMS else None
    Xt = arm_X(arm, te, nett, clip)
    okt = np.isfinite(Xt).all(1)
    if arm not in NET_ARMS:
        assert okt.all(), f"inputs no finitos en la cohorte TEST ({arm})"
    assert tr.date.max() <= lc.DEV[1] and te.date.min() >= lc.TEST[0]
    assert not (set(tr.station_code) & set(fold["test"])), "estacion evaluada en el entrenamiento"
    return {"train": tr, "X": X0, "X_inner": X_inner, "groups": groups, "y": target(arm, tr), "test": te,
            "Xt": Xt, "okt": okt, "net_test": nett, "n_drop_train": n_drop_train, "alt_clip": clip}


def nested_rows(fold, s, max_train_rows=None):
    """HGB-S0 anidado para la estacion de entrenamiento s: entrena SIN s ni las evaluadas (regla c) y predice todas
    las filas de s (DESARROLLO y TEST) con S0 finito."""
    df = panel()
    assert s in fold["train"]
    train = [t for t in fold["train"] if t != s]
    tr = df[(df.period == "DEV") & df.target_ok & df.station_code.isin(train)].reset_index(drop=True)
    X = r32.features("S0", tr)
    ok = np.isfinite(X).all(1)
    tr, X = tr[ok].reset_index(drop=True), X[ok]
    if max_train_rows and len(tr) > max_train_rows:
        idx = _subsample(len(tr), max_train_rows)
        tr, X = tr.iloc[idx].reset_index(drop=True), X[idx]
    pr = df[df.station_code == s].reset_index(drop=True)
    Xp = r32.features("S0", pr)
    okp = np.isfinite(Xp).all(1)
    pr, Xp = pr[okp].reset_index(drop=True), Xp[okp]
    assert s not in set(tr.station_code) and not (set(tr.station_code) & set(fold["test"]))
    return tr, X, pr, Xp, train


# ---------------------------------------------------------------- celdas
def cell_path(fold_id, arm, model):
    return CELLS / f"{fold_id}__{arm}__{model}.json.gz"


def nested_arm(s):
    return f"{NESTED}_{s}"


def env_info():
    import platform
    import sklearn
    return {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
            "scikit-learn": sklearn.__version__, "platform": platform.platform(),
            "cpu": platform.processor() or platform.machine(), "cpus": os.cpu_count()}


def _write(p, out):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(out, f, default=lambda o: list(o) if isinstance(o, tuple) else str(o))
    tmp.replace(p)


def fit_nested(fold, s, max_train_rows=None):
    t0 = time.time()
    tr, X, pr, Xp, train = nested_rows(fold, s, max_train_rows)
    r = lm.select_and_fit("HGB", X, tr["ET0_PM_FAO56_V1"].to_numpy(), tr.station_code.to_numpy(),
                          tr.date.to_numpy(), Xp)
    pred, nneg = lm.clip_negative(r["pred"])
    return {"study": "03.3", "fold": fold["id"], "arm": nested_arm(s), "model": "HGB", "station": s,
            "train_stations": train, "n_train": int(len(tr)), "params": r["params"], "cv": r["cv"],
            "negatives_clipped": nneg, "convergence_warnings": 0, "station_code": pr.station_code.tolist(),
            "date": pr.date.tolist(), "pred": pred.tolist(), "seconds": round(time.time() - t0, 1),
            "env": env_info(), "test_run": bool(max_train_rows)}


def fit_arm(fold, arm, model, max_train_rows=None):
    t0 = time.time()
    P = prepare(fold, arm, max_train_rows)
    te, okt = P["test"], P["okt"]
    if arm in NET_ARMS:
        r = select_and_fit_net(model, P["X"], P["X_inner"], P["groups"], P["y"], P["Xt"][okt])
    else:
        r = lm.select_and_fit(model, P["X"], P["y"], P["groups"], P["train"].date.to_numpy(), P["Xt"][okt])
    sub = te[okt]
    pred_pm, nneg = lm.clip_negative(to_pm(arm, sub, r["pred"]))
    pred = np.full(len(te), np.nan)
    pred[okt] = pred_pm
    out = {"study": "03.3", "fold": fold["id"], "arm": arm, "model": model, "features": feature_names(arm),
           "target": "PM - ET0_OM" if arm in RES_ARMS else "PM", "n_train": int(len(P["y"])),
           "train_stations": fold["train"], "rows_dropped_train_empty_pool": P["n_drop_train"],
           "rows_test_without_network": int((~okt).sum()), "alt_clip": P["alt_clip"],
           "inner_rows_dropped": r.get("inner_rows_dropped", {}), "params": r["params"], "cv": r["cv"],
           "negatives_clipped": nneg, "convergence_warnings": r.get("warnings", 0),
           "station_code": te.station_code.tolist(), "date": te.date.tolist(),
           "pred": [None if not np.isfinite(v) else float(v) for v in pred],
           "seconds": round(time.time() - t0, 1), "env": env_info(), "test_run": bool(max_train_rows)}
    if "seed_preds" in r:
        sp = np.array([np.maximum(to_pm(arm, sub, x), 0) for x in r["seed_preds"]])
        out["seed_preds"] = sp.tolist()
    return out


def fit_cell(fold, arm, model, deadline=None, max_train_rows=None):
    if deadline is not None and time.time() > deadline:
        return "OMITIDA (limite de horas)", 0.0
    if arm.startswith(NESTED + "_"):
        out = fit_nested(fold, arm[len(NESTED) + 1:], max_train_rows)
    else:
        out = fit_arm(fold, arm, model, max_train_rows)
    p = cell_path(fold["id"], arm, model)
    _write(p, out)
    return p.name, out["seconds"]


def all_cells(arms=None, models=None, fold_ids=None):
    """(fold, brazo, modelo) de todo el estudio. Los anidados cuentan como brazo `anidado` y modelo HGB."""
    folds = lc.build_folds()
    if fold_ids:
        folds = [f for f in folds if f["id"] in fold_ids or f["scheme"] in fold_ids]
    out = []
    for arm, ms in list(ARMS.items()) + [(NESTED, ["HGB"])]:
        if arms and arm not in arms:
            continue
        for m in ms:
            if models and m not in models:
                continue
            for f in folds:
                if arm == NESTED:
                    out += [(f, nested_arm(s), "HGB") for s in f["train"]]
                else:
                    out.append((f, arm, m))
    return out


def _split(v):
    return [x for x in (v or "").split(",") if x]


def cmd_fit(arms, models, fold_ids, workers, max_hours, list_only, max_train_rows):
    CELLS.mkdir(parents=True, exist_ok=True)
    allc = all_cells(arms, models, fold_ids)
    todo = [a for a in allc if not cell_path(a[0]["id"], a[1], a[2]).exists()]
    # primero los anidados y los HGB (rapidos), las ANN al final
    todo.sort(key=lambda a: (a[2] == "ANN_M", a[2] != "HGB" or not a[1].startswith(NESTED)))
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
    ap.add_argument("--arms", default="", help=",".join(list(ARMS) + [NESTED]) + " (vacio = todos)")
    ap.add_argument("--models", default="", help="Ridge,HGB,ANN_M (vacio = los de cada brazo)")
    ap.add_argument("--folds", default="", help="ids de particion o esquema (F1_loso, F2_island); vacio = todas")
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
        cmd_fit(_split(a.arms), _split(a.models), _split(a.folds), a.workers, a.max_hours, a.list,
                a.max_train_rows)
    else:
        _load("estudio03_3_report", HERE / "report.py").main()
