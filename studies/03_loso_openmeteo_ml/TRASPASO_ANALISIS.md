# Traspaso: análisis e interpretación del estudio 03.2

> **HECHO (2026-11-27).** Análisis e interpretación redactados en el README («RF y ANN», «Interpretación»). Diagnóstico del fallo de las ANN: extrapolación de la altitud en IB01 (`diagnostico_ann_altitud.py`, figura 4). Este fichero queda como registro del traspaso.

**Estado (2026-11-27 15:45): LISTO PARA ANÁLISIS.** 360/360 celdas en `results/cells/` (72 por modelo), `missing_cells` vacío, `report` regenerado con todo, 34 tests OK. `decision.json`: H1–H4 se cumplen, igual que en el README. Tiempos Kaggle: sesiones 1–4 = 257, 266, 258 y ~329 min (4 núcleos).

Este documento es para quien haga el análisis final, previsto con Opus 5.5. La ejecución está hecha y es mecánica. Lo que queda es **leer los resultados, interpretarlos y redactar el README**.

## Reglas que siguen vigentes (no negociables)

- `README.md` (sección de plan, líneas 1–113) y `config/thresholds_v3.json` están **congelados**. No se cambian hipótesis, modelos, rejillas, comparadores ni regla de decisión.
- Los veredictos H1–H4 se basan **solo en HGB y F1** y ya están calculados en `results/decision.json`. RF y ANN no intervienen. Al completar las celdas, el veredicto no debería cambiar: hay que comprobarlo, no reinterpretarlo.
- Umbral práctico: 0,05 mm/día. Una diferencia significativa menor que eso se informa como «significativa pero pequeña».
- No se toca nada del 03.1: `studies/03_1_loso_inputs_siar/`, la rama `estudio-03-1-ejecucion` y el PR #10 quedan fuera. Los datos crudos tampoco se tocan.
- Trabajo en la rama `estudio-03-2-ejecucion`, PR #11 (draft). **No fusionar a main.** Los tests deben pasar: `PYTHONPATH=src python3 -m unittest discover -s tests`.
- Responder en español.

## Qué hay

| Fichero | Contenido |
|---|---|
| `results/cells/*.json.gz` | Una celda por partición × escenario × modelo (360). Contiene predicciones, rejilla de CV interna, parámetros elegidos, recortes a 0, entorno y, en las ANN, las predicciones de cada semilla. |
| `results/metrics_global.csv` | n, MAE, RMSE, sesgo y R² por alcance (F1/F2) y método (`escenario\|modelo`, comparadores, `techo\|…`). |
| `results/metrics_by_station.csv`, `metrics_by_month.csv` | Los mismos, desglosados. |
| `results/paired_ci.csv` | ΔRMSE con IC 95 % por bootstrap de bloques estación-año (2000 réplicas, semilla 20261126). |
| `results/decision.json` | Aplicación literal de H1–H4. |
| `results/ann_seed_spread.csv` | Dispersión entre las 5 semillas de cada ANN (solo F1 con las 9 particiones). |
| `results/model_selection.csv` | Hiperparámetros elegidos y n_train por celda. |
| `results/run_manifest.json` | SHA256 del código común y `missing_cells` (debe quedar vacío). |
| `figures/01–03_*.png` | RMSE por escenario y modelo, por estación y por mes. |

Regenerar: `python3 studies/03_loso_openmeteo_ml/run.py report` (~25 s).

## Qué hay que hacer

1. Comprobar que `missing_cells` está vacío (360 celdas) y que `decision.json` da los mismos H1–H4 que el README actual.
2. Actualizar en el README la sección «Resultados»:
   - estado de la ejecución: completo, con los tiempos reales de Kaggle (sesiones 1–3: 257, 266 y 258 min; sesión 4: pendiente);
   - filas RF, ANN_S y ANN_M en la tabla F1;
   - comparaciones secundarias de RF y ANN frente a HGB (sin veredicto);
   - resumen de `ann_seed_spread.csv`;
   - figuras regeneradas;
   - quitar la sección «Pendiente».
3. Interpretar los resultados y redactar la lectura final. Puntos que piden juicio:
   - **Hallazgo principal a explicar: las ANN fallan en IB01.** RMSE F1-S0 por estación (ANN_M / ANN_S / HGB / RF): IB01 **2,77 / 1,02** / 0,38 / 0,38; en las otras 8 estaciones las ANN están a la par o algo mejor que HGB (p. ej. IB03 0,32 frente a 0,37; IB11 0,56 frente a 0,63). Por eso el global F1 de ANN_M es ~1,0 en S0–L2 (peor que OM crudo) y de ANN_S 0,49–0,91. Parece extrapolación de la red cuando IB01 sale del rango de entrenamiento (revisar altitud, Ra o algún input de Open-Meteo de IB01 frente al resto; los árboles no extrapolan y no sufren). ANN_M S0_coord da 0,81. Comprobar con `metrics_by_station.csv` para todos los escenarios y con las `seed_preds` de las celdas `F1_IB01__*__ANN_*`.
   - **ANN muy inestable entre semillas** (ANN_S): en F1-S0 el ensemble de 5 semillas da 0,490, pero cada semilla va de 0,44 a 0,98 (sd 0,27). S1 y S2 empeoran con más inputs (0,58 y 0,67, sesgo negativo de −0,11 a −0,17), al revés que HGB y RF. Hay que valorar si es un rasgo del modelo con estación no vista o un problema de entrenamiento. Pistas: `MLPRegressor` con `early_stopping=True` usa un 10 % de validación aleatoria, no agrupada por estación, y el objetivo no está escalado. El código está congelado (copia literal del 03.1), así que esto solo puede **documentarse**, no corregirse. Compararlo con lo que obtuvo el 03.1 con las mismas ANN.
   - **RF** (provisional): S0 0,444, S1 0,434, S2 0,426, L1 0,646, L2 0,538. Sigue el mismo patrón que HGB, ligeramente peor.
   - El **empate de HGB-S0 con la IDW del mismo día** y con OM + AHC local (ver «Lectura» del README) es la salvedad principal para el estudio 04 (previsión).
   - H1 y H2 quedan a 0,0002 y 0,001 del umbral práctico.
   - F2 en Mallorca (informativo) es peor que OM + AHC.
4. Tests, commit y push. Actualizar el cuerpo del PR #11 y pasarlo a «ready for review» solo si está completo. Nunca fusionar.
5. Resumen final para el usuario, en español.
