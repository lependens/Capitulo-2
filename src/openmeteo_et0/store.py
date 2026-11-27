"""Almacenamiento de respuestas originales: nunca se sobrescriben, cada una lleva hash y fecha de consulta."""

import csv
import gzip
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from .stations import REPO_ROOT

RAW_DIR = REPO_ROOT / "data" / "raw"
MANIFEST_FIELDS = ["file", "product", "station_code", "tag", "url", "fetched_at_utc", "sha256_response", "bytes"]


def manifest_path(raw_dir: Path = RAW_DIR) -> Path:
    return raw_dir / "manifest.csv"


def read_manifest(raw_dir: Path = RAW_DIR):
    p = manifest_path(raw_dir)
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def already_fetched(product, station_code, tag, raw_dir: Path = RAW_DIR) -> bool:
    return any(
        r["product"] == product and r["station_code"] == station_code and r["tag"] == tag
        for r in read_manifest(raw_dir)
    )


def save_raw(product, station_code, tag, url, body: bytes, raw_dir: Path = RAW_DIR, now=None, ext="json"):
    """Guarda body comprimido (gzip determinista) y anade una fila al manifiesto. Devuelve la ruta.

    ext es solo la extension del fichero original (json, csv, zip); el contenido se guarda byte a byte.
    """
    now = now or datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    rel = Path(product) / station_code / f"{tag}__{stamp}.{ext}.gz"
    path = raw_dir / rel
    if path.exists():
        raise FileExistsError(f"No se sobrescribe: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
            gz.write(body)
    row = {
        "file": rel.as_posix(),
        "product": product,
        "station_code": station_code,
        "tag": tag,
        "url": url,
        "fetched_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha256_response": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
    }
    mp = manifest_path(raw_dir)
    new = not mp.exists()
    with open(mp, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)
    return path


def load_raw(rel_file, raw_dir: Path = RAW_DIR) -> bytes:
    with gzip.open(raw_dir / rel_file, "rb") as f:
        return f.read()


def verify(raw_dir: Path = RAW_DIR):
    """Comprueba que cada fichero del manifiesto existe y coincide con su hash. Devuelve lista de errores."""
    errors = []
    for r in read_manifest(raw_dir):
        p = raw_dir / r["file"]
        if not p.exists():
            errors.append(f"falta {r['file']}")
            continue
        if hashlib.sha256(load_raw(r["file"], raw_dir)).hexdigest() != r["sha256_response"]:
            errors.append(f"hash distinto {r['file']}")
    return errors
