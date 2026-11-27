"""Informe del estudio 03.3: une celdas del 03.3, metodos reutilizados del 03.2 y comparadores; construye
media_fija, media_ponderada y residuo_IDW; cohorte comun (interseccion); metricas, IC pareados, TOST, control de
dominio, interpretation.json, figuras y manifiesto.

Uso: python studies/03_3_om_red_residual/run.py report
Criterios: config/thresholds_v3_3.json (congelado). La regla de interpretacion se aplica de forma literal
(interpretation()); la aclaracion previa a la ejecucion sobre los casos no cubiertos esta en el README (Parte I bis).
"""
from __future__ import annotations

import gzip
import json
import math
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent


def _run_module():
    name = "estudio03_3_run"
    if name not in sys.modules:
        import importlib.util
        spec = importlib.util.spec_from_file_location(name, HERE / "run.py")
        sys.modules[name] = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sys.modules[name])
    return sys.modules[name]


R = _run_module()
lc, lm, nw, THR = R.lc, R.lm, R.nw, R.THR
FIG = Path(__import__("os").environ.get("LOSO_FIG_DIR", HERE / "figures"))   # solo pruebas
P32 = R.S032 / "results/predictions_test.csv.gz"
CELLS32 = R.S032 / "results/cells"
PRACT = THR["statistics"]["practical_threshold_mm_dia"]          # 0.05

# nombres de los metodos reutilizados del 03.2 y de los comparadores (thresholds_v3_3.json -> comparators)
HGB_S0, HGB_S2, ANN_S0 = "HGB-S0 (03.2)", "HGB-S2 (03.2)", "ANN_M-S0 (03.2)"
IDW, NEAR, AHC_T, OM = "PM_IDW_mismo_dia", "PM_estacion_mas_cercana_mismo_dia", \
    "OM_AHC_mensual_medio_entrenamiento", "OM_crudo"
FROM32 = {"S0|HGB": HGB_S0, "S2|HGB": HGB_S2, "S0|ANN_M": ANN_S0, "OM_crudo": OM,
          "OM_AHC_mensual_medio_entrenamiento": AHC_T, "PM_estacion_mas_cercana_mismo_dia": NEAR,
          "PM_IDW_estaciones_entrenamiento_mismo_dia": IDW}
COMPARATORS = [HGB_S0, IDW, NEAR, AHC_T, OM, HGB_S2, ANN_S0]
MF, MP, RIDW = "media_fija", "media_ponderada", "residuo_IDW"
PRIMARY_L3 = "S0+R1|HGB"
INFORMATIVE_L3 = [MF, MP, RIDW, "S2+R1|HGB", "S0+R1_ayer|HGB", "S0+R1|Ridge"]


def key(a, b):
    return pd.Series(a).astype(str).to_numpy() + "|" + pd.Series(b).astype(str).to_numpy()


def read_cell(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- metodos construidos (sin entrenar)
def residual_table(nested, df):
    """Tabla fecha x estacion de residuos PM - HGB-S0 anidado (cada estacion con SU modelo sin ella; regla c)."""
    pm = df[df.target_ok][["station_code", "date", "ET0_PM_FAO56_V1"]]
    parts = []
    for c in nested:
        t = pd.DataFrame({"station_code": c["station_code"], "date": c["date"], "hat": c["pred"]})
        parts.append(t)
    t = pd.concat(parts).merge(pm, on=["station_code", "date"], how="inner")
    t["res"] = t.ET0_PM_FAO56_V1 - t.hat
    return t.pivot(index="date", columns="station_code", values="res")


def residuo_idw(test, hgb_s0, fold, restab):
    """HGB-S0 + IDW (potencia 2) de los residuos de las estaciones del pool ese dia (network.py, misma exclusion)."""
    net = R.network(test, "S0+R1", fold["train"], table=restab)
    corr = net["IDW_PM"].to_numpy()
    return np.maximum(hgb_s0 + corr, 0.0), corr


def choose_w(nested, df, fold):
    """w de media_ponderada por validacion interna agrupada por estacion: para cada estacion de entrenamiento s,
    sus filas de DESARROLLO con la prediccion fuera de muestra del HGB-S0 anidado (sin s) y la IDW del dia con s fuera
    del pool (pool = resto de estaciones de entrenamiento). Metrica: media simple del RMSE por estacion; empate
    (<= TIE): el primero de la rejilla, como loso_models."""
    dev = df[(df.period == "DEV") & df.target_ok & df.station_code.isin(fold["train"])]
    oof = pd.concat([pd.DataFrame({"station_code": c["station_code"], "date": c["date"], "hat": c["pred"]})
                     for c in nested])
    d = dev.merge(oof, on=["station_code", "date"], how="inner").reset_index(drop=True)
    d["idw"] = R.network(d, "S0+R1", fold["train"])["IDW_PM"].to_numpy()
    d = d[np.isfinite(d.idw) & np.isfinite(d.hat)]
    y, h, i, g = d.ET0_PM_FAO56_V1.to_numpy(), d.hat.to_numpy(), d.idw.to_numpy(), d.station_code.to_numpy()
    cv = []
    for w in R.W_GRID:
        p = w * h + (1 - w) * i
        per = {s: float(np.sqrt(np.mean((p[g == s] - y[g == s]) ** 2))) for s in sorted(set(g))}
        cv.append({"w": w, "mean_rmse": float(np.mean(list(per.values()))), "fold_rmse": per})
    best = min(c["mean_rmse"] for c in cv)
    chosen = [c for c in cv if c["mean_rmse"] - best <= lm.TIE][0]
    return chosen["w"], cv, int(len(d))


# ---------------------------------------------------------------- ensamblado
def load32():
    p = pd.read_csv(P32)
    keep = ["fold", "scheme", "station_code", "date", "pm"] + list(FROM32)
    return p[keep].rename(columns=FROM32)


def assemble():
    df = R.panel()
    p32 = load32()
    folds = lc.build_folds()
    blocks, info, missing, counts, wsel, seeds = [], [], [], {}, {}, []
    for f in folds:
        te = lc.test_cohort(df)
        te = te[te.station_code.isin(f["test"])].reset_index(drop=True)
        k = key(te.station_code, te.date)
        b = p32[p32.fold == f["id"]].set_index(key(p32[p32.fold == f["id"]].station_code,
                                                    p32[p32.fold == f["id"]].date)).loc[k].reset_index(drop=True)
        assert np.allclose(b.pm.to_numpy(), te.ET0_PM_FAO56_V1.to_numpy(), atol=1e-4)  # CSV a 5 decimales
        cols = {c: b[c].to_numpy(dtype=float) for c in [HGB_S0, HGB_S2, ANN_S0, OM, AHC_T, NEAR, IDW]}
        net_d = R.network(te, "S0+R1", f["train"])
        net_y = R.network(te, "S0+R1_ayer", f["train"])
        # la IDW de network.py coincide con la del 03.2 (mismo pool y potencia)
        ok = np.isfinite(net_d.IDW_PM.to_numpy())
        assert np.allclose(net_d.IDW_PM.to_numpy()[ok], cols[IDW][ok], atol=1e-4)
        cols[MF] = 0.5 * cols[HGB_S0] + 0.5 * cols[IDW]
        nested, miss_n = [], []
        for s in f["train"]:
            p = R.cell_path(f["id"], R.nested_arm(s), "HGB")
            if p.exists():
                c = read_cell(p)
                nested.append(c)
                info.append(_info(c, f["id"], R.nested_arm(s), "HGB"))
            else:
                miss_n.append(p.name)
        missing += miss_n
        if not miss_n:
            w, cvw, nw_rows = choose_w(nested, df, f)
            wsel[f["id"]] = {"w": w, "n_rows": nw_rows, "cv": cvw}
            cols[MP] = w * cols[HGB_S0] + (1 - w) * cols[IDW]
            cols[RIDW], corr = residuo_idw(te, cols[HGB_S0], f, residual_table(nested, df))
            n_ridw_nan = int((~np.isfinite(corr)).sum())
        else:
            n_ridw_nan = None
        for arm, models in R.ARMS.items():
            for m in models:
                p = R.cell_path(f["id"], arm, m)
                if not p.exists():
                    missing.append(p.name)
                    continue
                c = read_cell(p)
                assert (key(c["station_code"], c["date"]) == k).all(), f"orden de filas distinto en {p.name}"
                cols[f"{arm}|{m}"] = np.array([np.nan if v is None else v for v in c["pred"]], float)
                info.append(_info(c, f["id"], arm, m))
                if "seed_preds" in c:
                    seeds.append((f["id"], f"{arm}|{m}", te.ET0_PM_FAO56_V1.to_numpy(), np.array(c["seed_preds"])))
        if f["scheme"] == "F1_loso" or f["id"].startswith("F2_"):
            p = CELLS32 / f"{f['id']}__S0__ANN_M.json.gz"
            if p.exists():
                c = read_cell(p)
                seeds.append((f["id"], ANN_S0, te.ET0_PM_FAO56_V1.to_numpy(), np.array(c["seed_preds"])))
        frame = pd.DataFrame({"fold": f["id"], "scheme": f["scheme"], "station_code": te.station_code,
                              "date": te.date, "pm": te.ET0_PM_FAO56_V1.to_numpy(),
                              "d1_km": net_d.d1_km.to_numpy(), "n_pool": net_d.n_pool.to_numpy()} | cols)
        meth = [c for c in frame.columns if c not in ID_COLS]
        allok = np.isfinite(frame[meth].to_numpy()).all(1)
        frame["en_cohorte"] = allok
        counts[f["id"]] = {"filas_cohorte_03_2": int(len(te)), "sin_red_dia_d": int((~ok).sum()),
                           "sin_red_dia_d_menos_1": int((~np.isfinite(net_y.IDW_PM.to_numpy())).sum()),
                           "sin_pool_de_residuos": n_ridw_nan, "fuera_de_la_cohorte_comun": int((~allok).sum()),
                           "filas_cohorte_comun": int(allok.sum())}
        blocks.append(frame)
    return pd.concat(blocks, ignore_index=True), info, missing, counts, wsel, seeds, folds


ID_COLS = ("fold", "scheme", "station_code", "date", "pm", "d1_km", "n_pool", "en_cohorte")


def _info(c, fold, arm, model):
    chosen = min(c["cv"], key=lambda x: x["mean_rmse"])
    return {"fold": fold, "arm": arm, "model": model, "n_train": c["n_train"], "params": json.dumps(c["params"]),
            "cv_mean_rmse_chosen": chosen["mean_rmse"], "negatives_clipped": c["negatives_clipped"],
            "convergence_warnings": c.get("convergence_warnings", 0),
            "rows_test_without_network": c.get("rows_test_without_network", 0), "seconds": c["seconds"],
            "platform": c.get("env", {}).get("platform", ""), "test_run": c.get("test_run", False)}


def methods(pred):
    return [c for c in pred.columns if c not in ID_COLS]


def scopes(pred):
    d = pred[pred.en_cohorte]
    out = {"F1": d[d.scheme == "F1_loso"]}
    for fid in sorted(d.fold.unique()):
        if fid.startswith("F2_"):
            out[fid] = d[d.fold == fid]
    return out


# ---------------------------------------------------------------- metricas
def metric_tables(pred):
    g_rows, s_rows, m_rows = [], [], []
    for scope, d in scopes(pred).items():
        season = lc.season_label(d.date).str[5:]
        for c in methods(pred):
            g_rows.append({"scope": scope, "method": c, **lc.metrics(d[c], d.pm)})
            for s, g in d.groupby("station_code"):
                s_rows.append({"scope": scope, "method": c, "station_code": s, **lc.metrics(g[c], g.pm)})
            for lab, keyser in (("month", d.date.str[5:7]), ("season", season), ("year", d.date.str[:4])):
                for kk, g in d.groupby(keyser):
                    m_rows.append({"scope": scope, "method": c, "breakdown": lab, "key": kk, **lc.metrics(g[c], g.pm)})
    return pd.DataFrame(g_rows), pd.DataFrame(s_rows), pd.DataFrame(m_rows)


def paired_delta_ci2(pred_a, pred_b, ref, blocks, draws):
    """Como loso_common.paired_delta_ci (mismos remuestreos), devolviendo el IC 95 % y el 90 % (TOST)."""
    ea, eb = (np.asarray(pred_a) - ref) ** 2, (np.asarray(pred_b) - ref) ** 2
    nb = blocks.max() + 1
    n = np.bincount(blocks, minlength=nb).astype(float)
    sa, sb = np.bincount(blocks, ea, nb), np.bincount(blocks, eb, nb)
    d0 = math.sqrt(sa.sum() / n.sum()) - math.sqrt(sb.sum() / n.sum())
    N, A, B = n[draws].sum(1), sa[draws].sum(1), sb[draws].sum(1)
    d = np.sqrt(A / N) - np.sqrt(B / N)
    lo95, hi95, lo90, hi90 = np.percentile(d, [2.5, 97.5, 5, 95])
    return float(d0), float(lo95), float(hi95), float(lo90), float(hi90)


def verdict(d0, lo, hi):
    if hi < 0:
        v = "A gana"
    elif lo > 0:
        v = "B gana"
    else:
        return "empate (IC incluye 0)"
    return v + (" (significativa pero pequena)" if abs(d0) < PRACT else "")


HYPOTHESES = {   # (ambito, A, B), literal de thresholds_v3_3.json -> hypotheses
    "H33_1": ("F1", PRIMARY_L3, HGB_S0),
    "H33_2": ("F1", PRIMARY_L3, IDW),
    "H33_3_Ibiza": ("F2_Ibiza", PRIMARY_L3, HGB_S0),
    "H33_3_Menorca": ("F2_Menorca", PRIMARY_L3, HGB_S0),
    "H5_1": ("F1", "S0_res|ANN_M", ANN_S0),
    "H5_2": ("F1", "S0_res|HGB", HGB_S0),
}


def comparisons(meths):
    out = []
    own = [m for m in meths if "|" in m or m in (MF, MP, RIDW)]
    for a in own:
        for b in COMPARATORS:
            out.append(("vs_comparador", a, b))
        if a.endswith("|ANN_M"):
            out.append(("ANN_vs_ANN_M-S0", a, ANN_S0))
        if a.endswith("|Ridge"):
            out.append(("Ridge_vs_HGB", a, a.replace("|Ridge", "|HGB")))
    out += [("red_ayer_vs_red_dia", "S0+R1_ayer|HGB", PRIMARY_L3), ("S2+R1_vs_S0+R1", "S2+R1|HGB", PRIMARY_L3),
            ("ANN_vs_HGB_mismo_brazo", "S0_res|ANN_M", "S0_res|HGB"),
            ("ANN_vs_HGB_mismo_brazo", "S0_sin_alt|ANN_M", "S0_sin_alt|HGB"),
            ("ANN_vs_HGB_mismo_brazo", "S0_res_sin_alt|ANN_M", "S0_res_sin_alt|HGB"),
            ("comparadores", ANN_S0, HGB_S0), ("comparadores", IDW, HGB_S0), ("comparadores", HGB_S2, HGB_S0)]
    seen, uniq = set(), []
    for k, a, b in out:
        if a != b and (a, b) not in seen and a in meths and b in meths:
            seen.add((a, b))
            uniq.append((k, a, b))
    return uniq


def paired(pred):
    rows = []
    hyp = {(sc, a, b): h for h, (sc, a, b) in HYPOTHESES.items()}
    for scope, d in scopes(pred).items():
        bi, _ = lc.block_index(d.station_code, d.date)
        draws = lc.boot_draws(bi.max() + 1)
        ref = d.pm.to_numpy()
        for kind, a, b in comparisons(methods(pred)):
            d0, lo, hi, lo9, hi9 = paired_delta_ci2(d[a].to_numpy(), d[b].to_numpy(), ref, bi, draws)
            rows.append({"scope": scope, "hypothesis": hyp.get((scope, a, b), ""), "kind": kind, "A": a, "B": b,
                         "n": len(d), "n_blocks": int(bi.max() + 1), "rmse_A": lc.metrics(d[a], ref)["rmse"],
                         "rmse_B": lc.metrics(d[b], ref)["rmse"], "delta_rmse": d0, "ci95_lo": lo, "ci95_hi": hi,
                         "ci90_lo": lo9, "ci90_hi": hi9, "verdict": verdict(d0, lo, hi),
                         "tost_equivalente_005": bool(lo9 > -PRACT and hi9 < PRACT)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- regla de interpretacion (literal)
def _row(pc, scope, a, b):
    r = pc[(pc.scope == scope) & (pc.A == a) & (pc.B == b)]
    if r.empty:
        return None
    r = r.iloc[0]
    return {"A": a, "B": b, "rmse_A": r.rmse_A, "rmse_B": r.rmse_B, "delta": r.delta_rmse,
            "ci95": [r.ci95_lo, r.ci95_hi], "ci90": [r.ci90_lo, r.ci90_hi]}


def l3_case(pc, arm):
    """Caso (1)-(4) de la regla para un brazo (el primario o, post hoc, un informativo)."""
    d1, d2 = _row(pc, "F1", arm, HGB_S0), _row(pc, "F1", arm, IDW)
    f2 = {s: _row(pc, s, arm, HGB_S0) for s in ("F2_Ibiza", "F2_Menorca")}
    if d1 is None or d2 is None or any(v is None for v in f2.values()):
        return None
    sig1, sig2 = d1["ci95"][1] < 0, d2["ci95"][1] < 0
    big = d1["delta"] <= -PRACT and d2["delta"] <= -PRACT
    f2_ok = all(v["delta"] <= PRACT for v in f2.values())
    if sig1 and sig2 and big:
        case, literal = (1 if f2_ok else 2), True
    elif sig1 or sig2:
        # (3) literal: algun IC95 < 0 con |Delta| < 0.05. Los casos con algun IC < 0 que no cumplen (1)/(2) y no
        # encajan literalmente en (3) van a (3) por la aclaracion previa a la ejecucion (README, 2026-11-27).
        literal = any(s and abs(d["delta"]) < PRACT for s, d in ((sig1, d1), (sig2, d2)))
        case = 3
    else:
        case, literal = 4, True
    return {"Delta1_vs_HGB-S0": d1, "Delta2_vs_IDW": d2, "F2_vs_HGB-S0": f2, "IC1<0": bool(sig1),
            "IC2<0": bool(sig2), "ambos_Delta<=-0.05": bool(big), "F2_no_empeora_mas_de_0.05": bool(f2_ok),
            "caso": case, "caso_por_texto_literal": bool(literal)}


TEXT = {1: "Open-Meteo + ML + red en toda Baleares",
        2: "combinar solo cerca de la red (distancia de corte con Andalucia, L4)",
        3: "mejora sin interes practico: el servicio sigue con HGB-S0",
        4: "la red no aporta sobre HGB-S0"}


def interpretation(pc):
    out = {"criterios": "config/thresholds_v3_3.json (congelado)", "umbral_practico": PRACT,
           "aclaracion_previa": "Decidida el 2026-11-27 ANTES de ejecutar: si algun IC95 < 0 y no se cumplen (1) "
                                "ni (2), es el caso (3), aunque el texto literal de (3) no lo cubra.",
           "hipotesis": {}}
    for h, (sc, a, b) in HYPOTHESES.items():
        r = _row(pc, sc, a, b)
        if r is None:
            out["hipotesis"][h] = {"estado": "faltan celdas"}
            continue
        if h in ("H33_1", "H33_2", "H5_1"):
            r["criterio"], r["cumple"] = "Delta < 0 y extremo superior del IC95 < 0", bool(r["delta"] < 0 and r["ci95"][1] < 0)
        elif h.startswith("H33_3"):
            r["criterio"] = "se informa Delta e IC y si supera +0.05"
            r["supera_+0.05"] = bool(r["delta"] > PRACT)
        elif h == "H5_2":
            r["criterio"] = "TOST +-0.05 (IC90 dentro de (-0.05, +0.05))"
            r["equivalente"] = bool(r["ci90"][0] > -PRACT and r["ci90"][1] < PRACT)
        out["hipotesis"][h] = r
    prim = l3_case(pc, PRIMARY_L3)
    out["L3"] = {"brazo_primario": PRIMARY_L3, **(prim or {"estado": "faltan celdas"})}
    if prim:
        out["L3"]["decision"] = TEXT[prim["caso"]]
    ph = {}
    for arm in INFORMATIVE_L3:
        c = l3_case(pc, arm)
        if c:
            ph[arm] = {"caso": c["caso"], "Delta1": c["Delta1_vs_HGB-S0"]["delta"], "Delta2": c["Delta2_vs_IDW"]["delta"]}
    out["L3"]["post_hoc_brazos_informativos"] = ph
    out["L3"]["post_hoc_cumplen_1_o_2_sin_el_primario"] = [a for a, v in ph.items() if v["caso"] in (1, 2)] \
        if prim and prim["caso"] not in (1, 2) else []
    h51 = out["hipotesis"].get("H5_1", {})
    ann_vs_hgb = _row(pc, "F1", "S0_res|ANN_M", HGB_S0)
    if h51.get("cumple") is not None and ann_vs_hgb:
        ok = bool(h51["cumple"] and ann_vs_hgb["delta"] < PRACT)
        out["L5"] = {"H5_1_cumple": h51["cumple"], "ANN_M_S0_res_menos_HGB-S0": ann_vs_hgb,
                     "a_menos_de_+0.05_de_HGB-S0": bool(ann_vs_hgb["delta"] < PRACT),
                     "decision": "las ANN vuelven a considerarse para Andalucia (L13)" if ok
                     else "las ANN quedan aparcadas"}
    else:
        out["L5"] = {"estado": "faltan celdas de ANN_M"}
    out["control_de_dominio"] = "se adopta en el servicio en cualquier caso (ver dominio.csv; sin veredicto)"
    return out


# ---------------------------------------------------------------- control de dominio
DOMAIN_INPUTS = [c for c in R.r32.feature_names("S0") if c != R.ALT]


def domain_flags(train_X, test_X, names):
    """Marca por fila y por variable: continuas fuera de [p0.5, p99.5] del entrenamiento; altitud fuera de [min, max]."""
    flags = {}
    for j, n in enumerate(names):
        if n == R.ALT:
            lo, hi = train_X[:, j].min(), train_X[:, j].max()
        else:
            lo, hi = np.percentile(train_X[:, j], [0.5, 99.5])
        flags[n] = (test_X[:, j] < lo) | (test_X[:, j] > hi)
    return pd.DataFrame(flags)


def domain(pred):
    df = R.panel()
    names = list(R.r32.feature_names("S0"))
    fl = []
    for f in lc.build_folds():
        tr = df[(df.period == "DEV") & df.target_ok & df.station_code.isin(f["train"])]
        X = R.r32.features("S0", tr)
        X = X[np.isfinite(X).all(1)]
        sub = pred[pred.fold == f["id"]]
        te = df.set_index(key(df.station_code, df.date)).loc[key(sub.station_code, sub.date)]
        fl.append(domain_flags(X, R.r32.features("S0", te), names).set_index(sub.index))
    flags = pd.concat(fl).loc[pred.index]
    flags["fuera_de_dominio"] = flags[names].any(axis=1)
    rows = []
    for scope, d in scopes(pred).items():
        fd = flags.loc[d.index]
        for n in names + ["fuera_de_dominio"]:
            rows.append({"scope": scope, "tipo": "tasa_de_marcas", "variable": n, "method": "", "region": "",
                         "n": int(fd[n].sum()), "tasa": float(fd[n].mean())})
        for c in methods(pred):
            for reg, m in (("dentro", ~fd.fuera_de_dominio), ("fuera", fd.fuera_de_dominio)):
                if m.sum() == 0:
                    continue
                mt = lc.metrics(d[c][m], d.pm[m])
                rows.append({"scope": scope, "tipo": "metricas", "variable": "", "method": c, "region": reg,
                             "n": mt["n"], "rmse": mt["rmse"], "bias": mt["bias"], "mae": mt["mae"]})
        # por estacion (F1): tasa de marcas
        if scope == "F1":
            for s, g in fd.groupby(d.station_code):
                rows.append({"scope": scope, "tipo": "tasa_por_estacion", "variable": s, "method": "", "region": "",
                             "n": int(g.fuera_de_dominio.sum()), "tasa": float(g.fuera_de_dominio.mean())})
    return pd.DataFrame(rows), flags


def seed_spread(seeds, pred):
    acc = {}
    for fid, k, y, sp in seeds:
        if fid.startswith("F1_"):
            a = acc.setdefault(k, {"y": [], "sp": []})
            a["y"].append(y)
            a["sp"].append(sp)
    rows = []
    for k, a in sorted(acc.items()):
        if len(a["y"]) != 9:
            continue
        y, sp = np.concatenate(a["y"]), np.concatenate(a["sp"], axis=1)
        r = np.sqrt(((sp - y) ** 2).mean(1))
        rows.append({"scope": "F1 (cohorte 03.2, n=19251)", "method": k, "n_seeds": len(r),
                     "rmse_ensemble": float(np.sqrt(((sp.mean(0) - y) ** 2).mean())), "rmse_seed_mean": float(r.mean()),
                     "rmse_seed_sd": float(r.std(ddof=1)), "rmse_seed_min": float(r.min()),
                     "rmse_seed_max": float(r.max())})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- figuras
SERIES = ["#257de0", "#f47230", "#00b894", "#f2a600", "#ee7fac", "#008a17"]   # paleta categorica validada (orden fijo)
INK, INK2, GRID = "#1f1f1f", "#6b6b6b", "#e6e6e6"
LABEL = {HGB_S0: "HGB-S0 (03.2)", IDW: "PM IDW del día", PRIMARY_L3: "S0+R1 HGB", MF: "media fija",
         MP: "media ponderada", RIDW: "residuo IDW", "S2+R1|HGB": "S2+R1 HGB", "S0+R1_ayer|HGB": "S0+R1 ayer HGB",
         "S0+R1|Ridge": "S0+R1 Ridge", "S0_res|HGB": "S0_res HGB", "S0_res|Ridge": "S0_res Ridge",
         "S0_res|ANN_M": "S0_res ANN M", "S0_sin_alt|HGB": "S0 sin alt HGB", "S0_sin_alt|ANN_M": "S0 sin alt ANN M",
         "S0_alt_recortada|HGB": "S0 alt recortada HGB", "S0_res_sin_alt|HGB": "S0_res sin alt HGB",
         "S0_res_sin_alt|ANN_M": "S0_res sin alt ANN M", ANN_S0: "ANN M-S0 (03.2)", HGB_S2: "HGB-S2 (03.2)",
         NEAR: "PM estación más cercana", AHC_T: "OM + AHC transferido", OM: "OM crudo"}


def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(INK2)
    ax.tick_params(colors=INK2, labelcolor=INK)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def figures(pc, by_st):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIG.mkdir(exist_ok=True)

    # 1: forest plot F1, Delta RMSE frente a HGB-S0 (03.2) con IC 95 %
    d = pc[(pc.scope == "F1") & (pc.B == HGB_S0) & (pc.A != ANN_S0) & (pc.A.isin(LABEL))].copy()
    d = d[~d.A.str.endswith("|ANN_M")].sort_values("delta_rmse", ascending=False)
    if len(d):
        fig, ax = plt.subplots(figsize=(8.5, 0.42 * len(d) + 1.4))
        y = np.arange(len(d))
        ax.axvspan(-PRACT, PRACT, color="#f2f2f2", zorder=0)
        ax.axvline(0, color=INK2, lw=1)
        ax.hlines(y, d.ci95_lo, d.ci95_hi, color=SERIES[0], lw=2)
        ax.plot(d.delta_rmse, y, "o", ms=8, color=SERIES[0], mec="white", mew=2)
        for yi, (_, r) in zip(y, d.iterrows()):
            ax.text(max(r.ci95_hi, 0) + 0.004, yi, f"{r.delta_rmse:+.3f}", va="center", fontsize=8, color=INK)
        ax.set_yticks(y, [f"{LABEL[a]}  ({r:.3f})" for a, r in zip(d.A, d.rmse_A)])
        ax.set_xlabel("ΔRMSE frente a HGB-S0 del 03.2 (mm/día), IC 95 %; banda gris = ±0,05")
        ax.set_title("F1 (estación no vista): cada método frente a HGB-S0 (RMSE entre paréntesis)", fontsize=10,
                     color=INK, loc="left")
        _style(ax)
        fig.tight_layout()
        fig.savefig(FIG / "01_delta_vs_hgb_s0_F1.png", dpi=150)
        plt.close(fig)

    # 2: RMSE por estacion (F1), IB01 aparte (con su altitud)
    s = by_st[by_st.scope == "F1"].pivot(index="station_code", columns="method", values="rmse")
    ser = [k for k in (HGB_S0, IDW, PRIMARY_L3, MF, RIDW, "S0_res|HGB") if k in s]
    alt = lc.load_stations().altitude_m
    if ser:
        fig, ax = plt.subplots(figsize=(11, 4.4))
        w = 0.8 / len(ser)
        for i, k in enumerate(ser):
            ax.bar(np.arange(len(s)) + (i - (len(ser) - 1) / 2) * w, s[k], w * 0.92, label=LABEL[k], color=SERIES[i])
        ax.set_xticks(range(len(s)), [f"{c}\n{alt.get(c, np.nan):.0f} m" for c in s.index])
        ax.set_ylabel("RMSE (mm/día)")
        ax.set_title("RMSE por estación dejada fuera (F1)", fontsize=10, color=INK, loc="left")
        ax.legend(fontsize=8, ncol=3, frameon=False, loc="upper left")
        _style(ax)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.grid(axis="x", visible=False)
        fig.tight_layout()
        fig.savefig(FIG / "02_rmse_por_estacion_L3.png", dpi=150)
        plt.close(fig)

    # 3: ANN por estacion (L5)
    ser = [k for k in (ANN_S0, "S0_res|ANN_M", "S0_sin_alt|ANN_M", "S0_res_sin_alt|ANN_M", HGB_S0) if k in s]
    if len(ser) > 1:
        top = 1.2
        fig, ax = plt.subplots(figsize=(11, 4.4))
        w = 0.8 / len(ser)
        for i, k in enumerate(ser):
            x = np.arange(len(s)) + (i - (len(ser) - 1) / 2) * w
            ax.bar(x, np.minimum(s[k], top), w * 0.92, label=LABEL[k], color=SERIES[i])
            for xi, v in zip(x, s[k]):
                if v > top:
                    ax.text(xi, top - 0.02, f"{v:.2f}", rotation=90, ha="center", va="top", fontsize=7, color="white")
        ax.set_xticks(range(len(s)), [f"{c}\n{alt.get(c, np.nan):.0f} m" for c in s.index])
        ax.set_ylim(0, top)
        ax.set_ylabel("RMSE (mm/día)")
        ax.set_title("L5: ANN M con objetivo residual y sin altitud frente a ANN M-S0 del 03.2 (F1)", fontsize=10,
                     color=INK, loc="left")
        ax.legend(fontsize=8, ncol=3, frameon=False, loc="upper right")
        _style(ax)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.grid(axis="x", visible=False)
        fig.tight_layout()
        fig.savefig(FIG / "03_ann_por_estacion_L5.png", dpi=150)
        plt.close(fig)

    # 4: F2 (fuera de isla)
    d = pc[pc.scope.str.startswith("F2_") & (pc.B == HGB_S0) & pc.A.isin([PRIMARY_L3, MF, RIDW, IDW, "S0_res|HGB"])]
    if len(d):
        sc = sorted(d.scope.unique())
        arms = [a for a in (PRIMARY_L3, MF, RIDW, IDW, "S0_res|HGB") if a in set(d.A)]
        fig, ax = plt.subplots(figsize=(9, 4))
        w = 0.8 / len(arms)
        for i, a in enumerate(arms):
            r = d[d.A == a].set_index("scope").reindex(sc)
            x = np.arange(len(sc)) + (i - (len(arms) - 1) / 2) * w
            ax.bar(x, r.delta_rmse, w * 0.92, color=SERIES[i], label=LABEL[a])
            ax.vlines(x, r.ci95_lo, r.ci95_hi, color=INK2, lw=1)
        ax.axhline(0, color=INK2, lw=1)
        ax.axhline(PRACT, color=INK2, lw=1, ls=":")
        ax.set_xticks(range(len(sc)), [x.replace("F2_", "fuera ").replace("_informativo", " (informativo)") for x in sc])
        ax.set_ylabel("ΔRMSE frente a HGB-S0 (mm/día), IC 95 %")
        ax.set_title("F2 (fuera de isla): la línea de puntos es +0,05 (H33.3)", fontsize=10, color=INK, loc="left")
        ax.legend(fontsize=8, frameon=False, ncol=3)
        _style(ax)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.grid(axis="x", visible=False)
        fig.tight_layout()
        fig.savefig(FIG / "04_F2_delta_vs_hgb_s0.png", dpi=150)
        plt.close(fig)


# ---------------------------------------------------------------- principal
def main():
    import sklearn
    R.RES.mkdir(exist_ok=True)
    pred, info, missing, counts, wsel, seeds, folds = assemble()
    lc.write_folds(R.RES / "folds.json", folds)
    glob, by_st, by_m = metric_tables(pred)
    glob.to_csv(R.RES / "metrics_global.csv", index=False, float_format="%.6f")
    by_st.to_csv(R.RES / "metrics_by_station.csv", index=False, float_format="%.6f")
    by_m.to_csv(R.RES / "metrics_by_month.csv", index=False, float_format="%.6f")
    pc = paired(pred)
    pc.to_csv(R.RES / "paired_ci.csv", index=False, float_format="%.6f")
    pc[["scope", "hypothesis", "kind", "A", "B", "n", "delta_rmse", "ci90_lo", "ci90_hi", "tost_equivalente_005"]] \
        .to_csv(R.RES / "equivalencia.csv", index=False, float_format="%.6f")
    dom, flags = domain(pred)
    dom.to_csv(R.RES / "dominio.csv", index=False, float_format="%.6f")
    seed_spread(seeds, pred).to_csv(R.RES / "ann_seed_spread.csv", index=False, float_format="%.6f")
    pd.DataFrame(info).sort_values(["model", "arm", "fold"]).to_csv(R.RES / "model_selection.csv", index=False,
                                                                    float_format="%.6f")
    out = pred.copy()
    out["fuera_de_dominio"] = flags.fuera_de_dominio.to_numpy()
    out.to_csv(R.RES / "predictions_test.csv.gz", index=False, float_format="%.5f", compression="gzip")
    conv = lambda o: o.item() if hasattr(o, "item") else str(o)  # noqa: E731
    interp = interpretation(pc)
    (R.RES / "interpretation.json").write_text(json.dumps(interp, indent=2, ensure_ascii=False, default=conv) + "\n",
                                               encoding="utf-8")
    figures(pc, by_st)
    inputs = ["config/thresholds_v3_3.json", "config/thresholds_v3.json", "config/stations.csv",
              "data/reference/reference_2004_2019.csv", "data/reference/reference_2020_2025.csv",
              "data/reference/siar_inputs_2004_2019.csv", "data/reference/siar_inputs_2020_2025.csv",
              "data/processed/openmeteo_archive.csv", "data/v2/et0_v2_annual_2020_2025.csv",
              "studies/03_2_loso_openmeteo_ml/results/predictions_test.csv.gz",
              "studies/03_2_loso_openmeteo_ml/results/folds.json",
              "studies/03_2_loso_openmeteo_ml/loso_common.py", "studies/03_2_loso_openmeteo_ml/loso_models.py",
              "studies/03_2_loso_openmeteo_ml/run.py", "studies/03_1_2_loso_sensor_red/network.py"]
    folds32 = json.loads((R.S032 / "results/folds.json").read_text(encoding="utf-8"))["folds"]
    by_model = {}
    for i in info:
        by_model.setdefault(i["model"], set()).add(i["platform"])
    man = {"study": "03.3", "criteria": "config/thresholds_v3_3.json (congelado)",
           "folds_identicas_al_03_2": folds32 == json.loads((R.RES / "folds.json").read_text(encoding="utf-8"))["folds"],
           "inputs_sha256": {p: lc.sha256(lc.ROOT / p) for p in inputs},
           "versions_report": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
                               "scikit-learn": sklearn.__version__},
           "cell_platforms_by_model": {k: sorted(v) for k, v in by_model.items()},
           "test_run_cells": sorted({f"{i['fold']}__{i['arm']}__{i['model']}" for i in info if i["test_run"]}),
           "seeds": {"bootstrap": lc.BOOT_SEED, "bootstrap_reps": lc.BOOT_REPS, "ANN_M": lm.ANN_SEEDS, "HGB": 0},
           "cohorte": {"rows_F1": int(((pred.scheme == "F1_loso") & pred.en_cohorte).sum()),
                       "rule": "common_core == 1 e interseccion de filas con todos los metodos finitos",
                       "por_particion": counts},
           "media_ponderada_w": {k: {"w": v["w"], "n_rows": v["n_rows"]} for k, v in wsel.items()},
           "media_ponderada_cv": wsel,
           "missing_cells": sorted(missing), "missing_cells_count": len(missing),
           "negatives_clipped_by_model": {m: int(sum(i["negatives_clipped"] for i in info if i["model"] == m))
                                          for m in ("Ridge", "HGB", "ANN_M")}}
    (R.RES / "run_manifest.json").write_text(json.dumps(man, indent=2, ensure_ascii=False, default=conv) + "\n",
                                             encoding="utf-8")
    print(json.dumps({k: interp[k] for k in ("L3", "L5")}, indent=1, ensure_ascii=False, default=conv)[:4000])
    print("celdas que faltan:", len(missing))
