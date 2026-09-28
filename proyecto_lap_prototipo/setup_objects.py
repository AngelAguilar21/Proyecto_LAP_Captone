"""Prepara pesos oficiales para la señal opcional de objetos, sin entrenamiento."""
import argparse
import os
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--download',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    os.environ.setdefault('YOLO_CONFIG_DIR',str(root/'data/ultralytics'))
    from ultralytics import YOLO
    target=root/'models/yolo11n.pt'
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.is_file():
        if not args.download:
            raise SystemExit('Faltan pesos. Ejecuta setup_objects.py --download.')
        from ultralytics.utils.downloads import attempt_download_asset
        attempt_download_asset(str(target))
    model=YOLO(str(target))
    if model.names.get(0)!='person' or model.names.get(26)!='handbag':
        raise SystemExit('El modelo no contiene las clases esperadas.')
    print('Detector opcional de objetos preparado. No confirma compras.')


if __name__=='__main__':
    main()
