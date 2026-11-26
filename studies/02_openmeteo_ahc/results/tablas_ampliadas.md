# Estudio 02 - tablas ampliadas (TEST 2020-2025, n=19.251)

## RMSE global por método, familia y granularidad (mm/día)

| Método | Familia (inputs) | Anual | Estacional | Mensual |
|---|---|---|---|---|
| Open-Meteo crudo | - | 0.752 | 0.752 | 0.752 |
| Open-Meteo + AHC | - | 0.534 | 0.454 | 0.427 |
| V2 FORMULA | HS-Ra (Tmin,Tmax,Ra) | 0.949 | 0.949 | 0.949 |
| V2 AHC | HS-Ra (Tmin,Tmax,Ra) | 0.631 | 0.621 | 0.620 |
| V2 ML | HS-Ra (Tmin,Tmax,Ra) | 0.553 | 0.557 | 0.558 |
| V2 ANN_A | HS-Ra (Tmin,Tmax,Ra) | 0.533 | 0.524 | 0.535 |
| V2 ANN_E | HS-Ra (Tmin,Tmax,Ra) | 0.533 | 0.524 | 0.536 |
| V2 FORMULA | HG-Rs (T,Rs) | 0.567 | 0.567 | 0.567 |
| V2 AHC | HG-Rs (T,Rs) | 0.413 | 0.399 | 0.395 |
| V2 ML | HG-Rs (T,Rs) | 0.381 | 0.353 | 0.345 |
| V2 ANN_A | HG-Rs (T,Rs) | 0.368 | 0.337 | 0.328 |
| V2 ANN_E | HG-Rs (T,Rs) | 0.368 | 0.335 | 0.328 |
| V2 FORMULA | Valiantzas (T,HR,Ra) | 0.624 | 0.624 | 0.624 |
| V2 AHC | Valiantzas (T,HR,Ra) | 0.512 | 0.509 | 0.507 |
| V2 ML | Valiantzas (T,HR,Ra) | 0.439 | 0.441 | 0.441 |
| V2 ANN_A | Valiantzas (T,HR,Ra) | 0.421 | 0.416 | 0.423 |
| V2 ANN_E | Valiantzas (T,HR,Ra) | 0.421 | 0.416 | 0.423 |

(FORMULA no depende de la granularidad; ML y ANN varían por la distinta corrida de V2 en cada resolución.)

## Sesgo global (mm/día)

| Método | Anual | Estacional | Mensual |
|---|---|---|---|
| Open-Meteo crudo | +0.542 | +0.542 | +0.542 |
| Open-Meteo + AHC | +0.103 | +0.016 | -0.005 |
| HG-Rs ANN | +0.043 | +0.048 | +0.064 |
| Valiantzas ANN | +0.088 | +0.087 | +0.105 |
| HS-Ra ANN | +0.145 | +0.134 | +0.144 |

## Por estación (resolución mensual, RMSE)

| Estación | OM crudo | OM + AHC | Valiantzas ANN | HG-Rs ANN |
|---|---|---|---|---|
| IB01 | 0.749 | 0.420 | 0.432 | 0.337 |
| IB02 | 0.520 | 0.402 | 0.406 | 0.368 |
| IB03 | 0.518 | 0.342 | 0.371 | 0.326 |
| IB04 | 0.727 | 0.409 | 0.419 | 0.266 |
| IB05 | 0.713 | 0.324 | 0.385 | 0.245 |
| IB06 | 0.644 | 0.384 | 0.393 | 0.341 |
| IB08 | 1.039 | 0.459 | 0.408 | 0.263 |
| IB10 | 0.915 | 0.444 | 0.446 | 0.292 |
| IB11 | 0.792 | 0.599 | 0.528 | 0.457 |

## Por mes calendario (resolución mensual, RMSE)

| Mes | Open-Meteo crudo | Open-Meteo + AHC mensual | HG-Rs ANN | Valiantzas ANN | HS-Ra ANN |
|---|---|---|---|---|---|
| E | 0.726 | 0.255 | 0.363 | 0.245 | 0.348 |
| F | 0.700 | 0.257 | 0.344 | 0.266 | 0.381 |
| M | 0.685 | 0.367 | 0.327 | 0.327 | 0.549 |
| A | 0.635 | 0.438 | 0.254 | 0.427 | 0.599 |
| M | 0.683 | 0.557 | 0.262 | 0.540 | 0.660 |
| J | 0.724 | 0.585 | 0.274 | 0.565 | 0.676 |
| J | 0.850 | 0.607 | 0.297 | 0.575 | 0.623 |
| A | 0.807 | 0.519 | 0.311 | 0.578 | 0.620 |
| S | 0.782 | 0.442 | 0.307 | 0.490 | 0.614 |
| O | 0.820 | 0.319 | 0.343 | 0.311 | 0.436 |
| N | 0.828 | 0.290 | 0.401 | 0.258 | 0.396 |
| D | 0.739 | 0.260 | 0.403 | 0.253 | 0.375 |

## Sesgo por año de TEST de Open-Meteo + AHC (mm/día)

| Año | Anual | Estacional | Mensual |
|---|---|---|---|
| 2020 | +0.105 | +0.017 | -0.001 |
| 2021 | +0.106 | +0.022 | +0.004 |
| 2022 | +0.082 | +0.006 | -0.011 |
| 2023 | +0.089 | -0.003 | -0.034 |
| 2024 | +0.178 | +0.076 | +0.054 |
| 2025 | +0.059 | -0.021 | -0.040 |

## Variantes más justas de Open-Meteo (RMSE / sesgo)

| Variante | Anual | Estacional | Mensual |
|---|---|---|---|
| OM_NATIVA_RAW | 0.752 / +0.541 | 0.752 / +0.541 | 0.752 / +0.541 |
| OM_NATIVA_AHC | 0.534 / +0.103 | 0.454 / +0.016 | 0.427 / -0.004 |
| PM_OM_TODO_RAW | 0.737 / +0.521 | 0.737 / +0.521 | 0.737 / +0.521 |
| PM_OM_TODO_AHC | 0.502 / +0.126 | 0.462 / +0.063 | 0.446 / +0.047 |
| PM_OM_U2=2_RAW | 0.657 / +0.409 | 0.657 / +0.409 | 0.657 / +0.409 |
| PM_OM_U2=2_AHC | 0.477 / +0.149 | 0.469 / +0.124 | 0.465 / +0.118 |
| HS_RA_OM_RAW | 1.022 / -0.236 | 1.022 / -0.236 | 1.022 / -0.236 |
| HS_RA_OM_AHC | 0.996 / +0.333 | 0.989 / +0.303 | 0.988 / +0.299 |
| HS_RA_V1_FORMULA  [V2, T de SIAR] | 0.949 / +0.578 | 0.949 / +0.578 | 0.949 / +0.578 |
| HS_RA_V1_AHC  [V2, T de SIAR] | 0.631 / +0.197 | 0.621 / +0.164 | 0.620 / +0.161 |

## Coeficientes AHC anuales por estación (a en PM ≈ a·ET0_OM, ajustados 2004-2019)

| Estación | a | n desarrollo |
|---|---|---|
| IB01 | 0.843217 | 5510 |
| IB02 | 0.951964 | 5676 |
| IB03 | 0.905513 | 5672 |
| IB04 | 0.865163 | 5584 |
| IB05 | 0.848024 | 5673 |
| IB06 | 0.880024 | 5669 |
| IB08 | 0.807205 | 4955 |
| IB10 | 0.828525 | 4879 |
| IB11 | 0.918883 | 4827 |
