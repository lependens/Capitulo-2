"""Estudio 01: tablas y graficos ampliados (Open-Meteo archive vs PM_FAO56_V1, 2020-2025)."""
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
FIG = HERE / "figures"
BLUE, ORANGE, INK, MUTED = "#257de0", "#f47230", "#191919", "#666666"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#999999", "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.titlecolor": INK, "axes.titleweight": "bold", "axes.titlesize": 11, "axes.titlelocation": "left"})

ref = {(r["station_code"], r["date"]): float(r["ET0_PM_FAO56_V1"]) for r in csv.DictReader(open(ROOT / "data/reference/reference_2020_2025.csv")) if r["ET0_PM_FAO56_V1"] != ""}
rows = []
for r in csv.DictReader(open(ROOT / "data/processed/openmeteo_archive.csv")):
    k = (r["station_code"], r["date"])
    if k in ref and r["et0_om_mm"] != "":
        rows.append((k[0], k[1], float(r["et0_om_mm"]), ref[k]))
st = sorted({r[0] for r in rows})
x = np.array([r[3] for r in rows]); y = np.array([r[2] for r in rows])
mon = np.array([int(r[1][5:7]) for r in rows]); yr = np.array([int(r[1][:4]) for r in rows]); sta = np.array([r[0] for r in rows])
print("n", len(rows))

# 1) dispersion
fig, ax = plt.subplots(figsize=(5.6, 5.2))
hb = ax.hexbin(x, y, gridsize=45, mincnt=1, cmap="Blues", bins="log")
lim = [0, max(x.max(), y.max()) + 0.3]
ax.plot(lim, lim, color=ORANGE, lw=2); ax.set_xlim(lim); ax.set_ylim(lim)
ax.text(lim[1] * 0.97, lim[1] * 0.90, "1:1", color=ORANGE, ha="right", fontweight="bold")
m = compute(list(zip(y, x)))
ax.set_xlabel("PM_FAO56_V1 (SIAR), mm/día"); ax.set_ylabel("ET0 Open-Meteo, mm/día")
ax.set_title(f"Open-Meteo sobreestima: RMSE {m['rmse']:.2f}, sesgo {m['bias']:+.2f}, R² {m['r2']:.2f}")
fig.colorbar(hb, label="nº de días (log)"); fig.tight_layout(); fig.savefig(FIG / "01_scatter.png", dpi=150); plt.close(fig)

# 2) sesgo y RMSE por mes
bm = [np.mean(y[mon == k] - x[mon == k]) for k in range(1, 13)]
rm = [math.sqrt(np.mean((y[mon == k] - x[mon == k]) ** 2)) for k in range(1, 13)]
fig, ax = plt.subplots(figsize=(7.4, 3.8))
ax.bar(np.arange(1, 13) - 0.2, bm, 0.38, color=BLUE, label="Sesgo (Open-Meteo − PM)")
ax.bar(np.arange(1, 13) + 0.2, rm, 0.38, color=ORANGE, label="RMSE")
ax.axhline(0, color="#999999", lw=1); ax.set_xticks(range(1, 13)); ax.set_xticklabels("E F M A M J J A S O N D".split())
ax.set_ylabel("mm/día"); ax.set_title("Sesgo positivo todos los meses; mayor en otoño-invierno, mínimo en mayo-junio"); ax.legend(frameon=False, loc="upper left")
fig.tight_layout(); fig.savefig(FIG / "02_mes.png", dpi=150); plt.close(fig)

# 3) mapa de calor sesgo estacion x mes
H = np.array([[np.mean(y[(sta == s) & (mon == k)] - x[(sta == s) & (mon == k)]) for k in range(1, 13)] for s in st])
fig, ax = plt.subplots(figsize=(7.6, 4.2))
im = ax.imshow(H, cmap="Blues", aspect="auto", vmin=0)
ax.set_xticks(range(12)); ax.set_xticklabels("E F M A M J J A S O N D".split()); ax.set_yticks(range(len(st))); ax.set_yticklabels(st)
for i in range(len(st)):
    for j in range(12):
        ax.text(j, i, f"{H[i, j]:.1f}", ha="center", va="center", fontsize=8, color="white" if H[i, j] > H.max() * 0.6 else INK)
ax.set_title("Sesgo Open-Meteo − PM (mm/día) por estación y mes"); fig.colorbar(im, label="mm/día")
fig.tight_layout(); fig.savefig(FIG / "03_sesgo_estacion_mes.png", dpi=150); plt.close(fig)

# 4) escenarios de sustitucion de inputs
sub = [r for r in csv.DictReader(open(HERE / "results/inputs_2020_2025/et0_substitution.csv")) if r["group"] == "global"]
sub = sorted(sub, key=lambda r: float(r["rmse"]))
fig, ax = plt.subplots(figsize=(7.4, 3.9))
names = [r["scenario"] for r in sub]; vals = [float(r["rmse"]) for r in sub]
cols = [ORANGE if "viento" in n and "solo" in n else BLUE for n in names]
ax.barh(names, vals, color=cols, height=0.6)
for i, v in enumerate(vals):
    ax.text(v + 0.01, i, f"{v:.3f}", va="center", color=INK, fontsize=9)
ax.invert_yaxis(); ax.set_xlabel("RMSE frente a PM_FAO56_V1 (mm/día)")
ax.set_title("El viento de Open-Meteo concentra casi todo el error"); fig.tight_layout(); fig.savefig(FIG / "04_sustitucion_inputs.png", dpi=150); plt.close(fig)

# 5) inputs: sesgo relativo
inp = list(csv.DictReader(open(HERE / "results/inputs_2020_2025/inputs_comparison.csv")))

# tablas
def tab(headers, body):
    return "\n".join(["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)] + ["| " + " | ".join(r) + " |" for r in body])

L = ["# Estudio 01 - tablas ampliadas (Open-Meteo archive vs PM_FAO56_V1, 2020-2025, n=%d)\n" % len(rows)]
L.append("## Por estación\n")
body = []
for s in st:
    mm = compute(list(zip(y[sta == s], x[sta == s])))
    body.append([s, str(mm["n"]), f"{mm['rmse']:.3f}", f"{mm['mae']:.3f}", f"{mm['bias']:+.3f}", f"{mm['r2']:.3f}", f"{float(np.mean(x[sta == s])):.2f}", f"{float(np.mean(y[sta == s])):.2f}"])
L.append(tab(["Estación", "n", "RMSE", "MAE", "Sesgo", "R²", "PM medio", "OM medio"], body))
L.append("\n## Por mes\n\n(R² mensual bajo o negativo en invierno: dentro de un mes la ET0 varía poco y el sesgo constante domina; no indica pérdida de correlación diaria.)\n")
body = []
for k in range(1, 13):
    mm = compute(list(zip(y[mon == k], x[mon == k])))
    body.append([f"{k:02d}", f"{mm['rmse']:.3f}", f"{mm['bias']:+.3f}", f"{mm['r2']:.3f}", f"{float(np.mean(x[mon == k])):.2f}", f"{float(np.mean(y[mon == k])):.2f}", f"{100 * mm['bias'] / float(np.mean(x[mon == k])):+.0f}%"])
L.append(tab(["Mes", "RMSE", "Sesgo", "R²", "PM medio", "OM medio", "Sesgo relativo"], body))
L.append("\n## Por año\n")
body = []
for k in sorted(set(yr)):
    mm = compute(list(zip(y[yr == k], x[yr == k])))
    body.append([str(k), str(mm["n"]), f"{mm['rmse']:.3f}", f"{mm['bias']:+.3f}", f"{mm['r2']:.3f}"])
L.append(tab(["Año", "n", "RMSE", "Sesgo", "R²"], body))
L.append("\n## Qué parte del error es sesgo y qué parte es ruido\n")
mm = compute(list(zip(y, x)))
L.append(f"RMSE total {mm['rmse']:.3f}; sesgo {mm['bias']:+.3f}; RMSE tras restar el sesgo medio global {math.sqrt(mm['rmse']**2 - mm['bias']**2):.3f}. "
         "Es decir, más de la mitad del error cuadrático es un desplazamiento sistemático corregible por calibración.\n")
L.append("## Inputs de Open-Meteo frente al sensor SIAR (OM − SIAR)\n")
L.append(tab(["Variable", "SIAR medio", "OM medio", "Sesgo", "RMSE", "Correlación"],
             [[r["variable"], f"{float(r['media_siar']):.2f}", f"{float(r['media_openmeteo']):.2f}", f"{float(r['sesgo']):+.2f}", f"{float(r['rmse']):.2f}", (f"{float(r['correlacion']):.2f}" if r["correlacion"] else "-")] for r in inp]))
L.append("\n## Escenarios de sustitución de inputs en PM (RMSE y sesgo globales frente a PM_FAO56_V1)\n")
L.append(tab(["Escenario", "RMSE", "Sesgo"], [[r["scenario"], f"{float(r['rmse']):.3f}", f"{float(r['bias']):+.3f}"] for r in sub[::-1]][::-1]))
(HERE / "results/tablas_ampliadas.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L)[:3500])
