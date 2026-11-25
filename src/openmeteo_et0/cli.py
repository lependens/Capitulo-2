"""Linea de comandos: backfill historico, captura diaria de prevision y construccion de tablas.

Uso (desde la raiz del repo):
    PYTHONPATH=src python -m openmeteo_et0 backfill --product archive --start 2020-01-01 --end 2025-12-31
    PYTHONPATH=src python -m openmeteo_et0 daily-forecast
    PYTHONPATH=src python -m openmeteo_et0 build-processed --product archive
    PYTHONPATH=src python -m openmeteo_et0 verify
"""

import argparse
import sys
import time
from datetime import date, datetime, timezone

from . import client, normalize, store
from .stations import load_stations


def year_chunks(start: str, end: str):
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    if e < s:
        raise ValueError("end anterior a start")
    out = []
    for y in range(s.year, e.year + 1):
        a = max(s, date(y, 1, 1))
        b = min(e, date(y, 12, 31))
        out.append((a.isoformat(), b.isoformat()))
    return out


def _codes(arg):
    return [c.strip() for c in arg.split(",") if c.strip()] if arg else None


def run_backfill(product, start, end, codes=None, force=False, models=None,
                 pause=1.0, raw_dir=store.RAW_DIR, fetcher=client.fetch, sleep=time.sleep):
    failures = []
    for st in load_stations(codes=codes):
        for a, b in year_chunks(start, end):
            tag = f"{a}_{b}"
            if not force and store.already_fetched(product, st.code, tag, raw_dir):
                print(f"= {product} {st.code} {tag}: ya descargado")
                continue
            params = client.build_params(product, st, start=a, end=b, models=models)
            url = client.build_url(product, params)
            try:
                body = fetcher(url)
                store.save_raw(product, st.code, tag, url, body, raw_dir)
                print(f"+ {product} {st.code} {tag}: {len(body)} bytes")
            except Exception as e:  # sigue con el resto y falla al final
                failures.append(f"{st.code} {tag}: {e}")
                print(f"! {product} {st.code} {tag}: {e}", file=sys.stderr)
            sleep(pause)
    return failures


def run_daily_forecast(codes=None, pause=1.0, raw_dir=store.RAW_DIR, fetcher=client.fetch,
                       sleep=time.sleep, now=None):
    now = now or datetime.now(timezone.utc)
    tag = now.strftime("%Y-%m-%d")  # fecha de emision (UTC)
    failures = []
    for st in load_stations(codes=codes):
        if store.already_fetched("forecast", st.code, tag, raw_dir):
            print(f"= forecast {st.code} {tag}: ya capturado hoy")
            continue
        params = client.build_params("forecast", st)
        url = client.build_url("forecast", params)
        try:
            body = fetcher(url)
            store.save_raw("forecast", st.code, tag, url, body, raw_dir, now=now)
            print(f"+ forecast {st.code} {tag}: {len(body)} bytes")
        except Exception as e:
            failures.append(f"{st.code} {tag}: {e}")
            print(f"! forecast {st.code} {tag}: {e}", file=sys.stderr)
        sleep(pause)
    return failures


def main(argv=None):
    p = argparse.ArgumentParser(prog="openmeteo_et0")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("backfill", help="descarga historica por estacion y anio")
    b.add_argument("--product", choices=["archive", "historical_forecast"], required=True)
    b.add_argument("--start", required=True)
    b.add_argument("--end", required=True)
    b.add_argument("--stations", help="codigos separados por comas (por defecto, todas)")
    b.add_argument("--models", help="parametro models de Open-Meteo (opcional)")
    b.add_argument("--force", action="store_true", help="vuelve a pedir aunque ya exista (se guarda como captura nueva)")

    d = sub.add_parser("daily-forecast", help="captura la prevision de hoy (16 dias)")
    d.add_argument("--stations")

    t = sub.add_parser("build-processed", help="construye data/processed/*.csv desde las respuestas crudas")
    t.add_argument("--product", choices=["archive", "historical_forecast", "forecast"], required=True)

    sub.add_parser("verify", help="comprueba hashes de data/raw")

    a = p.parse_args(argv)
    if a.cmd == "backfill":
        fails = run_backfill(a.product, a.start, a.end, _codes(a.stations), a.force, a.models)
    elif a.cmd == "daily-forecast":
        fails = run_daily_forecast(_codes(a.stations))
    elif a.cmd == "build-processed":
        path, n = normalize.build_processed(a.product)
        print(f"{path}: {n} filas")
        return 0
    else:
        errs = store.verify()
        for e in errs:
            print(e, file=sys.stderr)
        print("OK" if not errs else f"{len(errs)} errores")
        return 1 if errs else 0

    if fails:
        print(f"{len(fails)} descargas fallidas:", *fails, sep="\n  ", file=sys.stderr)
        return 1
    return 0
