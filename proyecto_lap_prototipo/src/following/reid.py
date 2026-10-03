"""Embeddings de apariencia OSNet para reidentificación entre cámaras.

El vector describe ropa, silueta y textura; no identifica a nadie. Se calcula en
memoria, no se guarda en disco ni se publica y se descarta junto con el ID
temporal.

OSNet se ejecuta con onnxruntime a partir de un archivo .onnx local. Si el
modelo no existe o no carga, `OSNetEmbedder.available` es False y el sistema
sigue con la firma de color (torso_histogram), sin detener el monitoreo.
"""
import os
from pathlib import Path

import cv2
import numpy as np

DEFAULT_MODEL = Path(__file__).resolve().parents[2] / "models" / "osnet.onnx"
MODEL_ENV = "AEROTRACK_OSNET_MODEL"
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
MIN_CROP_PX = 12


def resolve_model_path(configured=None):
    """Orden: ruta de la configuración, variable de entorno, models/osnet.onnx."""
    for candidate in (configured, os.environ.get(MODEL_ENV), DEFAULT_MODEL):
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    return None


class OSNetEmbedder:
    def __init__(self, model_path=None, providers=None):
        self.session = None
        self.error = None
        self.batch = None
        self.size = (128, 256)  # (ancho, alto) de entrada habitual de OSNet
        path = resolve_model_path(model_path)
        if path is None:
            self.error = "Sin modelo OSNet (.onnx): se usa la firma de color."
            return
        try:
            import onnxruntime as ort
            self.session = ort.InferenceSession(str(path), providers=providers or ["CPUExecutionProvider"])
            shape = self.session.get_inputs()[0].shape
            if len(shape) == 4 and all(isinstance(v, int) and v > 0 for v in shape[2:]):
                self.size = (int(shape[3]), int(shape[2]))
            self.input_name = self.session.get_inputs()[0].name
            self.batch = shape[0] if isinstance(shape[0], int) and shape[0] > 0 else None
        except Exception as exc:  # onnxruntime lanza tipos propios según el fallo
            self.session = None
            self.error = f"No se pudo cargar OSNet: {exc}"

    @property
    def available(self):
        return self.session is not None

    def _crop(self, frame, box):
        height, width = frame.shape[:2]
        x1, y1, x2, y2 = box
        x1, x2 = max(0, int(x1)), min(width, int(x2))
        y1, y2 = max(0, int(y1)), min(height, int(y2))
        if x2 - x1 < MIN_CROP_PX or y2 - y1 < MIN_CROP_PX:
            return None
        rgb = cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, self.size, interpolation=cv2.INTER_LINEAR)
        return ((resized.astype(np.float32) / 255. - MEAN) / STD).transpose(2, 0, 1)

    def embed(self, frame, boxes):
        """Devuelve un vector L2-normalizado por caja (None si el recorte es inválido)."""
        if not self.available or not boxes:
            return [None] * len(boxes)
        crops = [self._crop(frame, box) if box is not None else None for box in boxes]
        valid = [i for i, crop in enumerate(crops) if crop is not None]
        result = [None] * len(boxes)
        if not valid:
            return result
        batch = np.stack([crops[i] for i in valid])
        # Algunos exports ONNX fijan el tamaño de lote: se procesa por bloques con relleno.
        step = self.batch or len(batch)
        try:
            chunks = []
            for start in range(0, len(batch), step):
                part = batch[start:start + step]
                if self.batch and len(part) < self.batch:
                    part = np.concatenate([part, np.zeros((self.batch - len(part), *part.shape[1:]), np.float32)])
                chunks.append(self.session.run(None, {self.input_name: part})[0][:min(step, len(batch) - start)])
            output = np.concatenate(chunks)
        except Exception as exc:  # un fallo de inferencia no debe parar el monitoreo
            self.session, self.error = None, f"OSNet desactivado: {exc}"
            return result
        output = np.asarray(output, dtype=np.float32).reshape(len(valid), -1)
        norms = np.linalg.norm(output, axis=1, keepdims=True)
        output = output / np.maximum(norms, 1e-9)
        for row, i in zip(output, valid):
            result[i] = row
        return result


def _iou(a, b):
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0., ix2 - ix1) * max(0., iy2 - iy1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.


def occluded_ids(tracks, threshold=.2):
    """IDs de tracks cuyo recuadro se solapa con el de otra persona.

    En grupos el recorte incluye ropa del vecino y el embedding resultante mezcla
    a dos personas: es mejor conservar el último embedding limpio que actualizarlo.
    """
    boxes = [(tr.id, tr.ultima_caja) for tr in tracks if tr.ultima_caja is not None]
    blocked = set()
    for i, (ida, a) in enumerate(boxes):
        for idb, b in boxes[i + 1:]:
            if _iou(a, b) > threshold:
                blocked.update((ida, idb))
    return blocked


class EmbeddingScheduler:
    """Decide cuándo recalcular el embedding de un track para limitar la latencia.

    Se calcula al crear el track, cada `interval` frames, y de inmediato si la
    confianza del track es baja o aún no tiene embedding.
    """
    def __init__(self, interval=8, low_score=.5):
        self.interval = max(1, int(interval))
        self.low_score = low_score
        self.state = {}

    def due(self, track_id, frame_index, score):
        last = self.state.get(track_id)
        if last is None or last["vec"] is None:
            return True
        return frame_index - last["frame"] >= self.interval or score < self.low_score

    def store(self, track_id, frame_index, vec):
        if vec is not None:
            self.state[track_id] = {"frame": frame_index, "vec": vec}
        elif track_id not in self.state:
            self.state[track_id] = {"frame": frame_index, "vec": None}

    def get(self, track_id):
        entry = self.state.get(track_id)
        return None if entry is None else entry["vec"]

    def prune(self, live_ids):
        self.state = {k: v for k, v in self.state.items() if k in live_ids}
