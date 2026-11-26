# Diagnostico de inputs (2020-2025, 9 estaciones)

Cohorte: 19251 dias con inputs completos en SIAR y Open-Meteo y referencia PM_FAO56_V1; SHA256 de claves `7f24e7d90d83a619aa78fc4d094013f6e38d0953748223fb701d7b606f49eb26`.
Viento de Open-Meteo convertido de 10 m a 2 m (x0.748).

## Inputs: Open-Meteo menos SIAR

| Variable | Media SIAR | Media Open-Meteo | Sesgo | RMSE | Correlacion |
|---|---:|---:|---:|---:|---:|
| Tmax (C) | 23.95 | 22.13 | -1.83 | 2.38 | 0.975 |
| Tmin (C) | 11.74 | 14.98 | +3.23 | 3.96 | 0.929 |
| HRmax (%) | 94.98 | 90.28 | -4.70 | 8.55 | 0.556 |
| HRmin (%) | 50.61 | 53.43 | +2.82 | 10.05 | 0.774 |
| HRmedia (%) | 76.51 | 73.44 | -3.08 | 7.34 | 0.801 |
| Viento a 2 m (m/s) | 1.25 | 2.60 | +1.35 | 1.68 | 0.680 |
| Radiacion (MJ/m2/dia) | 15.35 | 16.89 | +1.53 | 2.75 | 0.952 |
| Rango diurno Tmax-Tmin (C) | 12.21 | 7.15 | -5.06 | 5.89 |  |

## ET0 recalculada con PM sustituyendo inputs (frente a PM_FAO56_V1)

| Escenario | RMSE | Sesgo | R2 |
|---|---:|---:|---:|
| control: todos del sensor | 0.000 | +0.000 | 1.000 |
| solo T de Open-Meteo | 0.124 | -0.049 | 0.995 |
| solo HR de Open-Meteo | 0.168 | -0.010 | 0.990 |
| solo viento de Open-Meteo | 0.658 | +0.509 | 0.851 |
| solo Rs de Open-Meteo | 0.304 | +0.147 | 0.968 |
| T + Rs de Open-Meteo | 0.310 | +0.102 | 0.967 |
| T + HR de Open-Meteo | 0.231 | -0.045 | 0.982 |
| todos de Open-Meteo (PM propia) | 0.737 | +0.521 | 0.814 |
| ET0 nativa de Open-Meteo (referencia) | 0.752 | +0.542 | 0.806 |
