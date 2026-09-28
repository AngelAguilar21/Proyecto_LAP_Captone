"""
Deteccion de cabezas por frame con P2PNet (arXiv:2107.12746).

No se reimplementa la red: se usa el repo oficial como submodulo git en
external/P2PNet (Tencent Youtu Research). Setup necesario antes de usar
esta clase:

    git submodule update --init proyecto_lap_prototipo/external/P2PNet
    python proyecto_lap_prototipo/src/aplicar_parche_p2pnet.py
    # El checkpoint preentrenado (external/P2PNet/weights/SHTechA.pth) ya
    # viene incluido en el repo oficial, no hace falta descargarlo aparte.

El preprocesamiento (resize a multiplos de 128, normalizacion ImageNet) y el
umbral de confianza (0.5 por defecto) siguen exactamente run_test.py del
repo oficial, para no desviarnos de como fue entrenado el modelo.
"""
import sys
import os
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch
from PIL import Image
from torchvision import transforms

_RUTA_P2PNET = Path(__file__).resolve().parent.parent / "external" / "P2PNet"
if str(_RUTA_P2PNET) not in sys.path:
    sys.path.insert(0, str(_RUTA_P2PNET))


@dataclass
class DeteccionCabeza:
    x: float
    y: float
    confianza: float


class DetectorP2PNet:
    def __init__(self, ruta_pesos: str, backbone: str = "vgg16_bn", row: int = 2,
                 line: int = 2, umbral: float = 0.5, device: str = None,
                 lado_max: int = None):
        try:
            from models import build_model  # noqa: viene del submodulo external/P2PNet
        except ImportError as exc:
            raise ImportError(
                "No se encontro el submodulo de P2PNet. Corre:\n"
                "  git submodule update --init proyecto_lap_prototipo/external/P2PNet\n"
                "y descarga un checkpoint preentrenado antes de instanciar DetectorP2PNet."
            ) from exc

        self.umbral = umbral
        # En CPU el costo crece con el area del frame y las camaras se procesan una tras
        # otra, asi que en vivo conviene acotar el lado mayor. Se limita el lado MAYOR y no
        # el ancho porque los videos de celular llegan verticales: ahi el lado caro es el
        # alto. None = resolucion original.
        self.lado_max = lado_max
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        if self.device == "cpu":
            # Evitar que cada lote pequeño ocupe todos los hilos del equipo.
            # Coincide con el límite del motor de conteo independiente.
            torch.set_num_threads(max(1, min(4, (os.cpu_count() or 2)//2)))

        args = SimpleNamespace(backbone=backbone, row=row, line=line,
                                weight_path=ruta_pesos, gpu_id=0)
        self.modelo = build_model(args, training=False)

        checkpoint = torch.load(ruta_pesos, map_location=self.device)
        estado = checkpoint["model"] if isinstance(checkpoint, dict) and "model" in checkpoint else checkpoint
        self.modelo.load_state_dict(estado)
        self.modelo.to(self.device)
        self.modelo.eval()

        self._transformar = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    def _preparar_frame(self, frame_bgr: np.ndarray):
        frame_rgb = frame_bgr[:, :, ::-1]
        alto, ancho = frame_rgb.shape[:2]
        objetivo_ancho, objetivo_alto = ancho, alto
        if self.lado_max and max(ancho, alto) > self.lado_max:
            escala = self.lado_max / max(ancho, alto)
            objetivo_ancho = max(1, round(ancho * escala))
            objetivo_alto = max(1, round(alto * escala))
        # La red exige lados multiplos de 128; se redondea hacia abajo pero sin bajar de 128.
        nuevo_ancho = max(128, objetivo_ancho // 128 * 128)
        nuevo_alto = max(128, objetivo_alto // 128 * 128)
        imagen = Image.fromarray(frame_rgb).resize((nuevo_ancho, nuevo_alto), Image.LANCZOS)
        escala_x = ancho / nuevo_ancho
        escala_y = alto / nuevo_alto
        tensor = self._transformar(imagen).unsqueeze(0).to(self.device)
        return tensor, escala_x, escala_y

    @torch.inference_mode()
    def detectar_lote(self, frames_bgr):
        """Procesa juntas las cámaras que terminan con el mismo tamaño de tensor.

        P2PNet acepta lotes. Agrupar aquí evita recorrer la red completa una vez
        por cámara cuando dos fuentes comparten resolución, que es el caso común
        del monitoreo sincronizado.
        """
        prepared = [self._preparar_frame(frame) for frame in frames_bgr]
        results = [None] * len(prepared)
        groups = {}
        for index, (tensor, scale_x, scale_y) in enumerate(prepared):
            groups.setdefault(tuple(tensor.shape), []).append((index, tensor, scale_x, scale_y))
        for group in groups.values():
            batch = torch.cat([item[1] for item in group], dim=0)
            output = self.modelo(batch)
            for batch_index, (result_index, _, scale_x, scale_y) in enumerate(group):
                probabilities = torch.softmax(output["pred_logits"][batch_index], dim=-1)[:, 1]
                points = output["pred_points"][batch_index]
                mask = probabilities > self.umbral
                valid_points = points[mask].cpu().numpy()
                confidence = probabilities[mask].cpu().numpy()
                results[result_index] = [
                    DeteccionCabeza(x=float(px * scale_x), y=float(py * scale_y), confianza=float(score))
                    for (px, py), score in zip(valid_points, confidence)
                ]
        return results

    def detectar(self, frame_bgr: np.ndarray):
        """Devuelve detecciones en píxeles del frame original."""
        return self.detectar_lote([frame_bgr])[0]
