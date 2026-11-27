# Estudio 03.3: Open-Meteo + ML + red SIAR del día, y objetivo residual (L3 y L5)

Estado: **PLAN**, criterios congelados en `config/thresholds_v3_3.json` al fusionar el PR que los crea (2026-11-27). No se ha ejecutado nada. La ejecución se hará en un chat aparte con el prompt de `PROMPT_CHAT.md`.

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

## Riesgos y salvedades

- Diseño escrito después del 03.2 y de su indicio: declarado. F1 es optimista; F2 es el caso que más interesa.
- La red es la validada; el servicio tendría la del día sin validar: límite superior. `S0+R1_ayer` mide el coste de no esperar.
- En tiempo real Open-Meteo `archive` llega con ~5 días de retraso: el servicio usaría la previsión o el análisis del día (estudio 04). Este estudio mide la corrección, no la disponibilidad.
- Licencia: la API gratuita de Open-Meteo es no comercial. El estudio 03.4 (propuesto) repetiría lo esencial con ERA5 de Copernicus.
