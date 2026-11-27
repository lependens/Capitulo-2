#!/usr/bin/env bash
# Una sesion de Kaggle (CPU, sin acelerador, 4 nucleos, tope 12 h) del estudio 03.3. Uso (desde la raiz del repo):
#   bash studies/03_3_om_red_residual/kaggle_session.sh N
# N = 1: ANN_M de los 3 brazos (S0_res, S0_sin_alt, S0_res_sin_alt) x 12 particiones x 5 semillas
#        36 celdas, ~11 h de nucleo -> ~3-3,5 h con 4 procesos
#     0: todo lo que falte (Ridge, HGB, anidados y ANN_M); para continuar una sesion cortada o si lo local no cabe
# Se detiene al empezar celdas nuevas pasadas 8 h (margen para el tope de 12 h) y siempre empaqueta lo hecho.
# Reanudable: las celdas ya existentes (en el repo o recuperadas de salidas anteriores montadas como entrada) se saltan.
# Mismas versiones fijadas que el 03.2 (requirements.txt y check_env.py del 03.2). NO usa ningun token ni secreto.
set -uo pipefail
N="${1:?uso: kaggle_session.sh 0|1}"
D=studies/03_3_om_red_residual
D32=studies/03_2_loso_openmeteo_ml
OUT=/kaggle/working
mkdir -p "$OUT"
START=$(date +%s)
pip install -q -r "$D32/requirements.txt" || { echo "pip no pudo instalar las versiones fijadas"; exit 1; }
python "$D32/check_env.py" || exit 1
echo "nucleos: $(nproc)"
# Recupera celdas del 03.3 de salidas montadas (solo nombres de celda del 03.3)
python - "${KAGGLE_INPUT_DIR:-/kaggle/input}" "$D/results/cells" <<'PY'
import glob, os, re, shutil, sys, zipfile
src, dst = sys.argv[1], sys.argv[2]
pat = re.compile(r"^F[12]_[A-Za-z0-9]+(_informativo)?__(S0\+R1|S2\+R1|S0\+R1_ayer|S0_res|S0_sin_alt|S0_alt_recortada"
                 r"|S0_res_sin_alt|anidado_IB\d\d)__(Ridge|HGB|ANN_M)\.json\.gz$")
os.makedirs(dst, exist_ok=True)
n = 0
for z in glob.glob(os.path.join(src, "**", "celdas_03_3_sesion_*.zip"), recursive=True):
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
print(f"celdas del 03.3 recuperadas de sesiones anteriores: {n}")
PY
case "$N" in
  0) MODELS="" ;;
  1) MODELS=ANN_M ;;
  *) echo "N debe ser 0 o 1"; exit 1 ;;
esac
python "$D/run.py" fit --models "$MODELS" --list
python "$D/run.py" fit --models "$MODELS" --workers "$(nproc)" --max-hours 8
python "$D/run.py" fit --models "$MODELS" --list
# Empaqueta las celdas de la sesion (N=1: las de ANN_M; N=0: todas): cada salida es autosuficiente
python - "$OUT/celdas_03_3_sesion_$N.zip" "$D/results/cells" "$N" <<'PY'
import glob, os, sys, zipfile
out, cells, n = sys.argv[1], sys.argv[2], sys.argv[3]
files = sorted(glob.glob(os.path.join(cells, "*__ANN_M.json.gz" if n == "1" else "*.json.gz")))
with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
    for f in files:
        z.write(f, os.path.basename(f))
print(f"{len(files)} celdas empaquetadas en {out}")
PY
echo "duracion de la sesion: $(( ($(date +%s) - START) / 60 )) min"
