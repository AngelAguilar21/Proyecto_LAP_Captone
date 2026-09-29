"""Fast person detector used as the primary identity signal.

The detector deliberately exposes foot points as well as boxes.  Foot points
are the stable geometry used by the homography and line counters; boxes are
kept for overlays and the lightweight appearance signature.
"""
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PersonDetection:
    x: float
    y: float
    confianza: float
    box: tuple


class YoloPersonDetector:
    def __init__(self, weights, confidence=.25, imgsz=640, device=None, model_factory=None):
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
        self.device = device

    @staticmethod
    def _convert(result):
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return []
        xyxy = boxes.xyxy.cpu().tolist() if hasattr(boxes.xyxy, "cpu") else boxes.xyxy.tolist()
        conf = boxes.conf.cpu().tolist() if hasattr(boxes.conf, "cpu") else boxes.conf.tolist()
        classes = boxes.cls.cpu().tolist() if hasattr(boxes.cls, "cpu") else boxes.cls.tolist()
        output = []
        for box, score, category in zip(xyxy, conf, classes):
            if int(category) != 0:
                continue
            x1, y1, x2, y2 = [float(value) for value in box]
            output.append(PersonDetection((x1 + x2) / 2, y2, float(score), (x1, y1, x2, y2)))
        return output

    def detectar_lote(self, frames_bgr):
        kwargs = {"source": frames_bgr, "classes": [0], "conf": self.confidence,
                  "imgsz": self.imgsz, "verbose": False}
        if self.device:
            kwargs["device"] = self.device
        results = self.model.predict(**kwargs)
        return [self._convert(result) for result in results]

    def detectar(self, frame_bgr):
        return self.detectar_lote([frame_bgr])[0]
