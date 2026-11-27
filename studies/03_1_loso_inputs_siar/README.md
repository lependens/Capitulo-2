# Estudio 03.1: ¿los modelos de pocos inputs SIAR funcionan en una estación no vista?

Estado: **EJECUTADO COMPLETO (2026-11-27)**: las 432 celdas (Ridge, HGB, RF, ANN S, ANN M y ANN tipo V2, en las 12 particiones, familias y variantes). Ridge y HGB se calcularon el 2026-11-26 en el entorno de trabajo; RF y ANN entre el 26 y el 27 en Kaggle (CPU). Criterios en `config/thresholds_v3_1.json` (commit 4647f62 del PR #9), sin cambios. Se ejecuta **antes** que el estudio 03.2 (`studies/03_loso_openmeteo_ml/`).

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

## Salvedades

- Prueba exploratoria previa declarada en `studies/03_loso_openmeteo_ml/exploratorio/`: ya sugirió que los modelos solo de sensor se degradan (0,57 y 0,69 mm/día). Este estudio se diseñó después de verla; se ejecuta para medirlo con protocolo y cubrir las tres familias y las ANN tipo V2.
- Si la arquitectura de las ANN de V2 no está documentada lo bastante para replicarla, se informa y se usan solo ANN S y M.
- Referencia calculada, no ET0 medida; 9 estaciones cercanas (F1 optimista).
- El 03.2 ya incluye L1 y L2 (modelos conjuntos solo de sensor con calendario). Coinciden en parte con la variante secundaria de este estudio; se mantienen allí porque sus criterios están congelados.

---

# Resultados (ejecución del 2026-11-26/27)

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

## Análisis exploratorio posterior (post hoc): ajuste mensual frente a anual y equivalencia

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

**3. Criterio adicional de equivalencia (TOST).** Un «empate» por IC que incluye 0 no demuestra que dos métodos sean equivalentes. Para decir que lo son se usa el margen que el estudio ya fijó como diferencia sin interés práctico (0,05 mm/día): dos métodos son **equivalentes** si el IC al 90 % de ΔRMSE (bootstrap de bloques estación-año, los mismos remuestreos) queda dentro de ±0,05. Se informa además el **margen mínimo de equivalencia** (el menor margen con el que se declararía equivalencia). Resultados con HGB (igual con RF y ANN):

- **Valiantzas frente a la estación más cercana:** IC90 [+0,009; +0,058], margen mínimo 0,058; **no equivalente** por poco (supera 0,05). Frente a OM + AHC mensual transferido: margen mínimo 0,063, tampoco.
- **Valiantzas frente a OM + AHC mensual de la estación más cercana: equivalente** (IC90 [−0,021; +0,041], margen mínimo 0,041; también con RF y las tres ANN).
- **HG-Rs frente a la IDW: equivalente** (margen mínimo 0,037).
- **HS-Ra: no es equivalente a nada** de lo anterior.

**4. Lectura.**

- Con **piranómetro (HG-Rs)** el modelo conjunto gana de forma clara y con margen a la estación más cercana y a Open-Meteo + AHC, tanto mensual como anual (−0,06 a −0,18 mm/día), y solo empata (equivalente) con la IDW, que usa las observaciones SIAR del mismo día. Es el único resultado claramente favorable a los modelos de sensor.
- **Valiantzas** está cerca, pero no se puede decir que sea equivalente a la estación más cercana ni a OM + AHC mensual transferido con el margen de 0,05; sí lo es frente a OM + AHC mensual de la estación más cercana.
- **Cuidado con el comparador anual:** frente a OM + AHC **anual**, Valiantzas gana (−0,06 a −0,08) y HS-Ra pierde por poco o empata. Pero el anual es un comparador **más débil** (0,575–0,597, frente a 0,483), y elegirlo después de ver los resultados sería favorecer al modelo; por eso la regla congelada, que usa el mensual, es la prueba más exigente para el método Open-Meteo y la que gobierna la decisión. El resultado con el anual se informa como contexto.
- **La regla de decisión no cambia** (se cumple con HS-Ra y Valiantzas frente a los comparadores congelados).
- Salvedad: la referencia PM_FAO56_V1 es calculada, no medida, y Open-Meteo recibe en este diseño ya el ajuste con la PM de las estaciones de entrenamiento; el margen de 0,05 es una elección del estudio, no un valor universal (el margen mínimo permite ver cómo cambiaría la conclusión con otro).

## Salvedades de la ejecución

- El PR #9 (criterios del 03.1) no estaba fusionado al ejecutar. Se usó su contenido sin cambios (SHA256 de `thresholds_v3_1.json` en el manifiesto). Esta rama parte de él.
- Paso previo hecho con la alternativa de crudos (coincidencia exacta en 2020–2025).
