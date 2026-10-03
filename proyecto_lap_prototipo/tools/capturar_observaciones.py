"""Captura las observaciones por cámara de un proyecto, con el flujo del servidor.

Lee el proyecto (videos, calibración, zonas), corre YOLO -> ByteTrack -> OSNet cada
`--dt` segundos de fuente y guarda en un .pkl lo que recibe IdentityStore. Así la
asociación se puede evaluar y ajustar (tools/evaluar_asociacion.py) sin repetir YOLO.

Uso (desde proyecto_lap_prototipo):
    python tools/capturar_observaciones.py p-7fc87baa --seconds 20
"""
import argparse
import copy
import json
import pickle
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from live_core import calibration, ground_point, estimate_height  # noqa: E402
from spatial_scope import accepts  # noqa: E402
from tracking import ByteTrackPuntos  # noqa: E402
from following.appearance import torso_histogram  # noqa: E402
from following.detector import YoloPersonDetector  # noqa: E402
from following.reid import OSNetEmbedder, EmbeddingScheduler, occluded_ids  # noqa: E402
from following.clutter import SizeFilter, StaticClutter  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", help="id del proyecto, p. ej. p-7fc87baa")
    ap.add_argument("--seconds", type=float, default=20.)
    ap.add_argument("--dt", type=float, default=.2, help="segundos de fuente entre muestras (el servidor usa 0.2)")
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--no-clutter", action="store_true", help="sin filtros de objetos pequeños e inmóviles")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    stored = json.loads((ROOT / "config" / "projects" / f"{args.project}.json").read_text(encoding="utf-8"))
    config = stored.get("config", stored)
    cams = {}
    for camera in config["cameras"]:
        if camera.get("active", True) is False:
            continue
        cap = cv2.VideoCapture(camera["source"])
        if not cap.isOpened():
            sys.exit(f"No se pudo abrir {camera['source']}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.
        c = copy.deepcopy(camera)
        c.update(cap=cap, fps=fps, h=calibration(c.get("pairs", [])), headPoints=False,
                 tracker=ByteTrackPuntos(umbral_alto=.4, max_frames_perdido=45),
                 sched=EmbeddingScheduler(8), size=SizeFilter(), still=StaticClutter())
        c["projects"] = c["h"] is not None
        c["scope"] = {k: config.get(k) for k in ("width", "height", "workArea", "zones", "mapAsset")}
        cams[c["id"]] = c

    detector = YoloPersonDetector(ROOT / "models" / "yolo11n.pt", imgsz=args.imgsz)
    detector.confidence = .25
    embedder = OSNetEmbedder()
    print("OSNet:", "activo" if embedder.available else embedder.error, "| cámaras:", list(cams))
    recorded, started, step = [], time.time(), 0
    t = 0.
    while t <= args.seconds:
        frames = {}
        for cid, c in cams.items():
            c["cap"].set(cv2.CAP_PROP_POS_FRAMES, max(0, int((t + c.get("offset", 0)) * c["fps"])))
            ok, frame = c["cap"].read()
            if not ok:
                frames = None
                break
            if frame.shape[1] > 1280:
                frame = cv2.resize(frame, (1280, round(frame.shape[0] * 1280 / frame.shape[1])))
            frames[cid] = frame
        if frames is None:
            break
        step += 1
        batches = dict(zip(cams, detector.detectar_lote([frames[cid] for cid in cams])))
        rows = []
        for cid, c in cams.items():
            frame = frames[cid]
            height, width = frame.shape[:2]
            keep = []
            for d in batches[cid]:
                ground = ground_point(c, d.x / width, d.y / height) if c["projects"] else None
                if accepts(c, c["scope"], d.x / width, d.y / height, ground, image_only=not c["projects"]):
                    keep.append(d)
            if not args.no_clutter:
                keep, _ = c["size"].apply(keep, (width, height))
            for d in keep:
                d.appearance = torso_histogram(frame, d.box)
            tracks, _, _ = c["tracker"].actualizar(keep, t)
            if not args.no_clutter:
                ignored = c["still"].update(tracks, t, (width, height))
                tracks = [tr for tr in tracks if tr.id not in ignored]
            if embedder.available:
                blocked = occluded_ids(tracks)
                due = [tr for tr in tracks if tr.ultima_caja is not None and tr.id not in blocked
                       and c["sched"].due(tr.id, step, tr.score)]
                for tr, vec in zip(due, embedder.embed(frame, [tr.ultima_caja for tr in due])):
                    c["sched"].store(tr.id, step, vec)
                c["sched"].prune({tr.id for tr in c["tracker"].tracks_activos + c["tracker"].tracks_perdidos})
            for tr in tracks:
                px, py = tr.posicion
                point = ground_point(c, px / width, py / height) if c["projects"] else None
                if not accepts(c, c["scope"], px / width, py / height, point, image_only=not c["projects"]):
                    continue
                if point and not (0 <= point[0] <= c["scope"]["width"] and 0 <= point[1] <= c["scope"]["height"]):
                    point = None
                color = tr.apariencia if tr.apariencia is not None else torso_histogram(frame, tr.ultima_caja)
                rows.append({"camera": cid, "local": tr.id, "point": point, "pixel": [float(px), float(py)],
                             "box": tr.ultima_caja, "color": color, "score": tr.score,
                             "embedding": c["sched"].get(tr.id) if embedder.available else None,
                             "height": estimate_height(c, tr.ultima_caja, width, height)})
        recorded.append((round(t, 3), rows))
        if step % 10 == 0:
            print(f"t={t:5.1f}s  muestras={step}  {time.time() - started:.0f}s", flush=True)
        t += args.dt
    out = Path(args.out) if args.out else ROOT / "data" / "salida_reid" / f"obs_{args.project}.pkl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(pickle.dumps({"config": {k: v for k, v in config.items() if k != "cameras"},
                                  "cameras": [{k: v for k, v in c.items() if k in ("id", "links", "x", "y", "height", "planId", "offset")}
                                              for c in cams.values()], "obs": recorded}))
    print("Guardado:", out, "| muestras:", len(recorded))


if __name__ == "__main__":
    main()
