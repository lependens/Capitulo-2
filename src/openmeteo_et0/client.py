"""Cliente minimo de Open-Meteo (solo libreria estandar).

Se guardan las respuestas originales tal como llegan; no se interpretan aqui.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

TIMEZONE = "Europe/Madrid"
USER_AGENT = "Capitulo-2-research/0.1 (non-commercial scientific use; github.com/lependens/Capitulo-2)"

# Variables diarias con nombre confirmado en la documentacion de Open-Meteo.
DAILY_VARS = [
    "et0_fao_evapotranspiration",
    "temperature_2m_max",
    "temperature_2m_min",
    "shortwave_radiation_sum",
    "wind_speed_10m_max",
]
# La humedad diaria no tiene nombre confirmado: se baja horaria y se agrega en normalize.py.
HOURLY_VARS = ["relative_humidity_2m", "wind_speed_10m"]

PRODUCTS = {
    # Reanalisis (ERA5 y similares): serie homogenea para el test retrospectivo.
    "archive": {
        "url": "https://archive-api.open-meteo.com/v1/archive",
        "daily": DAILY_VARS,
        "hourly": HOURLY_VARS,
        "uses_dates": True,
    },
    # Salidas de modelos operativos archivadas (datos desde 2022, segun la documentacion).
    "historical_forecast": {
        "url": "https://historical-forecast-api.open-meteo.com/v1/forecast",
        "daily": DAILY_VARS,
        "hourly": HOURLY_VARS,
        "uses_dates": True,
    },
    # Prevision actual: se guarda una captura diaria (no se puede reconstruir despues).
    "forecast": {
        "url": "https://api.open-meteo.com/v1/forecast",
        "daily": DAILY_VARS,
        "hourly": [],
        "uses_dates": False,
    },
}


def build_params(product, station, start=None, end=None, models=None, forecast_days=16, past_days=1):
    spec = PRODUCTS[product]
    params = {
        "latitude": f"{station.latitude:.4f}",
        "longitude": f"{station.longitude:.4f}",
        "elevation": f"{station.altitude_m:g}",
        "timezone": TIMEZONE,
        "wind_speed_unit": "ms",
        "daily": ",".join(spec["daily"]),
    }
    if spec["hourly"]:
        params["hourly"] = ",".join(spec["hourly"])
    if spec["uses_dates"]:
        if not (start and end):
            raise ValueError(f"El producto {product} necesita start y end")
        params["start_date"] = start
        params["end_date"] = end
    else:
        params["forecast_days"] = str(forecast_days)
        params["past_days"] = str(past_days)
    if models:
        params["models"] = models
    return params


def build_url(product, params):
    return PRODUCTS[product]["url"] + "?" + urllib.parse.urlencode(params, safe=",")


def fetch(url, retries=4, backoff=5.0, timeout=90, sleep=time.sleep):
    """GET con reintentos en 429/5xx y errores de red. Devuelve los bytes de la respuesta."""
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
            check_body(body)
            return body
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in (429, 500, 502, 503, 504):
                detail = e.read()[:300].decode("utf-8", "replace")
                raise RuntimeError(f"HTTP {e.code} en {url}: {detail}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
        if attempt < retries:
            sleep(backoff * (2**attempt))
    raise RuntimeError(f"Fallo tras {retries + 1} intentos en {url}: {last}")


def check_body(body):
    """Open-Meteo puede devolver 200 con {"error": true, "reason": ...}."""
    data = json.loads(body)
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(f"Open-Meteo devolvio error: {data.get('reason')}")
