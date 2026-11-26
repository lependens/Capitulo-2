# Estudio 01 - ET0 de Open-Meteo frente a PM_FAO56_V1

**Pregunta.** La ET0 de Open-Meteo se parece a la PM calculada de SIAR mas de lo que se parecen las formulas V2 con pocos inputs? Responde si el producto es competitivo y, si no, que variable de rejilla falla.

**Pasos**
1. ET0 directa: `et0_fao_evapotranspiration` de Open-Meteo (`archive`) frente a `PM_FAO56_V1`, 9 estaciones activas, 2020-2025 (`compare.py`).
2. Diagnostico de inputs: Tmax, Tmin, humedad, viento y radiacion de Open-Meteo frente a los medidos en SIAR (pendiente: script `diagnose_inputs.py`, depende de tener el dataset de inputs en `data/reference/`).
3. Comparacion con modelos V2 (AHC, ML, ANN) sobre las mismas claves estacion-fecha (pendiente: exportar sus predicciones desde Capitulo-1).

**Criterio de exito**: `config/thresholds.json` (v1, fijado el 2026-11-25 antes de descargar nada).

**Ejecucion**
```
PYTHONPATH=src python studies/01_et0_vs_pm/compare.py \
    --reference data/reference/reference_2020_2025.csv \
    --openmeteo data/processed/openmeteo_archive.csv
```
Escribe en `results/openmeteo_archive/`: metricas global, por estacion, anio, mes, temporada y combinaciones (`openmeteo.csv`, y una por formula clasica), `summary.md` con veredicto y el SHA256 de las claves de la cohorte.

**Que no se concluye**: que Open-Meteo sea mejor o peor en general; solo su acuerdo con PM calculada en estas estaciones y fechas.

## Primer resultado (26/11/2026)

Datos: `archive` de Open-Meteo (reanalisis), 9 estaciones, 2020-2025; referencia `ET0_PM_FAO56_V1` de `classical-baselines.csv`
(SHA256 del original `f55e4ed1...af44`, subconjunto en `data/reference/`). Cohorte: 19.251 pares (coincide con el `PM n` de V2).
Sanity check: las formulas V2 sin ajustar dan RMSE 0,949 (HS-Ra) y 0,624 (Valiantzas), iguales a las publicadas.

| Metodo | RMSE (mm/dia) | Sesgo (mm/dia) |
|---|---:|---:|
| Open-Meteo `et0_fao_evapotranspiration` | 0,752 | +0,542 |
| HS-Ra sin ajustar | 0,949 | +0,578 |
| Valiantzas sin ajustar | 0,624 | +0,237 |
| HG-Rs sin ajustar | 0,567 | +0,294 |

Veredicto con `config/thresholds.json` v1: **UTILIZABLE_NO_DIFERENCIAL** (RMSE global entre 0,62 y 0,95; ademas IB08 supera 1,0 por estacion).
Con la ventana 2021-2025 el resultado es practicamente el mismo (RMSE 0,746, sesgo +0,541). La ventana de TEST no esta
definida de forma unica en la documentacion de Capitulo-1 (2020-2025 frente a 2021-2025), por eso se publican ambas.

Lectura: casi todo el error es sesgo sistematico (sobreestima en las 9 estaciones y en todos los meses). Con RMSE^2 = sesgo^2 + varianza,
el error sin ese sesgo seria de unos 0,52 mm/dia. Pendiente: diagnostico de inputs (temperatura, humedad, radiacion, viento; el viento
exige convertir 10 m a 2 m) y comparacion con las predicciones de AHC, ML y ANN de V2.

Resultados completos: `results/archive_2020_2025/` y `results/archive_2021_2025/`.
