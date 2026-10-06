"""Mide la precisión de detección contra una secuencia MOT20 en tres puntos del pipeline.

Reproduce, cuadro a cuadro, el camino de live_server.run para una cámara: redimensionado,
YOLO, SizeFilter, BoT-SORT por puntos y StaticClutter. No usa calibración (MOT20 no la trae),
así que la zona útil y el límite de trabajo no descartan nada.

Puntos medidos:
  yolo      cajas que devuelve YOLO
  filtros   tras SizeFilter
  tracks    tracks activos del cuadro menos los que StaticClutter suprime (lo que se cuenta)

Referencia (gt/gt.txt de MOT20): personas = clase 1, marcadas para evaluar y con visibilidad
>= --vis-min. Lo demás (visibilidad baja, personas en vehículo, estáticas, distractores,
oclusores) es zona ignorada: una predicción que cae ahí no cuenta como acierto ni como falso
positivo, y tampoco suma al conteo. Emparejamiento húngaro con IoU >= --iou.

Variantes:
  actual    configuración de main en un equipo con GPU de 4 GB y cámaras elevadas
  mejoras   umbral de track 0.25, SizeFilter y StaticClutter relajados, sin reducir a 1280,
            NMS 0.65, max_det 500
  mejoras_m lo mismo con yolo11m a 1280

Uso (desde proyecto_lap_prototipo):
  python tools/evaluar_deteccion_mot.py data/raw/MOT20/MOT20-01 data/raw/MOT20/MOT20-03 --device cuda:0
Opciones: --variantes actual,mejoras --fp32 --paso 5 --json resultado.json
"""
import argparse
import configparser
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from following.appearance import torso_histogram  # noqa: E402
from following.clutter import SizeFilter, StaticClutter  # noqa: E402
from following.detector import YoloPersonDetector  # noqa: E402
from tracking import BoTSortPuntos  # noqa: E402

PERSONA, IGNORADAS = 1, {2, 7, 8, 12}
ALTURAS = (("<40", 0, 40), ("40-100", 40, 100), (">100", 100, math.inf))
ETAPAS = ("yolo", "filtros", "tracks")

# Valores de main: hardware.py (gpu_baja con cámaras elevadas: yolo11n a 1280, FP16),
# live_server.py (confianza 0.15 con cámaras elevadas, cuadro a 1280 px, tracker 0.4) y
# detector.py (NMS 0.5, max_det por defecto de ultralytics: 300).
VARIANTES = {
    "actual": dict(pesos="yolo11n.pt", imgsz=1280, conf=.15, iou=.5, max_det=300, ancho_max=1280,
                   umbral_track=.4, size_filter={}, static_clutter={}),
    "mejoras": dict(pesos="yolo11n.pt", imgsz=1280, conf=.15, iou=.65, max_det=500, ancho_max=None,
                    umbral_track=.25, size_filter=dict(ratio=.35), static_clutter=dict(min_age=4., max_mean_score=.35)),
    "mejoras_m": dict(pesos="yolo11m.pt", imgsz=1280, conf=.15, iou=.65, max_det=500, ancho_max=None,
                      umbral_track=.25, size_filter=dict(ratio=.35), static_clutter=dict(min_age=4., max_mean_score=.35)),
}


class DetectorConMaxDet(YoloPersonDetector):
    """El detector del prototipo, más max_det (main usa el valor por defecto de ultralytics)."""

    def __init__(self, *args, max_det=300, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_det = int(max_det)

    def detectar_lote(self, frames_bgr):
        kwargs = {"source": frames_bgr, "classes": [0], "conf": self.confidence, "imgsz": self.imgsz,
                  "iou": self.iou, "max_det": self.max_det, "verbose": False}
        if self.device:
            kwargs["device"] = self.device
        if self.half:
            kwargs["half"] = True
        return [self._convert(r) for r in self.model.predict(**kwargs)]


def iou_matriz(a, b):
    if not len(a) or not len(b):
        return np.zeros((len(a), len(b)))
    a, b = np.asarray(a, float)[:, None], np.asarray(b, float)[None]
    ix = np.clip(np.minimum(a[..., 2], b[..., 2]) - np.maximum(a[..., 0], b[..., 0]), 0, None)
    iy = np.clip(np.minimum(a[..., 3], b[..., 3]) - np.maximum(a[..., 1], b[..., 1]), 0, None)
    inter = ix * iy
    union = (a[..., 2] - a[..., 0]) * (a[..., 3] - a[..., 1]) + (b[..., 2] - b[..., 0]) * (b[..., 3] - b[..., 1]) - inter
    return np.where(union > 0, inter / np.maximum(union, 1e-9), 0.)


def leer_secuencia(carpeta, vis_min):
    ini = configparser.ConfigParser()
    ini.read(carpeta / "seqinfo.ini")
    fps = float(ini["Sequence"]["frameRate"])
    gt = defaultdict(lambda: ([], []))          # cuadro -> (personas, ignoradas)
    for fila in np.loadtxt(carpeta / "gt" / "gt.txt", delimiter=",", ndmin=2):
        cuadro, _, x, y, w, h, marcada, clase, vis = fila[:9]
        caja = (x - 1, y - 1, x - 1 + w, y - 1 + h)   # MOT usa coordenadas desde 1
        evaluable = int(clase) == PERSONA and marcada > 0 and vis >= vis_min
        if evaluable:
            gt[int(cuadro)][0].append(caja)
        elif int(clase) == PERSONA or int(clase) in IGNORADAS:
            gt[int(cuadro)][1].append(caja)
    imagenes = sorted((carpeta / "img1").glob("*.jpg"))
    return fps, gt, imagenes


def comparar(pred, personas, ignoradas, umbral):
    """(aciertos por persona, falsos positivos, predicciones contadas)."""
    m = iou_matriz(personas, pred)
    acierto, usadas = [False] * len(personas), set()
    if m.size:
        filas, cols = linear_sum_assignment(-m)
        for f, c in zip(filas, cols):
            if m[f, c] >= umbral:
                acierto[f] = True
                usadas.add(c)
    resto = [i for i in range(len(pred)) if i not in usadas]
    if resto and ignoradas:
        sobre_ignorada = iou_matriz([pred[i] for i in resto], ignoradas).max(axis=1) >= umbral
        resto = [i for i, ign in zip(resto, sobre_ignorada) if not ign]
    return acierto, len(resto), len(usadas) + len(resto)


class Acumulado:
    def __init__(self):
        self.tp = self.fp = 0
        self.por_altura = {k: [0, 0] for k, _, _ in ALTURAS}   # aciertos, total
        self.errores, self.reales = [], []

    def sumar(self, personas, acierto, fp, contadas):
        self.tp += sum(acierto)
        self.fp += fp
        for caja, ok in zip(personas, acierto):
            alto = caja[3] - caja[1]
            for k, lo, hi in ALTURAS:
                if lo <= alto < hi:
                    self.por_altura[k][0] += ok
                    self.por_altura[k][1] += 1
        self.errores.append(contadas - len(personas))
        self.reales.append(len(personas))

    def resumen(self):
        total = sum(t for _, t in self.por_altura.values())
        return {"recall": self.tp / max(1, total), "precision": self.tp / max(1, self.tp + self.fp),
                "recall_altura": {k: (a / t if t else None) for k, (a, t) in self.por_altura.items()},
                "personas_altura": {k: t for k, (_, t) in self.por_altura.items()},
                "mae": float(np.mean(np.abs(self.errores))), "sesgo": float(np.mean(self.errores)),
                "mae_pct": float(np.mean(np.abs(self.errores)) / max(1e-9, np.mean(self.reales)) * 100),
                "reales_cuadro": float(np.mean(self.reales))}


def sincronizar(device):
    if str(device).startswith("cuda"):
        import torch
        torch.cuda.synchronize()


def evaluar(carpeta, nombre, v, args):
    fps, gt, imagenes = leer_secuencia(carpeta, args.vis_min)
    imagenes = imagenes[::args.paso] if args.paso > 1 else imagenes
    detector = DetectorConMaxDet(ROOT / "models" / v["pesos"], confidence=v["conf"], imgsz=v["imgsz"], iou=v["iou"],
                                 device=args.device, half=not args.fp32, max_det=v["max_det"])
    tracker = BoTSortPuntos(umbral_alto=v["umbral_track"], max_frames_perdido=45)
    size_filter, clutter = SizeFilter(**v["size_filter"]), StaticClutter(**v["static_clutter"])
    acumulados = {e: Acumulado() for e in ETAPAS}
    cuadros = [(int(p.stem), cv2.imread(str(p))) for p in imagenes]
    detector.detectar(cuadros[0][1])                     # calentamiento: carga del modelo y CUDA
    t_det, t_total, nan = [], [], 0
    for indice, original in cuadros:
        sincronizar(args.device)
        inicio = time.perf_counter()
        frame, escala = original, 1.
        if v["ancho_max"] and frame.shape[1] > v["ancho_max"]:
            escala = frame.shape[1] / v["ancho_max"]
            frame = cv2.resize(frame, (v["ancho_max"], round(frame.shape[0] / escala)))
        alto, ancho = frame.shape[:2]
        detecciones = detector.detectar(frame)
        sincronizar(args.device)
        t_det.append(time.perf_counter() - inicio)
        nan += sum(not np.all(np.isfinite(d.box)) or not math.isfinite(d.confianza) for d in detecciones)
        etapa_yolo = [d.box for d in detecciones]
        detecciones, _ = size_filter.apply(detecciones, (ancho, alto))
        etapa_filtros = [d.box for d in detecciones]
        for d in detecciones:
            d.appearance = torso_histogram(frame, d.box)
        tracks, _, _ = tracker.actualizar(detecciones, indice / fps)
        quietos = clutter.update(tracks, indice / fps, (ancho, alto))
        etapa_tracks = [tr.ultima_caja for tr in tracks if tr.id not in quietos and tr.ultima_caja is not None]
        t_total.append(time.perf_counter() - inicio)
        personas, ignoradas = gt[indice]
        for etapa, cajas in zip(ETAPAS, (etapa_yolo, etapa_filtros, etapa_tracks)):
            cajas = [tuple(c * escala for c in caja) for caja in cajas]
            acumulados[etapa].sumar(personas, *comparar(cajas, personas, ignoradas, args.iou))
    ms_det, ms_total = np.median(t_det) * 1000, np.median(t_total) * 1000
    return {"secuencia": carpeta.name, "variante": nombre, "pesos": v["pesos"], "imgsz": v["imgsz"],
            "fp16": detector.half, "device": args.device, "cuadros": len(cuadros), "resolucion": list(cuadros[0][1].shape[1::-1]),
            "ms_detector": round(float(ms_det), 1), "ms_pipeline": round(float(ms_total), 1),
            "fps_pipeline": round(1000 / ms_total, 1), "cajas_nan": nan,
            "etapas": {e: a.resumen() for e, a in acumulados.items()}}


def tabla(resultados):
    def pct(x):
        return "—" if x is None else f"{x * 100:.1f}"
    lineas = ["| Secuencia | Variante | Etapa | Recall | Prec. | R <40 | R 40-100 | R >100 | MAE (pers./cuadro) | MAE % | Sesgo | ms YOLO | FPS pipeline |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in resultados:
        for e in ETAPAS:
            m = r["etapas"][e]
            ra = m["recall_altura"]
            lineas.append(f"| {r['secuencia']} | {r['variante']} | {e} | {pct(m['recall'])} | {pct(m['precision'])} | {pct(ra['<40'])} | "
                          f"{pct(ra['40-100'])} | {pct(ra['>100'])} | {m['mae']:.1f} | {m['mae_pct']:.1f} | {m['sesgo']:+.1f} | "
                          f"{r['ms_detector']} | {r['fps_pipeline']} |")
    return "\n".join(lineas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("secuencias", nargs="+", type=Path, help="carpetas MOT20-XX con img1/, gt/gt.txt y seqinfo.ini")
    ap.add_argument("--variantes", default="actual,mejoras,mejoras_m")
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--fp32", action="store_true", help="desactiva FP16 (por si la GPU devuelve NaN)")
    ap.add_argument("--paso", type=int, default=1, help="usa uno de cada N cuadros presentes en img1/")
    ap.add_argument("--iou", type=float, default=.5)
    ap.add_argument("--vis-min", type=float, default=.25)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    resultados = []
    for carpeta in args.secuencias:
        for nombre in args.variantes.split(","):
            r = evaluar(carpeta, nombre, VARIANTES[nombre], args)
            resultados.append(r)
            print(f"{r['secuencia']} {nombre}: {r['cuadros']} cuadros, YOLO {r['ms_detector']} ms, "
                  f"pipeline {r['fps_pipeline']} FPS, cajas NaN {r['cajas_nan']}", flush=True)
    print(tabla(resultados))
    if args.json:
        args.json.write_text(json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
