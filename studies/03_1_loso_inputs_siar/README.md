# Estudio 03.1: ¿los modelos de pocos inputs SIAR funcionan en una estación no vista?

Estado: **PLAN**. Criterios en `config/thresholds_v3_1.json`; se congelan al fusionar el PR que los introduce, antes de ejecutar. Se ejecuta **antes** que el estudio 03.2 (`studies/03_loso_openmeteo_ml/`).

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
