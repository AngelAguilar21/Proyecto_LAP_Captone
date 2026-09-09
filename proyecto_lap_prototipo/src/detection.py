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
                 line: int = 2, umbral: float = 0.5, device: str = None):
        try:
            from models import build_model  # noqa: viene del submodulo external/P2PNet
        except ImportError as exc:
            raise ImportError(
                "No se encontro el submodulo de P2PNet. Corre:\n"
                "  git submodule update --init proyecto_lap_prototipo/external/P2PNet\n"
                "y descarga un checkpoint preentrenado antes de instanciar DetectorP2PNet."
            ) from exc

        self.umbral = umbral
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

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
        nuevo_ancho = max(128, round(ancho / 128) * 128)
        nuevo_alto = max(128, round(alto / 128) * 128)
        imagen = Image.fromarray(frame_rgb).resize((nuevo_ancho, nuevo_alto), Image.LANCZOS)
        escala_x = ancho / nuevo_ancho
        escala_y = alto / nuevo_alto
        tensor = self._transformar(imagen).unsqueeze(0).to(self.device)
        return tensor, escala_x, escala_y

    @torch.no_grad()
    def detectar(self, frame_bgr: np.ndarray):
        """frame_bgr: frame de OpenCV (BGR, HxWx3). Devuelve una lista de
        DeteccionCabeza en coordenadas de pixel del frame original."""
        tensor, escala_x, escala_y = self._preparar_frame(frame_bgr)
        salida = self.modelo(tensor)

        probabilidades = torch.softmax(salida["pred_logits"], dim=-1)[0, :, 1]
        puntos = salida["pred_points"][0]

        mascara = probabilidades > self.umbral
        puntos_validos = puntos[mascara].cpu().numpy()
        confianzas = probabilidades[mascara].cpu().numpy()

        return [
            DeteccionCabeza(x=float(px * escala_x), y=float(py * escala_y), confianza=float(c))
            for (px, py), c in zip(puntos_validos, confianzas)
        ]
