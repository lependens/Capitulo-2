# Capitulo-2

Tras conseguir en Capitulo 1 el estado de ET0 v2, se propone revisar si se han obtenido resultados competitivos tomando como referencia OPEN-METEO, para revisar si se podria establecer un modelo o modelos competitivos para uso agronomico mejor a la competencia o a lo que se ofrece actualmente.

Origen de los modelos y la referencia: [Capitulo-1](https://github.com/lependens/Capitulo-1). Este repo solo contiene lo necesario para comparar con Open-Meteo y para los estudios que salgan de ahi; no duplica la documentacion de Capitulo-1.

## Que hay aqui

| Ruta | Contenido |
|---|---|
| `config/stations.csv` | Las 9 estaciones SIAR activas de Baleares (coordenadas del catalogo; longitud decimal **derivada** del formato nativo, solo para consultar a Open-Meteo) |
| `config/thresholds.json` | Criterio de exito del estudio 01, **fijado antes de ver resultados** |
| `src/openmeteo_et0/` | Descarga, almacenamiento con hash, normalizacion y metricas (solo libreria estandar de Python) |
| `data/raw/` | Respuestas originales de la API (`.json.gz`), nunca se sobrescriben; `manifest.csv` con fecha de consulta, URL y SHA256 |
| `data/processed/` | Tablas diarias derivadas de lo crudo (reconstruibles) |
| `config/thresholds_v2.json` | Criterios del estudio 02, **fijados antes de ejecutarlo** |
| `data/v2/` | Predicciones ET0 V2 2020-2025 exportadas de Capitulo-1 (con manifiesto y SHA256) |
| `data/reference/` | Referencia PM_FAO56_V1 congelada (subconjunto de Capitulo-1) con su manifiesto y SHA256 |
| `studies/02_openmeteo_ahc/` | Estudio 02: Open-Meteo + AHC (ajuste ≤2019, test 2020-2025) frente a V2 |
| `config/thresholds_v3.json` | Criterios del estudio **03.2** (congelados con el PR #8; conserva su nombre original porque su SHA256 consta en los manifiestos del 03.1 y 03.2 y lo lee el código del 03.1) |
| `config/thresholds_v3_1.json` | Criterios del estudio 03.1 (congelados antes de ejecutar) |
| `studies/03_1_loso_inputs_siar/` | Estudio 03.1 (ejecutado): modelos de pocos inputs SIAR de V2 en estaciones no vistas; justifica el cambio de rumbo |
| `config/thresholds_v3_1_2.json` | Criterios del estudio 03.1.2 (PROPUESTA; se congelan con su PR, antes de ejecutar) |
| `studies/03_1_2_loso_sensor_red/` | Estudio 03.1.2 (plan): sensor local + red SIAR del mismo día y previsión a D+1; prompt de ejecución en `PROMPT_CHAT.md` |
| `studies/03_2_loso_openmeteo_ml/` | Estudio 03.2 (ejecutado): Open-Meteo corregido con ML, evaluado en estaciones no vistas (leave-one-station-out). Criterios en `config/thresholds_v3.json` |
| `config/thresholds_v3_3.json` | Criterios del estudio 03.3 (congelados al crearlo) |
| `studies/03_3_om_red_residual/` | Estudio 03.3 (plan): Open-Meteo + ML + red SIAR del día, y objetivo residual; prompt en `PROMPT_CHAT.md` |
| `config/thresholds_v4.json` | Criterios de la fase B del estudio 04 (PROPUESTA; se congelan antes de evaluar con las capturas) |
| `config/thresholds_v5.json` | Criterios del estudio 05 (PROPUESTA; falta la tabla de cultivos de FAO-56) |
| `studies/05_balance_hidrico/` | Estudio 05 (plan + exploratorio): cuánto cambia el riego según la fuente de ET0; prompt en `PROMPT_CHAT.md` |
| `docs/COMO_ACTUALIZAR.md` | Qué se actualiza (README de estudio, README principal, ideas) en cada avance |
| `docs/IDEAS_Y_MEJORAS.md` | Documento vivo: lo aprendido, líneas de investigación, publicación y cómo rentabilizar |
| `studies/04_prevision_et0/` | Estudio 04 (fase A preparada): previsión de ET0 a 1–7 días; prompt en `PROMPT_CHAT.md` |
| `tools/capture_ecmwf.py` | Captura de la previsión abierta de ECMWF (CC-BY-4.0) en los puntos de las estaciones |
| `studies/01_et0_vs_pm/` | Estudio 01: ET0 de Open-Meteo frente a PM_FAO56_V1 y frente a las formulas V2 |
| `tools/export_reference.py` | Extrae de `classical-baselines.csv` (Capitulo-1, 56 MB) solo 2020-2025 y las columnas necesarias |
| `.github/workflows/` | `daily_forecast` (Open-Meteo, diaria), `ecmwf_forecast` (ECMWF, 00z y 12z), `backfill` (descarga historica manual), `tests` |

## Hoja de ruta (seguir en orden)

Cada paso nace de lo que dejo el anterior. Los criterios de exito se congelaron **antes** de ejecutar (carpeta `config/`).

| # | Estudio | Pregunta | Resultado clave | Estado |
|---|---|---|---|---|
| 1 | [01 - Open-Meteo frente a PM](studies/01_et0_vs_pm/README.md) | La ET0 de Open-Meteo, se parece a la PM calculada de SIAR? Que variable de rejilla falla? | Cohorte de 19.251 pares estacion-dia (2020-2025); el error viene sobre todo del viento y del rango diurno de temperatura de la rejilla. Criterio: [`thresholds.json`](config/thresholds.json) | Ejecutado |
| 2 | [02 - Open-Meteo + AHC](studies/02_openmeteo_ahc/README.md) | Corrigiendo Open-Meteo con un coeficiente por estacion (AHC), compite con las ANN de V2? | RMSE 0,752 (crudo) -> 0,534 / 0,454 / 0,427 (AHC anual / estacional / mensual). Las ANN con radiacion medida ganan; las de solo temperaturas pierden; Valiantzas empata en mensual. Criterio: [`thresholds_v2.json`](config/thresholds_v2.json) | Ejecutado |
| 3 | [03.1 - Pocos inputs SIAR en estacion no vista](studies/03_1_loso_inputs_siar/README.md) | Los modelos de pocos inputs de V2, funcionan en una estacion que no han visto (LOSO)? | No: degradan fuera de su estacion, HS-Ra no compensa y las ANN con altitud se rompen. Justifica el cambio de rumbo. Criterio: [`thresholds_v3_1.json`](config/thresholds_v3_1.json) | Ejecutado |
| 4 | [03.2 - Open-Meteo + ML en estacion no vista](studies/03_2_loso_openmeteo_ml/README.md) | Open-Meteo como entrada de un modelo entrenado con otras estaciones, supera a Open-Meteo + AHC? | HGB con las mismas variables de Open-Meteo (S0): RMSE 0,433 frente a 0,483 (AHC transferido) y 0,752 (crudo); con Tmax/Tmin (S1) 0,411 y con HR (S2) 0,396. Techo local 0,427. Las ANN fallan por extrapolar altitud (IB01). Criterio: [`thresholds_v3.json`](config/thresholds_v3.json) | Ejecutado (PR #11) |
| 5 | [03.1.2 - Sensor local + red SIAR](studies/03_1_2_loso_sensor_red/README.md) | Con sensor propio y estaciones vecinas, cuanto mejora la estimacion en una estacion no vista? | Escenarios de sensor y de red (mismo dia, prevision a D+1, distancia a la costa). Criterio: [`thresholds_v3_1_2.json`](config/thresholds_v3_1_2.json) | En ejecucion |
| 6 | [03.3 - Open-Meteo + ML + red, y objetivo residual](studies/03_3_om_red_residual/README.md) | Anadir la red SIAR del dia a Open-Meteo + ML mejora a ambos? Deja de romperse la ANN si predice la correccion? | Indicio post hoc del 03.2: media HGB-S0 + IDW 0,377. Criterio: [`thresholds_v3_3.json`](config/thresholds_v3_3.json) | Plan, criterios congelados |
| 7 | 03.4 - Fuente con licencia comercial (propuesto) | Se mantienen los resultados del 03.2/03.3 entrenando con ERA5 de Copernicus en lugar de Open-Meteo? | Requisito para un servicio con anuncios o de pago (L14) | Idea, sin plan |
| 8 | [04 - Prevision de ET0 a 1-7 dias](studies/04_prevision_et0/README.md) | Se puede predecir ET0 a 1-7 dias corrigiendo la prevision (Open-Meteo, ECMWF) mejor que la persistencia y que la prevision oficial? | Fase A (exploratoria, previsiones historicas) preparada; fase B con capturas propias desde 2026-11, criterio [`thresholds_v4.json`](config/thresholds_v4.json) en PROPUESTA | Fase A preparada; capturas en marcha |
| 9 | [05 - Balance hidrico por fuente de ET0](studies/05_balance_hidrico/README.md) | Cuanto cambia el riego de una temporada segun la fuente de ET0? | Exploratorio: Open-Meteo crudo riega un 15-26 % de mas; las fuentes corregidas quedan en torno al 10 % y HGB-S0 da el menor error por estacion (6-7 %). Criterio [`thresholds_v5.json`](config/thresholds_v5.json) en PROPUESTA | Plan + exploratorio |

**Lectura rapida de la secuencia:** 01 y 02 muestran que Open-Meteo corregido compite con V2 donde V2 no era realista; 03.1 comprueba que los modelos locales no se generalizan; 03.2 demuestra que un modelo entrenado con el resto de estaciones sobre las variables de Open-Meteo iguala o supera la correccion local, y mejora si se anade un termometro o higrometro; 03.1.2 (en ejecucion), 03.3 y 05 son los siguientes pasos baratos; 04 madura con las capturas, y Andalucia (L4) espera los datos.

**Siguientes propuestas (aun sin estudio):** ver [`docs/IDEAS_Y_MEJORAS.md`](docs/IDEAS_Y_MEJORAS.md). Nota de numeracion: lo que la Parte V del 03.1 llamaba 03.3 (estaciones a 50-100 km) y 03.4 (subdiaria) pasa a las lineas L4 (Andalucia) y L16; 03.3 y 03.4 son ahora los de la hoja de ruta. **Como se actualiza el repo:** [`docs/COMO_ACTUALIZAR.md`](docs/COMO_ACTUALIZAR.md).

## Rumbo actual (2026-11-26)

Los estudios 01 y 02 muestran que las ANN de V2 ganan a Open-Meteo sobre todo en su propia estacion y con radiacion medida, el caso de menos valor practico, y que el error de Open-Meteo viene del viento y del rango diurno de temperatura de la rejilla, no de su radiacion ni de su humedad. Se propone reorientar el producto de "ANN con pocos inputs locales" a **"datos de Open-Meteo corregidos para tu ubicacion con la referencia SIAR"**, con sensor del usuario opcional. El estudio 03.1 comprueba primero si los modelos de pocos inputs SIAR funcionan en estaciones no vistas; el 03.2 evalua Open-Meteo corregido en esas mismas condiciones; el 04 lo extiende a prevision. Justificacion en `studies/03_1_loso_inputs_siar/README.md` y `studies/03_2_loso_openmeteo_ml/README.md`.

## Como se obtienen los datos

Todo se ejecuta en GitHub Actions y se guarda en este repo; no ocupa espacio en el servidor.

1. **Captura diaria de prevision** (`daily_forecast`, 04:17 UTC): guarda la prevision de 16 dias de Open-Meteo de las 9 estaciones. Esa serie no se puede reconstruir despues. El commit diario mantiene vivo el cron.
2. **Captura de ECMWF abierto** (`ecmwf_forecast`, 09:40 y 21:40 UTC, emisiones 00z y 12z): previsión IFS a 0,25° hasta D+10 en los 4 puntos de rejilla mas cercanos a cada estacion (`tools/capture_ecmwf.py`). Licencia CC-BY-4.0: es la fuente valida para un servicio comercial.
3. **Descarga historica** (`backfill`, manual desde la pestana Actions): elige producto y fechas. Es idempotente: lo ya descargado se omite.

Productos de Open-Meteo:

| Producto | Uso | Cobertura (segun su documentacion) |
|---|---|---|
| `archive` | Reanalisis; serie homogenea para el test retrospectivo 2020-2025 | 1940 hasta ~5 dias antes de hoy |
| `historical_forecast` | Salidas de modelos operativos tal como se emitieron | Desde 2022 (varia por modelo): **no cubre 2020-2021** |
| `forecast` | Captura diaria propia de la prevision | Desde que se activa el workflow |

Variables diarias: ET0 FAO, Tmax, Tmin, radiacion solar (suma), viento 10 m maximo. Humedad y viento medio se bajan horarios y se agregan por dia local (`Europe/Madrid`). Viento en m/s a 10 m; **no** se convierte a 2 m en los datos crudos ni procesados.

Ejecucion local (sin dependencias):

```
PYTHONPATH=src python -m openmeteo_et0 backfill --product archive --start 2020-01-01 --end 2025-12-31
PYTHONPATH=src python -m openmeteo_et0 build-processed --product archive
PYTHONPATH=src python -m openmeteo_et0 verify
PYTHONPATH=src python -m unittest discover -s tests
```

## Reglas del repo

- Lo crudo no se edita ni se sobrescribe; lo procesado se reconstruye desde lo crudo.
- Metricas con las mismas definiciones que ET0 V2: error = prediccion - referencia; n, MAE, RMSE, sesgo, R2 = 1 - SSE/SST; DJF asigna diciembre al anio siguiente.
- PM_FAO56_V1 es referencia **calculada** (FAO-56), no ET0 medida. No confundir con `EtPMon` (ET0 calculada por SIAR).
- La comparacion no es de iguales: Open-Meteo usa todos los inputs en rejilla; los modelos V2 usan pocos inputs de sensor.
- Se compara con una referencia calculada de forma retrospectiva; no valida frente a ET0 medida ni demuestra transferencia a estaciones nuevas.

## Licencias y creditos

- **Open-Meteo**: datos CC BY 4.0, uso de la API gratuita solo **no comercial** (menos de 10.000 llamadas/dia). Uso aqui: cientifico y divulgativo. Atribucion: [Open-Meteo.com](https://open-meteo.com/) (Zippenfenig, P., Open-Meteo.com Weather API, doi:10.5281/zenodo.7970649). Antes de cualquier servicio de pago hay que pasar a suscripcion comercial o a un servidor propio.
- **SiAR (MAPA)**: datos meteorologicos de las estaciones; uso permitido citando al SiAR del Ministerio de Agricultura, Pesca y Alimentacion. El uso comercial no se menciona de forma explicita; confirmar con el MAPA antes de cobrar.
- **ECMWF (datos abiertos en tiempo real)**: CC-BY-4.0; citar "Fuente: ECMWF". Permite uso comercial con atribucion.
- **Copernicus ERA5 / ERA5-Land**: CC-BY desde julio de 2025; citar la fuente.
- Los resultados derivados deben indicar las modificaciones respecto a los datos originales (CC BY 4.0).
