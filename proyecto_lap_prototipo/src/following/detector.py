"""YOLO preentrenado: devuelve cajas de personas en píxeles originales."""
from pathlib import Path
from types import SimpleNamespace

DEFAULT_WEIGHTS = Path(__file__).resolve().parents[2] / "models" / "yolo11n.pt"


class PersonDetector:
    def __init__(self, weights=None, image_size=640):
        if image_size not in (480,640,960):raise ValueError("Resolución de análisis inválida.")
        self.image_size=image_size
        from importlib.metadata import version
        if version("ultralytics") != "8.3.203":
            raise ValueError("La versión de seguimiento no coincide con el proyecto. Inicia con iniciar_sistema.ps1 o instala requirements-tracking.txt en este entorno.")
        import torch
        from ultralytics import YOLO

        path = Path(weights) if weights else DEFAULT_WEIGHTS
        if not path.is_file():
            raise ValueError("Falta el modelo de seguimiento. Ejecuta setup_tracking.py --download en el servidor.")
        torch.set_num_threads(min(2, torch.get_num_threads()))
        import cv2
        cv2.setNumThreads(2)
        self.model = YOLO(str(path), task="detect")
        if self.model.names.get(0) != "person":
            raise ValueError("El modelo debe incluir la clase person en el índice 0 (formato COCO).")

    def detect(self, frame):
        result = self.model.predict(frame, device="cpu", classes=[0], conf=.1,
                                    imgsz=self.image_size, max_det=500, verbose=False)[0]
        boxes = result.boxes.xyxy.cpu().tolist()
        scores = result.boxes.conf.cpu().tolist()
        detections = [SimpleNamespace(x=(b[0]+b[2])/2, y=b[3], confianza=s)
                      for b, s in zip(boxes, scores)]
        return detections, boxes
