# Estudio 01 - tablas ampliadas (Open-Meteo archive vs PM_FAO56_V1, 2020-2025, n=19251)

## Por estación

| Estación | n | RMSE | MAE | Sesgo | R² | PM medio | OM medio |
|---|---|---|---|---|---|---|---|
| IB01 | 2192 | 0.749 | 0.628 | +0.581 | 0.811 | 2.98 | 3.57 |
| IB02 | 2017 | 0.520 | 0.425 | +0.333 | 0.921 | 3.08 | 3.42 |
| IB03 | 2192 | 0.518 | 0.437 | +0.381 | 0.911 | 3.01 | 3.39 |
| IB04 | 2124 | 0.727 | 0.605 | +0.553 | 0.825 | 2.84 | 3.40 |
| IB05 | 2154 | 0.713 | 0.627 | +0.603 | 0.824 | 2.75 | 3.35 |
| IB06 | 2190 | 0.644 | 0.545 | +0.500 | 0.856 | 2.86 | 3.36 |
| IB08 | 2097 | 1.039 | 0.945 | +0.941 | 0.534 | 2.46 | 3.40 |
| IB10 | 2097 | 0.915 | 0.777 | +0.764 | 0.674 | 2.66 | 3.42 |
| IB11 | 2188 | 0.792 | 0.651 | +0.228 | 0.776 | 3.26 | 3.49 |

## Por mes

(R² mensual bajo o negativo en invierno: dentro de un mes la ET0 varía poco y el sesgo constante domina; no indica pérdida de correlación diaria.)

| Mes | RMSE | Sesgo | R² | PM medio | OM medio | Sesgo relativo |
|---|---|---|---|---|---|---|
| 01 | 0.726 | +0.640 | -1.493 | 1.05 | 1.69 | +61% |
| 02 | 0.700 | +0.620 | -1.594 | 1.48 | 2.10 | +42% |
| 03 | 0.685 | +0.540 | 0.079 | 2.19 | 2.73 | +25% |
| 04 | 0.635 | +0.417 | 0.402 | 3.09 | 3.51 | +13% |
| 05 | 0.683 | +0.330 | 0.478 | 4.15 | 4.48 | +8% |
| 06 | 0.724 | +0.309 | 0.450 | 5.06 | 5.37 | +6% |
| 07 | 0.850 | +0.495 | -0.097 | 5.34 | 5.84 | +9% |
| 08 | 0.807 | +0.513 | 0.173 | 4.71 | 5.23 | +11% |
| 09 | 0.782 | +0.579 | -0.006 | 3.24 | 3.82 | +18% |
| 10 | 0.820 | +0.703 | -0.764 | 2.16 | 2.86 | +33% |
| 11 | 0.828 | +0.705 | -1.402 | 1.32 | 2.03 | +53% |
| 12 | 0.739 | +0.632 | -1.568 | 0.94 | 1.57 | +67% |

## Por año

| Año | n | RMSE | Sesgo | R² |
|---|---|---|---|---|
| 2020 | 3293 | 0.779 | +0.544 | 0.790 |
| 2021 | 3283 | 0.735 | +0.536 | 0.800 |
| 2022 | 3176 | 0.739 | +0.527 | 0.843 |
| 2023 | 3281 | 0.780 | +0.540 | 0.781 |
| 2024 | 3154 | 0.780 | +0.608 | 0.758 |
| 2025 | 3064 | 0.689 | +0.494 | 0.849 |

## Qué parte del error es sesgo y qué parte es ruido

RMSE total 0.752; sesgo +0.542; RMSE tras restar el sesgo medio global 0.521. Es decir, más de la mitad del error cuadrático es un desplazamiento sistemático corregible por calibración.

## Inputs de Open-Meteo frente al sensor SIAR (OM − SIAR)

| Variable | SIAR medio | OM medio | Sesgo | RMSE | Correlación |
|---|---|---|---|---|---|
| Tmax (C) | 23.95 | 22.13 | -1.83 | 2.38 | 0.98 |
| Tmin (C) | 11.74 | 14.98 | +3.23 | 3.96 | 0.93 |
| HRmax (%) | 94.98 | 90.28 | -4.70 | 8.55 | 0.56 |
| HRmin (%) | 50.61 | 53.43 | +2.82 | 10.05 | 0.77 |
| HRmedia (%) | 76.51 | 73.44 | -3.08 | 7.34 | 0.80 |
| Viento a 2 m (m/s) | 1.25 | 2.60 | +1.35 | 1.68 | 0.68 |
| Radiacion (MJ/m2/dia) | 15.35 | 16.89 | +1.53 | 2.75 | 0.95 |
| Rango diurno Tmax-Tmin (C) | 12.21 | 7.15 | -5.06 | 5.89 | - |

## Escenarios de sustitución de inputs en PM (RMSE y sesgo globales frente a PM_FAO56_V1)

| Escenario | RMSE | Sesgo |
|---|---|---|
| control: todos del sensor | 0.000 | +0.000 |
| solo T de Open-Meteo | 0.124 | -0.049 |
| solo HR de Open-Meteo | 0.168 | -0.010 |
| T + HR de Open-Meteo | 0.231 | -0.045 |
| solo Rs de Open-Meteo | 0.304 | +0.147 |
| T + Rs de Open-Meteo | 0.310 | +0.102 |
| solo viento de Open-Meteo | 0.658 | +0.509 |
| todos de Open-Meteo (PM propia) | 0.737 | +0.521 |
| ET0 nativa de Open-Meteo | 0.752 | +0.542 |
