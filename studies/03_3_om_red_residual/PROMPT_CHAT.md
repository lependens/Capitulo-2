# Prompt para el chat que ejecuta el estudio 03.3

Copiar desde la línea siguiente hasta el final y pegarlo en un chat nuevo del proyecto.

---

Vamos a ejecutar el **estudio 03.3 (Open-Meteo + ML + red SIAR del día, y objetivo residual)** del repositorio `lependens/Capitulo-2`. Respóndeme siempre en español.

**Lee primero, en este orden:**
1. `studies/03_3_om_red_residual/README.md`: el plan. Es la especificación; síguelo.
2. `config/thresholds_v3_3.json`: los criterios, **ya congelados**.
3. `studies/03_2_loso_openmeteo_ml/README.md` y su código (`loso_common.py`, `loso_models.py`, `run.py`, `report.py`, `kaggle_session.sh`): de ahí sale todo.
4. `studies/03_1_2_loso_sensor_red/network.py` y sus tests: construcción de la red (R1).
5. `docs/COMO_ACTUALIZAR.md`: cómo se actualizan README y `docs/IDEAS_Y_MEJORAS.md` al cerrar.

**Reglas que no se negocian:**
- No cambies hipótesis, brazos, modelos, rejillas, comparadores ni la regla de interpretación. Si algo no se puede hacer tal cual, para, explícamelo y propón la alternativa; no la apliques por tu cuenta.
- Antes de ejecutar nada, compara el README con el JSON. Si ves una contradicción, dímela antes de seguir.
- No toques los datos crudos ni nada de `studies/03_2_loso_openmeteo_ml/` ni de `studies/03_1_2_loso_sensor_red/` (el 03.1.2 se ejecuta en otro chat). **Importa** `network.py`, `loso_common` y `loso_models`; no los copies ni los modifiques. Si necesitas un cambio en ellos, pídemelo.
- Reutiliza HGB-S0, HGB-S2 y ANN M-S0 del 03.2 (predicciones y celdas); no los reentrenes.
- Reglas de construcción con tests propios: (a) la estación evaluada nunca está en el pool de red; (b) en la validación interna, la estación de validación sale del pool de todas las filas; (c) en `residuo_IDW`, el residuo de cada estación de entrenamiento viene de un HGB-S0 entrenado sin ella ni la evaluada; (d) objetivo residual: predicción = ET0_OM + modelo; (e) recorte de altitud al rango de entrenamiento de la partición.
- Todos los métodos se evalúan sobre las mismas filas: si un día no hay red, esa fila sale de todos y se cuenta.
- Los tests deben pasar: `PYTHONPATH=src python3 -m unittest discover -s tests` (hoy 61) más los nuevos.

**Orden de trabajo:**
1. Código y tests en `studies/03_3_om_red_residual/`: `run.py`, `report.py`, `kaggle_session.sh`. Prueba con un subconjunto pequeño, sin guardar resultados como definitivos.
2. HGB y Ridge de todos los brazos (incluidos los HGB anidados de `residuo_IDW`): en local si cabe; si no, en Kaggle (sesión 0).
3. ANN M en Kaggle, una sesión (3 brazos × 12 particiones × 5 semillas). Dame la rama, el comando (`bash studies/03_3_om_red_residual/kaggle_session.sh N`), cuánto calculas que tardará y qué zip descargar. Celdas reanudables en `results/cells/*.json.gz`.
4. Informe: métricas, IC pareados, TOST, control de dominio (`dominio.csv`), figuras, `interpretation.json` aplicando la regla literal, y el README completado (resultados, hipótesis, regla, por estación con IB01 aparte, F2). Separa lo planificado de lo *post hoc*.
5. Cierre según `docs/COMO_ACTUALIZAR.md`: fila del estudio en la hoja de ruta del README principal, «Lo que sabemos hoy» y estado de L3 y L5 en `docs/IDEAS_Y_MEJORAS.md`, y línea en su registro de cambios.

**Cómo trabajamos:**
- Para GitHub usa `gh api` (API REST; GraphQL puede estar bloqueada). Puedes fusionar a `main` los PR de código e informe cuando los tests pasen.
- Kaggle: CPU, sin tokens ni secretos; versiones fijadas como en el 03.2 (`requirements.txt` y `check_env.py`).
- Al acabar cada fase dame un resumen corto: lo hecho, lo que falta y cualquier desviación del plan.
- Si encuentras un error en el plan o en el 03.2, dímelo con franqueza antes de seguir.
