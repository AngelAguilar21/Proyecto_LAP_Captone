"""Fast person detector used as the primary identity signal.

The detector deliberately exposes foot points as well as boxes.  Foot points
are the stable geometry used by the homography and line counters; boxes are
kept for overlays and the lightweight appearance signature.
"""
from dataclasses import dataclass
import math
from pathlib import Path


def clip_box(box, width, height):
    """Return a finite box clipped to the frame, or ``None`` if it is empty.

    Ultralytics normally clips its output, but trackers, alternate detector
    adapters and decoded video frames do not all make that guarantee. Keeping
    this invariant at the detector boundary prevents an out-of-frame box from
    contaminating the foot point, homography projection, Re-ID crop or overlay.
    """
    if box is None or width <= 0 or height <= 0:
        return None
    try:
        values = tuple(float(value) for value in box)
    except (TypeError, ValueError):
        return None
    if len(values) != 4 or not all(math.isfinite(value) for value in values):
        return None
    x1, y1, x2, y2 = values
    x1, x2 = max(0.0, min(float(width), x1)), max(0.0, min(float(width), x2))
    y1, y2 = max(0.0, min(float(height), y1)), max(0.0, min(float(height), y2))
    if x2 <= x1 or y2 <= y1:
        return None
    return (x1, y1, x2, y2)


@dataclass
class PersonDetection:
    x: float
    y: float
    confianza: float
    box: tuple
    appearance: object = None


class YoloPersonDetector:
    def __init__(self, weights, confidence=.25, imgsz=640, device=None, model_factory=None, iou=.5, half=False):
        weights = Path(weights)
        if not weights.is_file():
            raise FileNotFoundError(f"No se encontraron los pesos YOLO: {weights}")
        try:
            factory = model_factory
            if factory is None:
                from ultralytics import YOLO
                factory = YOLO
            self.model = factory(str(weights))
        except ImportError as exc:
            raise ImportError("Instala ultralytics para activar el detector YOLO11.") from exc
        self.confidence = float(confidence)
        self.imgsz = int(imgsz)
        # NMS más estricto que el 0.7 por defecto: en grupos evita cajas dobles de una misma persona.
        self.iou = float(iou)
        self.half = bool(half) and str(device or '').startswith('cuda')
        self.device = device

    @staticmethod
    def _convert(result):
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return []
        xyxy = boxes.xyxy.cpu().tolist() if hasattr(boxes.xyxy, "cpu") else boxes.xyxy.tolist()
        conf = boxes.conf.cpu().tolist() if hasattr(boxes.conf, "cpu") else boxes.conf.tolist()
        classes = boxes.cls.cpu().tolist() if hasattr(boxes.cls, "cpu") else boxes.cls.tolist()
        shape = getattr(result, "orig_shape", None)
        if shape is None:
            original = getattr(result, "orig_img", None)
            shape = getattr(original, "shape", None)
        height, width = (shape[:2] if shape is not None and len(shape) >= 2 else (None, None))
        output = []
        for box, score, category in zip(xyxy, conf, classes):
            if int(category) != 0:
                continue
            if width and height:
                cleaned = clip_box(box, width, height)
            else:
                try:
                    cleaned = tuple(float(value) for value in box)
                except (TypeError, ValueError):
                    cleaned = None
                if cleaned is not None and (len(cleaned) != 4
                                             or not all(math.isfinite(value) for value in cleaned)
                                             or cleaned[2] <= cleaned[0] or cleaned[3] <= cleaned[1]):
                    cleaned = None
            if cleaned is None:
                continue
            x1, y1, x2, y2 = cleaned
            output.append(PersonDetection((x1 + x2) / 2, y2, float(score), (x1, y1, x2, y2)))
        return output

    def detectar_lote(self, frames_bgr):
        kwargs = {"source": frames_bgr, "classes": [0], "conf": self.confidence,
                  "imgsz": self.imgsz, "iou": self.iou, "verbose": False}
        if self.device:
            kwargs["device"] = self.device
        if self.half:
            kwargs["half"] = True
        results = self.model.predict(**kwargs)
        return [self._convert(result) for result in results]

    def detectar(self, frame_bgr):
        return self.detectar_lote([frame_bgr])[0]
