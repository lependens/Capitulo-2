# Estudio 03.1.2: sensor local + red SIAR en una estación no vista

Estado: **EJECUTADO** (27-11-2026). Criterios congelados en `config/thresholds_v3_1_2.json` (PR #16) antes de entrenar; 780 de 780 celdas. Resultados en la [Parte VII](#parte-vii--resultados-planificados), análisis post hoc en la [Parte VIII](#parte-viii--análisis-post-hoc-sin-veredicto) y decisiones y desviaciones en la [Parte IX](#parte-ix--decisiones-previas-a-la-congelación-y-desviaciones). Las Partes I–VI son el plan tal como se aprobó.

## Índice

| Parte | Contenido |
|---|---|
| [I — Pregunta y motivación](#parte-i--pregunta-y-motivación) | De dónde sale el estudio y qué decide |
| [II — Escenarios](#parte-ii--escenarios-a-b-c-y-b-ayer) | B (mismo día), C (previsión a D+1), B-ayer y A (distancia a la costa), con la valoración de cada uno |
| [III — Diseño](#parte-iii--diseño) | Inputs de red, conjuntos, modelos (y por qué una sola ANN), comparadores, hipótesis, regla de interpretación |
| [IV — Ejecución](#parte-iv--ejecución) | Qué se reutiliza del 03.1, código a escribir, volumen, sesiones de Kaggle, salidas |
| [V — Riesgos y salvedades](#parte-v--riesgos-y-salvedades) | |
| [VI — Bibliografía de costa y continentalidad](#parte-vi--bibliografía-de-costa-y-continentalidad) | Base de la variante A |
| [VII — Resultados planificados](#parte-vii--resultados-planificados) | Regla de interpretación, G1–G3, P1–P2, F2, B-ayer, A y diagnóstico de costa |
| [VIII — Análisis post hoc](#parte-viii--análisis-post-hoc-sin-veredicto) | Por estación, distancia a la red, Ridge frente a HGB, semillas de la ANN |
| [IX — Decisiones previas y desviaciones](#parte-ix--decisiones-previas-a-la-congelación-y-desviaciones) | Qué se decidió antes de congelar y qué se apartó del plan |

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

# Parte VII — Resultados planificados

Todo lo de esta parte estaba fijado antes de entrenar (criterios congelados en el PR #16). Métrica: RMSE en mm/día sobre TEST 2020–2025, cohorte común. Δ = RMSE(A) − RMSE(B): negativo significa que A gana. IC del bootstrap de bloques estación-año (2.000 réplicas, semilla 20261126). Equivalencia: TOST con margen ±0,05 (IC 90 % dentro del margen). Tablas completas en `results/paired_ci.csv`, `results/equivalencia.csv` y `results/metrics_*.csv`; figuras 01–05 en `figures/`.

**Comprobaciones previas al análisis.**
- 780 de 780 celdas, ninguna de prueba, todas con scikit-learn 1.9.1 (`results/run_manifest.json`).
- Las predicciones `S` coinciden con las 108 celdas del 03.1 (tolerancia de media unidad del redondeo a 5 decimales; ver Parte IX).
- Cohortes: n = 19.251 en B, B-ayer y A; n = 19.216 en C (F1). Cada comparación usa las mismas filas para A y B; ninguna fila de TEST se quedó sin pool.
- Los valores de `S` frente a la IDW reproducen los del 03.1 (Valiantzas +0,084; HS-Ra +0,198; HG-Rs empata).

## VII.1 Regla de interpretación (B, F1, HGB)

| Familia | Conjunto | RMSE | IDW | Δ | IC 95 % | IC 90 % | Caso | Lectura |
|---|---|---|---|---|---|---|---|---|
| **Valiantzas (rige)** | **S+R1** | 0,435 | 0,434 | **+0,001** | [−0,021; +0,022] | [−0,018; +0,019] | **3** | **equivalentes: basta la red** |
| Valiantzas | S+R3 | 0,385 | 0,434 | −0,049 | [−0,065; −0,035] | [−0,062; −0,036] | 2 | mejora estadística sin interés práctico |
| HS-Ra | S+R1 | 0,455 | 0,434 | +0,020 | [−0,000; +0,041] | [+0,003; +0,037] | 3 | equivalentes: basta la red |
| HS-Ra | S+R3 | 0,413 | 0,434 | −0,021 | [−0,034; −0,008] | [−0,032; −0,011] | 2 | mejora estadística sin interés práctico |
| HG-Rs (aparte, piranómetro) | S+R1 | 0,362 | 0,434 | −0,072 | [−0,093; −0,052] | [−0,089; −0,055] | 1 | sensor + red |
| HG-Rs (aparte, piranómetro) | S+R3 | 0,343 | 0,434 | −0,092 | [−0,111; −0,073] | [−0,108; −0,076] | 1 | sensor + red |

**Veredicto (literal de la regla).** Para el sensor barato (Valiantzas), en B y cerca de la red, **basta la red**: S+R1 y la IDW del mismo día son equivalentes. El sensor solo se justifica lejos de la red (F2, estudio 03.3). Con piranómetro (HG-Rs), **sensor + red** gana con interés práctico (−0,072 con S+R1).

Dos matices que no cambian el veredicto:
- Valiantzas S+R3 queda en el límite del caso 1 (Δ = −0,0495 frente al umbral de −0,05). Es informativo según la regla; no rige.
- En HS-Ra S+R1 el extremo inferior del IC 95 % es −0,0003: el caso 3 se cumple por muy poco, y el modelo está más cerca de perder que de ganar.

## VII.2 Hipótesis de B (HGB, F1)

| Hipótesis | Comparación | HS-Ra | Valiantzas | HG-Rs |
|---|---|---|---|---|
| G1 | S+R1 − IDW | +0,020 [−0,000; +0,041] | +0,001 [−0,021; +0,022] | **−0,072** [−0,093; −0,052] |
| G1 (R3) | S+R3 − IDW | **−0,021** [−0,034; −0,008] | **−0,049** [−0,065; −0,035] | **−0,092** [−0,111; −0,073] |
| G2 | S+R1 − S | **−0,178** [−0,206; −0,152] | **−0,083** [−0,108; −0,060] | **−0,058** [−0,077; −0,038] |

- **G1 (el sensor aporta sobre la red):** se cumple solo con HG-Rs. Con S+R3 se cumple en las tres familias, pero en HS-Ra y Valiantzas por menos del umbral práctico.
- **G2 (la red aporta sobre el sensor):** se cumple en las tres familias, con ganancias grandes. La red es la mayor fuente de información.
- **G3 (el ML mejora a la IDW con la misma información):** R (HGB) − IDW = −0,006 [−0,023; +0,011], equivalente por TOST. **No se cumple**: un HGB con la red sola no mejora la IDW. Con Ridge (+0,018) y ANN M (+0,052) es peor.

## VII.3 Hipótesis de C, previsión a d+1 (HGB, F1, n = 19.216)

| Hipótesis | Comparación | HS-Ra | Valiantzas | HG-Rs |
|---|---|---|---|---|
| P1 | C S+R1 − persistencia IDW | **−0,037** [−0,050; −0,024] | **−0,044** [−0,058; −0,031] | **−0,057** [−0,069; −0,045] |
| P2 | C S+R1 − C R | +0,014 [+0,000; +0,029] | +0,007 [−0,009; +0,023] | −0,006 [−0,020; +0,009] |

- **P1 (la previsión gana a la persistencia): se cumple en las tres familias.** La regla dice que, si P1 falla, la previsión sin modelo meteorológico no aporta. No falla, pero la ganancia es pequeña: menor que 0,05 salvo con HG-Rs. RMSE de referencia: persistencia IDW 0,725; climatología 0,742; persistencia de la vecina 0,768; el mejor C con HGB es S+R3 Valiantzas, 0,655.
- **P2 (el sensor aporta en la previsión): no se cumple.** S+R1 y R son equivalentes por TOST en las tres familias. En HS-Ra el extremo inferior del IC es +0,00003, así que formalmente S+R1 pierde, por una diferencia sin interés práctico. En la previsión a un día, el sensor no añade nada a la red.
- **Coste de horizonte (informativo):** pasar de d a d+1 con S+R1 cuesta +0,23 a +0,31 mm/día (Valiantzas: 0,681 frente a 0,435).
- **Open-Meteo + AHC del día d+1 (informativo, no es una previsión):** 0,483, mucho mejor que cualquier previsión de C. Indica el margen que podría aportar un modelo meteorológico; es la pregunta del estudio 04.

## VII.4 F2: islas no vistas (sin veredicto)

F2 estaba en el plan como resultado sin veredicto. F2_Menorca entrena con las mismas 8 estaciones que F1_IB08, así que sus resultados son idénticos. En F2 la estación evaluada está a 93–130 km de la red (Parte V).

| Partición (n) | IDW | S Valiantzas | S+R1 Valiantzas | S+R3 Valiantzas | S HG-Rs | S+R1 HG-Rs | R |
|---|---|---|---|---|---|---|---|
| Ibiza: IB01, IB11 (4.380) | 0,612 | **0,532** | 0,608 | 0,637 | **0,435** | 0,540 | 0,749 |
| Menorca: IB08 (2.097) | 0,568 | 0,593 | 0,623 | **0,480** | **0,422** | 0,458 | 0,517 |
| Mallorca, informativo (12.774) | 0,494 | 0,512 | **0,450** | 0,478 | 0,421 | **0,377** | 0,563 |

(RMSE, HGB, escenario B.)

- **Ibiza:** el sensor solo gana a la IDW (Valiantzas −0,080 [−0,124; −0,033]; HG-Rs −0,177), y **añadir la red lo empeora** (S+R1 − S: Valiantzas +0,076 [+0,037; +0,120]; HG-Rs +0,106 [+0,076; +0,133]). R es mucho peor que la IDW (+0,137).
- **Menorca:** con Valiantzas, S+R1 pierde frente a la IDW (+0,054 [+0,024; +0,090]) y S+R3 gana (−0,089 [−0,108; −0,072]). Una sola estación: muy dependiente de ella.
- **Mallorca (informativo):** se entrena solo con Ibiza y Menorca, y d₁ ronda los 90–130 km; aun así S+R1 gana a la IDW (Valiantzas −0,044 [−0,072; −0,013]).
- **C en F2:** S+R1 frente a la persistencia IDW es equivalente o gana por poco (Valiantzas: Ibiza −0,013, Menorca +0,004, Mallorca −0,036).

## VII.5 B-ayer: red desfasada un día (sin veredicto)

| HGB, F1 | HS-Ra | Valiantzas | HG-Rs | R |
|---|---|---|---|---|
| B-ayer − B (mismo conjunto) | +0,162 [+0,140; +0,185] | +0,094 [+0,079; +0,110] | +0,029 [+0,019; +0,039] | +0,244 [+0,225; +0,265] |
| B-ayer S+R1 − IDW del mismo día | +0,182 | +0,095 | −0,043 [−0,068; −0,019] | +0,239 |

La red del día anterior pierde casi todo su valor: con Valiantzas, B-ayer queda en 0,529, prácticamente el sensor solo (0,518). Solo con HG-Rs sigue ganando a la IDW del mismo día. Para el servicio, la red tiene que ser la del mismo día.

## VII.6 A: distancia a la costa (sin veredicto)

| S+costa − S, F1 | HS-Ra | Valiantzas | HG-Rs |
|---|---|---|---|
| HGB | +0,006 [−0,015; +0,028] | +0,011 [−0,009; +0,032] | +0,025 [+0,012; +0,039] |
| Ridge | +0,029 [+0,015; +0,043] | +0,030 [+0,017; +0,046] | +0,010 [+0,001; +0,020] |

La distancia a la costa no mejora nada en F1 y empeora en varios casos, como anticipaba el diagnóstico plano (VII.7). En F2 los signos cambian según la isla (Menorca mejora con Valiantzas −0,074; Ibiza empeora +0,041): es el comportamiento de una etiqueta de estación, no de una señal física. La variante queda cerrada para este conjunto; la continentalidad se reserva para el 03.3.

## VII.7 Diagnóstico de costa (previo, sin entrenar)

- Fuente: Natural Earth 1:10m coastline (`ne_10m_coastline.geojson`, repositorio nvkelso/natural-earth-vector). `config/stations_coast.csv`, SHA256 `6f75ae0e0de157b14946e2255eb1f5486d9a13819032e26d4610852d296788f6`.
- Distancias (km): IB01 8,15 · IB02 20,59 · IB03 12,73 · IB04 2,26 · IB05 16,35 · IB06 7,12 · IB08 4,20 · IB10 1,77 · IB11 0,04.
- Spearman con log1p(costa), n = 9, solo indicativo:

| Modelo o comparador del 03.1 | Sesgo | Sesgo JJA | RMSE |
|---|---|---|---|
| HGB HS-Ra | −0,13 | −0,13 | −0,48 |
| HGB Valiantzas | −0,17 | −0,03 | −0,65 |
| HGB HG-Rs | −0,37 | −0,45 | −0,18 |
| Open-Meteo + AHC | −0,15 | −0,12 | −0,67 |
| IDW | −0,07 | −0,32 | −0,35 |

- La relación del sesgo no es monótona: IB11 (0,04 km) tiene sesgo de verano negativo, y IB10 e IB08 (1,8–4,2 km) positivo. El RMSE baja algo hacia el interior, pero con 9 puntos no basta. **Diagnóstico plano**: A se ejecutó como estaba previsto y se informa sin veredicto.

## VII.8 Qué significa para el servicio

- **Sensor barato (termohigrómetro, Valiantzas) cerca de la red SIAR:** no compensa; la IDW de la red del mismo día da lo mismo.
- **Con piranómetro (HG-Rs):** sensor + red mejora a la red en unos 0,07 mm/día (S+R1) o 0,09 (S+R3).
- **Lejos de la red (F2, sin veredicto):** el sensor solo gana a la red y combinarlos con R1 empeora. Es la pregunta del estudio 03.3.
- **Previsión a un día sin modelo meteorológico:** gana a la persistencia, pero por poco, y el sensor no aporta. El estudio 04 debería partir de previsiones meteorológicas.

# Parte VIII — Análisis post hoc, sin veredicto

Nada de esta parte estaba planificado como contraste. Sirve para entender los resultados y orientar estudios futuros, no para cambiar veredictos.

**1. La equivalencia media esconde heterogeneidad por estación.** RMSE F1, escenario B, HGB Valiantzas (`results/metrics_by_station.csv`):

| Estación | IDW | S | S+R1 | S+R3 |
|---|---|---|---|---|
| IB01 | 0,457 | 0,439 | **0,379** | 0,386 |
| IB02 | 0,429 | 0,483 | 0,388 | **0,371** |
| IB03 | 0,334 | 0,431 | 0,288 | **0,268** |
| IB04 | **0,301** | 0,501 | 0,366 | 0,341 |
| IB05 | **0,366** | 0,532 | 0,464 | **0,364** |
| IB06 | 0,347 | 0,444 | 0,311 | **0,288** |
| IB08 | 0,568 | 0,593 | 0,623 | **0,480** |
| IB10 | 0,451 | 0,596 | 0,357 | **0,353** |
| IB11 | 0,571 | 0,612 | 0,606 | **0,537** |

S+R1 gana a la IDW en 5 de 9 estaciones y pierde en 4 (IB04, IB05, IB08, IB11). S+R3 es más estable: gana o empata en 8 de 9.

**2. La red extrapola mal lejos de la red.** En entrenamiento, la mediana de d₁ está entre 16 y 31 km y el percentil 75 por debajo de 45 km en todas las particiones salvo Mallorca informativo (`model_selection.csv`, `d1_km_train_quantiles`). En TEST de F2, d₁ está entre 93 y 130 km. En Ibiza y en Menorca, con Valiantzas, añadir R1 al sensor empeora (VII.4), que es el riesgo declarado en la Parte V. Para el 03.3 conviene entrenar con distancias más variadas, por ejemplo excluyendo también a los vecinos más cercanos de algunas filas de entrenamiento.

**3. Ridge aprovecha mejor la IDW que el HGB.** Con Valiantzas, Ridge S+R1 da 0,424 (−0,010 [−0,023; +0,001] frente a la IDW) y HGB S+R1 0,435. Una hipótesis: la relación entre la IDW y la PM es casi lineal y el árbol la aproxima por tramos; con R3 la ventaja se invierte (HGB 0,385, Ridge 0,434). La regla se aplica a HGB, tal como se congeló; esto no la cambia.

**4. La ANN M es inestable con inputs de red.** Desviación típica del RMSE entre las 5 semillas: en B, media 0,051 y máximo 0,222; en C, media 0,022 (`results/ann_seed_spread.csv`). Con S+R1 la ANN M pierde frente a la IDW en Valiantzas (+0,055) y HS-Ra (+0,043). Con S+R3 gana a la IDW en Valiantzas (−0,042) y HG-Rs (−0,092); en HS-Ra el IC incluye 0.

**5. Filas sin pool.** En entrenamiento se descartaron, en total sobre todas las celdas, 4.836 filas en B, 8.585 en C y 2.882 en B-ayer (días sin otra estación válida; en C se suman los dos días). En TEST no se descartó ninguna.

# Parte IX — Decisiones previas a la congelación y desviaciones

## IX.1 Decisiones tomadas antes de congelar

Josep delegó estas dudas con la instrucción «decide tú con criterio científico y déjalo documentado en el README». Están en `config/thresholds_v3_1_2.json`, en `_clarifications_before_freeze`, y se congelaron con el PR #16, antes de entrenar.

- **Cohorte de C.** El día d y el d+1 deben estar en la cohorte común (n = 19.216 en F1). El entrenamiento usa pares (d, d+1) con los dos días en DESARROLLO. Así todos los comparadores de C (persistencias, que usan las predicciones B del día d; climatología; Open-Meteo + AHC; B|S+R1) se evalúan sobre las mismas filas, y ningún par cruza la frontera entre DESARROLLO y TEST.
- **Ra(d+1) en C.** Se añade en todos los conjuntos de C, también HG-Rs y R. Es astronómica y se conoce sin error, no favorece a ningún conjunto, y sin ella el modelo no sabría a qué día del año se refiere la previsión.
- **Comparadores secundarios.** B-ayer se compara con B|S+R1 del mismo modelo y familia y con la IDW del mismo día, para medir cuánto cuesta el retraso de un día. A se compara con `S` del 03.1.
- **Regla de interpretación.** La versión propuesta no cubría todos los casos. Se cerró en 5 casos aplicados en orden (VII.1), sin mover el umbral de 0,05 ni el TOST del 03.1.

## IX.2 Desviaciones del plan

1. **`select_and_fit` replicada en `design.py` (`select_and_fit_net`).** La de `loso_models` no podía reutilizarse tal cual: la red debe reconstruirse en cada pliegue interno, excluyendo del pool a la estación de validación. Usa la misma rejilla, los mismos pliegues por estación, la misma media de RMSE y la misma regla de desempate, y llama a `lm._fit_predict_simple` y `lm._fit_predict_mlp`. No cambia ningún criterio.
2. **Prueba de humo antes de la aprobación.** Se lanzó un `fit` con `--max-train-rows 3000` (F1_IB05, Valiantzas) antes de fusionar el PR #16, lo que incumplía la regla de no ejecutar hasta la aprobación. Se borró sin mirar ninguna métrica (solo se vieron nombres de celda y tiempos) y se comunicó en su momento. Ningún resultado sale de esa prueba.
3. **Ridge y HGB se entrenaron en Kaggle** (sesión 0) y no en local, a petición de Josep. Mismo código.
4. **La línea de costa se descargó dentro de Kaggle** (sesión 0), porque el entorno del chat no tenía red.
5. **Tolerancia de `check_s_cells` en `report.py`.** Comprobaba con 10⁻⁹ que las predicciones `S` leídas de `predictions_test.csv.gz` del 03.1 coincidían con sus celdas. Ese CSV está redondeado a 5 decimales, así que la diferencia máxima era 5·10⁻⁶ y la comprobación fallaba. Se cambió a media unidad del último decimal (5,01·10⁻⁶). Es un error de código del informe, no cambia ningún criterio, y el efecto del redondeo en el RMSE es despreciable (los comparadores del 03.1 ya tenían ese redondeo).

## IX.3 Ejecución

- Kaggle, CPU, 4 procesos por sesión: sesión 0 (Ridge y HGB, 576 celdas, 1 h 47 min), sesión 1 (ANN M de B, 84, 6 h 22 min), sesión 2 (ANN M de C, IB01–IB06, 60, 3 h 32 min) y sesión 3 (ANN M de C, resto, 60, 2 h 54 min).
- Entorno de todas las celdas: Python 3.13.18, numpy 2.5.3, pandas 3.0.5, scikit-learn 1.9.1.
- Informe: `python studies/03_1_2_loso_sensor_red/run.py report` (unos 30 s).
