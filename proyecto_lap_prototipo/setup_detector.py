"""Prepare the official small YOLO person detector used by AeroTrack.

Run explicitly: python setup_detector.py --download
Model downloads occur only in this setup command, never implicitly in the server.
"""
import argparse
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download',action='store_true',help='Allow downloading official Ultralytics YOLO11n weights.')
    args=parser.parse_args()
    model=Path(__file__).resolve().parent/'models'/'yolo11n.pt'
    if not model.exists() and not args.download:
        raise SystemExit('Faltan los pesos. Ejecuta este comando con --download para prepararlos.')
    from ultralytics import YOLO
    model.parent.mkdir(parents=True,exist_ok=True)
    detector=YOLO(str(model))
    if detector.names.get(0)!='person':
        raise SystemExit('El modelo no tiene la clase person esperada.')
    print(f'Detector disponible: {model}')


if __name__=='__main__':
    main()
