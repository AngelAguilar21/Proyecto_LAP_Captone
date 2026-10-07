"""Detecta CPU, RAM y GPU del equipo y elige un perfil de inferencia.

La misma instalación corre en una laptop modesta y en una estación con GPU. El
perfil decide modelo YOLO, resolución, precisión (FP16) y proveedor de OSNet para
aprovechar cada equipo sin que el operador tenga que configurarlo.

Los umbrales de cada nivel son criterios de diseño, no mediciones: no se midió
la velocidad en cada GPU. Se pueden forzar con config["hardware"] = "cpu" | "gpu"
o con config["yoloWeights"] / config["yoloImgsz"].
"""
import ctypes
import os
import shutil
import subprocess
from pathlib import Path

MODELS = Path(__file__).resolve().parents[1] / "models"
# Nivel -> (pesos preferidos, resolución base, resolución con cámaras elevadas, FP16, intervalo OSNet)
TIERS = {
    "gpu_alta": ("yolo11m.pt", 1280, 1920, True, 4),
    "gpu_media": ("yolo11s.pt", 1280, 1280, True, 6),
    "gpu_baja": ("yolo11n.pt", 960, 1280, True, 8),
    "cpu": ("yolo11n.pt", 960, 1280, False, 8),
}


def _ram_gb():
    try:
        import psutil
        return psutil.virtual_memory().total / 2 ** 30
    except ImportError:
        pass
    if os.name == "nt":
        class Status(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                        ("avail", ctypes.c_ulonglong), ("pt", ctypes.c_ulonglong), ("pa", ctypes.c_ulonglong),
                        ("vt", ctypes.c_ulonglong), ("va", ctypes.c_ulonglong), ("ve", ctypes.c_ulonglong)]
        status = Status(length=ctypes.sizeof(Status))
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return status.total / 2 ** 30
    return 0.


def _nvidia_smi():
    """Nombre y VRAM (GB) de la primera GPU NVIDIA, o None si no hay controlador."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5).stdout.strip().splitlines()
        name, mem = [v.strip() for v in out[0].rsplit(",", 1)]
        return name, float(mem) / 1024
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def detect():
    """Capacidades del equipo. Nunca falla: lo que no se pueda leer queda vacío."""
    info = {"cpuThreads": os.cpu_count() or 1, "ramGb": round(_ram_gb(), 1), "gpu": None, "vramGb": 0.,
            "cudaTorch": False, "ortProviders": ["CPUExecutionProvider"], "hint": None}
    smi = _nvidia_smi()
    if smi:
        info["gpu"], info["vramGb"] = smi[0], round(smi[1], 1)
    try:
        import torch
        info["cudaTorch"] = bool(torch.cuda.is_available())
        if info["cudaTorch"] and not info["gpu"]:
            info["gpu"] = torch.cuda.get_device_name(0)
            info["vramGb"] = round(torch.cuda.get_device_properties(0).total_memory / 2 ** 30, 1)
    except ImportError:
        pass
    try:
        import onnxruntime
        info["ortProviders"] = onnxruntime.get_available_providers()
    except ImportError:
        pass
    if info["gpu"] and not info["cudaTorch"]:
        info["hint"] = (f"Se detectó {info['gpu']}, pero PyTorch no tiene CUDA: instala una versión CUDA de torch "
                        "(pytorch.org) para usar la GPU. Mientras tanto se usa la CPU.")
    return info


def tier_for(info):
    if info["cudaTorch"]:
        return "gpu_alta" if info["vramGb"] >= 16 else "gpu_media" if info["vramGb"] >= 6 else "gpu_baja"
    return "cpu"


def choose(config=None, elevated=False, info=None, models_dir=MODELS):
    """Perfil de inferencia: {tier, device, weights, imgsz, half, osnetProviders, osnetInterval, ...}."""
    config = config or {}
    info = info or detect()
    mode = str(config.get("hardware", "auto")).lower()
    tier = tier_for(info) if mode == "auto" else ("cpu" if mode == "cpu" else tier_for(info) if info["cudaTorch"] else "cpu")
    wanted, size, size_elevated, half, interval = TIERS[tier]
    explicit = config.get("yoloWeights")
    weights, missing = Path(models_dir) / (explicit or wanted), None
    if not weights.is_file():
        missing = weights.name
        # Cadena de respaldo: el mejor modelo disponible localmente, nunca una descarga implícita.
        order = [w for w in ("yolo11m.pt", "yolo11s.pt", "yolo11n.pt") if (Path(models_dir) / w).is_file()]
        weights = Path(models_dir) / (order[-1] if tier.startswith("cpu") else order[0]) if order else weights
    on_gpu = tier != "cpu"
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if on_gpu and "CUDAExecutionProvider" in info["ortProviders"] else ["CPUExecutionProvider"]
    requested = str(config.get("reidProvider", "auto"))
    provider_names = {"cpu": "CPUExecutionProvider", "cuda": "CUDAExecutionProvider",
                      "openvino": "OpenVINOExecutionProvider", "directml": "DmlExecutionProvider"}
    provider_hint = None
    if requested != "auto":
        wanted_provider = provider_names.get(requested)
        if wanted_provider is None:
            raise ValueError("Proveedor ReID inválido.")
        if wanted_provider in info["ortProviders"]:
            providers = [wanted_provider] + ([] if requested == "cpu" else ["CPUExecutionProvider"])
        else:
            providers = ["CPUExecutionProvider"]
            provider_hint = f"{requested} no está instalado; ReID usa CPU."
    hilos = config.get("reidThreads") or (None if on_gpu else max(1, min(4, (info["cpuThreads"] or 2) // 2)))
    return {"tier": tier, "device": "cuda:0" if on_gpu else "cpu", "weights": str(weights), "missingWeights": missing,
            "imgsz": int(config.get("yoloImgsz") or (size_elevated if elevated else size)), "half": half and on_gpu,
            "osnetProviders": providers, "osnetInterval": interval, "hint": provider_hint or info["hint"],
            # En CPU un tope de hilos evita que OSNet se pelee con el resto (medido en un i5 de 8 hilos, lote de 16: 461 ms con 1 hilo,
            # 219 con 2, 163 con 4 y 271 con 8). Se puede fijar con reidThreads.
            "osnetThreads": int(hilos) if hilos else None,
            "summary": {"cpuThreads": info["cpuThreads"], "ramGb": info["ramGb"], "gpu": info["gpu"], "vramGb": info["vramGb"]}}
