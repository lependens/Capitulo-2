"""Catalogo de estaciones activas (config/stations.csv)."""

import csv
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIONS_CSV = REPO_ROOT / "config" / "stations.csv"


@dataclass(frozen=True)
class Station:
    code: str
    name: str
    latitude: float
    longitude: float  # derivada del formato nativo del catalogo; solo para consultar Open-Meteo
    altitude_m: float


def load_stations(path: Path = STATIONS_CSV, codes=None):
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if codes and row["station_code"] not in codes:
                continue
            out.append(
                Station(
                    code=row["station_code"],
                    name=row["name"],
                    latitude=float(row["latitude_deg"]),
                    longitude=float(row["longitude_deg_derived"]),
                    altitude_m=float(row["altitude_m"]),
                )
            )
    if codes:
        missing = set(codes) - {s.code for s in out}
        if missing:
            raise ValueError(f"Estaciones desconocidas: {sorted(missing)}")
    return out
