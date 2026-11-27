# Estudio 03.1.2: sensor local + red SIAR en una estación no vista

Estado: **PLAN**, pendiente de aprobar los criterios (`config/thresholds_v3_1_2.json`, en estado PROPUESTA). No se ha ejecutado nada. La ejecución se hará en un chat aparte con el prompt de `PROMPT_CHAT.md`.

## Índice

| Parte | Contenido |
|---|---|
| [I — Pregunta y motivación](#parte-i--pregunta-y-motivación) | De dónde sale el estudio y qué decide |
| [II — Escenarios](#parte-ii--escenarios-a-b-c-y-b-ayer) | B (mismo día), C (previsión a D+1), B-ayer y A (distancia a la costa), con la valoración de cada uno |
| [III — Diseño](#parte-iii--diseño) | Inputs de red, conjuntos, modelos (y por qué una sola ANN), comparadores, hipótesis, regla de interpretación |
| [IV — Ejecución](#parte-iv--ejecución) | Qué se reutiliza del 03.1, código a escribir, volumen, sesiones de Kaggle, salidas |
| [V — Riesgos y salvedades](#parte-v--riesgos-y-salvedades) | |
| [VI — Bibliografía de costa y continentalidad](#parte-vi--bibliografía-de-costa-y-continentalidad) | Base de la variante A |

# Parte I — Pregunta y motivación

El 03.1 mostró que un modelo de pocos inputs entrenado en otras estaciones pierde frente a la IDW de la red del mismo día (Valiantzas +0,084 mm/día; HS-Ra +0,198; HG-Rs empata), pero que, al alejarse de la red, la IDW se degrada y el modelo de sensor casi no se mueve (Parte III, punto 2 del README del 03.1). Las dos fuentes tienen información distinta: el sensor ve el sitio, la red ve el tiempo de ese día alrededor.

**Pregunta.** En una ubicación sin estación, ¿cuánto reduce el error combinar un sensor barato con la información de la red SIAR, frente a usar solo la red o solo el sensor? Y, como segunda pregunta, ¿sirve esa combinación para dar la ET0 de mañana?

Para el servicio, decide entre tres productos: «compra un termohigrómetro», «no compres nada, usa la red» o «las dos cosas».

# Parte II — Escenarios (A, B, C y B-ayer)

Cuándo está disponible cada dato marca qué escenario tiene sentido. El SIAR publica los datos del día en curso, pero sin haber pasado todos los procesos de validación (manual de la Web API SiAR). Los datos diarios del sensor del usuario (Tmax, Tmin, humedad media) tampoco existen hasta que acaba el día. Por eso ninguno de los escenarios da la ET0 «de hoy» a media mañana.

### B — mismo día (principal)

Sensor del día d + red del día d → PM del día d. Da la ET0 de un día **al terminar ese día o a la mañana siguiente**. Es la pregunta central y la que se recomendó en el 03.1. **Adelante.**

### C — previsión a D+1 (principal, nuevo)

Sensor del día d + red del día d (+ Ra del día d+1, que es astronómica) → PM del día **d+1**. Es una previsión de verdad a un día, **sin modelo meteorológico**.

Precisión sobre la idea original: usar «la red de ayer» con el sensor de hoy no es una previsión. Sigue estimando el día de hoy, y solo se diferencia de B en que no espera a la red del día. Una previsión necesita que el objetivo sea un día cuyos inputs todavía no existen. Por eso C se define con objetivo d+1, y la variante «red de ayer» queda como B-ayer (abajo).

Lo que hay que superar en C es la **persistencia**: la ET0 cambia poco de un día al siguiente, así que «mañana será como hoy» es un rival difícil. Los comparadores son persistencias (IDW del día d, PM vecina del día d, la estimación B del día d) y la climatología mensual. C sirve además como línea base para el estudio 04: si una previsión a un día sin modelo meteorológico no gana a la persistencia, el 04 tiene que partir de previsiones meteorológicas.

### B-ayer — red desfasada un día (secundario, sin veredicto)

Sensor del día d + red del día d−1 → PM del día d. Mide cuánto se pierde si la red del día no está disponible o no se quiere usar sin validar. Como el SIAR publica el día en curso, su valor práctico es limitado: solo Ridge y HGB, sin ANN.

### A — distancia a la costa (secundario, sin veredicto)

**Valoración crítica.** La opción A original (las distancias a las otras estaciones como inputs) no vale la pena: el vector de distancias identifica la ubicación y el 03.1 ya mostró con la altitud que eso rompe las ANN. La distancia al mar es otra cosa y tiene base física y bibliográfica (Parte VI): la costa reduce la amplitud térmica y cambia humedad y viento, y el coeficiente de radiación de Hargreaves se recomienda distinto en interior (0,16) y en costa (0,19).

Aun así, en este conjunto **tiene poco recorrido**, por tres motivos:

1. **Sigue siendo un dato estático por estación.** Con 8 estaciones de entrenamiento, el modelo ve 8 valores distintos. Puede usarlo como etiqueta de estación igual que la altitud.
2. **El rango es pequeño.** En unas islas, todas las estaciones están cerca del mar. El efecto que buscan los estudios de continentalidad aparece en decenas o cientos de kilómetros.
3. **Parte del efecto ya entra por los inputs diarios.** La amplitud Tmax − Tmin, que el modelo ya ve cada día, es la vía por la que la bibliografía mide la continentalidad (Parte VI).

Por eso se incluye solo como variante barata y acotada:
- **Input:** `log1p(distancia a la costa en km)`, un único número, calculado con una línea de costa oficial (Natural Earth 1:10m o GSHHG), nunca a ojo.
- **Modelos:** solo Ridge y HGB, sin ANN, por el precedente de la altitud.
- **Diagnóstico gratuito previo, sin entrenar nada:** relacionar el sesgo por estación del 03.1 (modelos de sensor y Open-Meteo + AHC) con la distancia a la costa. Hay un indicio que motiva mirarlo: los dos sesgos de verano más grandes de Open-Meteo + AHC, IB11 (−0,9 mm/día) e IB08 (+0,8), son de signo opuesto. Con 9 puntos es solo indicativo.

**El sitio donde la continentalidad sí tiene recorrido es una red grande (Andalucía o SIAR peninsular, estudio 03.3).** Si el diagnóstico sale plano, se cierra la variante sin más coste.

# Parte III — Diseño

**Protocolo: idéntico al 03.1.** Mismas particiones (`studies/03_1_loso_inputs_siar/results/folds.json`), DESARROLLO 2004–2019 / TEST 2020–2025, cohorte común (n = 19.251 en B), mismas métricas, bootstrap de bloques estación-año (2.000 réplicas, semilla 20261126), umbral práctico de 0,05 y TOST con ese margen.

### Inputs de red

- **Pool:** estaciones de entrenamiento de la partición con PM válida ese día.
- **Exclusión de la propia estación:** para una fila de la estación t, t queda siempre fuera del pool. En la validación interna, la estación de validación sale del pool de **todas** las filas.
- **R1:** la IDW de la PM (potencia 2, el mismo cálculo que el comparador del 03.1) y d₁, la distancia a la estación más cercana del pool.
- **R3:** la PM de las 3 estaciones más cercanas del pool, **ordenadas por distancia**, y sus distancias d₁ ≤ d₂ ≤ d₃. Nunca indexadas por el nombre de la estación.

### Conjuntos de inputs

| Escenario | Conjuntos | Modelos |
|---|---|---|
| B | `S` (reutilizado del 03.1), `S+R1`, `S+R3` por familia; `R` sin familia | Ridge, HGB, ANN M |
| C | `S`, `S+R1`, `S+R3` por familia; `R` sin familia | Ridge, HGB, ANN M |
| B-ayer | `S+R1` por familia; `R` sin familia | Ridge, HGB |
| A | `S+costa` por familia | Ridge, HGB |

### Modelos: ¿una o dos ANN, (64) y (64, 32)?

**Recomendación: una sola ANN, la ANN M (64, 32), con su rejilla del 03.1.** La evidencia de lo ya hecho:

- **En el 03.1 la arquitectura no cambió el resultado.** ANN S (una capa de 32) y ANN M (64, 32) dieron 0,627 y 0,626 en HS-Ra, 0,521 y 0,517 en Valiantzas, y 0,416 y 0,416 en HG-Rs. La diferencia es ≤ 0,004 mm/día, por debajo del ruido entre semillas. No hay nada que ganar entrenando dos.
- **Lo de Capitulo-1 es cierto, pero para modelos locales.** En V2 (una red por estación), la capa única de 64 fue la más elegida: 56 de 105 celdas en ANN A y 55 en ANN E (memoria científica V2, sección 9.2). La propia memoria advierte que esas frecuencias no aíslan el efecto del tamaño. Con datos de 8 estaciones juntas la elección cambia: la ANN tipo V2 del 03.1, que elegía entre las cinco arquitecturas, escogió (64, 32, 16) en 17 de 36 celdas y (64) en 11. Con más datos y más inputs (aquí hasta 10), la red algo más profunda no está en desventaja.
- **Elegir (64, 32) permite reutilizar el conjunto `S` del 03.1** (36 celdas por modelo), que es la comparación G2. Elegir (64) obligaría a recalcularlo.

RF, ANN S y ANN tipo V2 quedan fuera: no cambiaron ningún veredicto del 03.1 y son las más caras (730 s, 687 s y 6.327 s de mediana por celda).

### Comparadores

- **B:** IDW del mismo día, PM de la estación más cercana del mismo día, Open-Meteo + AHC mensual transferido, y `S` del 03.1 (mismo modelo y familia).
- **C:**
  - persistencia IDW: la IDW del día d como valor de d+1;
  - persistencia vecina: la PM de la estación más cercana del día d;
  - persistencia del modelo: la predicción B|S+R1 del día d;
  - climatología: media mensual de la PM de las estaciones de entrenamiento en DESARROLLO;
  - Open-Meteo + AHC del día d+1, solo informativo: es reanálisis, no previsión.

### Hipótesis (HGB, F1, por familia)

- **G1 — el sensor aporta sobre la red:** `S+R1` frente a la IDW, ΔRMSE con IC 95 % por debajo de 0. Se repite con `S+R3`.
- **G2 — la red aporta sobre el sensor:** `S+R1` frente a `S`.
- **G3 — el ML mejora a la IDW con la misma información:** `R` frente a la IDW.
- **P1 — la previsión gana a la persistencia:** C|`S+R1` frente a la persistencia IDW, IC por debajo de 0.
- **P2 — el sensor aporta en la previsión:** C|`S+R1` frente a C|`R`.
- **Sin veredicto:** el coste de pasar de d a d+1 (C frente a B), F2, el resultado por estación, B-ayer y A.

### Regla de interpretación, fijada antes de ejecutar

Para Valiantzas en B:
- G1 se cumple con |Δ| ≥ 0,05 → **sensor + red**.
- G1 no se cumple pero hay equivalencia (TOST) → cerca de la red **basta la red**, y el sensor solo se justifica lejos de ella (F2, estudio 03.3).
- `S+R1` pierde frente a la IDW → el sensor no aporta en esta red.

HS-Ra y HG-Rs se informan con la misma regla; HG-Rs aparte, porque requiere piranómetro.

En C, si P1 no se cumple, la previsión a un día sin modelo meteorológico no aporta.

# Parte IV — Ejecución

**Qué se reutiliza del 03.1, sin copiar código.**
- Se importan `loso_common` (datos, fórmulas, Ra, particiones, distancias, IDW, AHC, bootstrap) y `loso_models` (rejillas, selección, ANN M) desde `studies/03_1_loso_inputs_siar/`.
- Se reutilizan las celdas `S` del 03.1 (`results/cells/*__principal__{Ridge,HGB,ANN_M}.json.gz`) y sus comparadores (`predictions_test.csv.gz`).
- Se reutiliza el esquema de celdas reanudables, el reparto por sesiones de Kaggle (`kaggle_session.sh`) y el informe con IC pareados.

**Código nuevo, pequeño:**
1. `network.py` construye las columnas R1/R3 por partición y escenario (d, d−1), con la exclusión de la propia estación. Lleva tests propios: orden por distancia, que ninguna fila use su propia estación y los casos con el pool incompleto.
2. `run.py` define las celdas como partición × escenario × conjunto × familia × modelo y reutiliza `select_and_fit`. La validación interna recalcula el pool sin la estación de validación.
3. `coast.py` calcula la distancia a la costa y la guarda en `config/stations_coast.csv`. Necesita la línea de costa; si el entorno no tiene red, se ejecuta en Kaggle.
4. `report.py` calcula métricas, IC pareados, TOST, figuras y manifiesto.

**Volumen.**
- Ridge y HGB: 24 conjuntos × 12 particiones × 2 modelos = 576 celdas, unos 30 s cada una en HGB y despreciables en Ridge.
- ANN M: (7 de B, sin contar `S`, + 10 de C) × 12 = 204 celdas, unos 1.000 s cada una, que suben algo con más inputs. Son unas 57–65 h de núcleo, **unas 15–17 h con 4 procesos**.
- Plan de Kaggle (tope práctico de 8 h por sesión): sesión 1 con Ridge y HGB de todo más ANN M de B; sesiones 2 y 3 con ANN M de C, repartida por particiones. **Unas 3 sesiones**, frente a las 7 del 03.1.

**Orden de trabajo.**
1. PR que congela `config/thresholds_v3_1_2.json` (pasar `status` a CONGELADO), aprobado por el usuario antes de ejecutar.
2. Código y tests, que deben seguir pasando junto con los 31 actuales.
3. Diagnóstico de costa, sin entrenar nada.
4. Ridge y HGB en local o en Kaggle.
5. ANN M en Kaggle.
6. Informe y README completado (resultados, hipótesis, regla de interpretación, por estación, F2).

**Salidas.** Como en el 03.1:
- `results/` con las celdas, `metrics_global/by_station/by_month.csv`, `paired_ci.csv`, `equivalencia.csv`, `predictions_test.csv.gz`, `run_manifest.json` e `interpretation.json`;
- `figures/` con G1–G3, P1–P2 y el error frente a la distancia a la red.

# Parte V — Riesgos y salvedades

- **Fuga por construcción:** las PM vecinas son de la misma referencia que el objetivo. No es fuga de la estación evaluada, pero el resultado mide «red + sensor», no «sensor».
- **Cambio de distribución de las distancias:** en F2 la estación evaluada está a 93–130 km de la red, y las filas de entrenamiento suelen estar más cerca de sus vecinas. El modelo extrapola en d₁. Se informa la distribución de d₁ en entrenamiento y en TEST.
- **Red validada frente a red del día:** el estudio usa datos ya validados, y el servicio tendría la red del día sin validar. Los resultados de B son un límite superior.
- **Cohorte de C:** exige el día d y el d+1; se informa n y todos los comparadores se evalúan sobre las mismas filas.
- **Diseño escrito después del 03.1:** declarado. F1 sigue siendo optimista, y F2 es el escenario que más interesa aunque sus IC sean anchos.
- Sigue valiendo lo de siempre: la referencia es calculada, no ET0 medida, y los sensores son SIAR, no de usuario.

# Parte VI — Bibliografía de costa y continentalidad

Localizada en una búsqueda web rápida. No es una revisión sistemática; conviene verificarla antes de citarla en un texto formal.

- **Coeficiente de radiación de Hargreaves-Samani:** en Rs = k·√(Tmax−Tmin)·Ra se recomienda k = 0,16 en interior y 0,19 en costa (Hargreaves y Samani; también en FAO-56). La costa entra a través del rango térmico diario.
- **Matsui (2005), Japón:** el parámetro de ajuste de Hargreaves se estima por regresión con la raíz del rango térmico medio anual, **la proximidad a la costa** y otras variables anuales. Es el precedente más directo de usar la distancia al mar como predictor.
- **Vanderlinden, Giráldez y Van Meirvenne (2004), *J. Irrig. Drain. Eng.* 130(3):184–191, Andalucía:** el sesgo de Hargreaves es considerable, sobre todo en los meses secos y cálidos de verano, lo que motiva una calibración regional.
- **Regionalización del coeficiente de Hargreaves en el SE de España** (*Spanish J. Agric. Res.*, 66 estaciones): su variabilidad espacial se correlaciona bien con las medias anual y mensuales del rango térmico diario, que se usan como variables explicativas.
- **Gomariz-Castillo et al. (2018), *Earth Sci. Inform.* 11:325–340:** calibración y modelado espacial de Hargreaves con 79 estaciones del sureste semiárido español.
- **Andrade y Ventura (2024), *Finisterra*, Portugal:** el coeficiente de radiación depende más de la amplitud térmica que de la altitud.
- **Paredes, Pereira y otros (Mediterráneo, CLIMWAT):** regresiones del coeficiente de radiación a partir de los promedios locales de rango térmico, humedad y viento.

**Lectura para este estudio.** En la bibliografía, la continentalidad entra sobre todo a través del **rango térmico** (que el modelo ya ve cada día) y, en algún caso, de la distancia al mar como corrección regional de **una fórmula**. Ninguno de estos trabajos la usa como input de un modelo ML entrenado con pocas estaciones. De ahí la variante A acotada y el diagnóstico previo.
