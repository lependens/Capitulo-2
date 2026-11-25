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
