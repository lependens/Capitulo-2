"""Alternativa al paso previo de los estudios 03.1/03.2: inputs de sensor SIAR 2004-2019 desde los CSV crudos de Capitulo-1.

Se usa solo si no se puede ejecutar tools/export_reference.py sobre classical-baselines.csv.
Antes de exportar comprueba que, en 2020-2025, los crudos coinciden EXACTAMENTE (mismas claves, mismos vacios,
mismos valores) con data/reference/siar_inputs_2020_2025.csv (exportado de classical-baselines.csv). Si no
coinciden, se detiene sin escribir nada.

Las claves del resultado son las de data/reference/reference_2004_2019.csv (mismo universo de filas que tendria la
exportacion de classical-baselines.csv) y quality_status sale de ese mismo fichero. Lo crudo no se modifica.

Uso (desde la raiz de Capitulo-2):
    python tools/export_inputs_from_raw.py --raw-dir ../Capitulo-1/datos_siar_baleares \
        --output data/reference/siar_inputs_2004_2019.csv
"""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

COLS = ["TempMax", "TempMin", "TempMedia", "HumedadMax", "HumedadMin", "HumedadMedia", "VelViento", "Radiacion"]
ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def same(a, b):
    if a == "" or b == "":
        return a == b
    return float(a) == float(b) or (math.isnan(float(a)) and math.isnan(float(b)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--check", default=ROOT / "data/reference/siar_inputs_2020_2025.csv", type=Path)
    ap.add_argument("--keys", default=ROOT / "data/reference/reference_2004_2019.csv", type=Path)
    a = ap.parse_args()

    keys = list(csv.DictReader(open(a.keys, newline="", encoding="utf-8")))
    stations = sorted({r["station_code"] for r in keys} | {r["station_code"] for r in csv.DictReader(open(a.check))})
    raw, raw_files = {}, {}
    for st in stations:
        p = a.raw_dir / f"{st}_datos_completos.csv"
        raw_files[p.name] = sha256(p)
        for r in csv.DictReader(open(p, newline="", encoding="utf-8-sig")):
            k = (r["Estacion"], r["Fecha"][:10])
            if k in raw:
                raise SystemExit(f"Clave duplicada en crudo: {k}")
            raw[k] = r

    # 1) Comprobacion de coincidencia 2020-2025
    n_chk, bad = 0, []
    for r in csv.DictReader(open(a.check, newline="", encoding="utf-8")):
        k = (r["station_code"], r["date"])
        if k not in raw:
            bad.append((k, "falta en crudo"))
            continue
        for c in COLS:
            if not same(r[c], raw[k][c]):
                bad.append((k, c, r[c], raw[k][c]))
        n_chk += 1
    if bad:
        raise SystemExit(f"NO COINCIDEN en 2020-2025 ({len(bad)} discrepancias, primeras: {bad[:5]}). Se para.")
    print(f"Comprobacion 2020-2025: {n_chk} filas, {len(COLS)} columnas, 0 discrepancias.")

    # 2) Exportacion 2004-2019 con las claves de reference_2004_2019.csv
    missing = [(r["station_code"], r["date"]) for r in keys if (r["station_code"], r["date"]) not in raw]
    if missing:
        raise SystemExit(f"Claves de referencia sin fila cruda: {len(missing)} (p. ej. {missing[:5]}). Se para.")
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with open(a.output, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["station_code", "date"] + COLS + ["quality_status"])
        for r in keys:
            src = raw[(r["station_code"], r["date"])]
            w.writerow([r["station_code"], r["date"]] + [src[c] for c in COLS] + [r["quality_status"]])

    meta = {
        "source": "CSV crudos de Capitulo-1 (alternativa; classical-baselines.csv no disponible en el entorno de ejecucion)",
        "raw_files_sha256": raw_files,
        "keys_and_quality_from": {"file": a.keys.name, "sha256": sha256(a.keys)},
        "check_2020_2025": {"file": a.check.name, "sha256": sha256(a.check), "rows": n_chk,
                            "columns": COLS, "discrepancies": 0},
        "output_file": a.output.name, "output_sha256": sha256(a.output), "rows": len(keys),
        "period": ["2004-01-01", "2019-12-31"], "columns": ["station_code", "date"] + COLS + ["quality_status"],
        "note": "Mismas columnas que siar_inputs_2020_2025.csv. Origen de datos: SiAR (MAPA); citar siempre.",
    }
    a.output.with_suffix(".manifest.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
