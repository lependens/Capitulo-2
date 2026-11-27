# Prompt para el chat que ejecuta el estudio 05

Copiar desde la línea siguiente hasta el final y pegarlo en un chat nuevo del proyecto.

---

Vamos a ejecutar el **estudio 05 (balance hídrico por fuente de ET0)** del repositorio `lependens/Capitulo-2`. Respóndeme siempre en español.

**Lee primero:**
1. `studies/05_balance_hidrico/README.md` y la prueba exploratoria (`exploratorio/balance_rapido.py` y su salida).
2. `config/thresholds_v5.json`: criterios en PROPUESTA; falta la tabla de cultivos.
3. `studies/03_2_loso_openmeteo_ml/README.md` (qué es cada columna de `results/predictions_test.csv.gz`).
4. `docs/COMO_ACTUALIZAR.md`.

**Orden de trabajo:**
1. **Tabla de cultivos.** Completa en `config/thresholds_v5.json` los parámetros de FAO-56 (Kc ini/med/fin de la tabla 12, duración de fases de la tabla 11 para la región mediterránea o la más cercana, profundidad de raíces y fracción p de la tabla 22, agua disponible por tipo de suelo de la tabla 19) para césped, almendro, olivo, viña, cítricos y tomate de verano, con fechas de inicio razonables para Baleares. Cita la tabla de cada valor y marca lo que sea una decisión tuya. Abre un PR que solo toque ese fichero, deja `status` en PROPUESTA y **espera mi aprobación**. No calcules nada antes.
2. **Lluvia.** La de SIAR de cada estación está en Capitulo-1, `datos_siar_baleares/IBxx_datos_completos.csv` (columna `Precipitacion`). Si no tienes acceso a ese repo, pídemelo. Expórtala con su SHA256 a `data/reference/` con un script en `tools/`, sin tocar lo existente. Para la variante, la lluvia de Open-Meteo `archive` (si no está en `data/processed`, descárgala con el `backfill` del repo).
3. **Código** en `studies/05_balance_hidrico/`: `balance.py` (FAO-56 cap. 8, Kc por fases interpolado, riego al superar RAW, percolación), `report.py` y tests (un caso a mano de pocos días con resultado conocido, conservación del agua, que todas las fuentes usan la misma lluvia).
4. **Cálculo e informe**: métricas por estación-año, IC pareados, hipótesis B5.1–B5.3 y la regla de interpretación literal; figuras (error de riego por fuente y cultivo, y por estación); `results/` con CSV, `run_manifest.json` e `interpretation.json`. Si ya existen las predicciones del 03.3, añade sus brazos como informativos.
5. **Cierre** según `docs/COMO_ACTUALIZAR.md`.

**Reglas:**
- No cambies hipótesis, fuentes ni la regla una vez congelado. Si algo no se puede hacer tal cual, para y propón la alternativa.
- No toques datos crudos ni otros estudios.
- Tests: `PYTHONPATH=src python3 -m unittest discover -s tests` más los nuevos.
- Para GitHub usa `gh api` (API REST). Puedes fusionar los PR de código e informe cuando pasen los tests; el de criterios, no.
- Si el modelo de balance te parece demasiado simple para lo que se quiere decir, dímelo antes de seguir.
