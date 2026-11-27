"""Informe del estudio 03.2: une celdas, comparadores, metricas, IC pareados, veredictos, figuras y manifiesto.

Uso: python studies/03_loso_openmeteo_ml/run.py report
Criterios: config/thresholds_v3.json (congelado). Las hipotesis se evaluan de forma literal (ver decision()).
"""
from __future__ import annotations

import gzip
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run import CELLS, HEAVY, MODELS, RES, SCENARIOS, lc, lm  # noqa: E402

FIG = HERE / "figures"
THR = json.loads((lc.ROOT / "config/thresholds_v3.json").read_text(encoding="utf-8"))
PRACT = THR["statistics"]["practical_threshold_mm_dia"]
V2_METHODS = ["FORMULA", "AHC", "ANN_A", "ANN_E", "ML"]
RESOLUTIONS = ["annual", "seasonal", "monthly"]
OM_AHC_T = "OM_AHC_mensual_medio_entrenamiento"
OM_AHC_N = "OM_AHC_mensual_estacion_mas_cercana"
PM_N = "PM_estacion_mas_cercana_mismo_dia"
PM_IDW = "PM_IDW_estaciones_entrenamiento_mismo_dia"
COMPARATORS = ["OM_crudo", OM_AHC_T, OM_AHC_N, PM_N, PM_IDW]


# ---------------------------------------------------------------- comparadores (mismo codigo que el 03.1)
def fold_baselines(df, fold, dist):
    test = lc.test_cohort(df)
    test = test[test.station_code.isin(fold["test"])].copy()
    dev = df[(df.period == "DEV") & df.target_ok & df.station_code.isin(fold["train"])]
    om_dev = dev[np.isfinite(dev["et0_om_mm"])]
    cols = {"OM_crudo": test["et0_om_mm"].to_numpy()}
    per = lc.ahc_by_station(om_dev, "et0_om_mm", "monthly")
    cols[OM_AHC_T] = lc.apply_ahc(test, "et0_om_mm", lc.mean_coefs(per, fold["train"]), "monthly")
    nb = np.empty(len(test))
    for s in fold["test"]:
        m = (test.station_code == s).to_numpy()
        nb[m] = lc.apply_ahc(test[m], "et0_om_mm", per[lc.neighbours(s, fold["train"], dist)[0]], "monthly")
    cols[OM_AHC_N] = nb
    near, idw, fb = lc.pm_nearest_and_idw(df, test, fold["train"], dist)
    cols[PM_N], cols[PM_IDW] = near, idw
    return test, cols, fb


def techo_local(test):
    """Techo (no LOSO, solo contexto): V2 local y OM + AHC local del estudio 02, mismas claves."""
    out, keys = {}, test[["station_code", "date"]]
    for res in RESOLUTIONS:
        v2 = pd.read_csv(lc.ROOT / f"data/v2/et0_v2_{res}_2020_2025.csv").rename(columns={"station_id": "station_code"})
        t = keys.merge(v2, on=["station_code", "date"], how="left")
        for fam, v2fam in lc.V2_FAMILY.items():
            for m in V2_METHODS:
                out[f"techo|V2_{fam}_{m}_{res}"] = t[f"{v2fam}_{m}"].to_numpy()
    s02 = pd.read_csv(lc.ROOT / "studies/02_openmeteo_ahc/results/predictions_openmeteo_2020_2025.csv")
    for res in RESOLUTIONS:
        t = keys.merge(s02[s02.resolution == res], on=["station_code", "date"], how="left")
        out[f"techo|OM_AHC_local_{res}"] = t["om_ahc"].to_numpy()
    return out


def load_cells(fold_id, test):
    cols, seeds, info, missing = {}, {}, [], []
    key = (test.station_code + "|" + test.date).to_numpy()
    for scen in SCENARIOS:
        for m in MODELS:
            p = CELLS / f"{fold_id}__{scen}__{m}.json.gz"
            if not p.exists():
                missing.append(p.name)
                continue
            c = json.load(gzip.open(p, "rt", encoding="utf-8"))
            k = np.array([f"{s}|{d}" for s, d in zip(c["station_code"], c["date"])])
            assert (k == key).all(), f"orden de filas distinto en {p.name}"
            cols[f"{scen}|{m}"] = np.array(c["pred"])
            if "seed_preds" in c:
                seeds[f"{scen}|{m}"] = np.array(c["seed_preds"])
            chosen = min(c["cv"], key=lambda x: x["mean_rmse"])
            info.append({"fold": c["fold"], "scenario": scen, "model": m, "n_train": c["n_train"],
                         "params": json.dumps(c["params"]), "cv_mean_rmse_chosen": chosen["mean_rmse"],
                         "negatives_clipped": c["negatives_clipped"],
                         "convergence_warnings": c["convergence_warnings"], "seconds": c["seconds"],
                         "platform": c.get("env", {}).get("platform", "")})
    return cols, seeds, info, missing


def assemble():
    df = lc.load_panel()
    dist = lc.distances()
    folds = lc.build_folds()
    blocks, info, missing, fallbacks, seed_blocks = [], [], [], {}, []
    for f in folds:
        test, cols, fb = fold_baselines(df, f, dist)
        cc, seeds, inf, miss = load_cells(f["id"], test)
        cols.update(cc)
        cols.update(techo_local(test))
        fallbacks[f["id"]] = fb
        info += inf
        missing += miss
        blocks.append(pd.DataFrame({"fold": f["id"], "scheme": f["scheme"],
                                    "station_code": test.station_code.to_numpy(), "date": test.date.to_numpy(),
                                    "pm": test.ET0_PM_FAO56_V1.to_numpy()} | cols))
        for k, sp in seeds.items():
            seed_blocks.append((f["id"], k, test.ET0_PM_FAO56_V1.to_numpy(), sp))
    return pd.concat(blocks, ignore_index=True), info, missing, fallbacks, seed_blocks, folds


# ---------------------------------------------------------------- metricas
def scopes(pred):
    out = {"F1": pred[pred.scheme == "F1_loso"]}
    for fid in sorted(pred.fold.unique()):
        if fid.startswith("F2_"):
            out[fid] = pred[pred.fold == fid]
    return out


def method_cols(pred):
    return [c for c in pred.columns if c not in ("fold", "scheme", "station_code", "date", "pm")]


def metric_tables(pred):
    g_rows, s_rows, m_rows = [], [], []
    for scope, d in scopes(pred).items():
        season = lc.season_label(d.date).str[5:]
        for c in method_cols(pred):
            if d[c].isna().all():
                continue
            ok = d[c].notna()
            g_rows.append({"scope": scope, "method": c, **lc.metrics(d[c][ok], d.pm[ok]),
                           "n_missing": int((~ok).sum())})
            for s, g in d[ok].groupby("station_code"):
                s_rows.append({"scope": scope, "method": c, "station_code": s, **lc.metrics(g[c], g.pm)})
            for mth, g in d[ok].groupby(d[ok].date.str[5:7]):
                m_rows.append({"scope": scope, "method": c, "breakdown": "month", "key": mth, **lc.metrics(g[c], g.pm)})
            for sea, g in d[ok].groupby(season[ok]):
                m_rows.append({"scope": scope, "method": c, "breakdown": "season", "key": sea, **lc.metrics(g[c], g.pm)})
            for yr, g in d[ok].groupby(d[ok].date.str[:4]):
                m_rows.append({"scope": scope, "method": c, "breakdown": "year", "key": yr, **lc.metrics(g[c], g.pm)})
    return pd.DataFrame(g_rows), pd.DataFrame(s_rows), pd.DataFrame(m_rows)


def verdict(d0, lo, hi):
    if hi < 0:
        v = "A gana"
    elif lo > 0:
        v = "B gana"
    else:
        return "empate (IC incluye 0)"
    return v + (" (significativa pero pequena)" if abs(d0) < PRACT else "")


HYPOTHESES = {  # (A, B) en F1, literal de thresholds_v3.json
    "H1": ("S0|HGB", OM_AHC_T),
    "H2": ("S0|HGB", PM_N),
    "H3": ("S2|HGB", "S0|HGB"),
    "H4_L1": ("L1|HGB", "S0|HGB"),
    "H4_L2": ("L2|HGB", "S0|HGB"),
}


def comparisons():
    """Lista de (kind, A, B). Las de las hipotesis van primero; el resto es secundario."""
    out = [("hipotesis", a, b) for a, b in HYPOTHESES.values()]
    for scen in SCENARIOS:
        for m in MODELS:
            a = f"{scen}|{m}"
            for b in COMPARATORS:
                out.append(("vs_comparador", a, b))
            if scen != "S0":
                out.append(("escenario_vs_S0", a, f"S0|{m}"))
            if m != "HGB":
                out.append(("modelo_vs_HGB", a, f"{scen}|HGB"))
        out.append(("vs_techo_OM_AHC_local", f"{scen}|HGB", "techo|OM_AHC_local_monthly"))
        for fam in ("HS_RA", "VALIANTZAS", "HG_RS"):  # techo V2 local (mejor V2: ANN E anual); sin veredicto
            out.append(("vs_techo_V2_ANN_E_anual", f"{scen}|HGB", f"techo|V2_{fam}_ANN_E_annual"))
    out += [("comparadores", OM_AHC_T, PM_N), ("comparadores", PM_IDW, PM_N), ("comparadores", OM_AHC_N, OM_AHC_T)]
    seen, uniq = set(), []
    for k, a, b in out:
        if (a, b) not in seen:
            seen.add((a, b))
            uniq.append((k, a, b))
    return uniq


def paired(pred):
    rows = []
    hyp_of = {v: k for k, v in HYPOTHESES.items()}
    for scope, d in scopes(pred).items():
        bi, _ = lc.block_index(d.station_code, d.date)
        draws = lc.boot_draws(bi.max() + 1)
        for kind, a, b in comparisons():
            if a not in d or b not in d or d[a].isna().any() or d[b].isna().any():
                continue
            d0, lo, hi = lc.paired_delta_ci(d[a].to_numpy(), d[b].to_numpy(), d.pm.to_numpy(), bi, draws)
            rows.append({"scope": scope, "hypothesis": hyp_of.get((a, b), "") if scope == "F1" else "",
                         "kind": kind, "A": a, "B": b, "n": len(d), "n_blocks": int(bi.max() + 1),
                         "rmse_A": lc.metrics(d[a], d.pm)["rmse"], "rmse_B": lc.metrics(d[b], d.pm)["rmse"],
                         "delta_rmse": d0, "ci95_lo": lo, "ci95_hi": hi, "verdict": verdict(d0, lo, hi)})
    return pd.DataFrame(rows)


def decision(pc):
    """Aplicacion literal de thresholds_v3.json -> hypotheses (solo F1, HGB)."""
    h = pc[(pc.scope == "F1") & (pc.hypothesis != "")].set_index("hypothesis")
    out = {"umbral_practico_mm_dia": PRACT, "hipotesis": {}}

    def row(k):
        r = h.loc[k]
        return {"A": r.A, "B": r.B, "rmse_A": r.rmse_A, "rmse_B": r.rmse_B, "delta_rmse": r.delta_rmse,
                "ci95": [r.ci95_lo, r.ci95_hi], "pequena": bool(abs(r.delta_rmse) < PRACT)}

    for k, crit, test in (("H1", "Delta RMSE < 0 y extremo superior del IC < 0", lambda r: r["delta_rmse"] < 0 and r["ci95"][1] < 0),
                          ("H2", "Delta RMSE < 0 y extremo superior del IC < 0", lambda r: r["delta_rmse"] < 0 and r["ci95"][1] < 0),
                          ("H3", "extremo superior del IC < 0", lambda r: r["ci95"][1] < 0)):
        if k in h.index:
            r = row(k)
            r["criterio"], r["cumple"] = crit, bool(test(r))
            out["hipotesis"][k] = r
    if "H4_L1" in h.index and "H4_L2" in h.index:
        parts = {k: row(k) for k in ("H4_L1", "H4_L2")}
        out["hipotesis"]["H4"] = {"criterio": "HGB-L1 y HGB-L2 > HGB-S0: extremo inferior del IC > 0 en ambas",
                                  "partes": parts, "cumple": all(p["ci95"][0] > 0 for p in parts.values())}
    return out


def seed_spread(seed_blocks):
    acc = {}
    for fid, key, y, sp in seed_blocks:
        if fid.startswith("F1_"):
            a = acc.setdefault(key, {"y": [], "sp": []})
            a["y"].append(y)
            a["sp"].append(sp)
    rows = []
    for key, a in sorted(acc.items()):
        if len(a["y"]) != 9:
            continue
        y, sp = np.concatenate(a["y"]), np.concatenate(a["sp"], axis=1)
        r = np.sqrt(((sp - y) ** 2).mean(1))
        scen, m = key.split("|")
        rows.append({"scope": "F1", "scenario": scen, "model": m, "n_seeds": len(r),
                     "rmse_ensemble": float(np.sqrt(((sp.mean(0) - y) ** 2).mean())),
                     "rmse_seed_mean": float(r.mean()), "rmse_seed_sd": float(r.std(ddof=1)),
                     "rmse_seed_min": float(r.min()), "rmse_seed_max": float(r.max()),
                     "pred_sd_between_seeds_mean": float(sp.std(0, ddof=1).mean())})
    return pd.DataFrame(rows, columns=["scope", "scenario", "model", "n_seeds", "rmse_ensemble", "rmse_seed_mean",
                                       "rmse_seed_sd", "rmse_seed_min", "rmse_seed_max",
                                       "pred_sd_between_seeds_mean"])


# ---------------------------------------------------------------- figuras
COMP_LABEL = {"OM_crudo": "OM crudo", OM_AHC_T: "OM + AHC transferido", OM_AHC_N: "OM + AHC vecino",
              PM_N: "PM estación más cercana", PM_IDW: "PM IDW"}
COLORS = {"Ridge": "#9D9D9D", "HGB": "#E45756", "RF": "#54A24B", "ANN_S": "#4C78A8", "ANN_M": "#B279A2"}


def figures(glob, by_st, by_m):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIG.mkdir(exist_ok=True)
    g = glob[glob.scope == "F1"].set_index("method").rmse

    # 1: RMSE por escenario y modelo (F1) con los comparadores
    fig, ax = plt.subplots(figsize=(11, 4.8))
    models = [m for m in MODELS if any(f"{s}|{m}" in g for s in SCENARIOS)]
    w = 0.8 / max(1, len(models))
    for i, m in enumerate(models):
        vals = [g.get(f"{s}|{m}", np.nan) for s in SCENARIOS]
        ax.bar(np.arange(len(SCENARIOS)) + (i - (len(models) - 1) / 2) * w, vals, w, label=m, color=COLORS[m])
    for k, ls in ((OM_AHC_T, "--"), (PM_N, ":"), (PM_IDW, "-."), ("OM_crudo", "-")):
        ax.axhline(g[k], ls=ls, lw=1, color="k", alpha=0.7, label=f"{COMP_LABEL[k]} {g[k]:.3f}")
    ax.set_xticks(range(len(SCENARIOS)), ["S0 sin sensor", "S1 +T", "S2 +T,HR", "L1 solo T", "L2 solo T,HR",
                                          "S0+coord (sens.)"])
    ax.set_ylabel("RMSE frente a PM (mm/día), TEST 2020–2025")
    ax.set_title("Estación no vista (F1, n = 19.251): Open-Meteo corregido con ML frente a alternativas")
    top = 1.0
    for i, m in enumerate(models):  # barras recortadas por el eje: se rotula su valor
        for j, s_ in enumerate(SCENARIOS):
            v = g.get(f"{s_}|{m}", np.nan)
            if np.isfinite(v) and v > top:
                ax.text(j + (i - (len(models) - 1) / 2) * w, top - 0.01, f"{v:.2f}", rotation=90,
                        ha="center", va="top", fontsize=7, color="white", fontweight="bold")
    ax.legend(fontsize=8, ncol=1, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    ax.set_ylim(0, top)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG / "01_rmse_escenario_modelo.png", dpi=150)
    plt.close(fig)

    # 2: por estacion
    s = by_st[by_st.scope == "F1"].pivot(index="station_code", columns="method", values="rmse")
    series = [("HGB S0", "S0|HGB"), ("HGB S2", "S2|HGB"), ("HGB L2", "L2|HGB"), (COMP_LABEL[OM_AHC_T], OM_AHC_T),
              (COMP_LABEL[PM_N], PM_N), (COMP_LABEL[PM_IDW], PM_IDW)]
    series = [x for x in series if x[1] in s]
    fig, ax = plt.subplots(figsize=(11, 4.5))
    w = 0.8 / len(series)
    for i, (lab, k) in enumerate(series):
        ax.bar(np.arange(len(s)) + (i - (len(series) - 1) / 2) * w, s[k], w, label=lab)
    ax.set_xticks(range(len(s)), s.index)
    ax.set_ylabel("RMSE (mm/día)")
    ax.set_title("RMSE por estación dejada fuera (F1)")
    ax.set_ylim(0, 0.9)
    ax.legend(fontsize=8, ncol=6, loc="upper left")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG / "02_rmse_por_estacion.png", dpi=150)
    plt.close(fig)

    # 4: ANN frente a HGB y RF por estacion (S0): extrapolacion en altitud
    alt = lc.load_stations().altitude_m
    keys = [(m, f"S0|{m}") for m in ("HGB", "RF", "ANN_S", "ANN_M") if f"S0|{m}" in s]
    if keys:
        fig, ax = plt.subplots(figsize=(11, 4.5))
        w = 0.8 / len(keys)
        top = 1.2
        for i, (lab, k) in enumerate(keys):
            x = np.arange(len(s)) + (i - (len(keys) - 1) / 2) * w
            ax.bar(x, np.minimum(s[k], top), w, label=lab, color=COLORS[lab])
            for xi, v in zip(x, s[k]):
                if v > top:
                    ax.text(xi, top - 0.02, f"{v:.2f}", rotation=90, ha="center", va="top", fontsize=7,
                            color="white", fontweight="bold")
        ax.set_xticks(range(len(s)), [f"{c}\n{alt.get(c, np.nan):.0f} m" for c in s.index])
        ax.set_ylabel("RMSE (mm/día)")
        ax.set_title("S0 por estación dejada fuera (F1): las ANN fallan donde la altitud queda fuera del rango "
                     "de entrenamiento (IB01, 120 m; resto 4–82 m)", fontsize=10)
        ax.set_ylim(0, top)
        ax.legend(fontsize=8, ncol=4, loc="upper right")
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(FIG / "04_ann_por_estacion_altitud.png", dpi=150)
        plt.close(fig)

    # 3: por mes
    mm = by_m[(by_m.scope == "F1") & (by_m.breakdown == "month")].pivot(index="key", columns="method", values="rmse")
    fig, ax = plt.subplots(figsize=(10, 4.2))
    for lab, k in series + [("OM crudo", "OM_crudo")]:
        if k in mm:
            ax.plot(mm.index.astype(int), mm[k], marker="o", ms=3, label=lab)
    ax.set_xticks(range(1, 13))
    ax.set_xlabel("Mes")
    ax.set_ylabel("RMSE (mm/día)")
    ax.set_title("RMSE por mes (F1)")
    ax.legend(fontsize=8, ncol=2)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG / "03_rmse_por_mes.png", dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------- principal
def main():
    import sklearn
    RES.mkdir(exist_ok=True)
    pred, info, missing, fallbacks, seed_blocks, folds = assemble()
    lc.write_folds(RES / "folds.json", folds)
    glob, by_st, by_m = metric_tables(pred)
    glob.to_csv(RES / "metrics_global.csv", index=False, float_format="%.6f")
    by_st.to_csv(RES / "metrics_by_station.csv", index=False, float_format="%.6f")
    by_m.to_csv(RES / "metrics_by_month.csv", index=False, float_format="%.6f")
    pc = paired(pred)
    pc.to_csv(RES / "paired_ci.csv", index=False, float_format="%.6f")
    seed_spread(seed_blocks).to_csv(RES / "ann_seed_spread.csv", index=False, float_format="%.6f")
    pd.DataFrame(info).sort_values(["model", "scenario", "fold"]).to_csv(RES / "model_selection.csv", index=False,
                                                                        float_format="%.6f")
    keep = ["fold", "scheme", "station_code", "date", "pm"] + [c for c in method_cols(pred) if not c.startswith("techo|")]
    pred[keep].to_csv(RES / "predictions_test.csv.gz", index=False, float_format="%.5f", compression="gzip")
    dec = decision(pc)
    conv = lambda o: o.item() if hasattr(o, "item") else str(o)  # noqa: E731
    (RES / "decision.json").write_text(json.dumps(dec, indent=2, ensure_ascii=False, default=conv) + "\n",
                                       encoding="utf-8")
    figures(glob, by_st, by_m)
    inputs = ["config/thresholds_v3.json", "config/stations.csv",
              "data/reference/reference_2004_2019.csv", "data/reference/reference_2020_2025.csv",
              "data/reference/siar_inputs_2004_2019.csv", "data/reference/siar_inputs_2020_2025.csv",
              "data/processed/openmeteo_archive.csv", "data/v2/et0_v2_annual_2020_2025.csv",
              "data/v2/et0_v2_seasonal_2020_2025.csv", "data/v2/et0_v2_monthly_2020_2025.csv",
              "studies/02_openmeteo_ahc/results/predictions_openmeteo_2020_2025.csv",
              "studies/03_loso_openmeteo_ml/loso_common.py", "studies/03_loso_openmeteo_ml/loso_models.py"]
    by_model = {}
    for i in info:
        by_model.setdefault(i["model"], set()).add(i["platform"])
    man = {"study": "03.2", "criteria": "config/thresholds_v3.json (congelado, PR #8)",
           "shared_code": "loso_common.py y loso_models.py: copia literal de studies/03_1_loso_inputs_siar @ 76d4aa8",
           "inputs_sha256": {p: lc.sha256(lc.ROOT / p) for p in inputs},
           "versions_report": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
                               "scikit-learn": sklearn.__version__},
           "cell_platforms_by_model": {k: sorted(v) for k, v in by_model.items()},
           "seeds": {"bootstrap": lc.BOOT_SEED, "bootstrap_reps": lc.BOOT_REPS, "ANN_S_M": lm.ANN_SEEDS,
                     "HGB_RF": 0},
           "test_cohort": {"rows_F1": int((pred.scheme == "F1_loso").sum()), "rule": "common_core == 1"},
           "nearest_station_fallbacks": fallbacks, "missing_cells": sorted(missing),
           "missing_cells_count": len(missing),
           "negatives_clipped_by_model": {m: int(sum(i["negatives_clipped"] for i in info if i["model"] == m))
                                          for m in MODELS},
           "heavy_models": HEAVY}
    (RES / "run_manifest.json").write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(dec, indent=2, ensure_ascii=False, default=conv))
    print("celdas que faltan:", len(missing))
