"""Seguimiento de personas: detector, asociación temporal y apariencia."""
import os
from pathlib import Path

# Configuración local al proyecto; evita escribir preferencias en el perfil del usuario.
os.environ.setdefault("YOLO_CONFIG_DIR", str(Path(__file__).resolve().parents[2] / "config" / "ultralytics"))
os.environ.setdefault("YOLO_AUTOINSTALL", "false")
