# Prompt para el chat que ejecuta el estudio 03.1.2

Copiar desde la línea siguiente hasta el final y pegarlo en un chat nuevo del proyecto.

---

Vamos a ejecutar el **estudio 03.1.2 (sensor local + red SIAR)** del repositorio `lependens/Capitulo-2`. Respóndeme siempre en español.

**Lee primero, en este orden:**
1. `studies/03_1_2_loso_sensor_red/README.md`: el plan completo. Es la especificación; síguelo.
2. `config/thresholds_v3_1_2.json`: los criterios (estado PROPUESTA).
3. `studies/03_1_loso_inputs_siar/README.md`: el estudio del que parte, sobre todo las partes II, III y V, y su código (`loso_common.py`, `loso_models.py`, `run.py`, `report.py`, `kaggle_session.sh`).

**Reglas que no se negocian:**
- No cambies hipótesis, conjuntos de inputs, modelos, rejillas, comparadores ni la regla de interpretación una vez congelados. Si algo no se puede hacer tal cual, para, explícamelo y propón la alternativa; no la apliques por tu cuenta.
- Paso 1: abre un PR que solo pase `status` de `config/thresholds_v3_1_2.json` a CONGELADO (más las correcciones que yo te pida). **No ejecutes ninguna celda hasta que yo lo apruebe y se fusione.**
- No toques los datos crudos ni nada de `studies/03_1_loso_inputs_siar/` (resultados, celdas, README), ni de `studies/03_2_loso_openmeteo_ml/` (el 03.2 va en otro chat; no lo empieces).
- Reutiliza en lugar de copiar: importa `loso_common` y `loso_models` del 03.1 y reutiliza sus celdas `S` (`results/cells/*__principal__{Ridge,HGB,ANN_M}.json.gz`) y sus comparadores. Mismas particiones (`results/folds.json`), mismo bootstrap (2.000 réplicas, semilla 20261126, bloques estación-año), mismas métricas, umbral 0,05 y TOST.
- Respeta las dos reglas de construcción de la red: **exclusión de la propia estación** (una fila nunca ve su propia estación; en la validación interna la estación de validación sale del pool de todas las filas) y **PM y distancias ordenadas por cercanía**, nunca indexadas por nombre de estación. Escribe tests para ambas.
- Los tests deben pasar: `PYTHONPATH=src python3 -m pytest -q tests` (hoy, 31) más los nuevos.
- La distancia a la costa se calcula con una línea de costa oficial (Natural Earth 1:10m o GSHHG) y se guarda en `config/stations_coast.csv` con la fuente y su SHA256. Nunca a ojo. Si tu entorno no tiene red, prepara el script para Kaggle o pídeme que adjunte el fichero.

**Orden de trabajo:**
1. PR de congelación de criterios y espera mi aprobación.
2. Código: `network.py`, `run.py`, `coast.py`, `report.py`, `kaggle_session.sh` y tests, en `studies/03_1_2_loso_sensor_red/`. Prueba en local con un subconjunto pequeño, sin guardar resultados como definitivos.
3. Diagnóstico de costa (sin entrenar): sesgo por estación del 03.1 frente a la distancia a la costa.
4. Ridge y HGB de todos los escenarios: en local si cabe, si no en Kaggle.
5. ANN M en Kaggle (unas 3 sesiones; el reparto está en el README). Para cada sesión dame la rama, el comando (`bash studies/03_1_2_loso_sensor_red/kaggle_session.sh N`) y qué zip descargar. Las celdas se guardan como en el 03.1: `results/cells/*.json.gz`, reanudables.
6. Informe: métricas, IC pareados, TOST, figuras, `interpretation.json` y el README completado con resultados, hipótesis G1–G3 y P1–P2, regla de interpretación, por estación, F2, B-ayer y A. Separa claramente lo planificado de lo posterior (*post hoc*).

**Cómo trabajamos:**
- Para GitHub usa `gh api` (la API REST; GraphQL puede estar bloqueada). Puedes fusionar a `main` los PR de código e informe cuando los tests pasen; el de criterios, solo con mi aprobación.
- Si necesitas mi navegador o mi carpeta de Descargas para los zips de Kaggle, pídemelo.
- Antes de cada sesión larga dime cuánto calculas que tardará. Al acabar cada fase dame un resumen corto con lo hecho, lo que falta y cualquier desviación del plan.
- Si encuentras un error en el plan o en el 03.1, dímelo con franqueza antes de seguir.
