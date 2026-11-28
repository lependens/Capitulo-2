# Estudio 03.3: Open-Meteo + ML + red SIAR del día, y objetivo residual (L3 y L5)

Estado: **EJECUTADO** (2026-11-28). Criterios congelados en `config/thresholds_v3_3.json` (2026-11-27), sin cambios. Resultados en la sección «Resultados»; lo *post hoc* va aparte, en «Análisis *post hoc*».

> **Numeración.** Las Partes V del 03.1 y del 03.2 llamaban «03.3» a las estaciones a 50–100 km y a los sensores de usuario, y «03.4» a la resolución subdiaria. Ese contenido pasa a las líneas L4 (Andalucía, distancia de cruce), L11 (robustez del sensor) y L16 (subdiaria) de `docs/IDEAS_Y_MEJORAS.md`. Desde ahora, 03.3 es este estudio y 03.4 es la revalidación con fuentes de licencia comercial (L14).

## Por qué

El 03.2 dejó dos indicios fuertes y baratos de comprobar:

1. **L3, combinar con la red.** Los errores de HGB-S0 y de la IDW del día solo se correlacionan 0,51. Su media simple, sin ajuste, dio RMSE 0,377 frente a 0,433 y 0,434: −0,056 [−0,070; −0,042], el mayor salto de todo el estudio. Era un análisis *post hoc*; aquí se prerregistra.
2. **L5, objetivo residual y control de dominio.** Las ANN fallaron por extrapolar la altitud (IB01, sesgo −2,5). Si el modelo predice la corrección (PM − ET0 de Open-Meteo) en lugar de la PM, al equivocarse cae hacia Open-Meteo y no hacia valores absurdos. Y un servicio debe avisar cuando un punto queda fuera del rango con el que se entrenó.

Pregunta: **¿mejora la ET0 de una ubicación sin estación si al modelo Open-Meteo + ML se le añade la red SIAR del día? ¿Y deja de romperse la ANN si predice la corrección?**

Para el servicio decide: «Open-Meteo + ML» solo, «Open-Meteo + ML + red» en toda Baleares, o la combinación solo cerca de la red.

## Diseño

**Protocolo idéntico al 03.2:** mismas particiones (`studies/03_2_loso_openmeteo_ml/results/folds.json`), DESARROLLO 2004–2019 y TEST 2020–2025, cohorte común (n = 19.251), métricas, bootstrap de bloques estación-año (2.000 réplicas, semilla 20261126), umbral práctico 0,05 y TOST. Las filas sin red disponible ese día se cuentan y se quitan de **todos** los métodos.

**Red (R1):** IDW de la PM del día (potencia 2) y distancia a la estación más cercana del pool, construidas con `studies/03_1_2_loso_sensor_red/network.py`, importado sin modificar. Reglas: la estación evaluada nunca está en el pool; en la validación interna la estación de validación sale del pool de todas las filas.

### Brazos de L3 (combinación con la red)

| Brazo | Qué es | Papel |
|---|---|---|
| `S0+R1` | HGB con S0 más IDW_PM y d1_km | **primario** |
| `media_fija` | 0,5 × HGB-S0 + 0,5 × IDW | el indicio del 03.2, ahora prerregistrado |
| `media_ponderada` | w × HGB-S0 + (1 − w) × IDW, w elegido en validación interna | informativo |
| `residuo_IDW` | HGB-S0 + IDW de los residuos de las estaciones del pool ese día (regresión-kriging sencilla) | informativo |
| `S2+R1` | termohigrómetro + red | informativo |
| `S0+R1_ayer` | con la red del día anterior | informativo: no esperar a la red |

**Cuidado con `residuo_IDW`:** el residuo de una estación de entrenamiento s tiene que venir de un HGB-S0 entrenado **sin s** (ni la evaluada). Un residuo dentro de muestra es casi cero y el método no haría nada. Son 8 modelos HGB anidados por partición, baratos.

### Brazos de L5 (objetivo residual y dominio)

| Brazo | Qué es | Modelos |
|---|---|---|
| `S0_res` | objetivo PM − ET0_OM; predicción = ET0_OM + modelo | HGB, Ridge, ANN M (**primario**) |
| `S0_sin_alt` | sin altitud | HGB, ANN M |
| `S0_alt_recortada` | altitud recortada al rango de entrenamiento | HGB |
| `S0_res_sin_alt` | las dos cosas | HGB, ANN M |
| control de dominio | marca las filas con algún input fuera del rango de entrenamiento; error dentro y fuera | sin entrenar |

Se reutilizan del 03.2, sin reentrenar, HGB-S0, HGB-S2 y ANN M-S0 (predicciones y celdas).

### Hipótesis (F1 salvo que se diga)

- **H33.1, la red mejora a Open-Meteo + ML:** `S0+R1` frente a HGB-S0, IC 95 % < 0.
- **H33.2, Open-Meteo + ML mejora a la red:** `S0+R1` frente a la IDW, IC 95 % < 0.
- **H33.3, robustez lejos de la red (F2):** `S0+R1` frente a HGB-S0 fuera Ibiza y fuera Menorca; se informa si empeora más de +0,05.
- **H5.1, el residual arregla la ANN:** ANN M `S0_res` frente a ANN M S0 del 03.2, IC 95 % < 0.
- **H5.2, el residual no cambia HGB:** HGB `S0_res` frente a HGB-S0, TOST ±0,05.

### Regla de interpretación (fijada antes)

1. H33.1 y H33.2 con IC < 0 y |Δ| ≥ 0,05, y en F2 no empeora más de 0,05 → **Open-Meteo + ML + red en toda Baleares**.
2. Lo mismo, pero en F2 empeora → **combinar solo cerca de la red**; la distancia de corte se fija con Andalucía (L4).
3. Mejora significativa pero menor de 0,05 → **se queda HGB-S0**, que no depende de que SIAR publique a tiempo.
4. Sin mejora → la red no aporta sobre HGB-S0.

Si solo un brazo informativo cumple 1 o 2, se informa como *post hoc*. L5: si H5.1 se cumple y la ANN M residual queda a menos de 0,05 de HGB-S0, las ANN vuelven a considerarse para Andalucía (L13); si no, quedan aparcadas. El control de dominio se adopta en el servicio pase lo que pase.

## Ejecución

- **Código nuevo, pequeño**, en esta carpeta: `run.py` (celdas partición × brazo × modelo, reanudables como en el 03.2), `report.py`, `kaggle_session.sh` y tests (exclusión de la propia estación en R1 y en los residuos anidados, objetivo residual, recorte de altitud, control de dominio). Se importan `loso_common` y `loso_models` del 03.2 y `network.py` del 03.1.2.
- **Volumen:** HGB y Ridge, unas 100 celdas de ~30 s más 96 HGB anidados: 1–2 h de CPU, cabe en local o en una sesión corta de Kaggle. ANN M: 3 brazos × 12 particiones × 5 semillas, unas 36 celdas de ~1.000 s: **una sesión de Kaggle de 3–4 h con 4 procesos**.
- **Salidas** como en el 03.2: `results/` (celdas, `metrics_global/by_station/by_month.csv`, `paired_ci.csv`, `equivalencia.csv`, `dominio.csv`, `predictions_test.csv.gz`, `run_manifest.json`, `interpretation.json`) y `figures/`.
- Al terminar, el estudio 05 añade los brazos ganadores al balance hídrico.

## Aclaraciones previas a la ejecución (2026-11-27, antes de ajustar ningún modelo)

Decididas con el autor tras comparar este README con `thresholds_v3_3.json` (no hay contradicciones; el JSON añade Ridge en `S0+R1`, que se sigue). El JSON congelado no se toca.

1. **Hueco de la regla de interpretación.** Los casos (1)–(4) no cubren todas las combinaciones (p. ej., `S0+R1` gana a HGB-S0 por ≥ 0,05 pero empata con la IDW). Se fija: **si algún IC95 < 0 y no se cumplen (1) ni (2), es el caso (3)** (se queda HGB-S0). `interpretation.json` indica si el caso salió del texto literal o de esta aclaración.
2. **`S0_alt_recortada` con HGB es idéntico a HGB-S0 por construcción**: los árboles mandan cualquier valor por encima del máximo de entrenamiento al último tramo (comprobado en IB01: diferencia máxima 0,000). Se mantiene tal cual y se informa así; no se añade ANN M.
3. **HGB-S0 anidados (`residuo_IDW` y w de `media_ponderada`)**: selección de hiperparámetros **anidada completa** (rejilla y validación interna sin s ni las evaluadas), no los del 03.2.
4. **Implementación**: validación interna con la red recalculada por pliegue (`select_and_fit_net`, lógica literal de `loso_models.select_and_fit`); IDW de residuos con `network.py`; IC 90 % del TOST con los mismos remuestreos; cohorte común = filas con red del día d **y** de d−1 y con todos los métodos finitos; control de dominio con los 12 inputs de S0 distintos de la altitud ([p0,5; p99,5]) y la altitud ([min; max]), con la tasa por variable.

## Resultados

### Ejecución y controles

- **234 celdas, 0 pendientes**: 84 HGB, 24 Ridge y 90 HGB-S0 anidados en local (unos 30–50 s por celda, 2 procesos); 36 ANN M en una sesión de Kaggle (CPU, 4 núcleos, 158 min, 10,2 h·núcleo; scikit-learn 1.9.1, pandas 3.0.5, numpy 2.5.3, las versiones fijadas del 03.2).
- HGB-S0, HGB-S2 y ANN M-S0 se reutilizan del 03.2 (no se reentrenan). Particiones idénticas a las del 03.2 (test).
- **Cohorte común:** 19.251 filas en F1. Ninguna fila sale por falta de red (siempre hubo red el día d y el d−1).
- Negativos recortados a 0: Ridge 21, HGB 0, ANN M 2.621.
- Tests: 61 previos + 18 nuevos (`tests/test_estudio_03_3.py`), que cubren las reglas (a)–(e).
- Figuras en `figures/`: `01_delta_vs_hgb_s0_F1`, `02_rmse_por_estacion_L3`, `03_ann_por_estacion_L5` y `04_F2_delta_vs_hgb_s0`.

### F1 (estación no vista), RMSE en mm/día

| Método | RMSE | Δ frente a HGB-S0 [IC95] |
|---|---|---|
| HGB-S0 (03.2), referencia | 0,433 | — |
| PM IDW del día | 0,434 | +0,002 [−0,026; +0,030] |
| **S0+R1 HGB** (brazo primario de L3) | 0,444 | +0,011 [−0,012; +0,033] |
| S0+R1 Ridge | 0,438 | +0,005 |
| S2+R1 HGB | 0,423 | −0,010 (frente a HGB-S2 0,396: peor) |
| S0+R1_ayer HGB | 0,454 | +0,021 [+0,007; +0,036] |
| S0_res HGB | 0,431 | −0,002 [−0,004; +0,000] |
| S0_res Ridge | 0,485 | +0,052 |
| S0_res ANN M | 0,996 | +0,563 |
| ANN M-S0 (03.2) | 1,020 | +0,587 |
| S0_sin_alt HGB / ANN M | 0,459 / 0,452 | +0,026 / +0,019 [0,000; +0,039] |
| S0_alt_recortada HGB | 0,433 | 0,000 (idéntico por construcción, aclaración 2) |
| S0_res_sin_alt HGB / ANN M | 0,461 / 0,452 | +0,028 / +0,019 |
| residuo_IDW (informativo) | 0,400 | −0,032 [−0,050; −0,014] |
| media_fija (informativo) | 0,377 | −0,056 [−0,070; −0,042] |
| media_ponderada (informativo) | 0,378 | −0,055 |

Todas las cifras y los IC están en `results/metrics_global.csv` y `results/paired_ci.csv` (bootstrap por bloques estación-año, 2.000 remuestreos, semilla 20261126).

### Hipótesis planificadas

| Hipótesis | Comparación | Resultado | Veredicto |
|---|---|---|---|
| H33.1 | S0+R1 HGB frente a HGB-S0 (F1) | 0,444 frente a 0,433; Δ +0,011 [−0,012; +0,033] | **No se cumple** |
| H33.2 | S0+R1 HGB frente a IDW del día (F1) | Δ +0,009 [−0,016; +0,034] | **No se cumple** |
| H33.3 | S0+R1 HGB frente a HGB-S0 (F2) | Ibiza +0,166 [+0,141; +0,199]; Menorca +0,118 [+0,091; +0,137] | **Empeora más de +0,05** en las dos islas |
| H5.1 | ANN M S0_res frente a ANN M-S0 (F1) | 0,996 frente a 1,020; Δ −0,025 [−0,039; −0,006] | **Se cumple**, pero la mejora es pequeña |
| H5.2 | HGB S0_res frente a HGB-S0 (F1), TOST ±0,05 | Δ −0,002, IC90 [−0,004; +0,000] | **Equivalentes** |

### Regla de interpretación, aplicada literalmente

- **L3: caso (4), «la red no aporta sobre HGB-S0».** El brazo primario `S0+R1` HGB no mejora a HGB-S0 ni a la IDW en F1 (ningún IC95 por debajo de 0) y empeora mucho en F2. La aclaración 1 no interviene. `S2+R1` y `S0+R1_ayer` tampoco cumplen (1) ni (2).
- **L5: las ANN quedan aparcadas.** H5.1 se cumple, pero la ANN M residual queda a +0,563 de HGB-S0, muy lejos de 0,05. El objetivo residual no arregla IB01 (2,68 mm/día, sesgo −2,44): el fallo viene de la altitud, no del objetivo.
- **El control de dominio se adopta en el servicio**, como estaba previsto pase lo que pase.
- **Se queda HGB-S0** como modelo de Open-Meteo + ML. El objetivo residual con HGB es equivalente y no aporta.

`results/interpretation.json` lo registra caso por caso.

### Por estación (F1), RMSE en mm/día

| Estación (altitud) | HGB-S0 | IDW | S0+R1 HGB | media_fija | residuo_IDW |
|---|---|---|---|---|---|
| IB02 (78 m) | 0,418 | 0,429 | 0,304 | 0,378 | 0,369 |
| IB03 (79 m) | 0,367 | 0,334 | 0,297 | 0,259 | 0,287 |
| IB04 (8 m) | 0,417 | 0,301 | 0,371 | 0,314 | 0,363 |
| IB05 (82 m) | 0,412 | 0,366 | **0,537** | 0,357 | 0,313 |
| IB06 (4 m) | 0,388 | 0,347 | 0,382 | 0,319 | 0,355 |
| IB08 (40 m) | 0,458 | 0,568 | **0,576** | 0,474 | 0,411 |
| IB10 (30 m) | 0,358 | 0,451 | 0,379 | 0,332 | 0,368 |
| IB11 (7 m) | 0,630 | 0,571 | 0,614 | 0,531 | 0,590 |

**IB01 (120 m, aparte)**, la estación más alta y fuera del rango de altitud de entrenamiento:

- Con los HGB no hay problema: HGB-S0 0,382; S0+R1 0,403; media_fija 0,353; residuo_IDW 0,461.
- Las ANN con altitud se rompen: ANN M-S0 2,77; S0_res ANN M 2,68.
- Sin altitud la ANN funciona: S0_sin_alt 0,375 y S0_res_sin_alt 0,381.

### F2 (fuera de isla), Δ frente a HGB-S0 [IC95]

| Método | Fuera Ibiza (HGB-S0 0,509) | Fuera Menorca (HGB-S0 0,458) | Fuera Mallorca (informativo, 0,477) |
|---|---|---|---|
| S0+R1 HGB | +0,166 [+0,141; +0,199] | +0,118 [+0,091; +0,137] | −0,054 |
| PM IDW del día | +0,103 | +0,110 | +0,016 |
| media_fija | −0,004 | +0,015 | −0,048 |
| residuo_IDW | +0,042 | −0,047 | +0,102 |
| S0_res HGB | +0,003 | 0,000 | 0,000 |

### Control de dominio y dispersión entre semillas

- **Filas marcadas fuera de dominio en F1: 32,1 %.** Casi todas son por altitud (22,8 %; IB01 e IB06 al 100 %) (`results/dominio.csv`).
- Error dentro y fuera de dominio:

  | Modelo | Dentro | Fuera |
  |---|---|---|
  | HGB-S0 | 0,433 | 0,433 |
  | ANN M-S0 | 0,432 | 1,686 |
  | ANN M S0_res | 0,445 | 1,632 |

  El aviso separa exactamente los fallos de las ANN. Dentro de dominio, la ANN empata con HGB.
- **Desviación típica del RMSE entre las 5 semillas de la ANN M (F1):** ANN M-S0 0,137; S0_res 0,092; sin altitud ≤ 0,005 (`results/ann_seed_spread.csv`). Sin altitud la ANN es estable.

## Análisis *post hoc* (no planificado como confirmatorio)

Lo que sigue no cambia el veredicto anterior. Sirve para proponer estudios, no para concluir.

1. **Las combinaciones HGB-S0 + red sí cumplirían el caso (1).** Son brazos informativos, así que la regla los manda a *post hoc*.
   - `media_fija` (0,5 · HGB-S0 + 0,5 · IDW): 0,377, que es −0,056 frente a HGB-S0 y −0,058 frente a la IDW. En F2 no empeora de forma relevante (Ibiza −0,004, Menorca +0,015).
   - `media_ponderada` da lo mismo (0,378), porque la validación interna elige w = 0,5 en casi todas las particiones (0,6 en IB04 y fuera Mallorca).
   - `media_fija` usa las mismas predicciones de HGB-S0 y de la IDW que el 03.2, sobre el mismo TEST. Por eso da exactamente la misma cifra que el indicio del 03.2: **es un recálculo, no una réplica**. Lo nuevo es `media_ponderada`, cuyo peso se elige en DESARROLLO, sin ver TEST, y sale 0,5. Es el mejor método del estudio en F1 y no pierde lejos de la red.
2. **`residuo_IDW`** (regresión-kriging simplificada) mejora a HGB-S0 en F1 (0,400; −0,032), pero menos de 0,05, así que es el caso (3) por la aclaración 1. En F2 es inestable: Menorca −0,047, Ibiza +0,042, Mallorca +0,102. Interpolar residuos de estaciones lejanas propaga sesgos locales.
3. **Por qué falla `S0+R1`: probable causa, sin comprobar.** `d1_km` (distancia a la estación más cercana) es casi constante en cada estación, así que actúa como un identificador de sitio, igual que las coordenadas en el 03.2. Los peores casos son estaciones con un `d1_km` atípico:
   - IB05 pasa de 0,41 a 0,54; en test su d1 es 10,7 km, por debajo del rango de entrenamiento.
   - IB08 pasa de 0,46 a 0,58; su d1 es de 93 km.
   - En F2, d1 queda muy fuera del rango de entrenamiento.

   La ablación «S0+R1 sin `d1_km`» **queda propuesta, no ejecutada**: no estaba en el plan.
4. **La red del día anterior** (`S0+R1_ayer`) cuesta +0,010 frente a la del día (0,454 frente a 0,444) y queda peor que HGB-S0 (+0,021, IC por encima de 0). Por la vía de `S0+R1`, no esperar a SIAR no tiene contrapartida que perder.
5. **ANN sin altitud.** Es estable y ya no se rompe en IB01, pero sigue peor que HGB-S0 (+0,019) y empeora en IB08 e IB10. Si se retoman las ANN (L13), deben ir sin inputs estáticos que extrapolen.

## Valoración: qué se saca en claro, qué no, y propuestas

Esta parte es una valoración, como la Parte IV y la Parte V del 03.2. No cambia el veredicto, que ya está aplicado en «Regla de interpretación».

Las cifras nuevas salen de `results/predictions_test.csv.gz` (F1, cohorte común, n = 19.251) y no estaban en el informe: estación, temporada, sesgo y correlación de errores.

### Lo bueno (lo que se saca en claro)

1. **Queda cerrada, con criterio congelado, la pregunta de si la red sirve como input del modelo: no.**
   - `S0+R1` HGB (0,444) no mejora a HGB-S0 ni a la IDW.
   - Con Ridge pasa lo mismo (0,438; frente a la IDW +0,003 [−0,009; +0,017]).
   - Con el termohigrómetro incluso empeora: `S2+R1` 0,423 frente a HGB-S2 0,396, +0,027 [+0,004; +0,052].
   - Fuera de isla empeora mucho (+0,12 a +0,17).
   - Es un resultado negativo limpio. Evita llevar a Andalucía o al servicio un diseño que no funciona.
2. **La combinación más simple sí funciona, y por todas partes.**
   - La media HGB-S0 + IDW gana a HGB-S0 en las cuatro estaciones del año (DJF 0,245 frente a 0,258; MAM 0,378 frente a 0,451; JJA 0,487 frente a 0,582; SON 0,359 frente a 0,377).
   - Gana sobre todo en verano (−0,095), que es cuando más pesa en el riego.
   - Gana a HGB-S0 en 8 de 9 estaciones y a la IDW en 8 de 9. Las excepciones son IB08 frente a HGB-S0 e IB04 frente a la IDW.
   - Sin ningún sensor empata con HGB-S2, que sí lleva termohigrómetro: −0,019 [−0,046; +0,008].
3. **El peso 0,5 no está elegido mirando TEST.** La validación interna de `media_ponderada`, hecha solo con DESARROLLO y sin la estación evaluada, elige w = 0,5 en casi todas las particiones. Es la única evidencia nueva a favor de la media que aporta este estudio (ver Lo malo, 1).
4. **Los dos errores se compensan porque son poco parecidos.** La correlación entre el error de HGB-S0 y el de la IDW es 0,51 (entre 0,40 y 0,62 según la estación). Además, sus sesgos por estación suelen tener signo distinto: IB03 +0,16 frente a −0,20; IB10 −0,05 frente a +0,26; IB01 −0,06 frente a +0,17. El mecanismo es sencillo y explicable: Open-Meteo + ML y la red fallan por motivos distintos.
5. **`residuo_IDW` casi no tiene sesgo global** (−0,007, frente a +0,042 de HGB-S0 y +0,044 de la media). Para el balance hídrico, donde el sesgo se acumula (estudio 05), esto interesa aunque su RMSE sea peor que el de la media.
6. **El problema de las ANN queda diagnosticado del todo.**
   - No es el objetivo: el residual solo baja de 1,020 a 0,996.
   - Es la altitud: sin ella la ANN da 0,452, no se rompe en IB01 (0,375) y es estable entre semillas (desviación ≤ 0,005, frente a 0,137).
   - El control de dominio separa exactamente las filas malas. Dentro de dominio, la ANN empata con HGB (0,432 frente a 0,433); fuera, 1,686.
   - El control de dominio queda justificado con datos, no solo como prudencia.
7. **El objetivo residual es inocuo con HGB** (equivalente por TOST, Δ −0,002). Si en algún estudio conviene usarlo, por ejemplo para que un modelo caiga hacia Open-Meteo cuando extrapola, no cuesta nada.
8. **La ejecución ha sido limpia.** No se han perdido filas por falta de red, las particiones son idénticas a las del 03.2 y el HGB-S0 anidado tiene selección de hiperparámetros completa. Las cuatro aclaraciones se fijaron antes de ajustar ningún modelo.

### Lo malo (lo que no queda claro o sale mal)

1. **La media no tiene todavía una confirmación independiente.** `media_fija` es un recálculo sobre las mismas predicciones y el mismo TEST que el 03.2, no una réplica. Además, la regla congelada la deja como brazo informativo. Que sea la mejor opción solo se podrá afirmar cuando se prerregistre como brazo principal en datos nuevos: Andalucía (L4) o un periodo posterior a 2025.
2. **El brazo primario se diseñó mal, y era previsible.** El 03.1.2 ya había visto que `d1_km` extrapola mal lejos de la red (su Parte VIII, punto 2). Cuando se congeló el 03.3 no se tuvo en cuenta, porque los dos estudios se diseñaron en paralelo.
3. **La explicación de por qué falla `S0+R1` no está demostrada.** La hipótesis es que `d1_km` actúa como identificador de estación. La apoya la extrapolación fuera de isla y que el sesgo de `S0+R1` sube mucho en IB05 (+0,44 frente a +0,24) e IB08 (+0,46 frente a +0,27). Pero IB03, con el mismo d1 que IB05 (10,7 km, son vecinas), mejora con `S0+R1` (0,297 frente a 0,367). Sin la ablación no se puede afirmar.
4. **La media empeora donde la red está lejos.** En IB08 (Menorca, d1 = 93 km) la media da 0,474, frente a 0,458 de HGB-S0. Fuera Menorca da +0,015. Con un solo caso no se puede generalizar, pero apunta a que el peso de la red debería bajar con la distancia.
5. **`residuo_IDW` es inestable lejos de la red:** −0,047 fuera Menorca, +0,042 fuera Ibiza y +0,102 en Mallorca. Interpolar residuos de estaciones a más de 90 km propaga sesgos de otro sitio.
6. **Las ANN siguen sin aportar, incluso arregladas.** Sin altitud quedan +0,019 por encima de HGB-S0 y pierden mucho en IB08 (0,59) e IB10 (0,47). Como modelo de punto con estos datos no tienen recorrido.
7. **El 32 % de las filas de F1 queda fuera de dominio**, casi todo por altitud (IB01 e IB06 al 100 %). En un servicio, un aviso que salta en un tercio de los casos se ignora. La regla de dominio necesita un umbral que distinga «fuera de rango» de «fuera de rango y peligroso para este modelo»: con HGB el error fuera de dominio es el mismo que dentro.
8. **La red de ayer no se ha medido donde importa.** `S0+R1_ayer` solo dice que la red de ayer como input tampoco sirve. Cuánto pierde la media con la red de ayer, que es lo que decidiría si sirve para la ET0 de hoy, no se ha medido. En el 03.1.2, la red de ayer perdía casi todo su valor con un sensor barato.

### Lo que este estudio no responde

- Si la media gana en datos nuevos (ver Lo malo, 1).
- Cómo debería depender el peso de la red de la distancia, y a partir de qué distancia conviene no usarla.
- Si la media funciona con la red del día anterior o con la previsión (estudio 04).
- Si funciona en altura o en interior: ninguna estación supera los 120 m.
- Si el fallo de `S0+R1` se debe a `d1_km` o a otra cosa.

### Propuestas de mejora y variantes

Posibilidad de que funcionen: **alta**, **media** o **baja**, como en el 03.2. Cada una necesita su protocolo congelado antes de ejecutarse.

#### A. Prerregistrar la media HGB-S0 + IDW como brazo principal en Andalucía (L4) — posibilidad **alta**

Es la confirmación que falta. Hay que fijar antes de ver resultados:
- w = 0,5 (o el elegido en validación interna);
- las mismas comparaciones (frente a HGB-S0 y frente a la IDW);
- el umbral de 0,05.

Con unas 100 estaciones y la exclusión por radio de L4, se obtiene además la curva de la media frente a la distancia. Es la forma de convertir el mejor resultado *post hoc* en un resultado.

#### B. Peso de la red que baje con la distancia — posibilidad **media-alta**

La fórmula sería: w(d1) = peso de HGB-S0, que crece con d1 desde 0,5 cerca de la red hasta 1 lejos, por ejemplo con un corte o una rampa entre 30 y 90 km. Se ajusta en DESARROLLO.

Recoge lo que se ve en IB08 y en F2 sin meter `d1_km` en el modelo. En Baleares hay muy pocas estaciones lejanas para ajustarla, así que se diseña aquí y se estima en Andalucía (junto con A).

#### C. Ablación «S0+R1 sin `d1_km`» y variante «S0+R3» — posibilidad **media**

Cierra la duda de por qué falla `S0+R1`. Es barata: unas 24 celdas de HGB en local, con la misma infraestructura.
- `S0+R1 sin d1`: solo la IDW como input.
- `S0+R3`: las 3 vecinas ordenadas. En el 03.1.2, R3 fue más estable que R1 (ganaba o empataba en 8 de 9 estaciones).
- Opcional: entrenar con distancias más variadas, quitando a veces a los vecinos más cercanos (la idea del punto 2 de la Parte VIII del 03.1.2).

Si alguna iguala a la media, el modelo podría aprender la ponderación por sí solo. Si no, la media se queda como método.

#### D. Media con la red de ayer — posibilidad **alta** de que se pueda medir; resultado incierto

Basta con calcular la IDW del día d−1 (ya se hace para `S0+R1_ayer`) y promediarla con HGB-S0. Es un cálculo de minutos, sin entrenar nada. Responde a la pregunta abierta sobre el retraso de SIAR. Si la media con la red de ayer sigue ganando a HGB-S0, el método vale para la ET0 de hoy; si no, solo para la de ayer. Debe congelarse antes de calcular.

#### E. Combinar media y `residuo_IDW` por su sesgo — posibilidad **media**

La media tiene mejor RMSE y `residuo_IDW` casi no tiene sesgo. Para el balance hídrico (estudio 05), que acumula sesgo, conviene comparar las dos en litros y no solo en RMSE. Basta con añadirlas como fuentes al 05, sin entrenar nada.

#### F. Control de dominio por modelo, no por input — posibilidad **alta**

Que el aviso solo salte con modelos sensibles a extrapolar (ANN, Ridge) o cuando el input esté lejos del rango, no solo fuera. Con HGB el error dentro y fuera de dominio es el mismo (0,433), así que con el modelo de referencia no hace falta avisar por altitud. Se puede definir y probar con las predicciones que ya existen.

#### No recomendado

- **Más brazos con la red como input del modelo**, salvo la ablación C: tres variantes (Ridge, HGB, con sensor) fallan del mismo modo.
- **ANN como modelo de punto**, ni con objetivo residual ni sin altitud: quedan siempre por detrás de HGB. Solo tiene sentido retomarlas con contexto temporal o espacial (L13).
- **Recortar la altitud con árboles:** no hace nada por construcción.

## Riesgos y salvedades

- Diseño escrito después del 03.2 y de su indicio: declarado. El resultado de `media_fija` reproduce ese indicio, pero sigue siendo *post hoc*: para usarlo como resultado hay que prerregistrarlo en Andalucía (L4) o en un periodo nuevo. F1 es optimista; F2 es el caso que más interesa.
- La red es la validada; el servicio tendría la del día sin validar: límite superior. `S0+R1_ayer` mide el coste de no esperar.
- En tiempo real Open-Meteo `archive` llega con ~5 días de retraso: el servicio usaría la previsión o el análisis del día (estudio 04). Este estudio mide la corrección, no la disponibilidad.
- Licencia: la API gratuita de Open-Meteo es no comercial. El estudio 03.4 (propuesto) repetiría lo esencial con ERA5 de Copernicus.
