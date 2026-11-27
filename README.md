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
| `studies/04_prevision_et0/` | Estudio 04 (enfoque): previsión de ET0 a 0–7 días |
| `studies/01_et0_vs_pm/` | Estudio 01: ET0 de Open-Meteo frente a PM_FAO56_V1 y frente a las formulas V2 |
| `tools/export_reference.py` | Extrae de `classical-baselines.csv` (Capitulo-1, 56 MB) solo 2020-2025 y las columnas necesarias |
| `.github/workflows/` | `daily_forecast` (captura diaria), `backfill` (descarga historica manual), `tests` |

## Rumbo actual (2026-11-26)

Los estudios 01 y 02 muestran que las ANN de V2 ganan a Open-Meteo sobre todo en su propia estacion y con radiacion medida, el caso de menos valor practico, y que el error de Open-Meteo viene del viento y del rango diurno de temperatura de la rejilla, no de su radiacion ni de su humedad. Se propone reorientar el producto de "ANN con pocos inputs locales" a **"datos de Open-Meteo corregidos para tu ubicacion con la referencia SIAR"**, con sensor del usuario opcional. El estudio 03.1 comprueba primero si los modelos de pocos inputs SIAR funcionan en estaciones no vistas; el 03.2 evalua Open-Meteo corregido en esas mismas condiciones; el 04 lo extiende a prevision. Justificacion en `studies/03_1_loso_inputs_siar/README.md` y `studies/03_2_loso_openmeteo_ml/README.md`.

## Como se obtienen los datos

Todo se ejecuta en GitHub Actions y se guarda en este repo; no ocupa espacio en el servidor.

1. **Captura diaria de prevision** (`daily_forecast`, 04:17 UTC): guarda la prevision de 16 dias de las 9 estaciones. Esa serie no se puede reconstruir despues. El commit diario mantiene vivo el cron.
2. **Descarga historica** (`backfill`, manual desde la pestana Actions): elige producto y fechas. Es idempotente: lo ya descargado se omite.

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
- Los resultados derivados deben indicar las modificaciones respecto a los datos originales (CC BY 4.0).
