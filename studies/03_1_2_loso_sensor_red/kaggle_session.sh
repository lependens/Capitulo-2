#!/usr/bin/env bash
# Una sesion de Kaggle (CPU, 4 nucleos, 12 h) del estudio 03.1.2. Uso (desde la raiz del repo clonado):
#   bash studies/03_1_2_loso_sensor_red/kaggle_session.sh N
# N = 1: ANN M de B (7 conjuntos x 12 particiones = 84 celdas)                       ~6-7 h
#     2: ANN M de C, particiones F1_IB01..F1_IB06 (60 celdas)                        ~5 h
#     3: ANN M de C, particiones F1_IB08, F1_IB10, F1_IB11 y las 3 F2 (60 celdas)    ~5 h
#     4: continuacion: cualquier ANN M que falte (B y C)
#     0: Ridge y HGB de todos los escenarios (solo si no se hacen en local)           ~1-1,5 h
# Si falta config/stations_coast.csv y la sesion tiene Internet, lo calcula (coast.py --download) y lo empaqueta.
# Se detiene al empezar celdas nuevas pasadas 8 h (margen para el limite de 12 h) y siempre empaqueta lo hecho.
# Reanudable: las celdas ya existentes (en la rama o en salidas montadas de sesiones anteriores) se saltan.
# NO usa ningun token ni secreto. Versiones fijadas: las del 03.1 (requirements.txt y check_env.py).
set -uo pipefail
N="${1:?uso: kaggle_session.sh 0..4}"
D=studies/03_1_2_loso_sensor_red
D31=studies/03_1_loso_inputs_siar
OUT=/kaggle/working
pip install -q -r "$D31/requirements.txt" || { echo "pip no pudo instalar las versiones fijadas"; exit 1; }
python "$D31/check_env.py" || exit 1
mkdir -p "$D/results/cells"
python - "${KAGGLE_INPUT_DIR:-/kaggle/input}" "$D/results/cells" <<'PY'
import glob, os, shutil, sys, zipfile
src, dst = sys.argv[1], sys.argv[2]
n = 0
for z in glob.glob(os.path.join(src, "**", "celdas_0312_sesion_*.zip"), recursive=True):
    with zipfile.ZipFile(z) as zf:
        for name in zf.namelist():
            base = os.path.basename(name)
            if base.endswith(".json.gz") and not os.path.exists(os.path.join(dst, base)):
                with zf.open(name) as a, open(os.path.join(dst, base), "wb") as b:
                    shutil.copyfileobj(a, b)
                n += 1
print(f"celdas recuperadas de sesiones anteriores: {n}")
PY
EXTRA=()
if [ ! -f config/stations_coast.csv ]; then
  python "$D/coast.py" compute --download && EXTRA=(config/stations_coast.csv) \
    || echo "AVISO: no se pudo calcular la distancia a la costa (sin Internet?)"
fi
case "$N" in
  0) ARGS=(--models Ridge,HGB) ;;
  1) ARGS=(--models ANN_M --scenarios B) ;;
  2) ARGS=(--models ANN_M --scenarios C --folds F1_IB01,F1_IB02,F1_IB03,F1_IB04,F1_IB05,F1_IB06) ;;
  3) ARGS=(--models ANN_M --scenarios C --folds F1_IB08,F1_IB10,F1_IB11,F2_island) ;;
  4) ARGS=(--models ANN_M) ;;
  *) echo "N debe ser 0..4"; exit 1 ;;
esac
python "$D/run.py" fit "${ARGS[@]}" --list
python "$D/run.py" fit "${ARGS[@]}" --workers 4 --max-hours 8
python "$D/run.py" fit "${ARGS[@]}" --list
case "$N" in
  0) PAT='*__Ridge.json.gz *__HGB.json.gz' ;;
  *) PAT='*__ANN_M.json.gz' ;;
esac
python - "$OUT/celdas_0312_sesion_$N.zip" "$D/results/cells" "${EXTRA[@]:-}" -- $PAT <<'PY'
import glob, os, sys, zipfile
out, cells = sys.argv[1], sys.argv[2]
i = sys.argv.index("--")
extra = [x for x in sys.argv[3:i] if x]
pats = sys.argv[i + 1:]
files = sorted({f for p in pats for f in glob.glob(os.path.join(cells, p))})
with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
    for f in files:
        z.write(f, os.path.basename(f))
    for e in extra:
        z.write(e, os.path.basename(e))
print(f"{len(files)} celdas (+{len(extra)} extra) empaquetadas en {out}")
PY
