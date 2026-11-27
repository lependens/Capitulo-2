# Estudio 05: ¿cambia el riego según de dónde saques la ET0? (balance hídrico)

Estado: **PLAN** con prueba exploratoria. Criterios en `config/thresholds_v5.json` (PROPUESTA: falta la tabla de cultivos de FAO-56, que completa el chat de ejecución y apruebo antes de calcular). Prompt de ejecución en `PROMPT_CHAT.md`. No necesita entrenar modelos: usa las predicciones guardadas del 03.2 (y, cuando existan, del 03.3 y del 04). Cálculo de minutos en local; **no necesita Kaggle**.

## Por qué

Los estudios 02–03.2 deciden hipótesis por diferencias de 0,03–0,05 mm/día de RMSE diario. La ET0 media es ~2,9 mm/día, así que eso es un 1–2 %, menos que la incertidumbre de un Kc (10–20 %) o la eficiencia de un riego por goteo. La pregunta que le importa a quien riega no es el RMSE diario, sino **cuánta agua acaba aplicando** y si se equivoca de forma sistemática. En un balance, los errores diarios se compensan en parte y **el sesgo de cada sitio pesa más que el ruido**.

Pregunta: **en una ubicación sin estación SIAR, ¿cuánto se desvía el riego de una temporada según la fuente de ET0 que use el usuario, y compensa el esfuerzo de cada fuente?**

## Fuentes de ET0, por esfuerzo del usuario

| Esfuerzo | Fuente | Qué tiene que hacer |
|---|---|---|
| Nulo | Open-Meteo crudo | Leer la API o una app |
| Bajo | PM de la estación SIAR más cercana | Buscar su estación en SIAR |
| Medio | Open-Meteo + AHC mensual | Bajar Open-Meteo y aplicar 12 coeficientes |
| Medio-alto | IDW de las estaciones SIAR del día | Bajar varias estaciones y calcular pesos |
| Nulo (si se ofrece como servicio) | HGB-S0, HGB-S2 (este proyecto) | Consultar el servicio (S2: además un termohigrómetro) |

## Prueba exploratoria (2026-11-27, no es resultado)

`exploratorio/balance_rapido.py`, salida en `exploratorio/salida_2026-11-27.txt`. F1 del 03.2 (estación no vista), 2020–2025, lluvia SIAR común a todas las fuentes, Kc único y cubeta simple. Desviación del riego total de los 6 años frente a usar la PM SIAR de la propia estación:

| Fuente | Césped: sesgo / error medio por estación / peor | Almendro: sesgo / error medio / peor |
|---|---|---|
| Open-Meteo crudo | +26 % / 26 % / 58 % | +15 % / 16 % / 27 % |
| PM estación más cercana | +3 % / 14 % / 21 % | 0 % / 10 % / 17 % |
| OM + AHC mensual transferido | 0 % / 9 % / 23 % | 0 % / 8 % / 19 % |
| IDW mismo día | +2 % / 11 % / 22 % | +1 % / 9 % / 16 % |
| **HGB-S0 (sin sensor)** | **+2 % / 7 % / 16 %** | **0 % / 6 % / 13 %** |
| HGB-S2 (+T, HR) | +5 % / 9 % / 19 % | +3 % / 6 % / 16 % |
| HGB-L2 (solo sensor) | +8 % / 12 % / 24 % | +7 % / 11 % / 26 % |

Lectura provisional:
- **Open-Meteo crudo es el único error grande**: sobreestima el riego un 15–26 %, hasta un 58 % en la peor estación.
- Entre las fuentes corregidas, **HGB-S0 da el riego más cercano en cada estación** (6–7 % de error medio), aunque en RMSE diario empataba con la IDW. Es decir, su ventaja es de **sesgo local**, que es lo que se acumula.
- El sesgo positivo de S2 (+0,09 mm/día, Parte IV del 03.2) se nota en el balance (+3–5 %).
- Todas las fuentes corregidas quedan dentro de un ±10 % de media, del orden de la incertidumbre del Kc y de la eficiencia del riego.

Salvedades: cubeta y Kc simplificados, sin escorrentía, umbral de riego discreto (un evento más o menos mueve el total), 9 estaciones, reanálisis y no previsión, referencia calculada.

## Diseño (detalle en `config/thresholds_v5.json`)

- **Cultivos de Baleares:** césped (jardín y golf), almendro, olivo, viña, cítricos y una hortícola de verano. Kc por fases FAO-56 y TAW por tipo de suelo.
- **Lluvia:** la de la propia estación, igual para todas las fuentes (aísla el efecto de la ET0). Variante: lluvia de Open-Meteo, que es lo que tendría el usuario.
- **Métricas:** riego neto anual por estación-año (54 unidades por cultivo y suelo), error relativo frente a la PM de la propia estación, número de riegos y percolación. Bootstrap pareado de las 54 unidades y umbral práctico de 5 puntos.
- **Hipótesis:** B5.1, Open-Meteo crudo riega más de un 10 % de más; B5.2, HGB-S0 es la fuente más fiel por finca; B5.3, entre las fuentes corregidas la diferencia es menor de 5 puntos.
- **Vara de medir:** comparar cada desviación con la incertidumbre del Kc (±10–20 %) y de la eficiencia del riego. Lo que caiga dentro no tiene importancia práctica.
- **Particiones:** F1 y F2 del 03.2; más adelante, previsión (estudio 04) y Andalucía.
- **Fuentes:** las de la tabla de arriba, incluido el combinado HGB-S0 + IDW si se estudia (ver `docs/IDEAS_Y_MEJORAS.md`).
