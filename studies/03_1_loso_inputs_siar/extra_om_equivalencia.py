"""Analisis EXPLORATORIO posterior (post hoc) del estudio 03.1. No cambia hipotesis, criterios ni regla de decision.

1. Comparadores adicionales de Open-Meteo + AHC con coeficiente ANUAL (los congelados son mensuales):
   OM_AHC_anual_medio_entrenamiento y OM_AHC_anual_estacion_mas_cercana (misma construccion que los mensuales).
2. Equivalencia (TOST) con el umbral practico ya fijado (0,05 mm/dia): IC 90 % por bootstrap de bloques estacion-anio
   (los mismos remuestreos que el informe) dentro de +-0,05 => equivalentes; ademas el margen minimo de equivalencia.
Salidas: results/extra_om_equivalencia.csv, results/extra_om_comparadores.csv, figures/04_equivalencia.png
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

import loso_common as lc
import report as rp

MARGIN = rp.PRACT  # 0,05 mm/dia, de config/thresholds_v3_1.json (statistics.practical_threshold_mm_dia)
MODELS = ["HGB", "RF", "ANN_S", "ANN_M", "ANN_V2like"]
FAM = {"HS_RA": "HS-Ra", "VALIANTZAS": "Valiantzas", "HG_RS": "HG-Rs"}
COMP = {"PM_estacion_mas_cercana_mismo_dia": "Estación SIAR más cercana",
        "OM_AHC_mensual_medio_entrenamiento": "OM + AHC mensual transferido (H3)",
        "OM_AHC_anual_medio_entrenamiento": "OM + AHC anual transferido",
        "OM_AHC_mensual_estacion_mas_cercana": "OM + AHC mensual de la estación más cercana",
        "OM_AHC_anual_estacion_mas_cercana": "OM + AHC anual de la estación más cercana",
        "PM_IDW_estaciones_entrenamiento_mismo_dia": "IDW mismo día"}


def om_annual_cols(df, dist, folds):
    rows = []
    for f in folds:
        if f["scheme"] != "F1_loso":
            continue
        test = lc.test_cohort(df)
        test = test[test.station_code.isin(f["test"])].copy()
        dev = df[(df.period == "DEV") & df.target_ok & df.station_code.isin(f["train"])].copy()
        om = dev[np.isfinite(dev["et0_om_mm"])]
        per = lc.ahc_by_station(om, "et0_om_mm", "annual")
        mean = lc.apply_ahc(test, "et0_om_mm", lc.mean_coefs(per, f["train"]), "annual")
        nb = np.empty(len(test))
        for s in f["test"]:
            m = (test.station_code == s).to_numpy()
            nb[m] = lc.apply_ahc(test[m], "et0_om_mm", per[lc.neighbours(s, f["train"], dist)[0]], "annual")
        rows.append(pd.DataFrame({"station_code": test.station_code.to_numpy(), "date": test.date.to_numpy(),
                                  "OM_AHC_anual_medio_entrenamiento": mean,
                                  "OM_AHC_anual_estacion_mas_cercana": nb}))
    return pd.concat(rows, ignore_index=True)


def main():
    df, dist, folds = lc.load_panel(), lc.distances(), lc.build_folds()
    pred, *_ = rp.assemble()
    d = pred[pred.scheme == "F1_loso"].reset_index(drop=True)
    extra = om_annual_cols(df, dist, folds)
    assert (extra.station_code.to_numpy() == d.station_code.to_numpy()).all() and \
           (extra.date.to_numpy() == d.date.to_numpy()).all(), "filas desalineadas"
    for c in ("OM_AHC_anual_medio_entrenamiento", "OM_AHC_anual_estacion_mas_cercana"):
        d[c] = extra[c].to_numpy()

    # tabla de comparadores (RMSE, sesgo)
    ref = d.pm.to_numpy()
    cmp_rows = []
    for c in ["OM_crudo", "OM_AHC_mensual_medio_entrenamiento", "OM_AHC_anual_medio_entrenamiento",
              "OM_AHC_mensual_estacion_mas_cercana", "OM_AHC_anual_estacion_mas_cercana",
              "PM_estacion_mas_cercana_mismo_dia", "PM_IDW_estaciones_entrenamiento_mismo_dia"]:
        ok = d[c].notna()
        cmp_rows.append({"comparador": c, **lc.metrics(d[c][ok], ref[ok])})
    for fam in lc.FAMILIES:
        for g in ("annual", "monthly"):
            for k in ("transferido", "vecino"):
                c = f"{fam}|AHC_{k}_{g}"
                cmp_rows.append({"comparador": c, **lc.metrics(d[c], ref)})
    pd.DataFrame(cmp_rows).round(4).to_csv(rp.RES / "extra_om_comparadores.csv", index=False)

    # equivalencia
    bi, _ = lc.block_index(d.station_code, d.date)
    draws = lc.boot_draws(bi.max() + 1)
    out = []
    for fam in lc.FAMILIES:
        for m in MODELS:
            a = f"{fam}|principal|{m}"
            for c in COMP:
                if d[c].isna().any():
                    continue
                d0, lo95, hi95 = lc.paired_delta_ci(d[a].to_numpy(), d[c].to_numpy(), ref, bi, draws)
                ea, eb = (d[a].to_numpy() - ref) ** 2, (d[c].to_numpy() - ref) ** 2
                n = np.bincount(bi).astype(float)
                sa, sb = np.bincount(bi, ea), np.bincount(bi, eb)
                N, A, B = n[draws].sum(1), sa[draws].sum(1), sb[draws].sum(1)
                bs = np.sqrt(A / N) - np.sqrt(B / N)
                lo90, hi90 = np.percentile(bs, [5, 95])
                equiv = (lo90 > -MARGIN) and (hi90 < MARGIN)
                if hi95 < 0:
                    v = "el modelo gana"
                elif lo95 > 0:
                    v = "el modelo pierde"
                else:
                    v = "empate (IC95 incluye 0)"
                if equiv:
                    v += " · EQUIVALENTE (±%.2f)" % MARGIN
                out.append({"familia": FAM[fam], "modelo": m, "comparador": c, "rmse_modelo": lc.metrics(d[a], ref)["rmse"],
                            "rmse_comparador": lc.metrics(d[c], ref)["rmse"], "delta": d0, "ic95_lo": lo95,
                            "ic95_hi": hi95, "ic90_lo": lo90, "ic90_hi": hi90,
                            "margen_min_equivalencia": max(abs(lo90), abs(hi90)), "equivalente": bool(equiv),
                            "veredicto": v})
    o = pd.DataFrame(out)
    o.round(4).to_csv(rp.RES / "extra_om_equivalencia.csv", index=False)
    figures(pd.DataFrame(cmp_rows), o)
    return o


def figures(cmp, o):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    # 04: RMSE de los comparadores (OM crudo, mensual vs anual, estacion mas cercana, IDW) y HGB conjunto
    rows = [("OM crudo", "OM_crudo", "#bbbbbb"), ("OM + AHC anual\ntransferido", "OM_AHC_anual_medio_entrenamiento", "#F2B880"),
            ("OM + AHC anual\nestación cercana", "OM_AHC_anual_estacion_mas_cercana", "#F2B880"),
            ("OM + AHC mensual\nestación cercana", "OM_AHC_mensual_estacion_mas_cercana", "#E8833A"),
            ("OM + AHC mensual\ntransferido (H3)", "OM_AHC_mensual_medio_entrenamiento", "#E8833A"),
            ("PM estación SIAR\nmás cercana (H2)", "PM_estacion_mas_cercana_mismo_dia", "#4C78A8"),
            ("IDW mismo día", "PM_IDW_estaciones_entrenamiento_mismo_dia", "#4C78A8")]
    g = cmp.set_index("comparador").rmse
    fig, ax = plt.subplots(figsize=(11, 5))
    for i, (lab, key, c) in enumerate(rows):
        ax.bar(i, g[key], color=c)
        ax.text(i, g[key] + 0.01, f"{g[key]:.3f}", ha="center", fontsize=9)
    ax.set_xticks(range(len(rows)))
    ax.set_xticklabels([r[0] for r in rows], fontsize=8.5)
    for fam, col, ls in (("HS_RA", "#C44E52", "--"), ("VALIANTZAS", "#55A868", "-."), ("HG_RS", "#8172B3", ":")):
        v = o[(o.familia == FAM[fam]) & (o.modelo == "HGB")].rmse_modelo.iloc[0]
        ax.axhline(v, color=col, ls=ls, lw=1.6, label=f"HGB conjunto {FAM[fam]} ({v:.3f})")
    ax.set_ylabel("RMSE (mm/día), F1, TEST 2020–2025")
    ax.set_title("El ajuste mensual de Open-Meteo es mucho mejor que el anual: H3 compara con la versión más favorable a OM")
    ax.legend(fontsize=8.5, loc="upper right")
    fig.tight_layout()
    fig.savefig(rp.FIG / "04_comparadores_om_mensual_vs_anual.png", dpi=140)
    plt.close(fig)
    # 05: equivalencia (HGB) frente a cada comparador, por familia
    order = list(COMP)
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
    for ax, fam in zip(axes, FAM.values()):
        for i, c in enumerate(order):
            r = o[(o.familia == fam) & (o.modelo == "HGB") & (o.comparador == c)].iloc[0]
            col = "#55A868" if r.equivalente else ("#C44E52" if r.ic95_lo > 0 else ("#4C78A8" if r.ic95_hi < 0 else "#888888"))
            ax.plot([r.ic95_lo, r.ic95_hi], [i, i], color=col, lw=1.2)
            ax.plot([r.ic90_lo, r.ic90_hi], [i, i], color=col, lw=5, alpha=.65)
            ax.plot(r.delta, i, "o", color="k", ms=4)
        ax.axvspan(-MARGIN, MARGIN, color="#ddd", alpha=.45, lw=0)
        ax.axvline(0, color="k", lw=1)
        ax.set_title(f"{fam}: HGB conjunto − comparador", fontsize=10)
        ax.set_xlabel("ΔRMSE (mm/día)  · trazo fino IC95, grueso IC90")
        ax.grid(axis="x", alpha=.3)
    axes[0].set_yticks(range(len(order)))
    axes[0].set_yticklabels([COMP[c] for c in order], fontsize=8.5)
    axes[0].invert_yaxis()
    fig.suptitle("Equivalencia (TOST, margen ±0,05 mm/día, banda gris): verde = IC90 dentro de la banda; rojo = el modelo pierde; azul = gana; gris = sin diferencia clara")
    fig.tight_layout()
    fig.savefig(rp.FIG / "05_equivalencia.png", dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    main()
