"""Comprueba que el entorno tiene EXACTAMENTE las versiones fijadas en requirements.txt (si no, se detiene).

Uso: python studies/03_2_loso_openmeteo_ml/check_env.py
Importa: numpy, pandas, scikit-learn, matplotlib. Las versiones fijadas no se relajan para que las celdas de
distintas maquinas sean comparables."""
import importlib.metadata as md
import sys
from pathlib import Path

bad = []
for line in (Path(__file__).with_name("requirements.txt")).read_text().split():
    name, _, want = line.partition("==")
    try:
        have = md.version(name)
    except md.PackageNotFoundError:
        have = None
    print(f"{name}: pedido {want}, instalado {have}")
    if have != want:
        bad.append(name)
print("python", sys.version.split()[0])
if bad:
    raise SystemExit(f"VERSIONES DISTINTAS en {bad}. Se para: no se relajan las versiones fijadas.")
print("Entorno OK")
