#!/usr/bin/env bash
# Ajuste de las celdas pesadas del 03.1 (RF, ANN_S, ANN_M, ANN_V2like) en el servidor.
# Reanudable: las celdas ya hechas (results/cells/) se saltan. Uso, desde la raiz del repo:
#   bash studies/03_1_loso_inputs_siar/run_server.sh [WORKERS]
set -euo pipefail
WORKERS="${1:-4}"
D=studies/03_1_loso_inputs_siar
if [ ! -d .venv-03 ]; then
  python3 -m venv .venv-03
  .venv-03/bin/pip install -r "$D/requirements.txt"
fi
.venv-03/bin/python "$D/run.py" fit \
  --models RF,ANN_S,ANN_M,ANN_V2like --workers "$WORKERS"
.venv-03/bin/python "$D/run.py" report
echo "Hecho. Revisa $D/results/ y haz commit en la rama."
