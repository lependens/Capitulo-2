"""Analisis EXPLORATORIO posterior (post hoc) del estudio 03.1: H1, H2 y H3 estacion por estacion.

Responde a: el veredicto de cada hipotesis, es parecido en las 9 estaciones de F1 o hay alguna que lo cambie?
No modifica hipotesis, comparadores congelados, criterios ni la regla de decision.

Por estacion el bootstrap solo tiene 6 bloques (un anio cada uno), asi que los IC son MUY anchos: se usan
para ver la dispersion del signo, no para declarar significacion estacion a estacion.

Salidas: results/extra_por_estacion.csv, figures/06_por_estacion.png
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import loso_common as lc
import report as rp

MODELS = ["HGB", "RF", "ANN_S", "ANN_M", "ANN_V2like"]
FAM = {"HS_RA": "HS-Ra", "VALIANTZAS": "Valiantzas", "HG_RS": "HG-Rs"}
HYP = {"H1": None,  # se resuelve por familia: mejor local V2 anual
       "H2": "PM_estacion_mas_cercana_mismo_dia",
       "H3": "OM_AHC_mensual_medio_entrenamiento",
       "IDW": "PM_IDW_estaciones_entrenamiento_mismo_dia"}


def main():
    pred, *_ = rp.assemble()
    d = pred[pred.scheme == "F1_loso"].reset_index(drop=True)
    glob = pd.read_csv(rp.RES / "metrics_global.csv")
    g1 = glob[glob.scope == "F1"]
    best = {fam: rp.best_v2_local(g1, fam) for fam in lc.FAMILIES}

    rows = []
    for st, sub in d.groupby("station_code"):
        ref = sub.pm.to_numpy()
        bi, _ = lc.block_index(sub.station_code, sub.date)
        draws = lc.boot_draws(bi.max() + 1)
        for fam in lc.FAMILIES:
            for m in MODELS:
                a = f"{fam}|principal|{m}"
                for h, comp in HYP.items():
                    b = best[fam] if h == "H1" else comp
                    if sub[b].isna().any():
                        continue
                    d0, lo, hi = lc.paired_delta_ci(sub[a].to_numpy(), sub[b].to_numpy(), ref, bi, draws)
                    rows.append({"estacion": st, "familia": FAM[fam], "modelo": m, "hipotesis": h,
                                 "comparador": b, "n": len(sub), "rmse_modelo": lc.metrics(sub[a], ref)["rmse"],
                                 "rmse_comparador": lc.metrics(sub[b], ref)["rmse"], "delta": d0,
                                 "ic95_lo": lo, "ic95_hi": hi,
                                 "signo": "modelo pierde" if d0 > 0 else "modelo gana"})
    o = pd.DataFrame(rows)
    o.round(4).to_csv(rp.RES / "extra_por_estacion.csv", index=False)

    # resumen: cuantas estaciones con cada signo, por familia e hipotesis (HGB)
    h = o[o.modelo == "HGB"]
    print(h.pivot_table(index=["hipotesis", "familia"], columns="signo", values="estacion", aggfunc="count").fillna(0).to_string())
    print()
    print(h[h.hipotesis != "IDW"].pivot_table(index="estacion", columns=["hipotesis", "familia"], values="delta").round(3).to_string())

    figures(o)
    return o


def figures(o):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    sts = sorted(o.estacion.unique())
    fams = ["HS-Ra", "Valiantzas", "HG-Rs"]
    hyps = [("H1", "H1: frente al mejor local V2\n(>0 = se degrada)"),
            ("H2", "H2: frente a la estación más cercana\n(>0 = pierde)"),
            ("H3", "H3: frente a OM + AHC mensual\n(>0 = pierde)")]
    col = {"HS-Ra": "#C44E52", "Valiantzas": "#55A868", "HG-Rs": "#8172B3"}
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.6), sharey=True)
    x = np.arange(len(sts))
    for ax, (h, t) in zip(axes, hyps):
        for k, fam in enumerate(fams):
            s = o[(o.modelo == "HGB") & (o.hipotesis == h) & (o.familia == fam)].set_index("estacion").loc[sts]
            ax.plot(x + (k - 1) * 0.22, s.delta, "o-", color=col[fam], label=fam, ms=5, lw=1)
            ax.vlines(x + (k - 1) * 0.22, s.ic95_lo, s.ic95_hi, color=col[fam], alpha=.35, lw=1)
        gl = {"H1": None, "H2": "PM_estacion_mas_cercana_mismo_dia", "H3": "OM_AHC_mensual_medio_entrenamiento"}
        ax.axhline(0, color="k", lw=1)
        ax.axhspan(-0.05, 0.05, color="#ddd", alpha=.45, lw=0)
        ax.set_xticks(x)
        ax.set_xticklabels(sts, rotation=45, fontsize=8.5)
        ax.set_title(t, fontsize=10)
        ax.grid(axis="y", alpha=.3)
    axes[0].set_ylabel("ΔRMSE (mm/día), HGB conjunto − comparador")
    axes[0].legend(fontsize=9)
    fig.suptitle("03.1 · H1–H3 estación por estación (F1, HGB, variante principal). Barras = IC 95 % con solo 6 bloques-año: orientativas", fontsize=11)
    fig.tight_layout()
    fig.savefig(rp.FIG / "06_por_estacion.png", dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    main()
