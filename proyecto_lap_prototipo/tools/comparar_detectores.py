"""Comparación reproducible de latencia; no estima precisión sin anotaciones."""
import argparse
import hashlib
import json
import statistics
import time
from pathlib import Path


def main():
    import cv2
    import torch
    import ultralytics
    from ultralytics import YOLO
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--cameras', nargs='+', required=True)
    parser.add_argument('--models', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', type=int, default=640)
    args = parser.parse_args()
    torch.set_num_threads(4)
    config = json.loads(args.config.read_text(encoding='utf-8'))
    frames = []
    for camera in config['cameras']:
        if camera['id'] not in args.cameras:
            continue
        capture = cv2.VideoCapture(camera['source'])
        try:
            for second in (0, 5, 10, 20, 30):
                capture.set(cv2.CAP_PROP_POS_MSEC, second * 1000)
                ok, frame = capture.read()
                if ok:
                    frames.append((camera['id'], second, frame))
        finally:
            capture.release()
    if not frames:
        raise ValueError('No se pudieron leer cuadros.')
    report = {'runtime': ultralytics.__version__, 'device': 'cpu', 'threads': 4,
              'imgsz': args.size, 'precisionEvaluated': False, 'models': []}
    for path in args.models:
        model = YOLO(str(path))
        model.predict(frames[0][2], imgsz=args.size, device='cpu', verbose=False)
        rows = []
        for camera, second, frame in frames:
            start = time.perf_counter()
            result = model.predict(frame, imgsz=args.size, device='cpu', classes=[0], conf=0.25, verbose=False)[0]
            rows.append({'camera': camera, 'second': second, 'ms': (time.perf_counter()-start)*1000,
                         'people': len(result.boxes)})
        with path.open('rb') as stream:
            checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
        report['models'].append({'name': path.name, 'sha256': checksum,
                                 'medianMs': statistics.median(r['ms'] for r in rows), 'samples': rows})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({r['name']: round(r['medianMs'], 2) for r in report['models']}))


if __name__ == '__main__':
    main()
