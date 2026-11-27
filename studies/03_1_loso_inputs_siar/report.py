"""Informe del estudio 03.1: une celdas ajustadas, comparadores, metricas, IC pareados, figuras y manifiesto."""
from __future__ import annotations

import gzip
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd

import loso_common as lc
import loso_models as lm

HERE = Path(__file__).resolve().parent
RES, FIG, CELLS = HERE / "results", HERE / "figures", HERE / "results" / "cells"
MODELS = ["Ridge", "HGB", "RF", "ANN_S", "ANN_M", "ANN_V2like"]
VARIANTS = ["principal", "secundaria"]
V2_METHODS = ["FORMULA", "AHC", "ML", "ANN_A", "ANN_E"]
THR = json.loads((lc.ROOT / "config/thresholds_v3_1.json").read_text(encoding="utf-8"))
PRACT = THR["statistics"]["practical_threshold_mm_dia"]
SCOPES = {"F1": lambda f: f["scheme"] == "F1_loso"}


# ---------------------------------------------------------------- comparadores por particion (sin ML)
def fold_baselines(df, fold, dist):
    """Predicciones de los metodos sin ML para las filas TEST de la particion. Devuelve (test, {col: array})."""
    test = lc.test_cohort(df)
    test = test[test.station_code.isin(fold["test"])].copy()
    dev = df[(df.period == "DEV") & df.target_ok & df.station_code.isin(fold["train"])].copy()
    cols, meta = {}, {}
    for fam in lc.FAMILIES:
        dev["f"] = lc.formula(fam, dev)
        d = dev[np.isfinite(dev["f"])]
        f_test = lc.formula(fam, test)
        test["f_" + fam] = f_test
        cols[f"{fam}|FORMULA"] = f_test.to_numpy()
        for gran in ("annual", "monthly"):
            per = lc.ahc_by_station(d, "f", gran)
            tr = lc.mean_coefs(per, fold["train"])
            cols[f"{fam}|AHC_transferido_{gran}"] = lc.apply_ahc(test, "f_" + fam, tr, gran)
            nb = np.empty(len(test))
            for s in fold["test"]:
                m = (test.station_code == s).to_numpy()
                near = lc.neighbours(s, fold["train"], dist)[0]
                nb[m] = lc.apply_ahc(test[m], "f_" + fam, per[near], gran)
                meta[(s, "vecino")] = near
            cols[f"{fam}|AHC_vecino_{gran}"] = nb
    # Open-Meteo
    om_dev = dev[np.isfinite(dev["et0_om_mm"])]
    cols["OM_crudo"] = test["et0_om_mm"].to_numpy()
    per = lc.ahc_by_station(om_dev, "et0_om_mm", "monthly")
    cols["OM_AHC_mensual_medio_entrenamiento"] = lc.apply_ahc(test, "et0_om_mm", lc.mean_coefs(per, fold["train"]),
                                                              "monthly")
    nb = np.empty(len(test))
    for s in fold["test"]:
        m = (test.station_code == s).to_numpy()
        nb[m] = lc.apply_ahc(test[m], "et0_om_mm", per[lc.neighbours(s, fold["train"], dist)[0]], "monthly")
    cols["OM_AHC_mensual_estacion_mas_cercana"] = nb
    near, idw, fb = lc.pm_nearest_and_idw(df, test, fold["train"], dist)
    cols["PM_estacion_mas_cercana_mismo_dia"], cols["PM_IDW_estaciones_entrenamiento_mismo_dia"] = near, idw
    meta["nearest_fallbacks"] = fb
    return test, cols, meta


def load_cells(fold_id, test):
    cols, seeds, info, missing = {}, {}, [], []
    key = test.station_code + "|" + test.date
    for fam in lc.FAMILIES:
        for v in VARIANTS:
            for m in MODELS:
                p = CELLS / f"{fold_id}__{fam}__{v}__{m}.json.gz"
                if not p.exists():
                    missing.append(p.name)
                    continue
                c = json.load(gzip.open(p, "rt", encoding="utf-8"))
                k = pd.Series([f"{s}|{d}" for s, d in zip(c["station_code"], c["date"])])
                assert (k.to_numpy() == key.to_numpy()).all(), f"orden de filas distinto en {p.name}"
                cols[f"{fam}|{v}|{m}"] = np.array(c["pred"])
                if "seed_preds" in c:
                    seeds[f"{fam}|{v}|{m}"] = np.array(c["seed_preds"])
                info.append({k2: c[k2] for k2 in ("fold", "family", "variant", "model", "n_train", "params",
                                                   "negatives_clipped", "convergence_warnings", "final_epochs",
                                                   "seconds")}
                            | {"cv_mean_rmse_chosen": min(x["mean_rmse"] for x in c["cv"])})
    return cols, seeds, info, missing


def v2_local(test):
    out = {}
    for res in ("annual", "seasonal", "monthly"):
        v2 = pd.read_csv(lc.ROOT / f"data/v2/et0_v2_{res}_2020_2025.csv").rename(columns={"station_id": "station_code"})
        t = test[["station_code", "date"]].merge(v2, on=["station_code", "date"], how="left")
        for fam in lc.FAMILIES:
            for m in V2_METHODS:
                out[f"{fam}|V2_local_{m}_{res}"] = t[f"{lc.V2_FAMILY[fam]}_{m}"].to_numpy()
    return out


# ---------------------------------------------------------------- ensamblado
def assemble():
    df = lc.load_panel()
    dist = lc.distances()
    folds = lc.build_folds()
    blocks, all_info, all_missing, fallbacks, seed_blocks = [], [], [], {}, []
    for f in folds:
        test, cols, meta = fold_baselines(df, f, dist)
        cc, seeds, info, missing = load_cells(f["id"], test)
        cols.update(cc)
        cols.update(v2_local(test))
        fallbacks[f["id"]] = meta["nearest_fallbacks"]
        all_info += info
        all_missing += missing
        b = pd.DataFrame({"fold": f["id"], "scheme": f["scheme"], "station_code": test.station_code.to_numpy(),
                          "date": test.date.to_numpy(), "pm": test.ET0_PM_FAO56_V1.to_numpy()} | cols)
        blocks.append(b)
        for k, sp in seeds.items():
            seed_blocks.append((f["id"], k, test.ET0_PM_FAO56_V1.to_numpy(), sp))
    pred = pd.concat(blocks, ignore_index=True)
    return pred, all_info, sorted(set(all_missing)), fallbacks, seed_blocks, folds


def scopes(pred):
    """F1 (9 particiones LOSO juntas = cohorte completa) y cada particion F2."""
    out = {"F1": pred[pred.scheme == "F1_loso"]}
    for fid in sorted(pred.fold.unique()):
        if fid.startswith("F2_"):
            out[fid] = pred[pred.fold == fid]
    return out


def method_cols(pred):
    return [c for c in pred.columns if c not in ("fold", "scheme", "station_code", "date", "pm")]


def metric_table(pred):
    rows_g, rows_s, rows_m = [], [], []
    for scope, d in scopes(pred).items():
        for c in method_cols(pred):
            if d[c].isna().all():
                continue
            ok = d[c].notna()
            rows_g.append({"scope": scope, "method": c, **lc.metrics(d[c][ok], d.pm[ok]), "n_missing": int((~ok).sum())})
            for s, g in d[ok].groupby("station_code"):
                rows_s.append({"scope": scope, "method": c, "station_code": s, **lc.metrics(g[c], g.pm)})
            for mth, g in d[ok].groupby(d[ok].date.str[5:7]):
                rows_m.append({"scope": scope, "method": c, "month": mth, **lc.metrics(g[c], g.pm)})
    return pd.DataFrame(rows_g), pd.DataFrame(rows_s), pd.DataFrame(rows_m)


def best_v2_local(glob_f1, fam):
    """Mejor modelo local V2 de la familia (granularidad anual, menor RMSE TEST de la cohorte comun)."""
    g = glob_f1[glob_f1.method.str.startswith(f"{fam}|V2_local_") & glob_f1.method.str.endswith("_annual")]
    return g.sort_values("rmse").iloc[0].method


def paired(pred, glob):
    rows = []
    sc = scopes(pred)
    for scope, d in sc.items():
        bi, _ = lc.block_index(d.station_code, d.date)
        draws = lc.boot_draws(bi.max() + 1)
        g = glob[glob.scope == "F1"]

        def add(kind, a, b, hyp=""):
            if a not in d or b not in d or d[a].isna().any() or d[b].isna().any():
                return
            d0, lo, hi = lc.paired_delta_ci(d[a].to_numpy(), d[b].to_numpy(), d.pm.to_numpy(), bi, draws)
            if hi < 0:
                ver = "A gana" + (" (pequena)" if abs(d0) < PRACT else "")
            elif lo > 0:
                ver = "B gana" + (" (pequena)" if abs(d0) < PRACT else "")
            else:
                ver = "empate (IC incluye 0)"
            rows.append({"scope": scope, "hypothesis": hyp, "kind": kind, "A": a, "B": b, "n": len(d),
                         "n_blocks": int(bi.max() + 1), "rmse_A": lc.metrics(d[a], d.pm)["rmse"],
                         "rmse_B": lc.metrics(d[b], d.pm)["rmse"], "delta_rmse": d0, "ci95_lo": lo,
                         "ci95_hi": hi, "verdict": ver})

        for fam in lc.FAMILIES:
            best = best_v2_local(g, fam)
            for v in VARIANTS:
                for m in MODELS:
                    a = f"{fam}|{v}|{m}"
                    h = (v == "principal" and m == "HGB" and scope == "F1")
                    add("vs_V2_local_mejor", a, best, "H1" if h else "")
                    add("vs_PM_estacion_mas_cercana", a, "PM_estacion_mas_cercana_mismo_dia", "H2" if h else "")
                    add("vs_OM_AHC_transferido", a, "OM_AHC_mensual_medio_entrenamiento", "H3" if h else "")
                    add("vs_PM_IDW", a, "PM_IDW_estaciones_entrenamiento_mismo_dia")
                    add("vs_OM_crudo", a, "OM_crudo")
            # degradacion por metodo: no visto - local (mismo metodo, granularidad anual)
            add("degradacion_metodo", f"{fam}|FORMULA", f"{fam}|V2_local_FORMULA_annual")
            for gran in ("annual", "monthly"):
                add("degradacion_metodo", f"{fam}|AHC_transferido_{gran}", f"{fam}|V2_local_AHC_annual")
                add("degradacion_metodo", f"{fam}|AHC_vecino_{gran}", f"{fam}|V2_local_AHC_annual")
            for m in MODELS:
                add("degradacion_metodo", f"{fam}|principal|{m}", f"{fam}|V2_local_ML_annual")
                add("degradacion_metodo", f"{fam}|principal|{m}", f"{fam}|V2_local_ANN_A_annual")
            add("sensibilidad_H1", f"{fam}|principal|HGB", f"{fam}|V2_local_ANN_A_annual")
            mins = g[g.method.str.startswith(f"{fam}|V2_local_")].sort_values("rmse").iloc[0].method
            add("sensibilidad_H1_cualquier_granularidad", f"{fam}|principal|HGB", mins)
            add("comparadores", f"{fam}|AHC_transferido_monthly", "PM_estacion_mas_cercana_mismo_dia")
        add("comparadores", "OM_AHC_mensual_medio_entrenamiento", "PM_estacion_mas_cercana_mismo_dia")
        add("comparadores", "PM_IDW_estaciones_entrenamiento_mismo_dia", "PM_estacion_mas_cercana_mismo_dia")
    return pd.DataFrame(rows)


def seed_spread(seed_blocks):
    acc = {}
    for fid, key, y, sp in seed_blocks:
        if not fid.startswith("F1_"):
            continue
        a = acc.setdefault(key, {"y": [], "sp": []})
        a["y"].append(y)
        a["sp"].append(sp)
    rows = []
    for key, a in sorted(acc.items()):
        if len(a["y"]) != 9:
            continue
        y, sp = np.concatenate(a["y"]), np.concatenate(a["sp"], axis=1)
        r = np.sqrt(((sp - y) ** 2).mean(1))
        fam, v, m = key.split("|")
        rows.append({"scope": "F1", "family": fam, "variant": v, "model": m, "n_seeds": len(r),
                     "rmse_ensemble": float(np.sqrt(((sp.mean(0) - y) ** 2).mean())),
                     "rmse_seed_mean": float(r.mean()), "rmse_seed_sd": float(r.std(ddof=1)),
                     "rmse_seed_min": float(r.min()), "rmse_seed_max": float(r.max()),
                     "pred_sd_between_seeds_mean": float(sp.std(0, ddof=1).mean())})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- decision
def decision(pc):
    h = pc[pc.hypothesis != ""].set_index(["hypothesis", "A"])
    out = {"hypotheses": {}, "rule": {}}
    for fam in lc.FAMILIES:
        a = f"{fam}|principal|HGB"
        for hyp in ("H1", "H2", "H3"):
            if (hyp, a) in h.index:
                r = h.loc[(hyp, a)]
                out["hypotheses"][f"{hyp}_{fam}"] = {"B": r.B, "delta": r.delta_rmse, "lo": r.ci95_lo, "hi": r.ci95_hi,
                                                     "rmse_A": r.rmse_A, "rmse_B": r.rmse_B}
    cond = {}
    for fam in ("HS_RA", "VALIANTZAS"):
        hi2 = out["hypotheses"][f"H2_{fam}"]["hi"]
        hi3 = out["hypotheses"][f"H3_{fam}"]["hi"]
        cond[fam] = {"hi_vs_estacion_cercana": hi2, "hi_vs_OM_AHC": hi3, "no_gana_a_ninguno": hi2 >= 0 and hi3 >= 0}
    out["rule"] = {"condiciones": cond,
                   "cambio_de_rumbo_justificado": all(c["no_gana_a_ninguno"] for c in cond.values())}
    for fam in lc.FAMILIES:
        r = out["hypotheses"][f"H1_{fam}"]
        out["hypotheses"][f"H1_{fam}"]["cumple"] = r["delta"] > 0 and r["lo"] > 0
    return out


# ---------------------------------------------------------------- figuras
def figures(glob):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIG.mkdir(exist_ok=True)
    g = glob[glob.scope == "F1"].set_index("method").rmse
    names = {"HS_RA": "HS-Ra", "VALIANTZAS": "Valiantzas", "HG_RS": "HG-Rs"}
    pairs = [("Fórmula", "V2_local_FORMULA_annual", "FORMULA"),
             ("AHC", "V2_local_AHC_annual", "AHC_transferido_annual"),
             ("ML (HGB)", "V2_local_ML_annual", "principal|HGB"),
             ("ANN", "V2_local_ANN_A_annual", "principal|ANN_V2like")]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), sharey=True)
    for ax, fam in zip(axes, lc.FAMILIES):
        lab, loc, uns = [], [], []
        for name, a, b in pairs:
            if f"{fam}|{a}" in g and f"{fam}|{b}" in g:
                lab.append(name)
                loc.append(g[f"{fam}|{a}"])
                uns.append(g[f"{fam}|{b}"])
        x = np.arange(len(lab))
        ax.bar(x - 0.2, loc, 0.4, label="V2 local (misma estación)", color="#4C78A8")
        ax.bar(x + 0.2, uns, 0.4, label="Estación no vista (F1)", color="#F58518")
        for xi, (l, u) in enumerate(zip(loc, uns)):
            ax.text(xi - 0.2, l + 0.01, f"{l:.2f}", ha="center", fontsize=8)
            ax.text(xi + 0.2, u + 0.01, f"{u:.2f}", ha="center", fontsize=8)
        ax.set_xticks(x, lab)
        ax.set_title(names[fam])
        ax.grid(axis="y", alpha=0.3)
    axes[0].set_ylabel("RMSE frente a PM (mm/día), TEST 2020–2025")
    axes[0].legend(fontsize=8, loc="upper right")
    fig.suptitle("Degradación al salir de la estación (AHC no visto = coeficiente medio transferido)")
    fig.tight_layout()
    fig.savefig(FIG / "01_degradacion_local_no_vista.png", dpi=150)
    plt.close(fig)

    comps = [("PM estación más cercana", "PM_estacion_mas_cercana_mismo_dia"),
             ("PM IDW", "PM_IDW_estaciones_entrenamiento_mismo_dia"),
             ("OM + AHC transferido", "OM_AHC_mensual_medio_entrenamiento"), ("OM crudo", "OM_crudo")]
    fig, ax = plt.subplots(figsize=(11, 4.5))
    labels, vals, colors = [], [], []
    for fam in lc.FAMILIES:
        for m in MODELS:
            k = f"{fam}|principal|{m}"
            if k in g:
                labels.append(f"{names[fam]} {m}")
                vals.append(g[k])
                colors.append({"HS_RA": "#E45756", "VALIANTZAS": "#72B7B2", "HG_RS": "#B279A2"}[fam])
    ax.bar(range(len(vals)), vals, color=colors)
    for name, k in comps:
        ax.axhline(g[k], ls="--", lw=1, color="k" if "PM" in name else "#4C78A8", alpha=0.8)
        ax.text(len(vals) - 0.4, g[k] + 0.005, f"{name} {g[k]:.3f}", ha="right", fontsize=8)
    ax.set_xticks(range(len(vals)), labels, rotation=60, ha="right", fontsize=8)
    ax.set_ylabel("RMSE (mm/día), F1")
    ax.set_title("Modelos conjuntos en estación no vista frente a lo gratuito y a Open-Meteo")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG / "02_vs_cercana_openmeteo.png", dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------- principal
def main():
    import sklearn
    RES.mkdir(exist_ok=True)
    pred, info, missing, fallbacks, seed_blocks, folds = assemble()
    lc.write_folds(RES / "folds.json", folds)
    glob, by_st, by_m = metric_table(pred)
    glob.to_csv(RES / "metrics_global.csv", index=False, float_format="%.6f")
    by_st.to_csv(RES / "metrics_by_station.csv", index=False, float_format="%.6f")
    by_m.to_csv(RES / "metrics_by_month.csv", index=False, float_format="%.6f")
    pc = paired(pred, glob)
    pc.to_csv(RES / "paired_ci.csv", index=False, float_format="%.6f")
    seed_spread(seed_blocks).to_csv(RES / "ann_seed_spread.csv", index=False, float_format="%.6f")
    pd.DataFrame(info).sort_values(["model", "family", "variant", "fold"]).to_csv(
        RES / "model_selection.csv", index=False, float_format="%.6f")
    pred.to_csv(RES / "predictions_test.csv.gz", index=False, float_format="%.5f", compression="gzip")
    dec = decision(pc)
    (RES / "decision.json").write_text(json.dumps(dec, indent=2, ensure_ascii=False, default=lambda o: o.item() if hasattr(o, "item") else str(o)) + "\n", encoding="utf-8")
    figures(glob)
    inputs = ["config/thresholds_v3_1.json", "config/thresholds_v3.json", "config/stations.csv",
              "data/reference/reference_2004_2019.csv", "data/reference/reference_2020_2025.csv",
              "data/reference/siar_inputs_2004_2019.csv", "data/reference/siar_inputs_2020_2025.csv",
              "data/processed/openmeteo_archive.csv", "data/v2/et0_v2_annual_2020_2025.csv",
              "data/v2/et0_v2_seasonal_2020_2025.csv", "data/v2/et0_v2_monthly_2020_2025.csv"]
    man = {"study": "03.1", "inputs_sha256": {p: lc.sha256(lc.ROOT / p) for p in inputs},
           "versions": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
                        "scikit-learn": sklearn.__version__},
           "seeds": {"bootstrap": lc.BOOT_SEED, "bootstrap_reps": lc.BOOT_REPS, "ANN_S_M": lm.ANN_SEEDS,
                     "ANN_V2like": lm.ANN_V2_SEEDS, "HGB_RF": 0},
           "test_cohort": {"rows_F1": int((pred.scheme == "F1_loso").sum()), "rule": "common_core == 1"},
           "nearest_station_fallbacks": fallbacks, "missing_cells": missing,
           "negatives_clipped_total": int(sum(i["negatives_clipped"] for i in info)),
           "platform": platform.platform()}
    (RES / "run_manifest.json").write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(dec, indent=2, ensure_ascii=False, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    print("celdas que faltan:", len(missing))
