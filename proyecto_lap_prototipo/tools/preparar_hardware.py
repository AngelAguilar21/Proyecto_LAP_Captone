"""Muestra el perfil de hardware elegido y descarga los modelos que le faltan.

Uso (desde proyecto_lap_prototipo):
    python tools/preparar_hardware.py              # solo informa
    python tools/preparar_hardware.py --download   # baja los pesos YOLO recomendados
    python tools/preparar_hardware.py --osnet      # baja models/osnet.onnx si falta

Los modelos no se descargan solos al iniciar el servidor: este script es el paso explícito.
La descarga de YOLO usa ultralytics (pesos oficiales); OSNet viene del export ONNX
publicado en https://huggingface.co/anriha/osnet_x0_25_msmt17 (tercero, revisa su licencia).
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import hardware  # noqa: E402

OSNET_URL = "https://huggingface.co/anriha/osnet_x0_25_msmt17/resolve/main/osnet_x0_25_msmt17.onnx"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--osnet", action="store_true")
    ap.add_argument("--elevated", action="store_true", help="calcular el perfil para cámaras a 3 m o más")
    args = ap.parse_args()

    info = hardware.detect()
    profile = hardware.choose({}, args.elevated, info)
    print(json.dumps({"equipo": info, "perfil": {k: v for k, v in profile.items() if k != "summary"}}, indent=2, ensure_ascii=False))
    if profile["hint"]:
        print("\nAviso:", profile["hint"])

    if args.download:
        wanted = hardware.TIERS[profile["tier"]][0]
        target = hardware.MODELS / wanted
        if target.is_file():
            print(f"\n{wanted} ya existe.")
        else:
            from ultralytics import YOLO
            hardware.MODELS.mkdir(parents=True, exist_ok=True)
            YOLO(str(target))  # ultralytics descarga los pesos oficiales a esa ruta
            print(f"\nDescargado: {target}")
    elif profile["missingWeights"]:
        print(f"\nFalta {profile['missingWeights']}. Se usará {Path(profile['weights']).name}. Ejecuta con --download para obtenerlo.")

    if args.osnet:
        target = hardware.MODELS / "osnet.onnx"
        if target.is_file():
            print("osnet.onnx ya existe.")
        else:
            hardware.MODELS.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(OSNET_URL, target)
            print(f"Descargado: {target} ({target.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
