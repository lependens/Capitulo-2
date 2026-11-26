# Estudio 03: Open-Meteo corregido con ML, evaluado en estaciones no vistas (leave-one-station-out)

Estado: **PLAN**. Protocolo y criterios en `config/thresholds_v3.json`; se congelan al fusionar el PR que los introduce, antes de ejecutar nada de este protocolo.

## Por qué este estudio (cambio de rumbo)

Los estudios 01 y 02 dejan tres hechos:

1. Las ANN de V2 ganan a Open-Meteo + AHC **en su propia estación** (entrenadas y evaluadas en el mismo sitio). Es el caso de menos valor práctico: quien tiene una estación SIAR al lado ya tiene PM.
2. La familia que gana siempre (HG-Rs) necesita piranómetro. Quien tiene piranómetro suele tener también termohigrómetro y anemómetro, es decir, puede calcular PM. La familia realista con sensor barato (Valiantzas: T y HR) solo empata o gana por poco.
3. El error de Open-Meteo viene sobre todo del **viento** de la rejilla y de un **rango diurno de temperatura** demasiado estrecho; su radiación y su humedad son buenas (estudio 01, sustitución de inputs). Open-Meteo tiene la información, pero necesita corrección.

Una prueba exploratoria (`exploratorio/`, ver abajo) sugiere que un modelo **conjunto para Baleares** que corrige Open-Meteo con ML, entrenado con la PM de SIAR de otras estaciones, estima mejor en una estación no vista que copiar la estación más cercana o aplicar un coeficiente mensual. En cambio, los modelos que solo usan pocos inputs locales (T, o T y HR) se degradan mucho fuera de su estación.

Por eso se propone reorientar el producto de "ANN con pocos inputs locales" a **"datos de rejilla (Open-Meteo) corregidos para tu ubicación con la referencia SIAR"**, con sensor del usuario opcional. Este estudio lo comprueba con protocolo formal.

Pregunta principal: **en una ubicación sin estación SIAR, ¿un modelo conjunto que corrige Open-Meteo con ML se acerca a la PM de SIAR más que las alternativas sencillas?**

## Datos

| Bloque | Periodo | Fuente | Estado |
|---|---|---|---|
| Open-Meteo `archive` diario | 2004–2025 | `data/processed/openmeteo_archive.csv` | disponible |
| Referencia PM_FAO56_V1 | 2004–2025 | `data/reference/reference_*.csv` | disponible |
| Inputs de sensor SIAR | 2020–2025 | `data/reference/siar_inputs_2020_2025.csv` | disponible |
| Inputs de sensor SIAR | 2004–2019 | `data/reference/siar_inputs_2004_2019.csv` | **falta: paso previo** |
| Predicciones V2 (contexto) | 2020–2025 | `data/v2/` | disponible |

**Paso previo.** Exportar los inputs de sensor 2004–2019 con `tools/export_reference.py` desde `classical-baselines.csv` (SHA256 `f55e4ed1…af44`, en el servidor), con las mismas columnas que la exportación 2020–2025 (`--keep TempMax,TempMin,TempMedia,HumedadMax,HumedadMin,HumedadMedia,VelViento,Radiacion,quality_status --start 2004-01-01 --end 2019-12-31`). Si no se puede, alternativa: `datos_siar_baleares/IBxx_datos_completos.csv` de Capitulo-1, comprobando antes que en 2020–2025 coinciden con la exportación existente; si no coinciden, se para y se documenta.

## Diseño

**Separación espacial y temporal a la vez.** Se entrena solo con DESARROLLO (2004–2019) y solo con las estaciones de entrenamiento; se evalúa en TEST (2020–2025) en la estación dejada fuera, sobre la cohorte común de V2 (`common_core == 1`, n = 19.251), las mismas claves que el estudio 02. Así los números son comparables con V2 y con el estudio 02.

**Particiones (fijas, en `folds.json`):**
- **F1, leave-one-station-out (principal):** 9 particiones, una por estación.
- **F2, leave-one-island-out (prueba dura):** fuera Ibiza (IB01, IB11) y fuera Menorca (IB08). "Fuera Mallorca" deja solo 3 estaciones de entrenamiento: se ejecuta y se informa, pero no entra en los criterios.

**Escenarios de inputs** (lo que tendría un usuario en su parcela):

| Código | Inputs | Usuario tipo |
|---|---|---|
| S0 | Open-Meteo (ET0, Tmax, Tmin, radiación, viento medio y máximo, HR media/máx/mín) + seno y coseno del día del año + Ra + altitud | sin sensor |
| S1 | S0 + Tmax y Tmin del sensor | termómetro |
| S2 | S0 + Tmax, Tmin y HR media del sensor | termohigrómetro |
| L1 | solo sensor: Tmax, Tmin, Ra, día del año, altitud | modelo conjunto tipo HS-Ra |
| L2 | solo sensor: Tmax, Tmin, HR media, Ra, día del año, altitud | modelo conjunto tipo Valiantzas |

Latitud y longitud **no** entran en el escenario principal: con 9 estaciones funcionan casi como un identificador y el modelo memoriza. Se prueba solo como sensibilidad (S0+coord).

**Modelos (conjunto cerrado, declarado antes):**

| Modelo | Por qué |
|---|---|
| Ridge (lineal, inputs estandarizados) | Corrección estadística clásica (MOS); suelo de referencia |
| HistGradientBoosting | Primario (declarado de antemano) |
| Random Forest | Segundo árbol, distinto sesgo de modelo |
| ANN-S: MLP (32) | Red pequeña |
| ANN-M: MLP (64, 32) | Red media |

Hiperparámetros: rejilla pequeña declarada en `thresholds_v3.json`, elegida con validación cruzada interna agrupada por estación **dentro del entrenamiento** de cada partición. Nunca se mira TEST para elegir. Las ANN se entrenan con 5 semillas; la predicción es la media de las 5 y se informa además la dispersión entre semillas (incertidumbre de entrenamiento, que el estudio 02 no cubría). Predicciones negativas: se recortan a 0 y se informa cuántas.

No se añaden más arquitecturas después de ver resultados: comparar muchas variantes en el mismo TEST acaba eligiendo la que tuvo suerte.

**Comparadores:**

| Comparador | Qué representa |
|---|---|
| Open-Meteo crudo | lo que obtiene cualquiera gratis |
| OM + AHC mensual medio de las estaciones de entrenamiento | la corrección sencilla transferida |
| OM + AHC mensual de la estación de entrenamiento más cercana | idem, versión "vecino" |
| PM de la estación SIAR más cercana el mismo día | lo que hace la app SiAR |
| PM interpolada (IDW) de las estaciones de entrenamiento el mismo día | interpolación espacial sencilla |
| V2 local (HS-Ra, HG-Rs, Valiantzas: fórmula, AHC, ANN) y OM+AHC local del estudio 02 | **techo**: modelos de la propia estación; no son LOSO, solo contexto |

Los comparadores de estación más cercana e IDW usan observaciones del mismo día de otras estaciones: es legítimo como servicio operativo (esos datos existen en tiempo real), y se indica así.

## Métricas y criterios

Mismas definiciones que V2 y estudio 02: error = predicción − PM; n, MAE, RMSE, sesgo, R² = 1 − SSE/SST; DJF asigna diciembre al año siguiente. Desgloses por estación, mes, temporada y año. Diferencias pareadas ΔRMSE con IC 95 % por bootstrap de bloques estación-año (54 bloques, 2.000 réplicas, semilla fija).

Hipótesis (criterios en `config/thresholds_v3.json`):

- **H1 (principal):** HGB-S0 en F1 tiene menor RMSE que OM + AHC mensual medio transferido (ΔRMSE < 0 y extremo superior del IC < 0).
- **H2:** HGB-S0 en F1 tiene menor RMSE que la PM de la estación más cercana.
- **H3:** el sensor del usuario aporta: S2 mejora a S0 con el mismo modelo (IC < 0).
- **H4 (documenta el cambio de rumbo):** los modelos conjuntos solo de sensor (L1, L2) tienen mayor RMSE que S0.
- **Relevancia práctica:** una diferencia significativa menor de 0,05 mm/día se informa como "significativa pero pequeña".

Todo lo demás (otros modelos, F2, sensibilidad con coordenadas) se informa como secundario, sin veredicto.

## Salidas

`results/`: `folds.json`, `metrics_global.csv`, `metrics_by_station.csv`, `metrics_by_month.csv`, `paired_ci.csv`, `ann_seed_spread.csv`, `predictions_test.csv` (con columna de partición), `run_manifest.json` (SHA256 de entradas, versiones de librerías, semillas). `figures/` con RMSE por escenario y modelo, por estación y por mes. El README se completa con la lectura y las salvedades.

Dependencias: este estudio usa scikit-learn, pandas y numpy (`requirements.txt` de la carpeta). La librería `src/openmeteo_et0` sigue sin dependencias.

## Salvedades conocidas de antemano

- Referencia calculada (PM_FAO56_V1), no ET0 medida.
- Solo 9 estaciones, todas en zonas de regadío y cercanas entre sí: F1 es optimista; por eso F2.
- Se usa reanálisis (`archive`), que llega con unos 5 días de retraso. No dice nada del error con **previsión**: eso es el estudio 04.
- Open-Meteo: datos CC BY 4.0, API gratuita solo no comercial.

## Prueba exploratoria previa (no es resultado de este estudio)

`exploratorio/loso_rapido.py` y su salida `exploratorio/salida_2026-11-26.txt`: una sola ejecución con HGB, entrenamiento ≤ 2022 y prueba 2023–2025 (distinto de este protocolo), sin IC. Resultado: OM + ML sin sensor 0,41 mm/día de RMSE en estación no vista; OM + AHC mensual transferido 0,47; estación más cercana ≈ 0,47 (0,40–0,57 según el par); modelos conjuntos solo de sensor 0,57–0,69; Open-Meteo crudo 0,75. Se declara aquí porque el diseño de este estudio se escribió **después** de verla: es la razón del cambio de rumbo, no su demostración.
