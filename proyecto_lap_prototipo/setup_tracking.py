"""Instala los pesos oficiales: python setup_tracking.py --download."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import os

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / "config" / "ultralytics"))
URL = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Descargar los pesos oficiales si faltan")
    args = parser.parse_args()
    target = ROOT / "models" / "yolo11n.pt"
    if not target.exists():
        if not args.download:
            parser.error("Faltan pesos; añade --download para descargarlos.")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".download")
        try:
            urllib.request.urlretrieve(URL, tmp)
            if tmp.stat().st_size < 1_000_000:
                raise ValueError("Descarga incompleta del modelo")
            tmp.replace(target)
        finally:
            tmp.unlink(missing_ok=True)
    from ultralytics import YOLO
    import numpy as np
    import torch
    torch.set_num_threads(4)
    model = YOLO(str(target))
    if model.names.get(0) != "person":
        raise ValueError("El archivo no corresponde al detector de personas esperado.")
    model.predict(np.zeros((320, 320, 3), dtype=np.uint8), device="cpu", verbose=False)
    manifest = {"model": "YOLO11n", "dataset": "COCO", "url": URL,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    target.with_suffix(".json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print("Modelo de seguimiento disponible. Inferencia CPU verificada.")


if __name__ == "__main__":
    main()
