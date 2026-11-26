# Exportación de predicciones ET0 V2 (2020–2025)

Origen: Capitulo-1 / ET0 V2, retrospectivo 2020-2025 (referencia PM_FAO56_V1, mm/día). Datos SiAR (MAPA); citar siempre.

- `et0_v2_{annual,seasonal,monthly}_2020_2025.csv`: 19.272 filas × 22 columnas (cohorte común `common_core`=1: 19.251). Columnas `<FAMILIA>_<MÉTODO>` con familias HS_RA_V1, HG_RS_V1, VALIANTZAS_V1 y métodos FORMULA, AHC, ML, ANN_A, ANN_E. La resolución indica la granularidad del AHC (anual, estacional, mensual).
- `manifest.json`: SHA256 del zip original (2fddd95c…d420), del `predictions.csv.gz` interno y de cada CSV; el manifiesto del retrospectivo original es PASS.
- Se conservan vacíos (155 celdas) y 3 predicciones negativas en el CSV mensual.
- La predicción `ML` no es una variante fija: sus valores coinciden según el caso con distintas variantes (recuentos en el manifiesto).
- El catálogo derivado V2 sigue marcado DRAFT; no se ha confirmado un catálogo definitivo. Exportación hecha directamente desde el archivo original verificado.
- Copia de trabajo en el servidor de origen: `/home/josep/et0-v2-export-20261126/` (zip SHA256 f22f450e…179ce).
