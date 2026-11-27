"""Captura de la prevision de ECMWF (datos abiertos, IFS 0.25 grados) en los puntos de las estaciones.

Por que: es una fuente con licencia CC-BY-4.0 (uso comercial permitido citando a ECMWF), a diferencia
de la API gratuita de Open-Meteo. La serie de previsiones tal como se emitieron no se puede
reconstruir despues, y el estudio 04 la necesita.

Que guarda: por estacion y emision, los 4 puntos de rejilla mas cercanos (valor, lat, lon, distancia)
de cada variable y paso, en data/raw/ecmwf_ifs/<estacion>/<fecha>_<hora>z__<sello>.json.gz, con el mismo
manifiesto que el resto de capturas. No se guardan los campos globales (centenares de MB).

Requisitos (solo en el workflow, no en el nucleo del paquete): ecmwf-opendata y eccodes.

Uso:
    PYTHONPATH=src python tools/capture_ecmwf.py            # ultima emision disponible (00z o 12z)
    PYTHONPATH=src python tools/capture_ecmwf.py --time 0   # ultima emision de las 00z
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openmeteo_et0 import store  # noqa: E402
from openmeteo_et0.stations import load_stations  # noqa: E402

PRODUCT = "ecmwf_ifs"
SOURCE = "ecmwf"
# Variables instantaneas y acumuladas de la emision HRES de datos abiertos.
# 2t, 2d: temperatura y punto de rocio a 2 m (K); 10u, 10v: viento a 10 m (m/s);
# ssrd: radiacion solar descendente acumulada desde el paso 0 (J/m2); tp: precipitacion acumulada (m).
PARAMS = ["2t", "2d", "10u", "10v", "ssrd", "tp"]
# Cada 3 h hasta 144 h y cada 6 h hasta 240 h.
STEPS = list(range(0, 145, 3)) + list(range(150, 241, 6))
LICENSE_NOTE = "Fuente: ECMWF, datos abiertos en tiempo real, licencia CC-BY-4.0"


def empty_payload(station):
    return {"station_code": station.code, "latitude": station.latitude, "longitude": station.longitude, "fields": {}}


def add_points(payload, name, step, points):
    """Anade los vecinos de rejilla de una variable y un paso. points: dicts con lat, lon, value, distance."""
    payload["fields"].setdefault(name, {})[str(step)] = [
        {"lat": p["lat"], "lon": p["lon"], "value": p["value"], "distance_km": p["distance"]} for p in points
    ]


def _nearest(gid, lat, lon):
    import eccodes

    res = eccodes.codes_grib_find_nearest(gid, lat, lon, is_lsm=False, npoints=4)
    return [{"lat": r.lat, "lon": r.lon, "value": r.value, "distance": r.distance} for r in res]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--time", type=int, choices=[0, 12], default=None, help="hora de la emision (0 o 12); por defecto la ultima")
    ap.add_argument("--stations", nargs="*", default=None)
    a = ap.parse_args(argv)

    from ecmwf.opendata import Client

    client = Client(source=SOURCE)
    req = dict(type="fc", stream="oper", step=STEPS, param=PARAMS)
    if a.time is not None:
        req["time"] = a.time
    latest = client.latest(**{k: v for k, v in req.items() if k in ("type", "stream", "time", "param", "step")})
    tag = f"{latest:%Y-%m-%d}_{latest:%H}z"
    stations = load_stations(codes=a.stations)

    if all(store.already_fetched(PRODUCT, s.code, tag) for s in stations):
        print(f"= {tag}: ya capturada")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "fc.grib2"
        client.retrieve(date=latest.strftime("%Y-%m-%d"), time=latest.hour, target=str(target), **req)
        fields = _collect(target, stations)

    url = f"ecmwf-opendata source={SOURCE} stream=oper type=fc run={tag} params={','.join(PARAMS)}"
    fails = 0
    for code, payload in fields.items():
        payload.update({"run": tag, "license": LICENSE_NOTE, "grid": "0.25deg", "params": PARAMS})
        if not payload["fields"]:
            print(f"! {code} {tag}: sin campos", file=sys.stderr)
            fails += 1
            continue
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        store.save_raw(PRODUCT, code, tag, url, body)
        print(f"+ {PRODUCT} {code} {tag}: {len(body)} bytes")
    return 1 if fails else 0


def _collect(path, stations):
    """Lee el GRIB una vez y extrae los vecinos de cada estacion antes de liberar cada mensaje."""
    import eccodes

    out = {s.code: empty_payload(s) for s in stations}
    with open(path, "rb") as f:
        while True:
            gid = eccodes.codes_grib_new_from_file(f)
            if gid is None:
                break
            try:
                name = eccodes.codes_get(gid, "shortName")
                step = int(eccodes.codes_get(gid, "step"))
                for s in stations:
                    add_points(out[s.code], name, step, _nearest(gid, s.latitude, s.longitude))
            finally:
                eccodes.codes_release(gid)
    return out


if __name__ == "__main__":
    sys.exit(main())
