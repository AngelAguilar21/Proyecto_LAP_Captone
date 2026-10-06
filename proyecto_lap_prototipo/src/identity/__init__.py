"""Identidad entre cámaras: tracklets, vistas confiables, asociador, memoria de apariencia y reagrupación al cerrar.

Ver src/identity/engine.py (motor) y docs/EVALUACION_IDENTIDAD.md (cómo se mide). Solo numpy y cv2.
"""
from .associator import AsociadorMulticamara, cargar_registro
from .engine import MotorIdentidadV2, crear_motor_identidad, registro_desde_config
from .memory import AsociadorConMemoria, MemoriaApariencia
from .quality import recortar, vistas_confiables
from .tracklet import Tracklet, se_solapan
