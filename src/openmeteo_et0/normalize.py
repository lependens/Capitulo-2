"""De respuestas originales a tablas diarias (CSV). Las respuestas crudas no se tocan."""

import csv
import json
from datetime import date as _date
from pathlib import Path

from .stations import REPO_ROOT
from . import store

PROCESSED_DIR = REPO_ROOT / "data" / "processed"

ARCHIVE_FIELDS = [
    "station_code", "date", "product", "et0_om_mm", "tmax_c", "tmin_c",
    "shortwave_sum_mj_m2", "wind10_max_ms", "wind10_mean_ms",
    "rh_max_pct", "rh_min_pct", "rh_mean_pct", "rh_hours", "api_elevation_m", "fetched_at_utc",
]
FORECAST_FIELDS = [
    "station_code", "issue_date", "date", "lead_days", "et0_om_mm", "tmax_c", "tmin_c",
    "shortwave_sum_mj_m2", "wind10_max_ms", "api_elevation_m", "fetched_at_utc",
]


def _num(v):
    return "" if v is None else v


def parse_response(body: bytes):
    """Devuelve (daily_rows, elevation). daily_rows: dict fecha -> dict de valores (humedad agregada del horario)."""
    data = json.loads(body)
    if isinstance(data, dict) and data.get("error"):
        raise ValueError(f"respuesta con error: {data.get('reason')}")
    daily = data.get("daily") or {}
    times = daily.get("time") or []
    rows = {}
    for i, d in enumerate(times):
        rows[d] = {
            "et0_om_mm": _num(daily.get("et0_fao_evapotranspiration", [None] * len(times))[i]),
            "tmax_c": _num(daily.get("temperature_2m_max", [None] * len(times))[i]),
            "tmin_c": _num(daily.get("temperature_2m_min", [None] * len(times))[i]),
            "shortwave_sum_mj_m2": _num(daily.get("shortwave_radiation_sum", [None] * len(times))[i]),
            "wind10_max_ms": _num(daily.get("wind_speed_10m_max", [None] * len(times))[i]),
        }
    hourly = data.get("hourly") or {}
    htimes = hourly.get("time") or []
    rh = hourly.get("relative_humidity_2m") or []
    ws = hourly.get("wind_speed_10m") or []
    agg = {}
    for i, t in enumerate(htimes):
        day = t[:10]  # horas en hora local (timezone Europe/Madrid)
        a = agg.setdefault(day, {"rh": [], "ws": []})
        if i < len(rh) and rh[i] is not None:
            a["rh"].append(rh[i])
        if i < len(ws) and ws[i] is not None:
            a["ws"].append(ws[i])
    for day, a in agg.items():
        if day not in rows:
            continue
        r = rows[day]
        r["rh_hours"] = len(a["rh"])
        r["rh_max_pct"] = max(a["rh"]) if a["rh"] else ""
        r["rh_min_pct"] = min(a["rh"]) if a["rh"] else ""
        r["rh_mean_pct"] = round(sum(a["rh"]) / len(a["rh"]), 4) if a["rh"] else ""
        r["wind10_mean_ms"] = round(sum(a["ws"]) / len(a["ws"]), 4) if a["ws"] else ""
    return rows, data.get("elevation", "")


def build_archive_like(product, raw_dir=store.RAW_DIR):
    """Tabla (estacion, fecha) para archive / historical_forecast. Si hay duplicados gana la consulta mas reciente."""
    manifest = [r for r in store.read_manifest(raw_dir) if r["product"] == product]
    manifest.sort(key=lambda r: r["fetched_at_utc"])
    table = {}
    for r in manifest:
        rows, elev = parse_response(store.load_raw(r["file"], raw_dir))
        for d, v in rows.items():
            rec = {"station_code": r["station_code"], "date": d, "product": product,
                   "api_elevation_m": elev, "fetched_at_utc": r["fetched_at_utc"]}
            rec.update(v)
            table[(r["station_code"], d)] = rec
    return [table[k] for k in sorted(table)]


def build_forecast(raw_dir=store.RAW_DIR):
    """Una fila por (estacion, fecha de emision, fecha prevista). La fecha de emision es la de la consulta (UTC)."""
    out = []
    for r in store.read_manifest(raw_dir):
        if r["product"] != "forecast":
            continue
        rows, elev = parse_response(store.load_raw(r["file"], raw_dir))
        issue = r["tag"]
        for d, v in rows.items():
            lead = (_date.fromisoformat(d) - _date.fromisoformat(issue)).days
            out.append({
                "station_code": r["station_code"], "issue_date": issue, "date": d, "lead_days": lead,
                "et0_om_mm": v["et0_om_mm"], "tmax_c": v["tmax_c"], "tmin_c": v["tmin_c"],
                "shortwave_sum_mj_m2": v["shortwave_sum_mj_m2"], "wind10_max_ms": v["wind10_max_ms"],
                "api_elevation_m": elev, "fetched_at_utc": r["fetched_at_utc"],
            })
    out.sort(key=lambda x: (x["station_code"], x["issue_date"], x["date"]))
    return out


def write_csv(path: Path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", restval="")
        w.writeheader()
        w.writerows(rows)


def build_processed(product, raw_dir=store.RAW_DIR, out_dir=PROCESSED_DIR):
    if product == "forecast":
        rows = build_forecast(raw_dir)
        fields = FORECAST_FIELDS
    else:
        rows = build_archive_like(product, raw_dir)
        fields = ARCHIVE_FIELDS
    path = out_dir / f"openmeteo_{product}.csv"
    write_csv(path, fields, rows)
    return path, len(rows)
