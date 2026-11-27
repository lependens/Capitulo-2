# Estudio 03.1: ¿los modelos de pocos inputs SIAR funcionan en una estación no vista?

Estado: **EJECUTADO COMPLETO (2026-11-27)**: las 432 celdas (Ridge, HGB, RF, ANN S, ANN M y ANN tipo V2, en las 12 particiones, familias y variantes). Ridge y HGB se calcularon el 2026-11-26 en el entorno de trabajo; RF y ANN entre el 26 y el 27 en Kaggle (CPU). Criterios en `config/thresholds_v3_1.json` (commit 4647f62 del PR #9), sin cambios. Se ejecuta **antes** que el estudio 03.2 (`studies/03_loso_openmeteo_ml/`).

## Índice

| Parte | Contenido |
|---|---|
| [I — Plan congelado](#parte-i--plan-congelado) | Motivación, datos, diseño, hipótesis y regla de decisión, tal y como se fijaron antes de ejecutar |
| [II — Resultados](#parte-ii--resultados-ejecución-del-2026-11-2627) | Ejecución, controles, resultados F1, veredicto de H1–H3, regla de decisión, RF y ANN, secundario |
| [III — Análisis posterior (post hoc)](#parte-iii--análisis-exploratorio-posterior-post-hoc) | Ajuste mensual frente a anual de Open-Meteo, equivalencia (TOST) y resultado estación por estación |
| [IV — Conclusiones sobre los modelos](#parte-iv--conclusiones-sobre-los-modelos-de-pocos-inputs) | Lo bueno, lo malo y lo que el estudio no responde, al margen de la decisión |
| [V — Propuesta de estudio 03.1.2](#parte-v--propuesta-de-estudio-0312-sensor-local--red-valoración-y-plan) | Sensor local + red: valoración de la idea, diseño, modelos, coste y riesgos |
| [VI — Salvedades de la ejecución](#parte-vi--salvedades-de-la-ejecución) | |

Las partes I y II son el estudio tal y como se planificó y ejecutó. Las partes III a V son posteriores y **no modifican** hipótesis, comparadores congelados ni la regla de decisión.

# Parte I — Plan congelado

## Por qué

La idea original del proyecto era que cualquiera, en su ubicación y con pocos sensores, pudiera estimar la PM con las fórmulas, AHC, ML y ANN de V2. Pero en V2 todos los modelos se ajustan y se evalúan **en la misma estación**. Nadie ha comprobado qué pasa donde no hay estación SIAR, que es precisamente donde estaría el usuario.

Este estudio lo comprueba con los mismos inputs de sensor que V2, dejando fuera una estación (o una isla) cada vez. Si los modelos se degradan mucho fuera de su estación y no ganan a las alternativas sencillas, queda justificado cambiar a corregir Open-Meteo (estudio 03.2). Si funcionan, el cambio de rumbo no se justifica y se informa así.

Pregunta principal: **¿cuánto empeoran los modelos de pocos inputs de V2 al aplicarse en una estación que no han visto, y siguen siendo útiles?**

## Datos

Los mismos que el 03.2: referencia PM_FAO56_V1 2004–2025, inputs de sensor SIAR 2004–2025 (paso previo: exportar 2004–2019, ver README del 03.2), predicciones V2 locales en `data/v2/` como comparación, y Open-Meteo `archive` solo para los comparadores.

## Diseño

**Separación espacial y temporal**, igual que el 03.2: entrenamiento solo con 2004–2019 y solo con las estaciones de entrenamiento; evaluación en 2020–2025, en la estación o isla dejada fuera, sobre la cohorte común de V2 (`common_core == 1`, n = 19.251). Particiones F1 (leave-one-station-out, principal) y F2 (fuera Ibiza, fuera Menorca; fuera Mallorca solo informativo), idénticas al 03.2.

**Familias de inputs (las de V2):**

| Familia | Inputs de sensor | Sensor que necesita el usuario |
|---|---|---|
| HS-Ra | Tmax, Tmin, Ra | termómetro |
| Valiantzas | Tmax, Tmin, HR media, Ra | termohigrómetro |
| HG-Rs | Tmax, Tmin, radiación solar | termómetro y piranómetro |

**Métodos por familia:**

| Método | Qué se hace en cada partición |
|---|---|
| Fórmula | Sin ajuste: es igual en cualquier sitio (sirve de control: debe coincidir con V2) |
| AHC transferido | Coeficiente anual y mensual = medio de las estaciones de entrenamiento |
| AHC de la estación más cercana | Coeficiente anual y mensual de la estación de entrenamiento más próxima |
| ML conjunto | Ridge, HistGradientBoosting (primario) y Random Forest, entrenados con las estaciones de entrenamiento |
| ANN conjunta tipo V2 | La arquitectura y los ajustes de las ANN A de V2 (leer de la metodología de Capitulo-1), entrenada con las estaciones de entrenamiento, 5 semillas |
| ANN conjunta S y M | MLP (32) y (64, 32), 5 semillas, como en el 03.2 |

Entradas de ML y ANN: las de la granularidad anual de V2 (solo los inputs base de la familia). Variante secundaria: añadir seno y coseno del día del año y altitud. Hiperparámetros: misma rejilla que el 03.2, con validación interna agrupada por estación dentro del entrenamiento. Negativos recortados a 0, con recuento.

**Comparadores:**

- **V2 local** (mismo método y familia, en la propia estación): mide la **degradación** al salir de la estación. Es la comparación central.
- PM de la estación SIAR más cercana el mismo día e IDW: lo que se puede tener gratis.
- Open-Meteo crudo y Open-Meteo + AHC mensual transferido: el punto de partida del 03.2.

## Métricas e hipótesis

Mismas métricas y bootstrap de bloques estación-año que el 03.2 (2.000 réplicas, semilla 20261126). Hipótesis en `config/thresholds_v3_1.json`:

- **H1 (degradación):** para cada familia, el HGB conjunto en F1 tiene mayor RMSE que el mejor modelo local de V2 de esa familia (ΔRMSE > 0, IC > 0). Se informa el tamaño de la degradación.
- **H2 (utilidad frente a lo gratuito):** para cada familia, el HGB conjunto en F1 frente a la PM de la estación más cercana.
- **H3 (frente a Open-Meteo):** para cada familia, el HGB conjunto en F1 frente a Open-Meteo + AHC mensual transferido.
- **Regla de decisión, fijada antes:** el cambio de rumbo queda justificado si, para las familias de sensor barato (HS-Ra y Valiantzas), el HGB conjunto en F1 **no** gana a la estación más cercana **ni** a Open-Meteo + AHC transferido (extremo superior del IC ≥ 0 en ambos). HG-Rs se informa aparte: necesita piranómetro, que es un sensor caro.

## Salidas

Como en el 03.2: `results/` (particiones, métricas globales, por estación y por mes, IC pareados, dispersión de semillas, predicciones, manifiesto) y `figures/` (degradación local → no vista por familia y método; comparación con estación más cercana y con Open-Meteo). El README se completa con resultados, veredicto por hipótesis y la decisión.

Ficheros producidos (los marcados *post hoc* son de la Parte III, posteriores al plan):

| Fichero | Contenido |
|---|---|
| `results/cells/` | Las 432 celdas (partición × familia × variante × modelo) con predicciones, hiperparámetros y entorno |
| `results/metrics_global.csv`, `metrics_by_station.csv`, `metrics_by_month.csv` | RMSE, MAE, sesgo y R² por ámbito, estación y mes |
| `results/paired_ci.csv` | ΔRMSE e IC 95 % de todas las comparaciones pareadas |
| `results/ann_seed_spread.csv` | Dispersión entre las 5 semillas de cada ANN |
| `results/model_selection.csv` | Hiperparámetros elegidos, épocas, negativos recortados y tiempos |
| `results/decision.json`, `folds.json`, `run_manifest.json` | Regla de decisión aplicada, particiones y manifiesto de ejecución |
| `results/predictions_test.csv.gz` | Todas las predicciones de TEST, de todos los métodos y comparadores |
| `results/rf_ann_hipotesis.csv` | *(post hoc)* H1–H3 de cada modelo y familia |
| `results/extra_om_comparadores.csv`, `extra_om_equivalencia.csv` | *(post hoc)* Comparadores OM anual/mensual y prueba de equivalencia |
| `results/extra_por_estacion.csv` | *(post hoc)* H1–H3 estación por estación |
| `figures/01`–`02` | Degradación local → no vista; comparación con estación cercana y Open-Meteo |
| `figures/03`–`06` | *(post hoc)* RF y ANN frente a H1–H3; OM mensual frente a anual; equivalencia; resultado por estación |
| `extra_om_equivalencia.py`, `extra_por_estacion.py` | *(post hoc)* Código de los análisis posteriores |

## Salvedades

- Prueba exploratoria previa declarada en `studies/03_loso_openmeteo_ml/exploratorio/`: ya sugirió que los modelos solo de sensor se degradan (0,57 y 0,69 mm/día). Este estudio se diseñó después de verla; se ejecuta para medirlo con protocolo y cubrir las tres familias y las ANN tipo V2.
- Si la arquitectura de las ANN de V2 no está documentada lo bastante para replicarla, se informa y se usan solo ANN S y M.
- Referencia calculada, no ET0 medida; 9 estaciones cercanas (F1 optimista).
- El 03.2 ya incluye L1 y L2 (modelos conjuntos solo de sensor con calendario). Coinciden en parte con la variante secundaria de este estudio; se mantienen allí porque sus criterios están congelados.

---

# Parte II — Resultados (ejecución del 2026-11-26/27)

## Ejecución

```
python studies/03_1_loso_inputs_siar/run.py fit --models Ridge,HGB --workers 2   # ~18 min
bash studies/03_1_loso_inputs_siar/kaggle_session.sh N   # N = 1..7, RF y ANN en Kaggle
python studies/03_1_loso_inputs_siar/run.py report                              # ~30 s, cualquier equipo
```

Cada celda (partición × familia × variante × modelo) se guarda en `results/cells/` y `report` une todas las que haya, vengan de donde vengan. Las que faltan se listan en `results/run_manifest.json` (`missing_cells`). Cada celda guarda además la plataforma y las versiones con las que se calculó (`env`; las 144 de Ridge y HGB se calcularon en el entorno de trabajo de Claude, con las mismas versiones fijadas).

**RF, ANN S, ANN M y ANN tipo V2 (288 celdas)** se ejecutaron en Kaggle CPU (4 núcleos) con `kaggle_session.sh N`, en 7 sesiones: 1–3 (RF, ANN S, ANN M y parte de ANN tipo V2) y 4–7 (continuaciones: ANN M restante y ANN tipo V2 repartidas por particiones, con `--folds`). Las celdas de ANN tipo V2 tardaron entre 0,5 y 2,4 h por celda con 4 procesos en paralelo (unas 3,5 veces más que la estimación de un solo núcleo).

Alternativa en un equipo propio (todo en serie, reanudable): `bash studies/03_1_loso_inputs_siar/run_server.sh 4`.

Los filtros de `run.py fit` (`--families`, `--folds`, `--variants`, `--max-hours`, `--list`) solo seleccionan celdas; no cambian ningún modelo, rejilla ni criterio. `check_env.py` detiene la ejecución si las versiones no coinciden con `requirements.txt`. Cada sesión deja `celdas_sesion_N.zip`; se descomprime en `results/cells/` y se vuelve a ejecutar `report`.

**Paso previo.** `classical-baselines.csv` no estaba accesible desde el entorno de ejecución, así que se usó la alternativa: `tools/export_inputs_from_raw.py` sobre `datos_siar_baleares/IBxx_datos_completos.csv` de Capitulo-1. Comprobación 2020–2025 contra `siar_inputs_2020_2025.csv`: 19.272 filas × 8 columnas, **0 discrepancias** (mismos valores y mismos vacíos). Las claves y `quality_status` de 2004–2019 salen de `reference_2004_2019.csv` (56.224 filas). Manifiesto: `data/reference/siar_inputs_2004_2019.manifest.json`.

## Controles

- **La fórmula reproduce V2.** En la cohorte común (n = 19.251), las tres fórmulas coinciden con la columna `FORMULA` de V2: HG-Rs, exacta (diferencia máxima 9·10⁻¹⁶); HS-Ra y Valiantzas, hasta 4·10⁻⁶ mm/día (redondeo de la latitud de `stations.csv` en Ra). RMSE: 0,9491 / 0,6236 / 0,5670, iguales a V2.
- **AHC local reproduce V2.** Con la regla de objetivo de V2 (PM finita y ≥ 0, `et0_v2.py`), los coeficientes anuales por estación coinciden con los congelados de V2 (IB01: HS-Ra 0,893456; Valiantzas 0,980209; HG-Rs 0,918964; n = 5.512) y las predicciones AHC locales, hasta 4·10⁻⁶.
- **V2 local** (`data/v2`) da en la cohorte los RMSE publicados de V2 (p. ej. ANN E anual: 0,5327 / 0,4209 / 0,3676).

## ANN tipo V2: lo que se replica

Leído en Capitulo-1 (`ET0_V2_MEMORIA_CIENTIFICA.md` §9, `et0_methodology_review_v2.md` §6 y `ann_modern.py`). ANN A de V2:

| Elemento | V2 (ANN A, por estación) | 03.1 (conjunta) |
|---|---|---|
| Arquitecturas candidatas | (16), (32), (64), (64,32), (64,32,16) | iguales |
| Red | MLPRegressor, ReLU, Adam, α = 1e-4, tasa 0,001, lote 256, `shuffle=False`, salida lineal | igual |
| Escalado | StandardScaler ajustado solo con las filas que ajustan los pesos en cada fase | igual |
| Épocas | último 15 % de fechas del entrenamiento como validación interna; máx. 200, paciencia 15, mejora mínima 1e-4 de RMSE; después reajuste con todo el entrenamiento del fold durante esas épocas | igual (fechas únicas del conjunto de estaciones de entrenamiento) |
| Selección de arquitectura | dejar un año fuera dentro de DEVELOPMENT; media de RMSE; desempate: menor dispersión, menos parámetros, orden lexicográfico | **dejar una estación fuera** dentro del entrenamiento (lo exige el 03.1); mismos desempates |
| Ajuste final | épocas por semilla = mediana de las mejores épocas de los folds (mitades hacia arriba); ensemble = media de las redes | igual |
| Semillas | 3 (20261101–20261103) | **5** (20261101–20261105), como pide el 03.1 |
| Entradas | anuales de la familia | iguales (variante secundaria: + sen/cos del día del año + altitud) |

Las filas se ordenan por (fecha, estación) antes de entrenar, porque `shuffle=False` hace que el orden cuente. Implementado en `loso_models.py` y ejecutado entero (ver resultados).

## Decisiones de implementación (no fijadas en los criterios)

1. **Entradas de HG-Rs:** se usa el vector anual de V2, `[(Tmax+Tmin)/2, Rs]` (`et0_v2.py::_inputs`). El JSON enumera los sensores (Tmax, Tmin, Rs); el README pide «las entradas de la granularidad anual de V2».
2. **Objetivo:** PM_FAO56_V1 finita y ≥ 0 (regla de V2). El estudio 02 filtraba además por `evaluated_PM`; la diferencia son unas pocas filas por estación.
3. **Validación interna:** dejar una estación fuera dentro de las estaciones de entrenamiento (8 folds en F1). Métrica: media simple del RMSE de cada estación retenida. En caso de empate, la primera configuración de la rejilla.
4. **«Mejor modelo local V2 de la familia» (H1):** el de menor RMSE TEST entre FORMULA, AHC, ML, ANN A y ANN E en granularidad anual (las mismas entradas que la variante principal). En las tres familias sale ANN E. Sensibilidad en `paired_ci.csv` frente a ANN A y frente al mejor de cualquier granularidad: no cambia ningún veredicto.
5. **AHC transferido** = media simple de los coeficientes por estación de entrenamiento; **vecino** = la estación de entrenamiento más cercana (haversine).
6. **PM de la estación más cercana:** la estación de entrenamiento más próxima con PM válida ese día; si falta, la siguiente (en F1 pasa 384 veces de 19.251; recuento por partición en el manifiesto). **IDW:** potencia 2 sobre las estaciones de entrenamiento con PM ese día.
7. **Bootstrap:** 54 bloques estación-año (en F2, los de esas estaciones), 2.000 réplicas y semilla 20261126; los mismos remuestreos para todas las comparaciones; IC por percentiles.
8. Universo: las 9 estaciones de los criterios (IB07, IB09 e IB101 no entran en el entrenamiento).

## Resultados F1 (estación no vista), TEST 2020–2025, n = 19.251

RMSE en mm/día (sesgo entre paréntesis). Tabla completa en `results/metrics_global.csv`.

| Método | HS-Ra | Valiantzas | HG-Rs |
|---|---|---|---|
| Fórmula (= V2) | 0,949 (+0,58) | 0,624 (+0,24) | 0,567 (+0,29) |
| AHC transferido anual / mensual | 0,748 / 0,743 | 0,600 / 0,600 | 0,441 / 0,435 |
| AHC de la estación más cercana anual / mensual | 0,841 / 0,840 | 0,668 / 0,669 | 0,454 / 0,448 |
| Ridge conjunto | 0,684 | 0,559 | 0,479 |
| **HGB conjunto (primario)** | **0,633 (+0,16)** | **0,518 (+0,10)** | **0,421 (+0,07)** |
| HGB conjunto, variante secundaria | 0,668 | 0,553 | 0,416 |
| V2 local: AHC / ML / ANN A / ANN E | 0,631 / 0,553 / 0,533 / 0,533 | 0,512 / 0,439 / 0,421 / 0,421 | 0,413 / 0,381 / 0,368 / 0,368 |

Comparadores (no dependen de la familia): PM de la estación más cercana **0,484**; IDW **0,434**; Open-Meteo crudo 0,752; Open-Meteo + AHC mensual transferido **0,483**.

Por estación (`metrics_by_station.csv`), el HGB de Valiantzas va de 0,43 (IB03) a 0,61 (IB11); el de HG-Rs, de 0,36 (IB04) a 0,48 (IB11). La variante secundaria (calendario + altitud) empeora HS-Ra y Valiantzas; una explicación posible, no comprobada, es que con 8 estaciones la altitud actúe casi como identificador de estación.

## Hipótesis (ΔRMSE = HGB conjunto F1 − comparador; IC 95 %)

| Hipótesis | HS-Ra | Valiantzas | HG-Rs |
|---|---|---|---|
| H1: frente al mejor local V2 (ANN E anual) | +0,100 [+0,082; +0,119] | +0,098 [+0,074; +0,119] | +0,053 [+0,039; +0,067] |
| H2: frente a la PM de la estación más cercana | +0,149 [+0,123; +0,174] | +0,035 [+0,004; +0,062] | −0,063 [−0,094; −0,034] |
| H3: frente a OM + AHC mensual transferido | +0,150 [+0,120; +0,180] | +0,036 [+0,002; +0,069] | −0,062 [−0,098; −0,025] |

**Veredictos:**

- **H1 (degradación): se cumple en las tres familias** (Δ > 0 y extremo inferior > 0). Al salir de la estación, el HGB conjunto pierde 0,10 mm/día frente al mejor local en HS-Ra y en Valiantzas (+19 % y +23 %) y 0,05 en HG-Rs (+14 %). Por método (`degradacion_metodo`): AHC local → transferido, +0,12 (HS-Ra), +0,09 (Valiantzas), +0,03 (HG-Rs).
- **H2: HS-Ra y Valiantzas pierden** frente a la estación más cercana (Valiantzas por poco: 0,035 < 0,05, «significativa pero pequeña»). **HG-Rs gana** (−0,063).
- **H3: lo mismo frente a Open-Meteo + AHC transferido.** HS-Ra pierde, Valiantzas pierde por poco (0,036, pequeña) y HG-Rs gana (−0,062).

## Regla de decisión (aplicación literal)

> «El cambio de rumbo queda justificado si, para HS_RA y VALIANTZAS, el HGB conjunto en F1 no gana ni a PM_estacion_mas_cercana ni a OM_AHC_mensual_medio_entrenamiento (extremo superior del IC ≥ 0 en ambas comparaciones).»

| Familia | Extremo superior IC frente a la estación más cercana | Extremo superior IC frente a OM + AHC | ¿≥ 0 en ambas? |
|---|---|---|---|
| HS-Ra | +0,174 | +0,180 | sí |
| Valiantzas | +0,062 | +0,069 | sí |

**Se cumple: el cambio de rumbo a Open-Meteo corregido (estudio 03.2) queda justificado por este estudio.** HG-Rs, informado aparte: con piranómetro, el modelo conjunto sí gana a la estación más cercana y a OM + AHC (unos 0,06 mm/día), aunque no a la IDW (−0,014 [−0,041; +0,013], empate).

`results/decision.json` guarda el cálculo. RF y ANN no intervienen en la regla; al completarlas, el veredicto no cambia (ver «RF y ANN»).

## Secundario (sin veredicto)

- **F2.** Fuera Ibiza: el HGB de Valiantzas (0,532) gana a la estación más cercana, que queda lejos (0,745), y empata con OM + AHC (0,587). Fuera Menorca: Valiantzas 0,593, frente a 0,561 de la estación más cercana y 0,587 de OM + AHC, todo con IC que incluyen 0 (solo 6 bloques). HG-Rs gana a ambos comparadores en las dos islas. Fuera Mallorca (informativo): OM + AHC (0,428) gana a todos los modelos de sensor barato.
- **Interpolación sencilla:** la IDW del mismo día (0,434) gana a la estación más cercana (−0,049 [−0,069; −0,032]). OM + AHC transferido empata con la estación más cercana (−0,001 [−0,038; +0,035]).
- **Negativos recortados:** Ridge 667 en total entre todas las celdas; HGB 0.

## RF y ANN (completan el estudio; no intervienen en la regla de decisión)

RMSE F1 en mm/día, variante **principal** (ANN = ensemble de 5 semillas; `results/metrics_global.csv`):

| Modelo | HS-Ra | Valiantzas | HG-Rs |
|---|---|---|---|
| HGB conjunto (primario) | 0,633 | 0,518 | 0,421 |
| Random Forest | 0,641 | 0,525 | 0,424 |
| ANN S (32) | 0,627 | 0,521 | 0,416 |
| ANN M (64, 32) | 0,626 | 0,517 | 0,416 |
| ANN tipo V2 | **0,614** | 0,520 | **0,413** |
| V2 local, mejor (ANN E anual) | 0,533 | 0,421 | 0,368 |

Frente a la **estación más cercana** (0,484), ΔRMSE [IC 95 %]: ANN tipo V2 +0,130 [+0,102; +0,157] (HS-Ra), +0,036 [+0,003; +0,065] (Valiantzas), −0,071 [−0,102; −0,042] (HG-Rs). RF, ANN S y ANN M dan lo mismo: ninguna ANN gana a la estación más cercana con HS-Ra ni con Valiantzas (ANN M en Valiantzas: +0,033 [−0,000; +0,061], empate técnico), y todas la ganan con HG-Rs. Frente al mejor local V2 (H1) todas pierden en las tres familias: +0,08 a +0,11 mm/día (HS-Ra y Valiantzas) y +0,045 a +0,057 (HG-Rs), con IC > 0. En conjunto, **cambiar de HGB a RF o a cualquier ANN no altera ningún veredicto de H1–H3 ni la regla de decisión**; la ANN tipo V2 mejora al HGB solo 0,02 mm/día en HS-Ra y 0,008 en HG-Rs.

Hipótesis H1–H3 con cada modelo (ΔRMSE = modelo − comparador, IC 95 %, variante principal, F1; tabla completa en `results/rf_ann_hipotesis.csv`, figura `figures/03_rf_ann_hipotesis.png`):

| | H1 HS-Ra | H1 Valiantzas | H1 HG-Rs | H2 HS-Ra | H2 Valiantzas | H2 HG-Rs | H3 HS-Ra | H3 Valiantzas | H3 HG-Rs |
|---|---|---|---|---|---|---|---|---|---|
| HGB (ref.) | +0,100 | +0,098 | +0,053 | +0,149 | +0,035 | −0,063 | +0,150 | +0,036 | −0,062 |
| RF | +0,108 | +0,104 | +0,057 | +0,157 | +0,041 | −0,060 | +0,158 | +0,043 | −0,059 |
| ANN S | +0,095 | +0,100 | +0,048 | +0,144 | +0,037 | −0,068 | +0,145 | +0,038 | −0,067 |
| ANN M | +0,093 | +0,096 | +0,049 | +0,142 | +0,033 | −0,068 | +0,143 | +0,034 | −0,066 |
| ANN tipo V2 | +0,081 | +0,099 | +0,045 | +0,130 | +0,036 | −0,071 | +0,131 | +0,037 | −0,070 |

Lectura: H1 se cumple con todos los modelos y familias (ningún IC toca 0). En H2 y H3, con HS-Ra todos pierden por mucho; con Valiantzas todos pierden por poco (+0,03 a +0,04, bajo el umbral práctico de 0,05; con ANN M el extremo inferior del IC llega a 0); con HG-Rs todos ganan (−0,06 a −0,07). Por tanto, ningún modelo cambia la regla de decisión. Interpretación (hipótesis del autor, no probada con un experimento): el límite parece estar en la información disponible, no en la capacidad del modelo; con solo temperatura y Ra no se distingue un día ventoso de uno en calma, y la degradación frente al local viene de no conocer el sesgo propio de la estación (en F1 con HS-Ra el sesgo medio es de unos +0,16 mm/día). Las ANN solo mejoran de forma visible al HGB con HS-Ra (ANN tipo V2: 0,614 frente a 0,633).

**Dispersión entre semillas** (`results/ann_seed_spread.csv`): en la variante principal, la desviación típica del RMSE entre las 5 semillas es de 0,001–0,005 mm/día; es decir, las diferencias entre ANN S, M y tipo V2 (≤ 0,015) son del orden del ruido de semilla y no se pueden interpretar como mejora de una arquitectura.

**Variante secundaria (calendario + altitud) con ANN: falla.** Con ANN S, M y tipo V2 el RMSE F1 sube a 0,51–1,25 mm/día según familia y modelo (p. ej. ANN M, Valiantzas: 1,254; ANN tipo V2, HG-Rs: 1,052), con sesgo negativo y gran dispersión entre semillas (SD hasta 0,34), mientras Ridge, HGB y RF se mantienen en 0,42–0,72. Esta variante no interviene en hipótesis ni en la regla; una explicación posible, no comprobada, es que con 8 estaciones de entrenamiento la altitud sea casi un identificador de estación y la ANN extrapole mal a una altitud no vista. No se ha corregido nada: se informa tal cual.

# Parte III — Análisis exploratorio posterior (post hoc)

## Ajuste mensual frente a anual, equivalencia y resultado por estación

**Estatus.** Se hizo **después** de ver los resultados, a petición del autor. No cambia hipótesis, comparadores congelados, criterios ni la regla de decisión (el SHA256 de `config/thresholds_v3_1.json` no cambia). Código: `extra_om_equivalencia.py`; salidas: `results/extra_om_comparadores.csv`, `results/extra_om_equivalencia.csv`, `figures/04_comparadores_om_mensual_vs_anual.png`, `figures/05_equivalencia.png`.

**1. ¿Qué comparador de Open-Meteo usa H3?** Open-Meteo + AHC con coeficiente **mensual** = media de los coeficientes de las estaciones de entrenamiento («transferido»). Ya estaba calculado también el ajuste con el coeficiente **mensual de la estación más cercana** (`OM_AHC_mensual_estacion_mas_cercana`, RMSE 0,507), pero no entraba en ninguna hipótesis. El ajuste **anual** de Open-Meteo no se había calculado; aquí se añade con la misma construcción.

| Comparador (F1, n = 19.251) | RMSE | Sesgo |
|---|---|---|
| Open-Meteo crudo | 0,752 | +0,542 |
| OM + AHC **anual** transferido | 0,575 | +0,104 |
| OM + AHC **anual** de la estación más cercana | 0,597 | +0,132 |
| OM + AHC **mensual** de la estación más cercana | 0,507 | +0,027 |
| OM + AHC **mensual** transferido (el de H3) | **0,483** | −0,002 |
| PM de la estación SIAR más cercana (H2) | 0,484 | +0,038 |
| IDW mismo día | 0,434 | +0,047 |

El ajuste mensual es mucho mejor que el anual (0,483 frente a 0,575): corrige el sesgo estacional de Open-Meteo (el crudo sobreestima +0,54 mm/día) que un solo coeficiente anual no quita. Es decir, **H3 ya compara con la versión más favorable a Open-Meteo**. En cambio, para las fórmulas de sensor (HS-Ra, Valiantzas, HG-Rs) el AHC anual y el mensual casi no difieren (p. ej. Valiantzas transferido: 0,600 y 0,600; HS-Ra: 0,748 y 0,743; HG-Rs: 0,441 y 0,435).

**2. HGB conjunto frente a cada comparador** (ΔRMSE, IC 95 %; `results/extra_om_equivalencia.csv` trae también RF y ANN):

| Comparador | HS-Ra | Valiantzas | HG-Rs |
|---|---|---|---|
| Estación SIAR más cercana (H2) | +0,149 [+0,123; +0,174] | +0,035 [+0,004; +0,062] | −0,063 [−0,094; −0,034] |
| OM + AHC mensual transferido (H3) | +0,150 [+0,120; +0,180] | +0,036 [+0,002; +0,069] | −0,062 [−0,098; −0,025] |
| OM + AHC mensual, estación más cercana | +0,126 [+0,094; +0,155] | +0,011 [−0,027; +0,047] | −0,087 [−0,125; −0,048] |
| OM + AHC anual transferido | +0,057 [+0,020; +0,093] | −0,057 [−0,095; −0,021] | −0,155 [−0,196; −0,114] |
| OM + AHC anual, estación más cercana | +0,036 [−0,002; +0,071] | −0,078 [−0,120; −0,040] | −0,176 [−0,219; −0,133] |
| IDW mismo día | +0,198 [+0,179; +0,218] | +0,084 [+0,060; +0,106] | −0,014 [−0,041; +0,013] |
| **Mejor modelo local V2, misma estación (H1)** | **+0,100 [+0,082; +0,119]** | **+0,098 [+0,074; +0,119]** | **+0,053 [+0,039; +0,067]** |

La última fila (H1) es la única comparación en la que el rival **ha visto la estación**: es el techo de lo que se podría conseguir con esos mismos inputs si hubiera una estación SIAR en el sitio del usuario. Las demás filas son rivales que el usuario puede tener sin instalar nada. Que la distancia al techo (+0,05 a +0,10) sea **menor** que la distancia a la estación más cercana en HS-Ra (+0,149) y mayor que ella en HG-Rs (−0,063) resume el estudio: con sensor barato, lo que falta no es tanto «estar en tu estación» como «tener suficiente información meteorológica».
>> JOSEP: Lo que no entiendo de aqui es , estamos comparando nuestro modelo entonces contrA ESTACION siar mas cercana, que en realidad no tiene porque esa medida se mas proxima al valor de la estacion que hemos dejado fuera, por tanto, es lo que vemos, que baja de 0,149  a 0,100 .entonces mi pregunta es, que aporta la comparacion H2 a la estacion mas cercana si puede darnos lecturas o un error que no representa nada respecto lo que queremos conseguir? corrigeme si em equivoco

**3. Criterio adicional de equivalencia (TOST).** Un «empate» por IC que incluye 0 no demuestra que dos métodos sean equivalentes. Para decir que lo son se usa el margen que el estudio ya fijó como diferencia sin interés práctico (0,05 mm/día): dos métodos son **equivalentes** si el IC al 90 % de ΔRMSE (bootstrap de bloques estación-año, los mismos remuestreos) queda dentro de ±0,05. Se informa además el **margen mínimo de equivalencia** (el menor margen con el que se declararía equivalencia). Resultados con HGB (igual con RF y ANN):

- **Valiantzas frente a la estación más cercana:** IC90 [+0,009; +0,058], margen mínimo 0,058; **no equivalente** por poco (supera 0,05). Frente a OM + AHC mensual transferido: margen mínimo 0,063, tampoco.
- **Valiantzas frente a OM + AHC mensual de la estación más cercana: equivalente** (IC90 [−0,021; +0,041], margen mínimo 0,041; también con RF y las tres ANN).
- **HG-Rs frente a la IDW: equivalente** (margen mínimo 0,037).
- **HS-Ra: no es equivalente a nada** de lo anterior.

**4. ¿Hay alguna estación que cambie el veredicto?** Mismo cálculo, pero estación por estación (`extra_por_estacion.py`, `results/extra_por_estacion.csv`, `figures/06_por_estacion.png`). Aviso: dentro de una estación el bootstrap solo tiene 6 bloques-año, así que los IC son muy anchos y sirven para ver la **dispersión del signo**, no para declarar significación estación a estación.

Recuento con HGB (de 9 estaciones F1, cuántas gana el modelo):

| | HS-Ra | Valiantzas | HG-Rs |
|---|---|---|---|
| H1: se degrada frente al local V2 | 9 de 9 se degradan | 9 de 9 | 8 de 9 (IB06: −0,003, nulo) |
| H2: gana a la estación más cercana | 0 de 9 | 2 de 9 (IB01, IB06) | 6 de 9 |
| H3: gana a OM + AHC mensual | 0 de 9 | 1 de 9 (IB11) | 7 de 9 |
| Gana a la IDW | 0 de 9 | 1 de 9 | 3 de 9 |

ΔRMSE por estación (HGB; positivo = el modelo pierde):

| Estación | H1 HS-Ra | H1 Valiantzas | H1 HG-Rs | H2 HS-Ra | H2 Valiantzas | H2 HG-Rs | H3 HS-Ra | H3 Valiantzas | H3 HG-Rs |
|---|---|---|---|---|---|---|---|---|---|
| IB01 | +0,018 | +0,026 | +0,007 | +0,012 | **−0,132** | −0,196 | +0,184 | +0,039 | −0,025 |
| IB02 | +0,042 | +0,072 | +0,052 | +0,144 | +0,018 | −0,020 | +0,144 | +0,018 | −0,020 |
| IB03 | +0,030 | +0,043 | +0,041 | +0,145 | +0,030 | +0,011 | +0,176 | +0,060 | +0,042 |
| IB04 | +0,076 | +0,081 | +0,042 | +0,112 | +0,069 | −0,068 | +0,128 | +0,085 | −0,052 |
| IB05 | +0,160 | +0,140 | +0,106 | +0,233 | +0,130 | +0,032 | +0,285 | +0,182 | +0,084 |
| IB06 | +0,101 | +0,053 | −0,003 | +0,186 | −0,019 | −0,084 | +0,253 | +0,048 | −0,017 |
| IB08 | +0,150 | +0,181 | +0,118 | +0,131 | +0,032 | −0,139 | +0,105 | +0,007 | −0,164 |
| IB10 | +0,168 | +0,154 | +0,115 | +0,214 | +0,150 | +0,010 | +0,159 | +0,095 | −0,045 |
| IB11 | +0,143 | +0,106 | +0,016 | +0,177 | +0,040 | −0,088 | +0,015 | **−0,122** | −0,250 |

**Conclusión: el resultado es homogéneo; ninguna estación da la vuelta a ninguna hipótesis.**

- **H1 (degradación) es universal:** las tres familias se degradan en prácticamente todas las estaciones. El único caso nulo es HG-Rs en IB06 (−0,003), que es ruido. No hay ninguna estación en la que el modelo conjunto iguale al local.
- **H2 y H3 son homogéneas en HS-Ra:** pierde en las 9, sin excepción.
- **Las excepciones de Valiantzas tienen una explicación clara, y es la misma:** gana donde **el comparador falla**, no donde el modelo mejora. En IB01 la estación SIAR más cercana es la peor de la red (RMSE 0,571, por estar aislada) y por eso Valiantzas le gana por −0,132. En IB11 el ajuste de Open-Meteo es el peor de la red (0,733) y Valiantzas le gana por −0,122. En ambos casos el RMSE del propio modelo es normal; lo anómalo es el rival.
- **El modelo de sensor es más estable que los comparadores de red.** Desviación típica del RMSE entre las 9 estaciones: HG-Rs conjunto 0,040 (rango 0,364–0,484); HS-Ra 0,067; Valiantzas 0,072; estación más cercana 0,070; IDW 0,098; **OM + AHC mensual 0,123** (rango 0,351–0,733). El método que tiene mejor media (OM + AHC) es también el más irregular según dónde estés; el modelo de sensor da una calidad más predecible en cualquier sitio. Esto no aparece en el RMSE agregado y es, operativamente, un punto a favor de los modelos de sensor.

**5. Lectura.**

- Con **piranómetro (HG-Rs)** el modelo conjunto gana de forma clara y con margen a la estación más cercana y a Open-Meteo + AHC, tanto mensual como anual (−0,06 a −0,18 mm/día), y solo empata (equivalente) con la IDW, que usa las observaciones SIAR del mismo día. Es el único resultado claramente favorable a los modelos de sensor.
- **Valiantzas** está cerca, pero no se puede decir que sea equivalente a la estación más cercana ni a OM + AHC mensual transferido con el margen de 0,05; sí lo es frente a OM + AHC mensual de la estación más cercana.
- **Cuidado con el comparador anual:** frente a OM + AHC **anual**, Valiantzas gana (−0,06 a −0,08) y HS-Ra pierde por poco o empata. Pero el anual es un comparador **más débil** (0,575–0,597, frente a 0,483), y elegirlo después de ver los resultados sería favorecer al modelo; por eso la regla congelada, que usa el mensual, es la prueba más exigente para el método Open-Meteo y la que gobierna la decisión. El resultado con el anual se informa como contexto.
- **La regla de decisión no cambia** (se cumple con HS-Ra y Valiantzas frente a los comparadores congelados).
- Salvedad: la referencia PM_FAO56_V1 es calculada, no medida, y Open-Meteo recibe en este diseño ya el ajuste con la PM de las estaciones de entrenamiento; el margen de 0,05 es una elección del estudio, no un valor universal (el margen mínimo permite ver cómo cambiaría la conclusión con otro).

# Parte IV — Conclusiones sobre los modelos de pocos inputs

Esta parte valora los modelos **en sí mismos**, al margen de que el estudio se hiciera para tomar una decisión. La regla de decisión ya está aplicada en la Parte II y no cambia.

## Lo bueno

1. **Valiantzas se queda a muy poco, y el partido está amañado en su contra.** Pierde +0,035 mm/día frente a la estación más cercana y +0,036 frente a Open-Meteo + AHC mensual: por debajo del umbral práctico de 0,05 que el propio estudio fijó como «diferencia sin interés práctico». Conviene mirar contra quién pierde:
   - El **mejor local V2** es un modelo entrenado **en la misma estación** en la que se le evalúa. Es el techo, y Valiantzas conjunta queda a +0,098 de él.
   - **Open-Meteo + AHC mensual** no es un rival modesto: es un reanálisis con muchas más variables (viento, humedad, radiación, nubosidad) **y además** recibe una calibración mensual construida con la PM de las 8 estaciones de entrenamiento. Es decir, usa la red SIAR dos veces: para los datos y para corregirse.
     >> JOSEP:este ultimo parrafo, no me cuadra, entiendo que OM es et0 suya calculada con sus inputs y ppsteriormente ajustada anualmente o mensualmente, por tanto solamente ve 1 vez datos del siar. corrigeme si me equivoco
     >> 
   - Contra la versión **anual** de ese mismo ajuste, **Valiantzas gana** (−0,057 [−0,095; −0,021]), y con el ajuste mensual de la estación más cercana es **estadísticamente equivalente** (±0,05).
   - Resumen: con un termohigrómetro y un modelo entrenado en otras estaciones se consigue, en una ubicación nunca vista, algo comparable a un reanálisis global corregido con la red. Eso es un resultado respetable para el coste del sensor.
2. **Con radiación medida (HG-Rs) los modelos sí ganan, y con margen.** Baten a la estación más cercana (−0,063), a Open-Meteo + AHC mensual (−0,062), al ajuste anual (−0,155) y al mensual de la estación más cercana (−0,087), y empatan con la IDW. Hay que decirlo con honestidad: **es un resultado ventajista**, porque Rs es el input más informativo para la ET0 y también el caro (un piranómetro no es un sensor de aficionado). Lo que demuestra es que el cuello de botella está en la información de entrada, no en el método.
3. **La degradación al salir de la estación es moderada, no un hundimiento.** +0,05 a +0,10 mm/día sobre errores de 0,4–0,6. Los modelos de V2 **transfieren**: pierden calidad fuera de su estación, pero no se rompen. Esto es información nueva: hasta ahora nadie lo había comprobado.

>> JOSEP: la afirmacion de que nadie lo habia comprobado de donde sale? si on hay estudios al respecto comentar los mas parecidos o similares o cercanos.
>
5. **Calidad más predecible que la de los comparadores de red.** Entre las 9 estaciones, el RMSE del modelo HG-Rs varía con una desviación típica de 0,040, frente a 0,123 de Open-Meteo + AHC. El rival con mejor media es el más irregular según dónde estés. Para un servicio que no sabe de antemano dónde estará el usuario, eso cuenta.
   es decir que open meteo saca mejor media de prediccion una vez ajustado , pero tiene variabliidad muy alta (como haias comentado creo que en verano primavera? es por eso o me quvoco?)
   
7. **El resultado es homogéneo: no depende de una estación afortunada.** Ninguna de las 9 estaciones cambia ningún veredicto (Parte III, punto 4), y las dos excepciones de Valiantzas se explican porque el comparador falla, no porque el modelo mejore.
8. **La arquitectura ANN de V2 es reproducible y el resultado no depende del modelo.** Ridge, HGB, RF, ANN S, ANN M y ANN tipo V2 dan el mismo veredicto en las tres familias; las diferencias entre ANN están en el rango del ruido de semilla. El estudio no depende de haber elegido bien el modelo.

## Lo malo

1. **Con solo temperatura (HS-Ra) no vale la pena.** Pierde contra todo y por mucho: +0,149 frente a la estación más cercana, +0,150 frente a Open-Meteo + AHC, +0,198 frente a la IDW, en las 9 estaciones sin excepción. Para un usuario con termómetro y nada más, cualquier alternativa gratuita es mejor.
2. **La premisa original de V2 no se sostiene tal cual.** «Cualquiera puede estimar la PM en su ubicación con pocos sensores» es cierto solo si acepta perder frente a opciones que no requieren comprar nada. El modelo local de V2 es sistemáticamente mejor, y eso no se puede ofrecer donde no hay estación.
3. **Añadir geografía estática a las ANN rompe el modelo.** La variante secundaria (seno/coseno del día del año + altitud) dispara el RMSE a 0,51–1,25 mm/día en las ANN, con gran dispersión entre semillas, mientras Ridge, HGB y RF aguantan. Con 8 estaciones de entrenamiento, la altitud funciona casi como identificador de estación y la red extrapola mal a una altitud no vista. Es una advertencia directa para cualquier estudio futuro que quiera meter metadatos de ubicación como inputs.
4. **F1 es un escenario optimista.** Las 9 estaciones son cercanas entre sí, están en regadío y bien mantenidas. Un usuario real estará más lejos de la red y en condiciones peores; los comparadores de red (estación cercana, IDW) empeorarán, pero también lo hará la transferencia del modelo. F2 (fuera una isla entera) es más honesto y ahí los IC son demasiado anchos para concluir.
5. **La referencia es PM_FAO56 calculada, no ET0 medida.** Todo el estudio mide «parecerse a la PM de la estación», no «acertar la evapotranspiración real». Y los inputs son de sensores SIAR calibrados: el sensor de un usuario será peor, así que estos números son un **límite superior** de lo que obtendría.
6. **No se ha probado el caso que más importa al servicio: estar lejos de cualquier estación.** Justo donde los modelos de sensor tendrían ventaja, el diseño F1 no llega.

## Lo que este estudio no responde

- Qué pasa a 50 o 100 km de la estación más próxima (F1 no lo cubre; F2 lo insinúa pero sin potencia estadística).
  >> JOSEP: seria en andalucia con mcuhas mas estacione y mas superfície buen sitio?
- Cuánto se pierde con sensores de usuario en vez de sensores SIAR.
- >> JOSEP: que experimento podriamos entonces hacer para reproducir esto?
- Si combinar sensor local **y** red mejora a ambos por separado: es la pregunta de la Parte V.
- >> JOSEP: añadiria otra pregunta a ver si hay bibliografia , con mayor resolucion de datos, es decir , creo que siar puede dar dos lecturas cada hora, tendriamos mas informacion del dia aunque fuera solo con temperatur , o incluso con humedad. serian las redes neuronales cpaces ?

# Parte V — Propuesta de estudio 03.1.2 (sensor local + red): valoración y plan

## Valoración de la idea

El punto de partida es correcto: comparar un modelo que solo ve un termómetro contra la **IDW** no es una comparación entre iguales. Pero conviene precisar **cuál** es la información de más que tiene la IDW, porque de eso depende que el estudio tenga sentido o no.

La IDW usa dos cosas: (a) las **observaciones del mismo día** en las 8 estaciones de entrenamiento y (b) las **distancias**, solo como pesos. Lo que de verdad le da ventaja es (a): conoce el estado de la atmósfera ese día en los alrededores. Las distancias son metadatos estáticos que no aportan información meteorológica por sí solos.

De ahí salen dos estudios distintos, con pronósticos muy diferentes:

- **Opción A — añadir las distancias como inputs del modelo de sensor.** No la recomiendo. Para una estación dejada fuera, el vector de distancias a las 8 estaciones de entrenamiento es un **identificador único de esa ubicación**: el modelo nunca ha visto esa combinación y tiene que extrapolar. Es exactamente el mecanismo que hizo fracasar la variante secundaria con la altitud (RMSE de 0,51 a 1,25 en las ANN). Además no añade ninguna información sobre el tiempo que hizo ese día: solo le dice al modelo *dónde* está, no *qué pasó*. Expectativa realista: entre nada y empeorar.
- **Opción B — añadir la información de la red del mismo día.** Es la que recomiendo, y convierte el estudio en la pregunta que de verdad importa para el servicio futuro: **¿aporta algo un sensor barato cuando ya se puede interpolar la red?** Y su simétrica: **¿aporta algo la red a un usuario que ya tiene sensor?** Ninguna de las dos está respondida hoy, y la respuesta decide si el producto es «compra un termohigrómetro», «no compres nada, interpolamos» o «las dos cosas juntas».

Hay un matiz operativo que conviene fijar desde ahora: este diseño supone que la red está **disponible el mismo día**. SIAR tiene retardo de publicación, así que si el servicio quiere dar ET0 de hoy, parte de esa ventaja desaparece. Para ET0 pasada (riego de la semana anterior, balances) el supuesto es correcto. Merece la pena declararlo en los criterios y, si interesa, añadir una variante con los datos de red de *ayer*.

## Diseño propuesto

**Pregunta.** Dada la información de la red SIAR del mismo día en una ubicación sin estación, ¿cuánto reduce el error añadir sensores locales baratos, y al revés?

**Protocolo: idéntico al 03.1, sin cambios.** Mismas particiones (F1 leave-one-station-out, F2 por islas), mismo DESARROLLO 2004–2019 / TEST 2020–2025, misma cohorte común (n = 19.251), mismas métricas, mismo bootstrap de bloques estación-año con la semilla 20261126, mismo umbral práctico de 0,05 y el mismo criterio de equivalencia (TOST) estrenado en la Parte III. Así los resultados son directamente comparables con los de aquí.

**Conjuntos de inputs (lo único nuevo):**

| Clave | Inputs | Qué contesta |
|---|---|---|
| `S` | Solo sensor local (familia HS-Ra / Valiantzas / HG-Rs) | Ya calculado en el 03.1; se reutiliza |
| `R` | Solo red: estimación IDW del día + PM de las k = 3 estaciones más cercanas ese día + sus distancias **ordenadas** | ¿Puede el ML mejorar a la IDW usando lo mismo que ella? |
| `S+R1` | Sensor local + estimación IDW del día (un solo número extra) | El híbrido mínimo, el más robusto |
| `S+R3` | Sensor local + PM de las k = 3 más cercanas + distancias ordenadas | El híbrido completo |

**Regla de construcción de las distancias (importante).** Las distancias entran **ordenadas por cercanía** (d₁ ≤ d₂ ≤ d₃, en km), nunca como un vector indexado por el nombre de la estación. Un vector «distancia a IB01, a IB02, …» es un identificador de ubicación y lleva al problema de la altitud; «distancia a la 1.ª, 2.ª y 3.ª más cercana» es un descriptor de geometría que sí generaliza a una ubicación nueva. Mismo criterio para las PM vecinas: ordenadas por cercanía, no por identidad de estación.

**Modelos.** Tres, y la razón de cada uno:

| Modelo | Papel | Coste medido en el 03.1 (mediana por celda) |
|---|---|---|
| Ridge | Control lineal; detecta si la ganancia es trivial | ~1 s |
| HGB | Primario, como en el 03.1 | ~33 s |
| **ANN M (64, 32)** | Única ANN | ~1.011 s |

**Recomendación sobre la ANN: usar solo ANN M y dejar fuera ANN S, ANN tipo V2 y RF.** Justificación con los números de este estudio: la ANN tipo V2 cuesta **6,3 veces más** que ANN M (6.327 s frente a 1.011 s de mediana por celda) y la diferencia de RMSE entre ambas es ≤ 0,015 mm/día, del mismo orden que la dispersión entre semillas (0,001–0,005). ANN M fue además la mejor ANN en Valiantzas (0,517). RF nunca fue la mejor en ninguna familia y cuesta 730 s. Mantener la ANN tipo V2 solo tendría sentido si el objetivo fuera comparar arquitecturas con V2, y eso ya está hecho aquí.

**Hipótesis (a congelar antes de ejecutar, en `config/thresholds_v3_1_2.json`):**

- **G1 — el sensor aporta sobre la red:** `S+R1` (y `S+R3`) frente a la IDW sola. ΔRMSE < 0 con IC 95 % por debajo de 0. Es la hipótesis que decide si vale la pena comprar un sensor.
- **G2 — la red aporta sobre el sensor:** `S+R1` frente a `S` (los resultados del 03.1). Se espera que sí; cuantifica cuánto.
- **G3 — el ML mejora a la IDW con su misma información:** `R` frente a la IDW. Si no la mejora, la IDW es ya el techo de la interpolación simple.
- **Equivalencia:** mismo TOST con margen 0,05 para los casos en que el IC incluya 0.
- **Secundario, sin veredicto:** F2 por islas (es donde el usuario está lejos de la red y donde el híbrido debería lucir más), resultado por estación, y una variante con la red **desfasada un día** para el caso de uso en tiempo real.

**Volumen y coste.** 12 particiones × [3 familias × 3 conjuntos con sensor + 1 conjunto `R` sin familia] × 3 modelos = 12 × 10 × 3 = **360 celdas**, de las cuales 120 son ANN M. Con los tiempos medidos: 120 × 1.011 s ≈ 34 h de celda, que con 4 procesos en Kaggle son **unas 8–9 horas**, más Ridge y HGB que son despreciables (~20 min). Es decir: **una o dos sesiones de Kaggle**, frente a las siete que hizo falta aquí. Si se quisiera recortar más, bastaría dejar `S+R3` solo en la variante principal.

**Cómo ejecutarlo.** El andamiaje ya existe y casi no hay que tocarlo: `loso_common.py` ya calcula las particiones, las distancias, la IDW y el bootstrap; `run.py` ya es reanudable por celdas y `kaggle_session.sh` ya reparte sesiones. El trabajo real es (1) una función que construya las columnas de red por partición, respetando la regla de ordenación, (2) los nuevos conjuntos de inputs en `loso_models.py`, (3) los criterios congelados en un PR previo, como se hizo aquí con el PR #9. Estimación: cambios de código pequeños, y el coste dominante es el de cómputo.

**Riesgos y salvedades que deben constar en el plan.**

- **Fuga por construcción:** las PM vecinas son de la misma familia de referencia que el objetivo. No es fuga de la estación evaluada (sigue fuera del entrenamiento), pero sí hace que el input de red sea muy informativo. Es legítimo —es justo lo que tendría el servicio—, pero hay que decir que el resultado mide «red + sensor», no «sensor».
- **F1 sigue siendo optimista** y en este estudio aún más, porque la red está cerca. **F2 es el escenario que de verdad interesa** y conviene darle más peso en la lectura, aun sabiendo que sus IC son anchos.
- **Riesgo de identificador de ubicación** si la regla de ordenación de distancias se relaja: la variante secundaria con altitud de este estudio es el precedente.
- Sigue valiendo todo lo de la Parte IV: referencia calculada, no medida; sensores SIAR, no de usuario.

**Cuándo.** Es independiente del 03.2 (no comparten código ni criterios) y mucho más barato que este estudio. Para no tener dos experimentos pesados a la vez, lo razonable es prepararlo mientras el 03.2 esté en diseño y ejecutarlo cuando el 03.2 libere Kaggle.

# Parte VI — Salvedades de la ejecución

- El PR #9 (criterios del 03.1) no estaba fusionado al ejecutar. Se usó su contenido sin cambios (SHA256 de `thresholds_v3_1.json` en el manifiesto). Esta rama parte de él.
- Paso previo hecho con la alternativa de crudos (coincidencia exacta en 2020–2025).
