"""Modelos conjuntos y su seleccion de hiperparametros (estudios 03.1 y 03.2).

Rejillas literales de config/thresholds_v3.json y thresholds_v3_1.json. Seleccion: validacion cruzada interna
agrupada por estacion dentro del entrenamiento de cada particion (leave-one-station-out interno); metrica: media
simple del RMSE de cada estacion retenida (cada estacion pesa igual, analogo a la "media simple de RMSE anuales" de V2).
Empate (diferencia <= 1e-12): primera configuracion en el orden de la rejilla. Nunca se mira TEST.
Las ANN promedian sus 5 semillas antes de puntuar (como V2). Predicciones negativas: se recortan a 0 al final, con
recuento (thresholds: "recorte a 0 con recuento").
"""
from __future__ import annotations

import itertools
import math
import warnings
from statistics import median

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

TIE = 1e-12


def _grid(d):
    keys = list(d)
    return [dict(zip(keys, v)) for v in itertools.product(*(d[k] for k in keys))]


GRIDS = {
    "Ridge": _grid({"alpha": [0.1, 1, 10, 100]}),
    "HGB": _grid({"learning_rate": [0.03, 0.1], "max_leaf_nodes": [15, 31]}),
    "RF": _grid({"min_samples_leaf": [5, 20]}),
    "ANN_S": _grid({"alpha": [1e-4, 1e-3]}),
    "ANN_M": _grid({"alpha": [1e-4, 1e-3]}),
    # ANN tipo V2 (ANN A de Capitulo-1): la "rejilla" son sus cinco arquitecturas
    "ANN_V2like": [{"hidden": h} for h in [(16,), (32,), (64,), (64, 32), (64, 32, 16)]],
}
ANN_SEEDS = [0, 1, 2, 3, 4]                                      # thresholds: ANN_S / ANN_M
ANN_V2_SEEDS = [20261101, 20261102, 20261103, 20261104, 20261105]  # semillas de V2 + 2 consecutivas
ANN_V2 = {"activation": "relu", "alpha": 1e-4, "learning_rate_init": 1e-3, "batch_size": 256,
          "max_epochs": 200, "patience": 15, "min_delta": 1e-4, "inner_fraction": 0.15}


# ---------------------------------------------------------------- estimadores
def _fit_predict_simple(model, params, X, y, Xp):
    if model == "Ridge":
        m = make_pipeline(StandardScaler(), Ridge(alpha=params["alpha"]))
    elif model == "HGB":
        m = HistGradientBoostingRegressor(max_iter=500, early_stopping=False, random_state=0, **params)
    elif model == "RF":
        m = RandomForestRegressor(n_estimators=300, random_state=0, n_jobs=1, **params)
    else:
        raise KeyError(model)
    return m.fit(X, y).predict(Xp)


def _fit_predict_mlp(model, params, X, y, Xp, seeds=ANN_SEEDS):
    hidden = (32,) if model == "ANN_S" else (64, 32)
    preds, warn = [], 0
    for s in seeds:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", ConvergenceWarning)
            m = make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=hidden, alpha=params["alpha"],
                                                             early_stopping=True, random_state=s))
            preds.append(m.fit(X, y).predict(Xp))
        warn += sum(issubclass(x.category, ConvergenceWarning) for x in w)
    return np.array(preds), warn


# ---- ANN tipo V2 (copia de Capitulo-1 ann_modern.py adaptada a filas de varias estaciones)
def _v2_net(hidden, seed):
    return MLPRegressor(hidden_layer_sizes=tuple(hidden), activation=ANN_V2["activation"], solver="adam",
                        alpha=ANN_V2["alpha"], batch_size=ANN_V2["batch_size"],
                        learning_rate_init=ANN_V2["learning_rate_init"], random_state=seed,
                        shuffle=False, early_stopping=False)


def _v2_inner_cutoff(dates):
    """Regla ANN A: el ultimo 15 % de fechas (unicas, ordenadas) del entrenamiento es la validacion interna."""
    u = np.unique(dates)
    cut = min(len(u) - 1, max(1, math.floor(len(u) * (1 - ANN_V2["inner_fraction"]))))
    return u[cut]


def _v2_best_epoch(hidden, seed, X, y, dates):
    cutoff = _v2_inner_cutoff(dates)
    fit, hold = dates < cutoff, dates >= cutoff
    sc = StandardScaler().fit(X[fit])
    xi, xh = sc.transform(X[fit]), sc.transform(X[hold])
    net, best, best_e, stale = _v2_net(hidden, seed), float("inf"), 0, 0
    for e in range(1, ANN_V2["max_epochs"] + 1):
        net.partial_fit(xi, y[fit])
        r = float(np.sqrt(np.mean((net.predict(xh) - y[hold]) ** 2)))
        if r < best - ANN_V2["min_delta"]:
            best, best_e, stale = r, e, 0
        else:
            stale += 1
        if stale >= ANN_V2["patience"]:
            break
    return best_e


def _v2_train(hidden, seed, X, y, epochs):
    sc = StandardScaler().fit(X)
    net = _v2_net(hidden, seed)
    xs = sc.transform(X)
    for _ in range(epochs):
        net.partial_fit(xs, y)
    return sc, net


def _v2_fold(hidden, X, y, dates, Xv):
    """Por semilla: elegir epocas dentro del entrenamiento, reajustar con todo el entrenamiento y predecir."""
    out, epochs = [], []
    for s in ANN_V2_SEEDS:
        e = _v2_best_epoch(hidden, s, X, y, dates)
        sc, net = _v2_train(hidden, s, X, y, e)
        out.append(net.predict(sc.transform(Xv)))
        epochs.append(e)
    return np.array(out), epochs


def _params(hidden):
    return sum((a + 1) * b for a, b in zip(hidden[:-1], hidden[1:]))


# ---------------------------------------------------------------- seleccion y ajuste final
def select_and_fit(model, X, y, groups, dates, Xtest):
    """Devuelve dict con: params elegidos, cv (lista por config), pred (media), seed_preds (ANN) y extras."""
    stations = sorted(np.unique(groups))
    cv = []
    for p in GRIDS[model]:
        fold_rmse, epochs_by_fold = [], []
        for s in stations:
            tr, va = groups != s, groups == s
            if model in ("ANN_S", "ANN_M"):
                pr, _ = _fit_predict_mlp(model, p, X[tr], y[tr], X[va])
                pr = pr.mean(0)
            elif model == "ANN_V2like":
                pr, ep = _v2_fold(p["hidden"], X[tr], y[tr], dates[tr], X[va])
                pr = pr.mean(0)
                epochs_by_fold.append(ep)
            else:
                pr = _fit_predict_simple(model, p, X[tr], y[tr], X[va])
            fold_rmse.append(float(np.sqrt(np.mean((pr - y[va]) ** 2))))
        cv.append({"params": p, "mean_rmse": float(np.mean(fold_rmse)), "sd_rmse": float(np.std(fold_rmse)),
                   "fold_rmse": dict(zip(stations, fold_rmse)), "epochs_by_fold": epochs_by_fold})
    best_score = min(c["mean_rmse"] for c in cv)
    tied = [c for c in cv if c["mean_rmse"] - best_score <= TIE]
    if model == "ANN_V2like":   # desempates de V2: menor dispersion, menos parametros, orden lexicografico
        d = X.shape[1]
        tied.sort(key=lambda c: (c["sd_rmse"], _params((d, *c["params"]["hidden"], 1)), c["params"]["hidden"]))
    chosen = tied[0]
    res = {"params": chosen["params"], "cv": cv, "warnings": 0}
    if model in ("ANN_S", "ANN_M"):
        sp, res["warnings"] = _fit_predict_mlp(model, chosen["params"], X, y, Xtest)
        res["seed_preds"] = sp
        res["pred"] = sp.mean(0)
    elif model == "ANN_V2like":
        # epocas finales por semilla: mediana de las mejores epocas de los folds, mitades hacia arriba (V2)
        fe = [math.floor(median(f[i] for f in chosen["epochs_by_fold"]) + 0.5) for i in range(len(ANN_V2_SEEDS))]
        sp = []
        for s, e in zip(ANN_V2_SEEDS, fe):
            sc, net = _v2_train(chosen["params"]["hidden"], s, X, y, e)
            sp.append(net.predict(sc.transform(Xtest)))
        res["seed_preds"], res["final_epochs"] = np.array(sp), fe
        res["pred"] = res["seed_preds"].mean(0)
    else:
        res["pred"] = _fit_predict_simple(model, chosen["params"], X, y, Xtest)
    return res


def clip_negative(pred):
    pred = np.asarray(pred, float)
    n = int((pred < 0).sum())
    return np.maximum(pred, 0.0), n
