#!/usr/bin/env bash
# Una sesion de Kaggle (CPU, sin acelerador, 4 nucleos, tope 12 h) del estudio 03.2. Uso (desde la raiz del repo):
#   bash studies/03_loso_openmeteo_ml/kaggle_session.sh N
# Reparto en 4 sesiones paralelas (la cuenta admite 4 a la vez), sin solaparse:
# N = 1: RF, F1 IB01-IB05                                30 celdas, ~10-11 h de nucleo -> ~3 h
#     2: RF, F1 IB06, IB08, IB10, IB11 y las 3 de F2     42 celdas, ~12-13 h de nucleo -> ~3,5 h
#     3: ANN_S, todas las particiones y escenarios       72 celdas, ~7-9 h de nucleo   -> ~2-2,5 h
#     4: ANN_M, todas las particiones y escenarios       72 celdas, ~8-11 h de nucleo  -> ~2,5-3 h
#     0: todo lo pesado que falte (RF, ANN_S, ANN_M); para versiones de continuacion
# Se detiene al empezar celdas nuevas pasadas 8 h (margen para el tope de 12 h) y siempre empaqueta lo hecho.
# Reanudable: las celdas ya existentes (en el repo o recuperadas de salidas anteriores) se saltan.
# Para continuar: nueva version del cuaderno con la salida anterior montada como entrada (Add Input -> Notebook
# output). NO usa ningun token ni secreto. Ridge y HGB no se ejecutan aqui: ya estan en results/cells/.
set -uo pipefail
N="${1:?uso: kaggle_session.sh 0|1|2|3|4}"
D=studies/03_loso_openmeteo_ml
OUT=/kaggle/working
mkdir -p "$OUT"
START=$(date +%s)
pip install -q -r "$D/requirements.txt" || { echo "pip no pudo instalar las versiones fijadas"; exit 1; }
python "$D/check_env.py" || exit 1
echo "nucleos: $(nproc)"
# Recupera celdas del 03.2 de salidas montadas (solo nombres de celda del 03.2; las del 03.1 se ignoran)
python - "${KAGGLE_INPUT_DIR:-/kaggle/input}" "$D/results/cells" <<'PY'
import glob, os, re, shutil, sys, zipfile
src, dst = sys.argv[1], sys.argv[2]
pat = re.compile(r"^F[12]_[A-Za-z0-9]+(_informativo)?__(S0|S1|S2|L1|L2|S0_coord)__(Ridge|HGB|RF|ANN_S|ANN_M)\.json\.gz$")
os.makedirs(dst, exist_ok=True)
n = 0
for z in glob.glob(os.path.join(src, "**", "celdas_03_2_sesion_*.zip"), recursive=True):
    with zipfile.ZipFile(z) as zf:
        for name in zf.namelist():
            base = os.path.basename(name)
            if pat.match(base) and not os.path.exists(os.path.join(dst, base)):
                with zf.open(name) as a, open(os.path.join(dst, base), "wb") as b:
                    shutil.copyfileobj(a, b)
                n += 1
for f in glob.glob(os.path.join(src, "**", "*.json.gz"), recursive=True):
    base = os.path.basename(f)
    if pat.match(base) and not os.path.exists(os.path.join(dst, base)):
        shutil.copy(f, os.path.join(dst, base)); n += 1
print(f"celdas del 03.2 recuperadas de sesiones anteriores: {n}")
PY
FOLDS=""
case "$N" in
  0) MODELS=RF,ANN_S,ANN_M ;;
  1) MODELS=RF; FOLDS=F1_IB01,F1_IB02,F1_IB03,F1_IB04,F1_IB05 ;;
  2) MODELS=RF; FOLDS=F1_IB06,F1_IB08,F1_IB10,F1_IB11,F2_island ;;
  3) MODELS=ANN_S ;;
  4) MODELS=ANN_M ;;
  *) echo "N debe ser 0, 1, 2, 3 o 4"; exit 1 ;;
esac
python "$D/run.py" fit --models "$MODELS" --folds "$FOLDS" --list
python "$D/run.py" fit --models "$MODELS" --folds "$FOLDS" --workers "$(nproc)" --max-hours 8
python "$D/run.py" fit --models "$MODELS" --folds "$FOLDS" --list
# Empaqueta TODAS las celdas pesadas presentes (las recuperadas tambien): cada salida es autosuficiente
python - "$OUT/celdas_03_2_sesion_$N.zip" "$D/results/cells" <<'PY'
import glob, os, sys, zipfile
out, cells = sys.argv[1], sys.argv[2]
files = sorted(f for m in ("RF", "ANN_S", "ANN_M") for f in glob.glob(os.path.join(cells, f"*__{m}.json.gz")))
with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
    for f in files:
        z.write(f, os.path.basename(f))
print(f"{len(files)} celdas empaquetadas en {out}")
PY
echo "duracion de la sesion: $(( ($(date +%s) - START) / 60 )) min"
