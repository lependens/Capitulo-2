# Estudio 01 - resumen (openmeteo_archive.csv)

- Referencia: ET0_PM_FAO56_V1; periodo 2021-01-01 a 2025-12-31; estaciones activas del catalogo.
- Cohorte (estacion-fecha con referencia y Open-Meteo): n = 15958; SHA256 de claves = `bc57b87471ccf9f101260fff6b4c5605bd8768222a93d8b8a0fc68a93bfc2eff`.
- Open-Meteo global: RMSE 0.746, MAE 0.621, sesgo +0.541 mm/dia, R2 0.810.
- Umbrales: thresholds.json v1 (fijado 2026-11-25).
- **Veredicto: UTILIZABLE_NO_DIFERENCIAL**

Formulas V2 sin ajustar sobre sus propias parejas con PM (cohortes distintas: n aparte):

- ET0_HS_RA_V1: n 15958, RMSE 0.949, sesgo +0.571
- ET0_VALIANTZAS_V1: n 15958, RMSE 0.629, sesgo +0.243
- ET0_HG_RS_V1: n 15958, RMSE 0.565, sesgo +0.287

Que NO se concluye: que Open-Meteo sea mejor o peor en general, solo su acuerdo con PM calculada en estas estaciones y fechas. Rejilla con todos los inputs frente a modelos con pocos inputs de sensor.
