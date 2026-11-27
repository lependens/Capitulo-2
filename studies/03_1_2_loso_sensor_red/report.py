"""Informe del estudio 03.1.2: une las celdas, los comparadores y el conjunto S del 03.1; metricas, IC pareados,
TOST, regla de interpretacion, figuras y manifiesto. Criterios: config/thresholds_v3_1_2.json (congelado).

Reutiliza del 03.1, sin recalcular: las predicciones TEST de S (Ridge, HGB, ANN M, variante principal) y sus
comparadores (IDW, PM de la estacion mas cercana, OM + AHC mensual transferido), de
studies/03_1_loso_inputs_siar/results/predictions_test.csv.gz, comprobando que S coincide con sus celdas.

Nombres de columna: "<escenario>|<conjunto>|<familia>|<modelo>" (R lleva familia NONE). Comparadores con prefijo
del escenario: "B|IDW", "B|vecina", "B|OM_AHC", "C|pers_IDW", "C|pers_vecina", "C|pers_modelo|<fam>|<modelo>",
"C|climatologia", "C|OM_AHC_d1".
"""
from __future__ import annotations

import gzip
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd

import design as ds
from design import lc

HERE = Path(__file__).resolve().parent
RES, FIG = HERE / "results", HERE / "figures"
CELLS = RES / "cells"
S031 = HERE.parent / "03_1_loso_inputs_siar"
THR_PATH = lc.ROOT / "config/thresholds_v3_1_2.json"
THR = json.loads(THR_PATH.read_text(encoding="utf-8"))
MARGIN = THR["statistics"]["practical_threshold_mm_dia"]
KEY = ["fold", "scheme", "station_code", "date"]
FAMS = lc.FAMILIES


def _shift(dates, days):
    return ds._shift(dates, days)


# ---------------------------------------------------------------- carga
def load_031():
    p = pd.read_csv(S031 / "results/predictions_test.csv.gz")
    keep = KEY + ["pm", "PM_IDW_estaciones_entrenamiento_mismo_dia", "PM_estacion_mas_cercana_mismo_dia",
                  "OM_AHC_mensual_medio_entrenamiento"] + [f"{f}|principal|{m}" for f in FAMS
                                                           for m in ("Ridge", "HGB", "ANN_M")]
    p = p[keep].rename(columns={"PM_IDW_estaciones_entrenamiento_mismo_dia": "IDW",
                                "PM_estacion_mas_cercana_mismo_dia": "vecina",
                                "OM_AHC_mensual_medio_entrenamiento": "OM_AHC"})
    return p.rename(columns={f"{f}|principal|{m}": f"S|{f}|{m}" for f in FAMS for m in ("Ridge", "HGB", "ANN_M")})


def check_s_cells(p031):
    """El conjunto S del 03.1 se toma de predictions_test; se comprueba que coincide con sus celdas."""
    n = 0
    for fid in p031.fold.unique():
        d = p031[p031.fold == fid]
        for f in FAMS:
            for m in ("Ridge", "HGB", "ANN_M"):
                c = json.load(gzip.open(S031 / f"results/cells/{fid}__{f}__principal__{m}.json.gz", "rt",
                                        encoding="utf-8"))
                assert list(c["station_code"]) == d.station_code.tolist() and list(c["date"]) == d.date.tolist()
                # predictions_test.csv.gz del 03.1 esta redondeado a 5 decimales: tolerancia de media unidad
                assert np.allclose(np.array(c["pred"]), d[f"S|{f}|{m}"].to_numpy(), rtol=0, atol=5.01e-6), (fid, f, m)
                n += 1
    return n


def load_cells(folds):
    preds, seeds, info, missing = {}, {}, [], []
    for f in folds:
        for (sc, iset, fam, m) in ds.all_cells():
            p = CELLS / f"{f['id']}__{sc}__{iset}__{fam}__{m}.json.gz"
            if not p.exists():
                missing.append(p.name)
                continue
            c = json.load(gzip.open(p, "rt", encoding="utf-8"))
            assert not c.get("test_run"), f"{p.name} es una celda de prueba"
            col = f"{iset}|{fam}|{m}"
            df = pd.DataFrame({"fold": f["id"], "station_code": c["station_code"], "date": c["date"],
                               "value": c["pred"]})
            if "d1_km_test" in c:
                df["d1_km"] = c["d1_km_test"]
            preds.setdefault((sc, col), []).append(df)
            if "seed_preds" in c:
                seeds[(f["id"], sc, col)] = (c["station_code"], c["date"], np.array(c["seed_preds"]))
            info.append({k: c.get(k) for k in ("fold", "scenario", "input_set", "family", "model", "n_features",
                                               "n_train", "rows_dropped_train_empty_pool",
                                               "rows_dropped_test_empty_pool", "params", "negatives_clipped",
                                               "convergence_warnings", "seconds", "d1_km_train_quantiles")}
                        | {"cv_mean_rmse_chosen": min(x["mean_rmse"] for x in c["cv"])})
    return {k: pd.concat(v, ignore_index=True) for k, v in preds.items()}, seeds, info, missing


# ---------------------------------------------------------------- tablas por escenario
def _attach(base, preds, sc):
    d1 = None
    for (s, col), v in preds.items():
        if s != sc:
            continue
        base = base.merge(v[["fold", "station_code", "date", "value"]].rename(columns={"value": f"{sc}|{col}"}),
                          on=["fold", "station_code", "date"], how="left")
        if "d1_km" in v and d1 is None and col.startswith("S_R1"):
            d1 = v[["fold", "station_code", "date", "d1_km"]]
    if d1 is not None:
        base = base.merge(d1, on=["fold", "station_code", "date"], how="left")
    return base


def climatology(df, folds):
    """Media de la PM de las estaciones de entrenamiento en DESARROLLO por mes (todas las filas validas juntas)."""
    out = {}
    dev = df[(df.period == "DEV") & df.target_ok]
    for f in folds:
        g = dev[dev.station_code.isin(f["train"])]
        out[f["id"]] = g.groupby("month").ET0_PM_FAO56_V1.mean().to_dict()
    return out


def tables(preds, p031, df, folds):
    # ---- B (cohort 03.1) con S y comparadores del 03.1
    B = p031.copy()
    for c in [c for c in B.columns if c.startswith("S|")]:
        _, f, m = c.split("|")
        B[f"B|S|{f}|{m}"] = B.pop(c)
    B = B.rename(columns={"IDW": "B|IDW", "vecina": "B|vecina", "OM_AHC": "B|OM_AHC"})
    B = _attach(B, preds, "B")
    # ---- B-ayer: mismas filas que B
    Y = B[KEY + ["pm", "B|IDW"] + [c for c in B.columns if c.startswith("B|S_R1|") or c.startswith("B|R|")]].copy()
    Y = _attach(Y, preds, "Bayer")
    # ---- A
    A = B[KEY + ["pm"] + [c for c in B.columns if c.startswith("B|S|")]].copy()
    A = _attach(A, preds, "A")
    # ---- C: filas d+1 con d tambien en la cohorte
    cf = ds.scenario_frame("C")
    coh = cf[cf.cohort][["station_code", "date"]]
    C = p031[KEY + ["pm", "OM_AHC"]].merge(coh, on=["station_code", "date"], how="inner")
    C = C.rename(columns={"OM_AHC": "C|OM_AHC_d1"})
    C["date_d"] = _shift(C.date, -1)
    prev = B[["fold", "station_code", "date", "B|IDW", "B|vecina"] +
             [c for c in B.columns if c.startswith("B|S_R1|")]].rename(columns={"date": "date_d"})
    prev = prev.rename(columns={"B|IDW": "C|pers_IDW", "B|vecina": "C|pers_vecina"} |
                       {c: "C|pers_modelo|" + c.split("|", 2)[2] for c in prev.columns if c.startswith("B|S_R1|")})
    C = C.merge(prev, on=["fold", "station_code", "date_d"], how="left")
    clim = climatology(df, folds)
    C["C|climatologia"] = [clim[f][int(d[5:7])] for f, d in zip(C.fold, C.date)]
    # coste de horizonte: B|S+R1 en los mismos dias objetivo
    bsame = B[["fold", "station_code", "date"] + [c for c in B.columns if c.startswith("B|S_R1|")]]
    C = C.merge(bsame, on=["fold", "station_code", "date"], how="left")
    C = _attach(C, preds, "C")
    return {"B": B, "Bayer": Y, "A": A, "C": C}


def scopes(t):
    out = {"F1": t[t.scheme == "F1_loso"]}
    for fid in sorted(t.fold.unique()):
        if fid.startswith("F2_"):
            out[fid] = t[t.fold == fid]
    return out


def mcols(t):
    return [c for c in t.columns if "|" in c]


def metric_tables(T):
    g, s, m = [], [], []
    for sc, t in T.items():
        for scope, d in scopes(t).items():
            for c in mcols(t):
                ok = d[c].notna()
                if not ok.any():
                    continue
                g.append({"scenario": sc, "scope": scope, "method": c, **lc.metrics(d[c][ok], d.pm[ok]),
                          "n_missing": int((~ok).sum())})
                for st, gg in d[ok].groupby("station_code"):
                    s.append({"scenario": sc, "scope": scope, "method": c, "station_code": st,
                              **lc.metrics(gg[c], gg.pm)})
                for mo, gg in d[ok].groupby(d[ok].date.str[5:7]):
                    m.append({"scenario": sc, "scope": scope, "method": c, "month": mo, **lc.metrics(gg[c], gg.pm)})
    return pd.DataFrame(g), pd.DataFrame(s), pd.DataFrame(m)


# ---------------------------------------------------------------- comparaciones pareadas
def boot_delta(a, b, ref, bi, draws):
    ea, eb = (a - ref) ** 2, (b - ref) ** 2
    nb = bi.max() + 1
    n = np.bincount(bi, minlength=nb).astype(float)
    sa, sb = np.bincount(bi, ea, nb), np.bincount(bi, eb, nb)
    d0 = float(np.sqrt(sa.sum() / n.sum()) - np.sqrt(sb.sum() / n.sum()))
    N, A, B = n[draws].sum(1), sa[draws].sum(1), sb[draws].sum(1)
    bs = np.sqrt(A / N) - np.sqrt(B / N)
    lo95, hi95 = np.percentile(bs, [2.5, 97.5])
    lo90, hi90 = np.percentile(bs, [5, 95])
    return d0, float(lo95), float(hi95), float(lo90), float(hi90)


def comparisons():
    """(escenario, A, B, tipo, hipotesis si es HGB/F1). Se generan para Ridge, HGB y ANN M cuando existen."""
    out = []
    for m in ("Ridge", "HGB", "ANN_M"):
        H = m == "HGB"
        for f in FAMS:
            s1, s3, s = f"B|S_R1|{f}|{m}", f"B|S_R3|{f}|{m}", f"B|S|{f}|{m}"
            out += [("B", s1, "B|IDW", "S+R1 vs IDW", "G1" if H else ""),
                    ("B", s3, "B|IDW", "S+R3 vs IDW", "G1_R3" if H else ""),
                    ("B", s1, s, "S+R1 vs S", "G2" if H else ""),
                    ("B", s3, s, "S+R3 vs S", ""),
                    ("B", s3, s1, "S+R3 vs S+R1", ""),
                    ("B", s1, "B|vecina", "S+R1 vs vecina", ""),
                    ("B", s1, "B|OM_AHC", "S+R1 vs OM+AHC", ""),
                    ("B", s, "B|IDW", "S vs IDW", "")]
            c1 = f"C|S_R1|{f}|{m}"
            out += [("C", c1, "C|pers_IDW", "C S+R1 vs persistencia IDW", "P1" if H else ""),
                    ("C", c1, "C|pers_vecina", "C S+R1 vs persistencia vecina", ""),
                    ("C", c1, f"C|pers_modelo|{f}|{m}", "C S+R1 vs persistencia modelo", ""),
                    ("C", c1, "C|climatologia", "C S+R1 vs climatologia", ""),
                    ("C", c1, "C|OM_AHC_d1", "C S+R1 vs OM+AHC d+1 (informativo)", ""),
                    ("C", c1, f"C|R|NONE|{m}", "C S+R1 vs C R", "P2" if H else ""),
                    ("C", f"C|S_R3|{f}|{m}", "C|pers_IDW", "C S+R3 vs persistencia IDW", ""),
                    ("C", f"C|S|{f}|{m}", "C|pers_IDW", "C S vs persistencia IDW", ""),
                    ("C", c1, f"C|S|{f}|{m}", "C S+R1 vs C S", ""),
                    ("C", c1, f"B|S_R1|{f}|{m}", "coste de horizonte: C S+R1 (d+1) vs B S+R1 (d)", "")]
            out += [("Bayer", f"Bayer|S_R1|{f}|{m}", f"B|S_R1|{f}|{m}", "B-ayer S+R1 vs B S+R1", ""),
                    ("Bayer", f"Bayer|S_R1|{f}|{m}", "B|IDW", "B-ayer S+R1 vs IDW", ""),
                    ("A", f"A|S_costa|{f}|{m}", f"B|S|{f}|{m}", "S+costa vs S", "")]
        out += [("B", f"B|R|NONE|{m}", "B|IDW", "R vs IDW", "G3" if H else ""),
                ("B", f"B|R|NONE|{m}", "B|vecina", "R vs vecina", ""),
                ("C", f"C|R|NONE|{m}", "C|pers_IDW", "C R vs persistencia IDW", ""),
                ("Bayer", f"Bayer|R|NONE|{m}", f"B|R|NONE|{m}", "B-ayer R vs B R", ""),
                ("Bayer", f"Bayer|R|NONE|{m}", "B|IDW", "B-ayer R vs IDW", "")]
    out += [("C", "C|pers_IDW", "C|pers_vecina", "persistencia IDW vs persistencia vecina", ""),
            ("C", "C|pers_IDW", "C|climatologia", "persistencia IDW vs climatologia", "")]
    return out


def paired(T):
    rows = []
    for sc, t in T.items():
        for scope, d in scopes(t).items():
            bi, _ = lc.block_index(d.station_code, d.date)
            draws = lc.boot_draws(bi.max() + 1)
            for (s2, a, b, kind, hyp) in comparisons():
                if s2 != sc or a not in d or b not in d:
                    continue
                ok = d[a].notna() & d[b].notna()
                if ok.sum() == 0:
                    continue
                if not ok.all():   # mismas filas para A y B; se informa n
                    bi2, _ = lc.block_index(d.station_code[ok], d.date[ok])
                    dr2 = lc.boot_draws(bi2.max() + 1)
                else:
                    bi2, dr2 = bi, draws
                ref = d.pm[ok].to_numpy()
                d0, lo, hi, lo9, hi9 = boot_delta(d[a][ok].to_numpy(), d[b][ok].to_numpy(), ref, bi2, dr2)
                rows.append({"scenario": sc, "scope": scope, "hypothesis": hyp if scope == "F1" else "",
                             "kind": kind, "A": a, "B": b, "n": int(ok.sum()), "n_blocks": int(bi2.max() + 1),
                             "rmse_A": lc.metrics(d[a][ok], ref)["rmse"], "rmse_B": lc.metrics(d[b][ok], ref)["rmse"],
                             "delta_rmse": d0, "ci95_lo": lo, "ci95_hi": hi, "ci90_lo": lo9, "ci90_hi": hi9,
                             "equivalente_tost": bool(lo9 > -MARGIN and hi9 < MARGIN),
                             "margen_min_equivalencia": max(abs(lo9), abs(hi9)),
                             "verdict": ("A gana" if hi < 0 else "A pierde" if lo > 0 else "IC incluye 0")})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- regla de interpretacion (literal de los criterios)
def rule(r):
    if r.ci95_hi < 0 and r.delta_rmse <= -MARGIN:
        return 1, "sensor + red"
    if r.ci95_hi < 0:
        return 2, "mejora estadistica sin interes practico: cerca de la red basta la red; sensor solo lejos (F2, 03.3)"
    if r.ci95_lo <= 0 <= r.ci95_hi and r.equivalente_tost:
        return 3, "equivalentes (TOST): basta la red; sensor solo lejos (F2, 03.3)"
    if r.ci95_lo > 0:
        return 4, "S+R1 pierde frente a la IDW: el sensor no aporta en esta red"
    return 5, f"no concluyente (margen minimo de equivalencia {r.margen_min_equivalencia:.3f})"


def interpretation(pc):
    f1 = pc[(pc.scope == "F1")]
    out = {"_comment": "Aplicacion literal de interpretation_rule de config/thresholds_v3_1_2.json (HGB, F1).",
           "B": {}, "C": {}, "hipotesis": {}}
    for f in FAMS:
        for hyp in ("G1", "G1_R3"):
            r = f1[(f1.hypothesis == hyp) & f1.A.str.contains(f"\\|{f}\\|")]
            if len(r):
                r = r.iloc[0]
                case, txt = rule(r)
                out["B"][f"{f}|{'S+R1' if hyp == 'G1' else 'S+R3'}"] = {
                    "delta_rmse": r.delta_rmse, "ci95": [r.ci95_lo, r.ci95_hi], "ci90": [r.ci90_lo, r.ci90_hi],
                    "caso": case, "lectura": txt, "rige": f == "VALIANTZAS" and hyp == "G1",
                    "aparte_piranometro": f == "HG_RS"}
        r = f1[(f1.hypothesis == "P1") & f1.A.str.contains(f"\\|{f}\\|")]
        if len(r):
            r = r.iloc[0]
            ok = bool(r.ci95_hi < 0)
            out["C"][f] = {"delta_rmse": r.delta_rmse, "ci95": [r.ci95_lo, r.ci95_hi], "P1_se_cumple": ok,
                           "lectura": "la prevision a un dia gana a la persistencia" if ok else
                           "P1 no se cumple: la prevision a un dia sin modelo meteorologico no aporta; el estudio 04 "
                           "debe partir de previsiones meteorologicas"}
    for _, r in f1[f1.hypothesis != ""].iterrows():
        out["hipotesis"][f"{r.hypothesis}|{r.A}"] = {"B": r.B, "delta_rmse": r.delta_rmse,
                                                     "ci95": [r.ci95_lo, r.ci95_hi], "verdict": r.verdict,
                                                     "equivalente_tost": r.equivalente_tost}
    return out


# ---------------------------------------------------------------- figuras
def _forest(ax, d, title):
    d = d.reset_index(drop=True)
    for i, r in d.iterrows():
        col = "tab:blue" if r.ci95_hi < 0 else "tab:red" if r.ci95_lo > 0 else "0.4"
        ax.plot([r.ci95_lo, r.ci95_hi], [i, i], color=col, lw=1.2)
        ax.plot([r.ci90_lo, r.ci90_hi], [i, i], color=col, lw=4, alpha=.5)
        ax.plot(r.delta_rmse, i, "o", color=col)
    ax.axvspan(-MARGIN, MARGIN, color="0.9", zorder=0)
    ax.axvline(0, color="0.5", lw=.8)
    ax.set_yticks(range(len(d)))
    ax.set_yticklabels(d.label, fontsize=7)
    ax.invert_yaxis()
    ax.set_title(title, fontsize=9)
    ax.set_xlabel("ΔRMSE A − B (mm/día) · fino IC95, grueso IC90")


def figures(pc, T):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIG.mkdir(exist_ok=True)
    f1 = pc[pc.scope == "F1"].copy()
    f1["label"] = f1.A.str.split("|").str[1:].str.join(" ") + "  vs  " + f1.B.str.replace("B|", "").str.replace("C|", "")
    groups = {"01_G1_G3_vs_IDW.png": (["S+R1 vs IDW", "S+R3 vs IDW", "R vs IDW", "S vs IDW"], "B: frente a la IDW del mismo día (G1, G3)"),
              "02_G2_red_sobre_sensor.png": (["S+R1 vs S", "S+R3 vs S", "S+R3 vs S+R1"], "B: la red sobre el sensor (G2)"),
              "03_P1_P2_prevision.png": (["C S+R1 vs persistencia IDW", "C S+R1 vs persistencia vecina",
                                          "C S+R1 vs persistencia modelo", "C S+R1 vs climatologia", "C S+R1 vs C R",
                                          "C R vs persistencia IDW"], "C: previsión a d+1 (P1, P2)"),
              "05_secundarios_Bayer_A_horizonte.png": (["B-ayer S+R1 vs B S+R1", "B-ayer S+R1 vs IDW", "S+costa vs S",
                                                        "coste de horizonte: C S+R1 (d+1) vs B S+R1 (d)"],
                                                       "Secundarios sin veredicto: B-ayer, A (costa) y coste de horizonte")}
    for fn, (kinds, title) in groups.items():
        d = f1[f1.kind.isin(kinds)].sort_values(["kind", "A"])
        if d.empty:
            continue
        fig, ax = plt.subplots(figsize=(8, 0.28 * len(d) + 1.5))
        _forest(ax, d, title + " — F1, banda gris ±0,05")
        fig.tight_layout()
        fig.savefig(FIG / fn, dpi=150)
        plt.close(fig)
    # error frente a la distancia a la red (por estacion y particion; F1 y F2)
    B = T["B"]
    if "d1_km" in B:
        rows = []
        for (fid, st), g in B.groupby(["fold", "station_code"]):
            r = {"fold": fid, "station_code": st, "d1_km": g.d1_km.median()}
            for c in ["B|IDW", "B|vecina", "B|S|VALIANTZAS|HGB", "B|S_R1|VALIANTZAS|HGB", "B|S|HG_RS|HGB",
                      "B|S_R1|HG_RS|HGB", "B|R|NONE|HGB"]:
                if c in g and g[c].notna().all():
                    r[c] = lc.metrics(g[c], g.pm)["rmse"]
            rows.append(r)
        e = pd.DataFrame(rows)
        e.round(4).to_csv(RES / "error_vs_distancia_red.csv", index=False)
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for c in [c for c in e.columns if c.startswith("B|")]:
            ax.plot(e.d1_km, e[c], "o", alpha=.75, label=c.replace("B|", ""))
        ax.set_xlabel("d₁: distancia a la estación de entrenamiento más cercana (km, mediana)")
        ax.set_ylabel("RMSE (mm/día)")
        ax.set_title("B: error frente a la distancia a la red (por estación y partición, F1 y F2)", fontsize=9)
        ax.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(FIG / "04_error_vs_distancia_red.png", dpi=150)
        plt.close(fig)


# ---------------------------------------------------------------- dispersion de semillas
def seed_spread(seeds, T):
    rows = []
    for (fid, sc, col), (st, dt, sp) in seeds.items():
        t = T["C" if sc == "C" else "B"]
        ref = t[(t.fold == fid)].set_index(["station_code", "date"]).pm.reindex(list(zip(st, dt))).to_numpy()
        r = [float(np.sqrt(np.mean((s - ref) ** 2))) for s in sp]
        rows.append({"fold": fid, "scenario": sc, "method": col, "rmse_seed_mean": np.mean(r),
                     "rmse_seed_sd": np.std(r, ddof=1), "rmse_ensemble": float(np.sqrt(np.mean((sp.mean(0) - ref) ** 2)))})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- principal
def main():
    df = lc.load_panel()
    folds = lc.build_folds()
    p031 = load_031()
    n_s = check_s_cells(p031)
    preds, seeds, info, missing = load_cells(folds)
    T = tables(preds, p031, df, folds)
    glob, by_st, by_mo = metric_tables(T)
    pc = paired(T)
    RES.mkdir(exist_ok=True)
    glob.round(5).to_csv(RES / "metrics_global.csv", index=False)
    by_st.round(5).to_csv(RES / "metrics_by_station.csv", index=False)
    by_mo.round(5).to_csv(RES / "metrics_by_month.csv", index=False)
    pc.round(5).to_csv(RES / "paired_ci.csv", index=False)
    pc[["scenario", "scope", "kind", "A", "B", "n", "delta_rmse", "ci90_lo", "ci90_hi", "equivalente_tost",
        "margen_min_equivalencia"]].round(5).to_csv(RES / "equivalencia.csv", index=False)
    pd.DataFrame(info).to_csv(RES / "model_selection.csv", index=False)
    if seeds:
        seed_spread(seeds, T).round(5).to_csv(RES / "ann_seed_spread.csv", index=False)
    with gzip.open(RES / "predictions_test.csv.gz", "wt", encoding="utf-8") as fh:
        pd.concat([t.assign(scenario=k) for k, t in T.items()], ignore_index=True).to_csv(fh, index=False)
    interp = interpretation(pc)
    (RES / "interpretation.json").write_text(json.dumps(interp, indent=2, ensure_ascii=False,
                                                        default=lambda o: o.item() if hasattr(o, "item") else str(o))
                                             + "\n", encoding="utf-8")
    figures(pc, T)
    lc.write_folds(RES / "folds.json", folds)
    inputs = ["config/thresholds_v3_1_2.json", "config/thresholds_v3.json", "config/stations.csv",
              "config/stations_coast.csv", "data/reference/reference_2004_2019.csv",
              "data/reference/reference_2020_2025.csv", "data/reference/siar_inputs_2004_2019.csv",
              "data/reference/siar_inputs_2020_2025.csv", "data/v2/et0_v2_annual_2020_2025.csv",
              "studies/03_1_loso_inputs_siar/results/predictions_test.csv.gz",
              "studies/03_1_loso_inputs_siar/results/folds.json"]
    rows_n = {k: {sc: int(len(d)) for sc, d in scopes(t).items()} for k, t in T.items()}
    man = {"study": "03.1.2", "criteria_status": THR["status"],
           "inputs_sha256": {p: lc.sha256(lc.ROOT / p) for p in inputs if (lc.ROOT / p).exists()},
           "cells_found": len(info), "cells_expected": len(ds.all_cells()) * len(folds), "missing_cells": missing,
           "s_cells_031_checked": n_s, "rows_by_scenario_scope": rows_n,
           "rows_dropped_test_empty_pool": int(sum(i["rows_dropped_test_empty_pool"] or 0 for i in info)),
           "python": platform.python_version()}
    (RES / "run_manifest.json").write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(interp["B"], indent=2, ensure_ascii=False, default=str))
    print(f"celdas: {len(info)} de {man['cells_expected']}; faltan {len(missing)}")


if __name__ == "__main__":
    main()
