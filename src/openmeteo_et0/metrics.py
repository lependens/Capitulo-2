"""Metricas con las mismas definiciones que ET0 V2: error = prediccion - referencia;
n, MAE, RMSE, sesgo y R2 predictivo = 1 - SSE/SST. Temporadas: DJF asigna diciembre al anio siguiente."""

import hashlib
import math

SEASONS = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM",
           6: "JJA", 7: "JJA", 8: "JJA", 9: "SON", 10: "SON", 11: "SON"}


def season_key(iso_date: str):
    """(anio_de_temporada, temporada). Diciembre pertenece al DJF del anio siguiente."""
    y, m = int(iso_date[0:4]), int(iso_date[5:7])
    return (y + 1 if m == 12 else y), SEASONS[m]


def compute(pairs):
    """pairs: lista de (prediccion, referencia). Devuelve dict de metricas."""
    n = len(pairs)
    if n == 0:
        return {"n": 0, "mae": "", "rmse": "", "bias": "", "r2": "", "r2_status": "empty"}
    err = [p - r for p, r in pairs]
    sse = sum(e * e for e in err)
    mean_ref = sum(r for _, r in pairs) / n
    sst = sum((r - mean_ref) ** 2 for _, r in pairs)
    r2, status = ("", "sst_zero") if sst == 0 else (1 - sse / sst, "ok")
    return {"n": n, "mae": sum(abs(e) for e in err) / n, "rmse": math.sqrt(sse / n),
            "bias": sum(err) / n, "r2": r2, "r2_status": status}


def group_metrics(records, value_key="pred", ref_key="ref"):
    """records: dicts con station_code, date, pred, ref. Devuelve filas (group, key, metricas)."""
    groupers = {
        "global": lambda r: "all",
        "station": lambda r: r["station_code"],
        "year": lambda r: r["date"][:4],
        "month": lambda r: r["date"][5:7],
        "season": lambda r: "{}-{}".format(*season_key(r["date"])),
        "station_year": lambda r: f"{r['station_code']}|{r['date'][:4]}",
        "station_season": lambda r: "{}|{}-{}".format(r["station_code"], *season_key(r["date"])),
    }
    out = []
    for gname, fn in groupers.items():
        buckets = {}
        for r in records:
            buckets.setdefault(fn(r), []).append((r[value_key], r[ref_key]))
        for key in sorted(buckets):
            m = compute(buckets[key])
            out.append({"group": gname, "key": key, **m})
    return out


def cohort_hash(records):
    """SHA256 de las claves estacion|fecha ordenadas (identifica la cohorte, no los valores)."""
    keys = sorted(f"{r['station_code']}|{r['date']}" for r in records)
    return hashlib.sha256("\n".join(keys).encode("utf-8")).hexdigest()


def verdict(global_m, station_rmse_max, thresholds):
    """Aplica los umbrales congelados de config/thresholds.json."""
    comp, use = thresholds["competitive"], thresholds["usable"]
    rmse, bias = global_m["rmse"], abs(global_m["bias"])
    if rmse <= comp["global_rmse_max"] and bias <= comp["global_abs_bias_max"] \
            and station_rmse_max <= comp["per_station_rmse_max"]:
        return "COMPETITIVO"
    if rmse <= use["global_rmse_max"]:
        return "UTILIZABLE_NO_DIFERENCIAL"
    return "NO_COMPETITIVO"
