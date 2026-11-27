# Estudio 04: previsión de ET0 a 0–7 días (enfoque)

Estado: **FASE A preparada** (exploratoria, prompt en `PROMPT_CHAT.md`). La fase B (confirmatoria) tiene criterios en `config/thresholds_v4.json` en estado PROPUESTA: se congelan al cerrar la fase A y **antes** de evaluar con las capturas propias.

## Dos fases

| Fase | Datos | Qué hace | Veredicto |
|---|---|---|---|
| **A, exploratoria** (ya) | Previsiones históricas de Open-Meteo (*previous runs* y `historical_forecast`, 2022/2024–2025) contra la PM de 2020–2025 | Construye la cadena: descarga por horizonte, agregación diaria, ET0 PM de la previsión de ECMWF, comparadores y HGB por horizonte. Afina el diseño | No. Todo es exploratorio y se declara así |
| **B, confirmatoria** (cuando haya ≥ 12 meses de capturas) | Capturas propias tal como se emitieron: Open-Meteo `daily_forecast` (desde 2026-11-26) y ECMWF abierto (desde 2026-11-27), más las previsiones de SIAR y AEMET de Capitulo-1 | Evaluación fuera de muestra en el año capturado, con criterios congelados antes | Sí, con `thresholds_v4.json` |

Por qué así: la fase A puede mirar todo lo que quiera porque no decide nada. La fase B usa datos que **aún no existen**, así que sus criterios se congelan antes de que existan: es el prerregistro más limpio de todo el proyecto.

**Ojo:** para la fase B hará falta la PM de SIAR de 2026–2027. Hoy `data/reference/` llega a 2025; habrá que ampliarla desde Capitulo-1 (SIAR Sync).

## Qué se quiere saber

¿Se puede dar la ET0 de los próximos días en una ubicación de Baleares con un error conocido por horizonte, mejor que las alternativas gratuitas? Es la parte con más valor de uso (programar el riego de la semana) y la menos cubierta por lo que ya existe.

## Diferencia clave con el estudio 03.2

El estudio 03.2 usa **reanálisis** (`archive`): datos del pasado, consistentes, que llegan con unos 5 días de retraso. Una previsión tiene otro error, que crece con el horizonte. Un modelo entrenado con reanálisis y aplicado a previsión hereda una corrección pensada para otro tipo de dato. Por eso:

- El modelo de previsión se entrena con **previsiones tal como se emitieron**, no con reanálisis.
- Aplicar el modelo del estudio 03.2 a la previsión es solo un comparador más, no el método.

## Diseño previsto (a concretar en el protocolo)

- **Objetivo:** PM_FAO56_V1 de SIAR del día D+L, con L = 0…7 días.
- **Entradas:** previsión de Open-Meteo emitida el día D para D+L (ET0, temperaturas, radiación, humedad, viento), día del año, altitud; opcionalmente las últimas observaciones de SIAR disponibles en D (corrección con el error reciente).
- **Evaluación:** RMSE, MAE y sesgo por horizonte L; leave-one-station-out como en el estudio 03.2.
- **Comparadores:**
  - Open-Meteo crudo (su ET0 prevista).
  - Open-Meteo prevista + AHC mensual.
  - Modelo del estudio 03.2 aplicado a la previsión (transferencia reanálisis → previsión).
  - Persistencia: la PM de hoy como valor de D+L.
  - Climatología: PM media de ese día del año en la estación.
  - La previsión de ET0 que publica SIAR, si se dispone de sus emisiones (captura de Capitulo-1).
- **Habilidad:** mejora respecto a persistencia y a climatología por horizonte. Un modelo que no gana a la persistencia en D+1 no aporta.

## Datos y calendario

| Fuente | Qué aporta | Desde |
|---|---|---|
| `historical_forecast` de Open-Meteo | salidas de modelos operativos | 2022 (varía por modelo); no siempre separa el horizonte |
| Previsiones anteriores de Open-Meteo (*previous runs*) | previsiones por horizonte | 2024 (comprobar variables disponibles) |
| Captura propia `daily_forecast` (Open-Meteo) | previsión de 16 días tal como se emitió, fuera de muestra; solo investigación (API no comercial) | 2026-11-26 |
| Captura propia `ecmwf-forecast` (ECMWF datos abiertos, CC-BY-4.0) | IFS 0,25°, 00z y 12z, 4 puntos de rejilla por estación, T, Td, viento, radiación y lluvia hasta D+10; **fuente con licencia para el servicio** | desde el primer disparo del workflow |
| Captura propia `oficial-forecast` (SIAR y AEMET) | previsión oficial para comparar: ET0 prevista de SIAR (la suministra AEMET) y previsión municipal de AEMET (Tmáx, Tmín, HR, viento, lluvia; sin ET0 ni radiación), 9 estaciones, 3 capturas al día. Ver [CAPTURAS.md](CAPTURAS.md) | AEMET 2026-11-27; SIAR sin previsión publicada desde el 24-11-2026 |

La captura propia es la única evaluación realmente fuera de muestra, pero necesita meses: al menos un año para cubrir todas las estaciones del año. Mientras tanto, los productos históricos de Open-Meteo permiten construir y probar la cadena.

## Preguntas abiertas (las responde la fase A)

1. Qué producto histórico de Open-Meteo da el horizonte de forma fiable y con qué variables.
2. ~~Si la previsión de SIAR guarda su ET0 prevista o solo variables meteorológicas.~~ Resuelta el 27-11-2026: guarda la ET0 prevista (y Kc, ETc, Pe), y SIAR indica que la previsión la suministra AEMET. Ver [CAPTURAS.md](CAPTURAS.md).
3. Si conviene un modelo por horizonte o uno con L como entrada.
4. Cómo comunicar la incertidumbre (intervalos por cuantiles) en el servicio.

## Captura ECMWF

Workflow `.github/workflows/ecmwf_forecast.yml` (cron 09:40 y 21:40 UTC) y `tools/capture_ecmwf.py`. Guarda en `data/raw/ecmwf_ifs/<estación>/` los 4 vecinos de rejilla de cada variable y paso (cada 3 h hasta 144 h, cada 6 h hasta 240 h), con el mismo manifiesto. Los campos globales no se guardan.

Pendiente tras el primer disparo manual (`workflow_dispatch`): comprobar que descarga y que los pasos y variables son los esperados. Tmax y Tmin del día se derivarán de los pasos de 3 h (aproximación: el máximo real puede caer entre pasos); si hace falta, añadir `mx2t3`/`mn2t3` si están en la emisión abierta. El conjunto de miembros (ENS) para intervalos se añade más adelante.

## Plan de previsión (resumen)

1. Entrenar con previsiones **tal como se emitieron**; objetivo PM SIAR de D+L.
2. Rivales: persistencia, climatología, ET0 prevista cruda, previsión de SIAR y de AEMET (capturas del Capitulo-1), modelo del 03.2 aplicado a la previsión.
3. Referencia de la literatura (EE. UU., Medina y Tian, HESS 2020): error relativo semanal 8–11 %, diario 13–20 %, persistencia semanal ~22 %. Mejor comunicar sumas semanales en verano.
4. Después: intervalos con el conjunto de ECMWF.

## Licencias

Open-Meteo: datos CC BY 4.0, API gratuita solo no comercial. ECMWF datos abiertos: CC-BY-4.0 (citar a ECMWF). SiAR (MAPA): citar la fuente; uso comercial por confirmar con el MAPA.
