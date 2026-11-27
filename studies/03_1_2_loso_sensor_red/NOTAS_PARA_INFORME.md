# Notas de traspaso para el informe del 03.1.2

Este fichero es temporal. Lo preparó el chat que ejecutó el estudio (Sonnet 5.5) para que el análisis y la redacción los haga Opus 5.5 en el mismo chat, a petición de Josep. Cuando el README esté completo, se borra en el mismo PR de resultados.

## 1. Estado al dejarlo

- Rama: `resultados-03-1-2`, todavía sin PR. `main` ya tiene los PR #16 (criterios congelados) y #17 (código y tests).
- Celdas en `results/cells/`: el estudio tiene 780 en total.

| Sesión de Kaggle | Contenido | Celdas | Estado |
|---|---|---|---|
| 0 | Ridge y HGB, todos los escenarios | 576 | subida (f38bd88) |
| 3 | ANN_M de C: IB08, IB10, IB11 y F2 | 60 | subida (3cbeba4) |
| 2 | ANN_M de C: IB01–IB06 | 60 | subida (c78532b) |
| 1 | ANN_M de B | 84 | se recoge hacia las 23:30 del 27-11-2026 |

- Todas las celdas recogidas cumplen tres comprobaciones:
  - `test_run` es false;
  - scikit-learn 1.9.1, Python 3.13.18, numpy 2.5.3, pandas 3.0.5;
  - el `stations_coast.csv` de cada zip es idéntico al de `config/`.
- La recogida programada de las 23:30 hace lo siguiente:
  1. sube las celdas de la sesión 1;
  2. ejecuta `PYTHONPATH=src python3 -m pytest -q tests`;
  3. ejecuta `python studies/03_1_2_loso_sensor_red/run.py report`;
  4. sube `results/` y `figures/`.

  No escribe el README ni interpreta los resultados.

## 2. Qué falta (solo análisis, sin entrenar nada)

1. Revisar las salidas de `report`:
   - `metrics_global/by_station/by_month.csv`;
   - `paired_ci.csv` y `equivalencia.csv`;
   - `interpretation.json`;
   - `model_selection`;
   - `error_vs_distancia_red.csv`;
   - `seed_spread`;
   - las figuras 01–05.

   Antes de dar un resultado por bueno, comprobar que el informe calcula lo que dice. Por ejemplo: que las columnas S coinciden con el 03.1 (`check_s_cells`), que las cohortes tienen n = 19251 en B y B-ayer y n = 19216 en C, y que las comparaciones emparejan las mismas filas.
2. Completar el README con:
   - el estado;
   - los resultados;
   - G1–G3 y P1–P2;
   - la regla de interpretación aplicada;
   - los resultados por estación y los de F2;
   - B-ayer y A, sin veredicto;
   - el diagnóstico de costa;
   - las decisiones previas a la congelación (punto 4);
   - las desviaciones (punto 5).

   Lo planificado va separado de lo post hoc.
3. Abrir el PR de resultados y fusionarlo a `main` si los tests pasan. Lo permite la regla de Josep para los PR de código e informe.

## 3. Reglas que siguen vigentes (de Josep)

- No se cambian hipótesis, conjuntos, modelos, rejillas, comparadores ni la regla de interpretación. Si algo no cuadra, se para y se le explica.
- No se toca `studies/03_1_loso_inputs_siar/` ni `studies/03_loso_openmeteo_ml/` (el 03.2 se lleva en otro chat).
- GitHub se usa con `gh api` (REST), porque GraphQL está bloqueado. El remoto avisa de que el repositorio se ha movido a `https://github.com/lependens/Capitulo-2.git`; el push funciona igual.
- Respuestas en español. Un resumen corto al acabar cada fase.

## 4. Decisiones tomadas antes de congelar, con su justificación

Josep las delegó: «decide tú las dudas con criterio científico… déjalo documentado en el README». Están en `config/thresholds_v3_1_2.json`, en `_clarifications_before_freeze`.

- **Cohorte de C.** El día d y el d+1 deben estar ambos en la cohorte común (n = 19216). El entrenamiento usa pares (d, d+1) en los que los dos días caen en desarrollo.

  Justificación: todos los comparadores de C (persistencia, que usa las predicciones B del día d, climatología, OM_AHC y B|S_R1) se evalúan sobre las mismas filas, y ningún par cruza la frontera entre desarrollo y test.
- **Ra(d+1) en C.** Se añade como columna en todos los conjuntos de C, incluidos HG_RS y R.

  Justificación: es astronómica y se conoce sin error, así que no da ventaja a ningún conjunto. Sin ella, el modelo de C no sabría a qué día se refiere la previsión.
- **Comparadores secundarios.**
  - B-ayer se compara con B|S_R1 del mismo modelo y familia, y con PM_IDW del mismo día. Así se mide cuánto cuesta el día de retraso de la red.
  - A se compara con S del 03.1.
- **Regla de interpretación.** Tiene 5 casos aplicados en orden. Δ = RMSE(HGB S+R1, F1) − RMSE(IDW).
  1. El extremo superior del IC95 es menor que 0 y Δ ≤ −0,05: sensor + red.
  2. El extremo superior del IC95 es menor que 0 y −0,05 < Δ < 0: hay ganancia estadística sin interés práctico, y basta la red.
  3. El IC95 incluye el 0 y el TOST da equivalencia: basta la red.
  4. El extremo inferior del IC95 es mayor que 0: S+R1 pierde, y el sensor no aporta en esta red.
  5. Cualquier otro caso: no concluyente, y se informa el margen mínimo de equivalencia.

  Se repite con S+R3, HS_RA y HG_RS; HG_RS se informa aparte. En C, si P1 falla, una previsión a un día sin modelo meteorológico no aporta nada.

  Justificación: la versión propuesta no cubría todos los casos. Se cerró sin mover el umbral de 0,05 ni el TOST del 03.1.
- **Variante A.** El diagnóstico de costa, calculado antes de entrenar, es plano (punto 6). Por eso A queda cerrada: sus celdas se calculan y se informan sin veredicto, como estaba previsto.

## 5. Desviaciones que hay que declarar en el README

1. **`select_and_fit` se replica en `design.py`** (`select_and_fit_net`). El de `loso_models` no se puede reutilizar tal cual, porque la red tiene que reconstruirse en cada pliegue interno, excluyendo del pool la estación de validación. Usa la misma rejilla, los mismos pliegues por estación, la misma media de RMSE y la misma regla de desempate (TIE), y llama a `lm._fit_predict_simple` y `lm._fit_predict_mlp`. No cambia ningún criterio.
2. **Prueba de humo antes de la aprobación.** Se lanzó un `fit` con `--max-train-rows 3000` (F1_IB05, Valiantzas) antes de que se fusionara el PR #16, y eso incumplía la regla de Josep. Se borró el directorio temporal sin mirar ninguna métrica: solo se vieron nombres de celda y tiempos. Se le comunicó en su momento. Ningún resultado del estudio sale de esa prueba.
3. **Ridge y HGB se entrenaron en Kaggle** (sesión 0) y no en local, a petición de Josep. El código es el mismo.
4. **La línea de costa se descargó dentro de Kaggle** (sesión 0), porque el shell del chat no tiene red.

## 6. Diagnóstico de costa (ya hecho, en `results/coast_diagnostic.*` y `figures/00_diagnostico_costa.png`)

- Fuente: Natural Earth 1:10m coastline (`ne_10m_coastline.geojson`, repositorio nvkelso/natural-earth-vector).
- `config/stations_coast.csv` tiene el SHA256 `6f75ae0e0de157b14946e2255eb1f5486d9a13819032e26d4610852d296788f6`.
- Distancias a la costa (km): IB01 8,149 · IB02 20,589 · IB03 12,726 · IB04 2,255 · IB05 16,346 · IB06 7,12 · IB08 4,196 · IB10 1,765 · IB11 0,038.
- Correlación de Spearman con log1p(costa), n = 9, solo indicativa:

| Modelo o comparador | Sesgo | Sesgo JJA | RMSE |
|---|---|---|---|
| HGB HS_RA | −0,13 | −0,13 | −0,48 |
| HGB VALIANTZAS | −0,17 | −0,03 | −0,65 |
| HGB HG_RS | −0,37 | −0,45 | −0,18 |
| OM_AHC | −0,15 | −0,12 | −0,67 |
| IDW | −0,07 | −0,32 | −0,35 |

- La relación no es monótona. IB11 (0,04 km) tiene sesgo de verano negativo, mientras que IB10 e IB08 (1,8–4,2 km) lo tienen positivo. El RMSE baja algo hacia el interior, pero con n = 9 eso no basta para un veredicto. Conclusión: diagnóstico plano.

## 7. Detalles técnicos útiles

- Celdas: `results/cells/{fold}__{scen}__{iset}__{fam}__{model}.json.gz`. Cada una guarda params, cv, n_train, filas descartadas por pool vacío, `d1_km_test`, cuantiles de d1 en entrenamiento, seed_preds, env y test_run.
- Las celdas S son las del 03.1 (`*__principal__*`). `report.py` las lee de allí y no las recalcula.
- Escenarios y conjuntos:

| Escenario | Conjuntos | Modelos |
|---|---|---|
| B | S_R1, S_R3, R | Ridge, HGB, ANN_M |
| C | S, S_R1, S_R3, R | Ridge, HGB, ANN_M |
| Bayer | S_R1, R | Ridge, HGB |
| A | S_costa | Ridge, HGB |

  La familia de R es `NONE`.
- Particiones:
  - F1: 9 LOSO;
  - F2: Ibiza (IB01 e IB11), Menorca (IB08) y Mallorca_informativo.

  En total son 12. El bootstrap usa 2.000 réplicas con semilla 20261126, en bloques estación-año.
- En las sesiones 2 y 3, una celda de ANN_M tardó unos 1.300–1.500 s con 4 procesos; algunas de F2 tardaron mucho menos.
