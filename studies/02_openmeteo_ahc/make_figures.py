"""Estudio 02: tablas y graficos ampliados."""
import csv, math, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from openmeteo_et0.metrics import compute  # noqa: E402
HERE = Path(__file__).parent
RES, FIG = HERE / "results", HERE / "figures"
BLUE, ORANGE, VIOLET, GREEN, INK, MUTED = "#257de0", "#f47230", "#6a4ce2", "#008a17", "#191919", "#666666"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#999999",
                     "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED, "axes.titlecolor": INK,
                     "axes.titleweight": "bold", "axes.titlesize": 11, "axes.titlelocation": "left"})
FAMS = {"HS_RA_V1": "HS-Ra (Tmin,Tmax,Ra)", "HG_RS_V1": "HG-Rs (T,Rs)", "VALIANTZAS_V1": "Valiantzas (T,HR,Ra)"}
ST = [r["station_code"] for r in csv.DictReader(open(ROOT / "config/stations.csv"))]
MON = "E F M A M J J A S O N D".split()

# datos de test: V2 mensual (cohorte) + OM+AHC por resolucion
pred = {}
for r in csv.DictReader(open(RES / "predictions_openmeteo_2020_2025.csv")):
    pred[(r["resolution"], r["station_code"], r["date"])] = (float(r["pm_ref"]), float(r["om_et0"]), float(r["om_ahc"]))
v2 = {res: [r for r in csv.DictReader(open(ROOT / f"data/v2/et0_v2_{res}_2020_2025.csv")) if r["common_core"] == "1"] for res in ("annual", "seasonal", "monthly")}


def series(res, name):
    """lista (station, date, pred, ref) para un metodo."""
    out = []
    for r in v2[res]:
        k = (res, r["station_id"], r["date"])
        if k not in pred:
            continue
        ref, om, ahc = pred[k]
        if name == "OM_RAW": p = om
        elif name == "OM_AHC": p = ahc
        else:
            if r[name] == "": continue
            p = float(r[name])
        out.append((r["station_id"], r["date"], p, ref))
    return out


def met(rows):
    return compute([(p, y) for _, _, p, y in rows])


def rmse_by(rows, keyf):
    d = {}
    for s, dt, p, y in rows:
        d.setdefault(keyf(s, dt), []).append((p, y))
    return {k: compute(v) for k, v in d.items()}

# 1) RMSE global (resolucion mensual) todos los metodos
items = [("Open-Meteo crudo", "OM_RAW", ORANGE), ("Open-Meteo + AHC mensual", "OM_AHC", ORANGE)]
for f, lab in FAMS.items():
    for m, ml in (("FORMULA", "fórmula"), ("AHC", "+ AHC mensual"), ("ML", "ML"), ("ANN_A", "ANN")):
        items.append((f"{lab.split(' ')[0]} {ml}", f"{f}_{m}", BLUE))
vals = [(n, met(series("monthly", k))["rmse"], c) for n, k, c in items]
vals_sorted = sorted(vals, key=lambda t: t[1])
fig, ax = plt.subplots(figsize=(7.6, 7.2))
for i, (n, v, c) in enumerate(vals_sorted):
    ax.barh(i, v, color=c, height=0.62)
    ax.text(v + 0.01, i, f"{v:.3f}", va="center", fontsize=9, color=INK)
ax.set_yticks(range(len(vals_sorted))); ax.set_yticklabels([n for n, _, _ in vals_sorted]); ax.invert_yaxis()
ax.set_xlabel("RMSE TEST 2020–2025 (mm/día), n=19.251")
ax.set_title("Open-Meteo + AHC mensual (naranja) frente a V2 (azul)")
fig.tight_layout(); fig.savefig(FIG / "01_rmse_global.png", dpi=150); plt.close(fig)

# 2) RMSE por mes calendario
cand = [("Open-Meteo crudo", "OM_RAW", ORANGE, "--"), ("Open-Meteo + AHC mensual", "OM_AHC", ORANGE, "-"),
        ("HG-Rs ANN", "HG_RS_V1_ANN_A", BLUE, "-"), ("Valiantzas ANN", "VALIANTZAS_V1_ANN_A", VIOLET, "-"), ("HS-Ra ANN", "HS_RA_V1_ANN_A", GREEN, "-")]
fig, ax = plt.subplots(figsize=(7.8, 4.2))
bymonth = {}
for n, k, c, ls in cand:
    d = rmse_by(series("monthly", k), lambda s, dt: int(dt[5:7]))
    bymonth[n] = d
    ys = [d[m]["rmse"] for m in range(1, 13)]
    ax.plot(range(1, 13), ys, color=c, ls=ls, lw=2, marker="o", ms=4)
    off = {"Open-Meteo + AHC mensual": 0.018, "Valiantzas ANN": -0.018, "HG-Rs ANN": 0.0}.get(n, 0.0)
    ax.text(12.15, ys[-1] + off, n, color=INK, va="center", fontsize=8)
ax.set_xticks(range(1, 13)); ax.set_xticklabels(MON); ax.set_xlim(0.7, 15.8); ax.set_ylabel("RMSE (mm/día)")
ax.set_title("Open-Meteo + AHC iguala a las ANN en otoño-invierno y se queda atrás de marzo a septiembre")
fig.tight_layout(); fig.savefig(FIG / "02_rmse_por_mes.png", dpi=150); plt.close(fig)

# 3) por estacion
cand3 = [("Open-Meteo + AHC mensual", "OM_AHC", ORANGE), ("Valiantzas ANN", "VALIANTZAS_V1_ANN_A", VIOLET), ("HG-Rs ANN", "HG_RS_V1_ANN_A", BLUE)]
fig, ax = plt.subplots(figsize=(8, 4.0)); w = 0.26
bystation = {}
for j, (n, k, c) in enumerate(cand3):
    d = rmse_by(series("monthly", k), lambda s, dt: s); bystation[n] = d
    ax.bar(np.arange(len(ST)) + (j - 1) * w, [d[s]["rmse"] for s in ST], w, color=c, label=n)
ax.set_xticks(range(len(ST))); ax.set_xticklabels(ST); ax.set_ylabel("RMSE (mm/día)"); ax.legend(frameon=False, ncol=3, loc="upper left")
ax.set_ylim(0, 0.8); ax.set_title("Por estación: HG-Rs ANN gana en las 9; Open-Meteo + AHC ≈ Valiantzas ANN")
fig.tight_layout(); fig.savefig(FIG / "03_rmse_por_estacion.png", dpi=150); plt.close(fig)

# 4) variantes justas
fv = list(csv.DictReader(open(RES / "fair_variants_metrics.csv")))
def getv(var, res): return float([r for r in fv if r["variant"] == var and r["resolution"] == res][0]["rmse"])
fair = [("Open-Meteo nativa + AHC", "OM_NATIVA_AHC", ORANGE), ("PM con inputs OM (viento OM) + AHC", "PM_OM_TODO_AHC", ORANGE),
        ("PM con inputs OM, viento fijo 2 m/s + AHC", "PM_OM_U2=2_AHC", ORANGE), ("Hargreaves-Samani con T de OM + AHC", "HS_RA_OM_AHC", ORANGE),
        ("Hargreaves-Samani con T de SIAR + AHC (V2)", "HS_RA_V1_AHC  [V2, T de SIAR]", BLUE)]
fig, ax = plt.subplots(figsize=(8, 3.8))
for i, (n, k, c) in enumerate(fair):
    v = getv(k, "monthly"); ax.barh(i, v, color=c, height=0.6); ax.text(v + 0.01, i, f"{v:.3f}", va="center", fontsize=9, color=INK)
ax.set_yticks(range(len(fair))); ax.set_yticklabels([n for n, _, _ in fair]); ax.invert_yaxis(); ax.set_xlabel("RMSE TEST (mm/día), AHC mensual")
ax.set_title("Sin viento Open-Meteo pierde poco; sin su radiación y humedad (solo T) pierde mucho")
fig.tight_layout(); fig.savefig(FIG / "04_variantes_justas.png", dpi=150); plt.close(fig)

# 5) coeficientes mensuales
co = {}
for r in csv.DictReader(open(RES / "coefficients.csv")):
    if r["resolution"] == "monthly": co.setdefault(r["station_code"], {})[int(r["group"])] = float(r["coef_a"])
fig, ax = plt.subplots(figsize=(7.4, 3.8))
for s in ST: ax.plot(range(1, 13), [co[s][m] for m in range(1, 13)], color="#bbbbbb", lw=1)
mean = [np.mean([co[s][m] for s in ST]) for m in range(1, 13)]
ax.plot(range(1, 13), mean, color=BLUE, lw=2.5, marker="o", ms=4); ax.axhline(1, color="#999999", lw=1, ls=":")
ax.text(12.15, mean[-1], "media de estaciones", color=INK, fontsize=8, va="center"); ax.set_xlim(0.7, 14.6)
ax.set_xticks(range(1, 13)); ax.set_xticklabels(MON); ax.set_ylabel("coeficiente a (PM ≈ a · ET0 Open-Meteo)")
ax.set_title("Coeficientes AHC mensuales: hay que reducir Open-Meteo sobre todo en invierno")
fig.tight_layout(); fig.savefig(FIG / "05_coeficientes_mensuales.png", dpi=150); plt.close(fig)

# 6) deriva por anio
fig, ax = plt.subplots(figsize=(7.4, 3.8))
byyear = {}
for res, lab, c, ls in (("annual", "AHC anual", VIOLET, "-"), ("seasonal", "AHC estacional", GREEN, "-"), ("monthly", "AHC mensual", BLUE, "-")):
    d = rmse_by(series(res, "OM_AHC"), lambda s, dt: dt[:4]); byyear[res] = d
    ys = [d[str(y)]["bias"] for y in range(2020, 2026)]
    ax.plot(range(2020, 2026), ys, color=c, lw=2, marker="o", ms=4); ax.text(2025.1, ys[-1], lab, fontsize=8, va="center", color=INK)
ax.axhline(0, color="#999999", lw=1); ax.set_xlim(2019.8, 2027); ax.set_ylabel("sesgo (mm/día)")
ax.set_title("Sesgo residual por año de TEST de Open-Meteo + AHC (coeficientes fijados con ≤2019)")
fig.tight_layout(); fig.savefig(FIG / "06_sesgo_por_anio.png", dpi=150); plt.close(fig)

# tablas
def tab(h, b): return "\n".join(["| " + " | ".join(h) + " |", "|" + "---|" * len(h)] + ["| " + " | ".join(r) + " |" for r in b])
L = ["# Estudio 02 - tablas ampliadas (TEST 2020-2025, n=19.251)\n", "## RMSE global por método, familia y granularidad (mm/día)\n"]
body = []
for nm, k in (("Open-Meteo crudo", "OM_RAW"), ("Open-Meteo + AHC", "OM_AHC")):
    body.append([nm, "-"] + [f"{met(series(r, k))['rmse']:.3f}" for r in ("annual", "seasonal", "monthly")])
for f, lab in FAMS.items():
    for m in ("FORMULA", "AHC", "ML", "ANN_A", "ANN_E"):
        body.append([f"V2 {m}", lab] + [f"{met(series(r, f'{f}_{m}'))['rmse']:.3f}" for r in ("annual", "seasonal", "monthly")])
L.append(tab(["Método", "Familia (inputs)", "Anual", "Estacional", "Mensual"], body))
L.append("\n(FORMULA no depende de la granularidad; ML y ANN varían por la distinta corrida de V2 en cada resolución.)\n")
L.append("## Sesgo global (mm/día)\n")
body = [[nm] + [f"{met(series(r, k))['bias']:+.3f}" for r in ("annual", "seasonal", "monthly")] for nm, k in (("Open-Meteo crudo", "OM_RAW"), ("Open-Meteo + AHC", "OM_AHC"), ("HG-Rs ANN", "HG_RS_V1_ANN_A"), ("Valiantzas ANN", "VALIANTZAS_V1_ANN_A"), ("HS-Ra ANN", "HS_RA_V1_ANN_A"))]
L.append(tab(["Método", "Anual", "Estacional", "Mensual"], body))
L.append("\n## Por estación (resolución mensual, RMSE)\n")
body = [[s, f"{rmse_by(series('monthly','OM_RAW'), lambda a,b:a)[s]['rmse']:.3f}"] + [f"{bystation[n][s]['rmse']:.3f}" for n, _, _ in cand3] for s in ST]
L.append(tab(["Estación", "OM crudo", "OM + AHC", "Valiantzas ANN", "HG-Rs ANN"], body))
L.append("\n## Por mes calendario (resolución mensual, RMSE)\n")
body = [[MON[m - 1]] + [f"{bymonth[n][m]['rmse']:.3f}" for n, _, _, _ in cand] for m in range(1, 13)]
L.append(tab(["Mes"] + [n for n, _, _, _ in cand], body))
L.append("\n## Sesgo por año de TEST de Open-Meteo + AHC (mm/día)\n")
body = [[str(y)] + [f"{byyear[r][str(y)]['bias']:+.3f}" for r in ("annual", "seasonal", "monthly")] for y in range(2020, 2026)]
L.append(tab(["Año", "Anual", "Estacional", "Mensual"], body))
L.append("\n## Variantes más justas de Open-Meteo (RMSE / sesgo)\n")
vs = list(dict.fromkeys(r["variant"] for r in fv))
body = [[v] + [f"{float([r for r in fv if r['variant']==v and r['resolution']==res][0]['rmse']):.3f} / {float([r for r in fv if r['variant']==v and r['resolution']==res][0]['bias']):+.3f}" for res in ("annual", "seasonal", "monthly")] for v in vs]
L.append(tab(["Variante", "Anual", "Estacional", "Mensual"], body))
L.append("\n## Coeficientes AHC anuales por estación (a en PM ≈ a·ET0_OM, ajustados 2004-2019)\n")
ca = {r["station_code"]: r for r in csv.DictReader(open(RES / "coefficients.csv")) if r["resolution"] == "annual"}
L.append(tab(["Estación", "a", "n desarrollo"], [[s, ca[s]["coef_a"], ca[s]["n_dev"]] for s in ST]))
(RES / "tablas_ampliadas.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L))
