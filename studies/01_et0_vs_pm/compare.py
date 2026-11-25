"""Estudio 01: ET0 de Open-Meteo frente a PM_FAO56_V1 (y frente a las formulas clasicas V2).

Uso:
    PYTHONPATH=src python studies/01_et0_vs_pm/compare.py \
        --reference data/reference/reference_2020_2025.csv \
        --openmeteo data/processed/openmeteo_archive.csv

El criterio de exito se lee de config/thresholds.json (fijado antes de ver resultados).
Salida: studies/01_et0_vs_pm/results/<producto>/ (metricas por grupo, resumen y hash de cohorte).
"""

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from openmeteo_et0 import metrics  # noqa: E402
from openmeteo_et0.stations import load_stations  # noqa: E402

FIELDS = ["group", "key", "n", "mae", "rmse", "bias", "r2", "r2_status"]


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def to_float(v):
    try:
        return float(v) if v not in ("", None) else None
    except ValueError:
        return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", required=True, type=Path)
    ap.add_argument("--openmeteo", required=True, type=Path)
    ap.add_argument("--station-col", default="station_code")
    ap.add_argument("--date-col", default="date")
    ap.add_argument("--ref-col", default="PM_FAO56_V1")
    ap.add_argument("--om-col", default="et0_om_mm")
    ap.add_argument("--baselines", default="HS_RA_V1,VALIANTZAS_V1,HG_RS_V1",
                    help="columnas de formulas clasicas en el CSV de referencia (vacio para omitir)")
    ap.add_argument("--start", default="2020-01-01")
    ap.add_argument("--end", default="2025-12-31")
    ap.add_argument("--thresholds", default=ROOT / "config" / "thresholds.json", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)

    active = {s.code for s in load_stations()}
    om = {}
    for r in read_csv(a.openmeteo):
        v = to_float(r[a.om_col])
        if v is not None:
            om[(r["station_code"], r["date"])] = v

    baselines = [b for b in a.baselines.split(",") if b]
    cohort, base_rows = [], {b: [] for b in baselines}
    for r in read_csv(a.reference):
        st, d = r[a.station_col], r[a.date_col][:10]
        if st not in active or not (a.start <= d <= a.end):
            continue
        ref = to_float(r[a.ref_col])
        if ref is None:
            continue
        key = (st, d)
        if key in om:
            rec = {"station_code": st, "date": d, "pred": om[key], "ref": ref}
            cohort.append(rec)
            for b in baselines:
                bv = to_float(r.get(b))
                if bv is not None:
                    base_rows[b].append({"station_code": st, "date": d, "pred": bv, "ref": ref})

    out = a.out or Path(__file__).parent / "results" / a.openmeteo.stem
    out.mkdir(parents=True, exist_ok=True)

    def dump(name, recs):
        rows = metrics.group_metrics(recs)
        with open(out / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows)
        return rows

    om_rows = dump("openmeteo", cohort)
    for b in baselines:
        dump(b.lower(), base_rows[b])

    thresholds = json.loads(Path(a.thresholds).read_text(encoding="utf-8"))
    gm = next(r for r in om_rows if r["group"] == "global")
    st_rmse = [r["rmse"] for r in om_rows if r["group"] == "station" and r["n"]]
    result = metrics.verdict(gm, max(st_rmse), thresholds) if gm["n"] else "SIN_DATOS"

    lines = [f"# Estudio 01 - resumen ({a.openmeteo.name})", "",
             f"- Referencia: {a.ref_col}; periodo {a.start} a {a.end}; estaciones activas del catalogo.",
             f"- Cohorte (estacion-fecha con referencia y Open-Meteo): n = {len(cohort)}; "
             f"SHA256 de claves = `{metrics.cohort_hash(cohort)}`.",
             f"- Open-Meteo global: RMSE {gm['rmse']:.3f}, MAE {gm['mae']:.3f}, sesgo {gm['bias']:+.3f} mm/dia, R2 {gm['r2']:.3f}."
             if gm["n"] else "- Sin datos.",
             f"- Umbrales: thresholds.json v{thresholds['version']} (fijado {thresholds['frozen_on']}).",
             f"- **Veredicto: {result}**", "",
             "Formulas V2 sin ajustar sobre sus propias parejas con PM (cohortes distintas: n aparte):", ""]
    for b in baselines:
        g = next((r for r in metrics.group_metrics(base_rows[b]) if r["group"] == "global"), None)
        if g and g["n"]:
            lines.append(f"- {b}: n {g['n']}, RMSE {g['rmse']:.3f}, sesgo {g['bias']:+.3f}")
    lines += ["", "Que NO se concluye: que Open-Meteo sea mejor o peor en general, solo su acuerdo con PM calculada "
              "en estas estaciones y fechas. Rejilla con todos los inputs frente a modelos con pocos inputs de sensor."]
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
