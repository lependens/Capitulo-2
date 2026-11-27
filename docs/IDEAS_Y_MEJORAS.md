# Ideas, mejoras y cómo rentabilizar el proyecto

Documento **vivo e interno**. Recoge lo que se ha aprendido, las líneas que se podrían investigar y las formas de sacar algún provecho del trabajo. No es un plan congelado: cualquier idea que pase a estudio necesita su propio protocolo y criterios antes de ejecutarse.

**Cómo se mantiene:** al cerrar cada estudio se actualizan «Lo que sabemos hoy» y el estado de las líneas afectadas, y se añade una línea al registro de cambios del final. Las propuestas detalladas siguen en cada estudio (03.1 Parte V, 03.2 Parte V, 03.1.2); aquí solo se resumen y se priorizan.

Última actualización: 2026-11-27: 03.3, 04 (fase A) y 05 preparados con sus prompts; 03.1.2 en ejecución. Cómo se mantiene este documento: `docs/COMO_ACTUALIZAR.md`.

## 1. Lo que sabemos hoy

Cifras en mm/día de RMSE frente a PM_FAO56_V1, TEST 2020–2025, estación no vista (F1), salvo que se diga otra cosa.

1. **Open-Meteo crudo sobreestima la ET0 en Baleares un ~19 %** (unos 1.257 mm/año frente a 1.060; sesgo +0,54 mm/día). La causa es el viento de la rejilla (el doble que el medido) y un rango diurno de temperatura 5 °C demasiado estrecho (estudio 01). En un balance hídrico exploratorio, eso es regar un 15–26 % de más (estudio 05).
2. **Cualquier corrección quita casi todo ese error.** Coeficiente mensual transferido 0,483; estación SIAR más cercana 0,484; IDW del día 0,434; HGB-S0 (Open-Meteo + ML, sin sensor) 0,433 (03.2).
3. **Dentro de la red, HGB-S0 empata con la IDW en el error diario, pero da un riego más fiel en cada sitio** (error del riego total 6–7 % frente a 9–11 %, exploratorio, estudio 05): su ventaja es de sesgo local, que es lo que se acumula.
4. **Lejos de la red, HGB-S0 gana con claridad.** Fuera Ibiza 0,51 frente a 0,61 (IDW) y 0,75 (estación más cercana); fuera Menorca 0,46 frente a 0,57 y 0,56 (03.2, F2). El error del modelo casi no cambia con la distancia y el de la red sí.
5. **Los modelos de pocos inputs de V2 transfieren, pero peor:** +0,05 a +0,10 al salir de su estación. Con solo temperatura no vale la pena; con piranómetro sí, pero es caro (03.1).
6. **Un termohigrómetro barato añade poco** a Open-Meteo + ML (−0,037) y mete un sesgo positivo de +0,09 (03.2).
7. **Las ANN no son mejores que los árboles con estos datos** y se rompen al extrapolar inputs estáticos (altitud o coordenadas fuera del rango de entrenamiento, sesgo de −2,5 en IB01). HGB es el modelo de referencia (03.1, 03.2).
8. **Las diferencias entre métodos corregidos (0,03–0,05 mm/día, 1–2 %) son despreciables en la práctica** frente a la incertidumbre del Kc (10–20 %) o la eficiencia del riego. Lo que importa es corregir el sesgo de Open-Meteo y la robustez lejos de la red.

## 2. Líneas de investigación

Viabilidad: **alta** (indicio a favor o base sólida), **media** o **baja**. Coste: **bajo** (sin datos nuevos ni entrenamiento pesado), **medio** o **alto**.

| # | Línea | Por qué interesa | Viabilidad | Coste | Estado |
|---|---|---|---|---|---|
| L1 | **Balance hídrico por fuente de ET0** (estudio 05) | Traduce los deltas de RMSE a agua y euros; es el mensaje para vender el trabajo | alta | bajo | plan + prompt; falta tabla de cultivos |
| L2 | **Previsión D+1…D+7** (estudio 04) | Es lo que la red no da y lo más útil para programar el riego | media-alta | medio | fase A preparada; capturas Open-Meteo y ECMWF en marcha |
| L3 | **ML + red: corrección residual de HGB-S0 con la red del día** (regresión-kriging o IDW de los residuos) | La media simple HGB-S0 + IDW ya da 0,377 (−0,056); interpolar los residuos es la forma con base geoestadística | alta | bajo | plan: estudio 03.3 |
| L4 | **Andalucía: distancia de cruce** (a partir de qué distancia a la red gana cada fuente, con y sin sensor propio) | ~100 estaciones, relieve y distancias de 50–100 km; base de un artículo serio y de un mapa de decisión. Método: exclusión por radio (ver abajo) | alta | medio | datos en captura (SIAR Sync V3) |
| L5 | **Objetivo residual y control de dominio** (predecir PM − ET0_OM, quitar o recortar altitud, avisar fuera de rango) | Evita los fallos silenciosos de las ANN; imprescindible en un servicio | alta | bajo | plan: estudio 03.3 |
| L6 | **Incertidumbre por predicción** (cuantiles o intervalos conformes en LOSO) | «4,2 ± 0,4 mm» vale más que «4,2»; pocos servicios lo dan | alta | bajo | idea |
| L7 | **Reconstrucción histórica de la ET0 de Baleares desde 1940** con el reanálisis corregido, y su tendencia | Muy divulgable; serie insular de 85 años; ya tenemos el pipeline. Supone que la corrección de 2004–2019 vale hacia atrás | media | bajo | idea |
| L8 | **Control de calidad de la red SIAR** con los residuos de Open-Meteo + ML (detectar sensores que derivan o fallan) | Útil para el MAPA y para depurar nuestra propia referencia; publicable | media | medio | idea |
| L9 | **Dónde faltan estaciones** (diseño de red con la distancia de cruce) | Interesa a la administración | media | medio | depende de L4 |
| L10 | **Validación con lisímetro** (Albacete, Badajoz) | Responde a la crítica de que la referencia es PM calculada; con el grupo del tutor | media | medio | idea; depende de acceso a datos |
| L11 | **Robustez a un sensor de usuario** (degradar T y HR con errores típicos de sensores baratos) | Saber cuánto sobrevive la mejora de S2 | alta | bajo | idea (03.2 Parte V-E) |
| L12 | **Altura e interior** (estaciones > 120 m) | Ninguna estación de entrenamiento supera 120 m; la Tramuntana pasa de 1.000 | media | medio | idea (03.2 Parte V-C) |
| L13 | **ANN con contexto temporal o espacial** (varios días seguidos, rejilla alrededor del punto) | Es donde las redes sí suelen ganar a los árboles; tiene sentido con Andalucía | media | alto | idea |
| L14 | **Fuentes con licencia comercial** (ERA5/ERA5-Land, datos abiertos de ECMWF, AEMET) en lugar de la API gratuita de Open-Meteo | Requisito para cualquier uso con anuncios o de pago (ver sección 4) | alta | medio | captura ECMWF en marcha; revalidación con ERA5 propuesta como estudio 03.4 |
| L15 | **Sesgo positivo con sensor (S1, S2)** | +0,09 mm/día; se acumula en el balance | media | bajo | sin investigar |
| L16 | **Resolución subdiaria** (datos horarios de Open-Meteo y SIAR) | Antes «03.4» en la Parte V del 03.1; el rango diurno es la variable que más falla | media | medio | idea |
| L17 | **Terreno y emplazamiento como inputs** (altitud relativa a la celda del reanálisis, pendiente, orientación, posición en el relieve a 1/5/20 km, distancia a la costa, cobertura del suelo; modelo digital de elevación) | La orografía suavizada del reanálisis explica parte del error de temperatura y viento; hay base en la literatura (reducción de escala de ERA5 con topografía y descriptores de satélite). Con 9 estaciones bajas es solo un identificador: se prueba en Andalucía, por ablación (ver abajo) | media-alta | medio | idea; depende de L4; comprobar licencia del MDE para uso comercial |
| L18 | **Satélite y radar** como datos adicionales: radiación de satélite (CM SAF SARAH-3), ET0 de satélite (LSA SAF METREF), radar de lluvia de AEMET, NDVI/Kcb de Sentinel-2 | Radiación y ET0 de satélite como fuente alternativa o comparador; lluvia de radar para el balance hídrico; Kcb para el cultivo real | media | medio | idea; ver abajo |

### Método para L4: exclusión por radio

Para cada estación evaluada se quitan del entrenamiento y de la IDW todas las estaciones a menos de r km (r = 0, 25, 50, 75, 100). Así la curva de error frente a distancia es **controlada**, no limitada a las distancias que haya por casualidad. Se comparan: estación más cercana, IDW, Open-Meteo/ERA5 + ML sin sensor y con sensor (T; T + HR). El resultado es una regla de decisión: «si tu estación SIAR está a menos de X km, úsala; si no, usa esto; el sensor propio compensa solo si…». Protocolo prerregistrado, como los estudios 03.

### L17: terreno y emplazamiento (diseño previsto para Andalucía)

Ablación sobre Open-Meteo/ERA5 + ML, validada con estaciones retenidas: (1) sin datos estáticos; (2) + altitud relativa a la celda; (3) + descriptores de terreno; (4) + distancia a la costa; (5) + cobertura del suelo. Error por tipo de lugar (costa, interior, ladera, valle). No se usan curvas de nivel en bruto: se derivan descriptores de un modelo digital de elevación. Con pocos puntos de entrenamiento, cualquier dato estático actúa como identificador (03.1 y 03.2); por eso no se prueba en Baleares. Una ANN con parches de terreno solo tiene sentido con cientos de estaciones. Referencia: arXiv 2608.12271 (topografía explica la mayor parte del residuo de temperatura; descriptores de satélite ayudan al viento).

### L18: satélite y radar (qué aporta cada uno)

| Dato | Para qué sirve aquí | Valoración |
|---|---|---|
| **CM SAF SARAH-3** (radiación en superficie, 0,05°, cada 30 min, 1983 hasta hoy en tiempo casi real; gratuito, hay que mostrar «copyright EUMETSAT») | Mejor radiación que la del reanálisis en días con nubes. En el estudio 01 la radiación de Open-Meteo ya era buena, así que el margen es pequeño | media-baja para corregir; útil como comprobación |
| **LSA SAF METREF** (ET0 diaria de satélite a 3 km, 2004–hoy, CC BY 4.0, con registro) | Es una ET0 independiente ya calculada: comparador gratuito y con licencia clara | media-alta como comparador (si cubre Baleares; comprobar) |
| **Radar de lluvia de AEMET** (conjuntos abiertos; licencia por confirmar) | Lluvia observada para el balance hídrico (estudio 05); no afecta a la ET0 | media; requiere procesar imágenes |
| **Sentinel-2 (NDVI, Kcb)** | Cultivo real de la parcela (la app SiAR ya los usa) | otra línea: coeficiente de cultivo, no ET0 |
| **Presión atmosférica** | En FAO-56 solo entra por la constante psicrométrica y se obtiene de la altitud; ERA5 ya la trae | no aporta |

Satélite y radar mejoran sobre todo la **nubosidad y la lluvia** (previsión a corto plazo y balance), no el sesgo de viento que domina el error de Open-Meteo.

### Próximos estudios

| Estudio | Líneas | Estado | Necesita Kaggle |
|---|---|---|---|
| 03.1.2 sensor + red | — | en ejecución | sí (ANN M) |
| 03.3 Open-Meteo + ML + red, objetivo residual | L3, L5 | plan congelado, prompt listo | una sesión corta (ANN M) |
| 05 balance hídrico | L1 | plan, falta tabla de cultivos | no |
| 04 fase A previsión | L2 | prompt listo | probablemente no |
| **03.4 fuente con licencia comercial** (propuesto) | L14 | idea: repetir lo esencial del 03.2/03.3 con ERA5 de Copernicus (descarga con cuenta gratuita del CDS) y comprobar si el `archive` de Open-Meteo y ERA5 dan lo mismo | no |
| Andalucía, distancia de cruce | L4 | espera datos | sí |

**Orden recomendado:** L1 → L3 y L5 (baratas, mismas predicciones e infraestructura) → L4 (Andalucía) → L2 (cuando haya meses de previsión capturada) → el resto según interés.

### No recomendado

- Seguir partiendo en subestudios diferencias de 0,02–0,04 mm/día de RMSE diario: no cambian ninguna decisión de riego (punto 8).
- ANN tal cual con altitud o coordenadas como input (fallan dos veces: 03.1 y 03.2).
- Coordenadas o identificadores de estación como input con pocas estaciones de entrenamiento (memorizan).

## 3. Publicación

**Qué es nuevo y qué no.** Validar ML de ET0 en estaciones no vistas está establecido. Corregir reanálisis con ML también: un estudio de 2026 en Turquía entrena RF y XGBoost con variables de ERA5-Land contra la PM de 33 estaciones y obtiene RMSE 0,43 mm/día, como nosotros, pero con separación **temporal**, no espacial (Agronomy 16(2), 253). Lo que distingue a este proyecto:

1. Comparación, en una ubicación **sin estación** y con **protocolo prerregistrado**, de las opciones reales del usuario: sensor barato, red (vecina, IDW) y reanálisis corregido.
2. Dependencia de la **distancia a la red**, con las islas como experimento natural (y, después, Andalucía).
3. **Traducción a riego** (balance hídrico) en lugar de solo RMSE.
4. Código y datos abiertos y reproducibles.

**Artículo posible.** «¿De dónde sacar la ET0 en una finca sin estación: interpolar la red, corregir un reanálisis o instalar un sensor barato?». Con Baleares sola: revista modesta (Agronomy, Water, Atmosphere, Spanish Journal of Agricultural Research). Con Andalucía y el balance hídrico: Agricultural Water Management o Computers and Electronics in Agriculture. Escribirlo con el tutor (grupo UIB/UPV) mejora mucho las opciones.

**Debilidades que señalará un revisor:** 9 estaciones bajas y costeras, referencia calculada, efectos pequeños en RMSE. Se responden con Andalucía (L4), el balance (L1) y, si se puede, el lisímetro (L10).

## 4. Cómo rentabilizar (aunque sea poco)

**Condición previa de licencia.** La API gratuita de Open-Meteo es solo no comercial, y sus condiciones cuentan como comercial **cualquier web o app con suscripciones o anuncios**. Las **donaciones voluntarias sí están permitidas**. Con anuncios o cobro hay que pagar su API o cambiar de fuente (L14). SiAR: citar siempre la fuente; el uso comercial no se menciona de forma explícita y hay que confirmarlo con el MAPA antes de cobrar.

| Opción | Qué es | Ingresos esperables | Esfuerzo | Licencia |
|---|---|---|---|---|
| R1. Proyecto con la UIB (innovación agraria, grupos operativos, digitalización) | Proyecto financiado con el tutor y una comunidad de regantes o un ayuntamiento | El único camino con dinero real a corto plazo | medio-alto | sin problema |
| R2. Web gratuita + donaciones (Ko-fi, GitHub Sponsors) | ET0 corregida por zona, mapa y aviso del sesgo de Open-Meteo | Simbólicos | bajo | compatible con la API gratuita |
| R3. Boletín semanal por Telegram o correo («cuánto regar esta semana en tu zona») | ET0 de la semana y la previsión, por zona y cultivo | Simbólicos; un patrocinador local (vivero, tienda agrícola) pagaría más que la publicidad | bajo | patrocinio = comercial: revisar |
| R4. Integración con riego doméstico inteligente (Home Assistant, OpenSprinkler) | Endpoint de ET0 corregida para Baleares; mensaje: «tu riego inteligente riega un ~19 % de más» | Donaciones; visibilidad | medio | donaciones sí; de pago, no |
| R5. Auditorías de riego (golf, hoteles, ayuntamientos, comunidades de regantes) | Agua aplicada frente a ET0 corregida y balance (L1) | Por encargo | alto (trabajo activo) | uso comercial: fuente con licencia (L14) |
| R6. Reputación: artículo, repo abierto, divulgación | Artículo con el tutor, notas de prensa (L7), charlas | Indirecto: consultoría, colaboraciones, empleo en el sector | medio | sin problema |
| R7. Curso o material docente («ML con datos agroclimáticos abiertos») | Basado en este repo reproducible | Bajos | medio | educativo: no comercial si es gratuito |
| R8. Publicidad programática | Anuncios en la web | Muy bajos (nicho de pocas miles de visitas al mes) | bajo | **no** con la API gratuita |

**Fuentes con licencia que permiten cobrar o poner anuncios** (comprobado el 2026-11-27; confirmar siempre el texto vigente):

| Fuente | Uso | Condición |
|---|---|---|
| ERA5 / ERA5-Land (Copernicus) | Histórico para entrenar | CC-BY desde el 2 de julio de 2025; citar la fuente |
| ECMWF datos abiertos en tiempo real (IFS, AIFS) | Previsión diaria | CC-BY-4.0 desde octubre de 2025; citar a ECMWF |
| AEMET OpenData | Observación y previsión municipal | Reutilización comercial permitida citando «Fuente: AEMET» y sin sugerir aval; sus salidas de modelo no son abiertas |
| Météo-France AROME | — | Abierto pero solo Francia: no sirve |

Camino para un servicio de pago o con anuncios: entrenar con ERA5, predecir con ECMWF y **revalidar con la misma fuente que se usará en producción** (un modelo entrenado con Open-Meteo no se traslada sin comprobarlo). La referencia SIAR exige además confirmar con el MAPA el uso comercial. Los puntos de L14 y de la captura ECMWF están en `studies/04_prevision_et0/`.

**Recomendación:** R2 + R3 como escaparate y para validar interés, R1 con el tutor como vía de financiación y R6 como objetivo de fondo. R8 no compensa.

## 5. Preguntas abiertas

- ¿Qué fuente con licencia comercial reproduce mejor a Open-Meteo en Baleares (L14)? ¿Es el `archive` de Open-Meteo equivalente a ERA5 descargado de Copernicus?
- ¿Qué ET0 prevista da ECMWF con sus variables abiertas (T, Td, viento, radiación) frente a la de Open-Meteo, y falta Tmax/Tmin para el modelo?
- ¿Con qué retardo publica SIAR los datos del día? Decide si L3 sirve para la ET0 de hoy o solo para la de ayer.
- ¿Hay acceso a datos de lisímetro a través del tutor (L10)?
- ¿Mantiene HGB-S0 su ventaja con previsión en lugar de reanálisis (L2)?

## Registro de cambios

| Fecha | Cambio |
|---|---|
| 2026-11-27 | Creación tras cerrar el 03.2; exploratorio de balance hídrico (estudio 05) |
| 2026-11-27 | Licencias comerciales (ERA5, ECMWF, AEMET), método de exclusión por radio (L4), captura ECMWF y plan de previsión |
| 2026-11-27 | L17 (terreno y emplazamiento) y L18 (satélite y radar) |
| 2026-11-27 | Estudio 03.3 (L3 + L5) con criterios congelados; 04 fase A y 05 con prompts; 03.4 propuesto (L14); L16 subdiaria; renumeración 03.3/03.4; guía `docs/COMO_ACTUALIZAR.md` |
