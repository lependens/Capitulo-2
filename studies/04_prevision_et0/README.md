# Estudio 04: previsión de ET0 a 0–7 días (enfoque)

Estado: **ENFOQUE**, sin protocolo congelado ni código. Depende de lo que salga del estudio 03.2 (`studies/03_2_loso_openmeteo_ml/`).

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
| Captura propia `daily_forecast` | previsión de 16 días tal como se emitió, fuera de muestra | 2026-11-26 |
| Captura de previsión SIAR / AEMET (Capitulo-1) | previsión oficial para comparar | según la captura activa |

La captura propia es la única evaluación realmente fuera de muestra, pero necesita meses: al menos un año para cubrir todas las estaciones del año. Mientras tanto, los productos históricos de Open-Meteo permiten construir y probar la cadena.

## Preguntas abiertas

1. Qué producto histórico de Open-Meteo da el horizonte de forma fiable y con qué variables.
2. Si la previsión de SIAR guarda su ET0 prevista o solo variables meteorológicas.
3. Si conviene un modelo por horizonte o uno con L como entrada.
4. Cómo comunicar la incertidumbre (intervalos por cuantiles) en el servicio.

## Licencias

Open-Meteo: datos CC BY 4.0, API gratuita solo no comercial. SiAR (MAPA): citar la fuente; uso comercial por confirmar con el MAPA.
