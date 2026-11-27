# Prompt para el chat que ejecuta la fase A del estudio 04

Copiar desde la línea siguiente hasta el final y pegarlo en un chat nuevo del proyecto.

---

Vamos a hacer la **fase A (exploratoria) del estudio 04, previsión de ET0 a 1–7 días**, del repositorio `lependens/Capitulo-2`. Respóndeme siempre en español.

**Lee primero:**
1. `studies/04_prevision_et0/README.md`: enfoque, las dos fases, datos y comparadores.
2. `config/thresholds_v4.json`: criterios de la fase B, en estado PROPUESTA. Tu trabajo los afina; **no se congelan sin mi aprobación**.
3. `studies/03_2_loso_openmeteo_ml/README.md` y su código: protocolo LOSO, comparadores y bootstrap que se reutilizan.
4. `src/openmeteo_et0/` (cliente, almacenamiento con hash y manifiesto, `pm.py`), `tools/capture_ecmwf.py` y los workflows `daily_forecast` y `ecmwf_forecast`.
5. `docs/COMO_ACTUALIZAR.md`.

**Qué es la fase A:** construir y probar la cadena con previsiones históricas, sin veredicto. Puedes mirar todo lo que quieras, pero cada resultado se presenta como exploratorio. **No evalúes nada con filas del periodo de test de la fase B** (desde 2026-12-01), ni con las capturas propias salvo para comprobar que el formato se lee bien.

**Tareas, en este orden:**
1. **Inventario de datos de Open-Meteo:** qué ofrecen *previous runs* (`previous_day1..7`) y `historical_forecast` para los 9 puntos: desde cuándo, con qué modelos, si traen ET0 y las variables de S0, y si se puede separar el horizonte. Documenta lo que compruebes y lo que no.
2. **Descarga histórica** con la infraestructura del repo (añade el producto al cliente y al workflow `backfill` si hace falta; lo crudo nunca se sobrescribe y va al manifiesto con su hash). Uso: investigación, no comercial.
3. **Procesado de la captura ECMWF** (`data/raw/ecmwf_ifs/`): de los pasos de 3–6 h a valores diarios en hora local (Tmax y Tmin de los pasos de 3 h, HR desde T y Td, viento a 2 m desde u y v a 10 m con la conversión FAO-56, Rs diaria desde la diferencia de `ssrd`, lluvia desde `tp`), interpolación desde los 4 vecinos y ET0 PM con `src/openmeteo_et0/pm.py`. Tests con un fichero real ya capturado.
4. **Comparadores por horizonte** (persistencia, climatología, ET0 prevista cruda, + AHC, HGB-S0 del 03.2 aplicado a la previsión) y **HGB entrenado con previsiones tal como se emitieron**, LOSO, sobre el periodo histórico disponible hasta 2025-12-31. Métricas por horizonte y de la suma semanal.
5. **Informe exploratorio** en el README del 04: qué funciona, a qué horizonte deja de ganar a la persistencia, un modelo por horizonte o uno con L como input, y qué bloques de bootstrap tienen sentido.
6. **Propuesta de criterios de la fase B**: PR que solo edita `config/thresholds_v4.json` (sigue en PROPUESTA) con los cambios justificados. Lo congelo yo.
7. **Cierre** según `docs/COMO_ACTUALIZAR.md` (hoja de ruta, «Lo que sabemos hoy», L2 y L14, registro de cambios).

**Más adelante (no ahora):** comparar con las previsiones de SIAR y AEMET que capturo en Capitulo-1. Te daré acceso cuando tenga al menos 15 días buenos de captura.

**Reglas:**
- No toques los datos crudos existentes ni los estudios 01–03.x.
- Los tests deben pasar: `PYTHONPATH=src python3 -m unittest discover -s tests` más los nuevos.
- Para GitHub usa `gh api` (API REST). Puedes fusionar los PR de código e informe cuando pasen los tests; el de criterios, no.
- Si algo del enfoque te parece mal planteado, dímelo con franqueza antes de seguir.
