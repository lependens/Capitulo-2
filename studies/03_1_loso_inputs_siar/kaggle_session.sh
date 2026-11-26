#!/usr/bin/env bash
# Una sesion de Kaggle (CPU, 4 nucleos, 12 h) del estudio 03.1. Uso (desde la raiz del repo clonado):
#   bash studies/03_1_loso_inputs_siar/kaggle_session.sh N
# N = 1: RF + ANN S + ANN M (todas las familias)       ~16 h de nucleo -> ~4-5 h
#     2: ANN tipo V2 de HS_RA y HG_RS                  ~19 h de nucleo -> ~5-6 h
#     3: ANN tipo V2 de VALIANTZAS                     ~15 h de nucleo -> ~4-5 h
# Se detiene al empezar celdas nuevas pasadas 8 h (margen para el limite de 12 h) y siempre empaqueta lo hecho.
# Reanudable: las celdas ya existentes se saltan. NO usa ningun token ni secreto.
set -uo pipefail
N="${1:?uso: kaggle_session.sh 1|2|3}"
D=studies/03_1_loso_inputs_siar
OUT=/kaggle/working
pip install -q -r "$D/requirements.txt" || { echo "pip no pudo instalar las versiones fijadas"; exit 1; }
python "$D/check_env.py" || exit 1
case "$N" in
  1) ARGS=(--models RF,ANN_S,ANN_M) ;;
  2) ARGS=(--models ANN_V2like --families HS_RA,HG_RS) ;;
  3) ARGS=(--models ANN_V2like --families VALIANTZAS) ;;
  *) echo "N debe ser 1, 2 o 3"; exit 1 ;;
esac
python "$D/run.py" fit "${ARGS[@]}" --list
python "$D/run.py" fit "${ARGS[@]}" --workers 4 --max-hours 8
python "$D/run.py" fit "${ARGS[@]}" --list
# Empaqueta SOLO las celdas de esta sesion (las de los modelos/familias pedidos)
cd "$D/results/cells"
case "$N" in
  1) PAT='*__RF.json.gz *__ANN_S.json.gz *__ANN_M.json.gz' ;;
  2) PAT='*__HS_RA__*__ANN_V2like.json.gz *__HG_RS__*__ANN_V2like.json.gz' ;;
  3) PAT='*__VALIANTZAS__*__ANN_V2like.json.gz' ;;
esac
python - "$OUT/celdas_sesion_$N.zip" $PAT <<'PY'
import glob, sys, zipfile
out, pats = sys.argv[1], sys.argv[2:]
files = sorted({f for p in pats for f in glob.glob(p)})
with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
    for f in files:
        z.write(f)
print(f"{len(files)} celdas empaquetadas en {out}")
PY
