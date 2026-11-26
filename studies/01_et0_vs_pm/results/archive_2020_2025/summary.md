# Estudio 01 - resumen (openmeteo_archive.csv)

- Referencia: ET0_PM_FAO56_V1; periodo 2020-01-01 a 2025-12-31; estaciones activas del catalogo.
- Cohorte (estacion-fecha con referencia y Open-Meteo): n = 19251; SHA256 de claves = `7f24e7d90d83a619aa78fc4d094013f6e38d0953748223fb701d7b606f49eb26`.
- Open-Meteo global: RMSE 0.752, MAE 0.626, sesgo +0.542 mm/dia, R2 0.806.
- Umbrales: thresholds.json v1 (fijado 2026-11-25).
- **Veredicto: UTILIZABLE_NO_DIFERENCIAL**

Formulas V2 sin ajustar sobre sus propias parejas con PM (cohortes distintas: n aparte):

- ET0_HS_RA_V1: n 19251, RMSE 0.949, sesgo +0.578
- ET0_VALIANTZAS_V1: n 19251, RMSE 0.624, sesgo +0.237
- ET0_HG_RS_V1: n 19251, RMSE 0.567, sesgo +0.294

Que NO se concluye: que Open-Meteo sea mejor o peor en general, solo su acuerdo con PM calculada en estas estaciones y fechas. Rejilla con todos los inputs frente a modelos con pocos inputs de sensor.
