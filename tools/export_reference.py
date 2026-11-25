"""Extrae de classical-baselines.csv (Capitulo-1, ~56 MB) solo lo necesario para este repo.

Uso:
    python tools/export_reference.py --input classical-baselines.csv \
        --output data/reference/reference_2020_2025.csv

Escribe un CSV pequeno con las columnas pedidas y un .manifest.json con el SHA256 del original y del resultado.
Los nombres de columna por defecto son los del contrato de Capitulo-1; si la cabecera real difiere, se indica
con --station-col / --date-col y el script lista las columnas disponibles al fallar.
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--station-col", default="station_code")
    ap.add_argument("--date-col", default="date")
    ap.add_argument("--keep", default="split,PM_FAO56_V1,HS_RA_V1,HG_RS_V1,VALIANTZAS_V1,EtPMon,quality_status",
                    help="columnas adicionales a conservar (las que no existan se avisan y se omiten)")
    ap.add_argument("--start", default="2020-01-01")
    ap.add_argument("--end", default="2025-12-31")
    a = ap.parse_args()

    with open(a.input, newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        cols = rd.fieldnames or []
        for needed in (a.station_col, a.date_col):
            if needed not in cols:
                raise SystemExit(f"Falta la columna {needed!r}. Columnas disponibles: {cols}")
        keep = [c for c in a.keep.split(",") if c]
        missing = [c for c in keep if c not in cols]
        if missing:
            print(f"Aviso: columnas no encontradas y omitidas: {missing}")
        keep = [c for c in keep if c in cols]
        rows = [r for r in rd if a.start <= r[a.date_col][:10] <= a.end]

    a.output.parent.mkdir(parents=True, exist_ok=True)
    with open(a.output, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["station_code", "date"] + keep)
        for r in rows:
            w.writerow([r[a.station_col], r[a.date_col][:10]] + [r[c] for c in keep])

    meta = {
        "source_file": a.input.name, "source_sha256": sha256(a.input),
        "output_file": a.output.name, "output_sha256": sha256(a.output),
        "rows": len(rows), "period": [a.start, a.end], "columns": ["station_code", "date"] + keep,
        "note": "Subconjunto del CSV de Capitulo-1; PM_FAO56_V1 es referencia calculada (FAO-56), no ET0 medida. "
                "Origen de datos: SiAR (MAPA); citar siempre.",
    }
    a.output.with_suffix(".manifest.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
