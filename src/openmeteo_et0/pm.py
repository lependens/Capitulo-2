"""Penman-Monteith FAO-56 diaria (G = 0), para estudios de sensibilidad a los inputs.

Sigue FAO-56 y las decisiones documentadas en Capitulo-1 (es y ea desde Tmin/Tmax y HRmax/HRmin,
albedo 0,23, Rs/Rso con techo 1, temperatura media = (Tmax+Tmin)/2). No sustituye a PM_FAO56_V1:
se valida contra ella en tests y en el estudio (ver studies/01_et0_vs_pm/diagnose_inputs.py).
"""

import math
from datetime import date as _date

GSC = 0.0820  # MJ m-2 min-1
SIGMA = 4.903e-9  # MJ K-4 m-2 dia-1
WIND_10M_TO_2M = 4.87 / math.log(67.8 * 10 - 5.42)  # FAO-56 ec. 47 ~ 0,748


def e0(t):
    return 0.6108 * math.exp(17.27 * t / (t + 237.3))


def extraterrestrial_radiation(lat_deg, iso_date):
    j = _date.fromisoformat(iso_date).timetuple().tm_yday
    phi = math.radians(lat_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi * j / 365)
    delta = 0.409 * math.sin(2 * math.pi * j / 365 - 1.39)
    x = max(-1.0, min(1.0, -math.tan(phi) * math.tan(delta)))
    ws = math.acos(x)
    return (24 * 60 / math.pi) * GSC * dr * (ws * math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.sin(ws))


def et0_pm(tmax, tmin, rhmax, rhmin, u2, rs, lat_deg, alt_m, iso_date):
    """ET0 (mm/dia). Rs en MJ m-2 dia-1, u2 en m/s, HR en %."""
    tmean = (tmax + tmin) / 2
    es = (e0(tmax) + e0(tmin)) / 2
    ea = (e0(tmin) * rhmax / 100 + e0(tmax) * rhmin / 100) / 2
    delta = 4098 * e0(tmean) / (tmean + 237.3) ** 2
    pressure = 101.3 * ((293 - 0.0065 * alt_m) / 293) ** 5.26
    gamma = 0.000665 * pressure
    ra = extraterrestrial_radiation(lat_deg, iso_date)
    rso = (0.75 + 2e-5 * alt_m) * ra
    ratio = min(rs / rso, 1.0) if rso > 0 else 0.0
    rns = (1 - 0.23) * rs
    rnl = SIGMA * (((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2) * (0.34 - 0.14 * math.sqrt(max(ea, 0.0))) * (1.35 * ratio - 0.35)
    rn = rns - rnl
    num = 0.408 * delta * rn + gamma * 900 / (tmean + 273) * u2 * (es - ea)
    return num / (delta + gamma * (1 + 0.34 * u2))
