"""Prueba de reidentificación multicámara sobre dos videos con solape.

Corre YOLO11 -> ByteTrack (puntos + Kalman) -> OSNet -> IdentityStore sobre
camera_A y camera_B, usando la homografía de config/calibracion.json. Las mismas
detecciones alimentan dos IdentityStore: uno con OSNet y otro solo con la firma
de color, para comparar. Guarda un video anotado y un resumen en data/salida_reid.

Uso (desde proyecto_lap_prototipo):
    python tools/probar_reid.py [--a data/camera_A.mp4] [--b data/camera_B.mp4]
                                [--step 3] [--seconds 30] [--no-video]
"""
import argparse
import json
import pickle
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from live_server import default_config  # noqa: E402
from live_core import IdentityStore  # noqa: E402
from tracking import ByteTrackPuntos  # noqa: E402
from following.appearance import torso_histogram  # noqa: E402
from following.detector import YoloPersonDetector  # noqa: E402
from following.reid import OSNetEmbedder, EmbeddingScheduler  # noqa: E402

STATE_COLOR = {"local": (70, 220, 120), "estimated": (255, 180, 60), "reidentified": (255, 120, 220), "uncertain": (60, 170, 255)}


def ground(h, px, py):
    point = cv2.perspectiveTransform(np.array([[[px, py]]], np.float32), h)[0, 0]
    return float(point[0]), float(point[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="data/camera_A.mp4")
    ap.add_argument("--b", default="data/camera_B.mp4")
    ap.add_argument("--step", type=int, default=3, help="procesar 1 de cada N frames")
    ap.add_argument("--seconds", type=float, default=30., help="duración máxima a procesar")
    ap.add_argument("--no-video", action="store_true")
    ap.add_argument("--imgsz", type=int, default=960, help="resolución de YOLO; más alta ayuda con personas pequeñas")
    ap.add_argument("--no-scope", action="store_true", help="no filtrar por config/alcance.json (suelo caminable)")
    ap.add_argument("--from-cache", help="reutiliza observaciones guardadas (sin video ni YOLO) para ajustar la asociación")
    args = ap.parse_args()

    calibration = json.loads((ROOT / "config" / "calibracion.json").read_text(encoding="utf-8"))
    cfg = default_config()
    cfg["clocksVerified"] = True
    cfg["cameras"] = [c for c in cfg["cameras"] if c["id"] in ("A", "B")]
    for c in cfg["cameras"]:
        c["links"] = [o for o in ("A", "B") if o != c["id"]]
    scope_file = ROOT / "config" / "alcance.json"
    scopes = {} if args.no_scope or not scope_file.exists() else {
        k: np.array(v, np.float32).reshape(-1, 1, 2) for k, v in json.loads(scope_file.read_text(encoding="utf-8")).items()}
    cams = {}
    for cid, path in (("A", args.a), ("B", args.b)):
        cap = cv2.VideoCapture(str(ROOT / path))
        if not cap.isOpened():
            sys.exit(f"No se pudo abrir {path}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.
        cams[cid] = {"cap": cap, "fps": fps, "h": np.array(calibration[cid], np.float64),
                     "tracker": ByteTrackPuntos(umbral_alto=.4, max_frames_perdido=max(8, 45 // args.step)),
                     "sched": EmbeddingScheduler(interval=max(1, 8 // args.step)), "locals": set()}

    detector = YoloPersonDetector(ROOT / "models" / "yolo11n.pt", imgsz=args.imgsz)
    embedder = OSNetEmbedder()
    print("OSNet:", "activo" if embedder.available else embedder.error)
    stores = {"osnet": IdentityStore(cfg), "color": IdentityStore(cfg)}
    seen = {mode: defaultdict(set) for mode in stores}   # id global -> cámaras
    states = {mode: Counter() for mode in stores}
    events = {mode: Counter() for mode in stores}
    writer, out_path = None, ROOT / "data" / "salida_reid" / "reid_A_B.mp4"

    cache_path = ROOT / "data" / "salida_reid" / "observaciones.pkl"
    recorded = []

    def steps():
        """Genera (t, observaciones, frames) desde los videos o desde la caché."""
        if args.from_cache:
            for t, rows in pickle.loads(Path(args.from_cache).read_bytes()):
                yield t, rows, None
            return
        index = 0
        while True:
            frames = {}
            for cid, cam in cams.items():
                ok, frame = cam["cap"].read()
                if not ok:
                    return
                frames[cid] = frame
            index += 1
            if (index - 1) % args.step:
                continue
            t = (index - 1) / cams["A"]["fps"]
            if t > args.seconds:
                return
            rows = []
            batches = dict(zip(cams, detector.detectar_lote([frames[cid] for cid in cams])))
            for cid, cam in cams.items():
                frame = frames[cid]
                detections = batches[cid]
                if cid in scopes:
                    # Descarta reflejos en vidrio y zonas fuera del suelo caminable.
                    detections = [d for d in detections if cv2.pointPolygonTest(scopes[cid], (float(d.x), float(d.y)), True) >= -6]
                for d in detections:
                    d.appearance = torso_histogram(frame, d.box)
                tracks, _, _ = cam["tracker"].actualizar(detections, t)
                if embedder.available:
                    due = [tr for tr in tracks if tr.ultima_caja is not None and cam["sched"].due(tr.id, index, tr.score)]
                    for tr, vec in zip(due, embedder.embed(frame, [tr.ultima_caja for tr in due])):
                        cam["sched"].store(tr.id, index, vec)
                    cam["sched"].prune({tr.id for tr in cam["tracker"].tracks_activos + cam["tracker"].tracks_perdidos})
                for tr in tracks:
                    px, py = tr.posicion
                    color = tr.apariencia if tr.apariencia is not None else torso_histogram(frame, tr.ultima_caja)
                    cam["locals"].add(tr.id)
                    rows.append({"camera": cid, "local": tr.id, "point": ground(cam["h"], px, py), "pixel": [px, py],
                                 "box": tr.ultima_caja, "color": color, "score": tr.score,
                                 "embedding": cam["sched"].get(tr.id) if embedder.available else None})
            recorded.append((t, rows))
            yield t, rows, frames

    started, t, local_ids, last_print = time.time(), 0., defaultdict(set), -1.
    for t, rows, frames in steps():
        for r in rows:
            local_ids[r["camera"]].add(r["local"])
        obs = {"osnet": rows, "color": [{**r, "embedding": None} for r in rows]}
        people = {mode: store.update(obs[mode], t) for mode, store in stores.items()}
        for mode, rows in people.items():
            for p in rows:
                seen[mode][p["id"]].add(p["camera"])
                states[mode][p["association"]] += 1
            for e in stores[mode].events:
                events[mode][(e["type"], e["id"], round(e["t"], 3))] = 1
        if not args.no_video and frames is not None:
            panels = []
            for cid, frame in frames.items():
                canvas = frame.copy()
                for p in people["osnet"]:
                    if p["camera"] != cid or not p["box"]:
                        continue
                    x1, y1, x2, y2 = map(int, p["box"])
                    col = STATE_COLOR.get(p["association"], (200, 200, 200))
                    cv2.rectangle(canvas, (x1, y1), (x2, y2), col, 2)
                    score = f" {p['reidScore']:.2f}" if p.get("reidScore") is not None else ""
                    cv2.putText(canvas, f"{p['id']} {p['association']}{score}", (x1, max(14, y1 - 6)),
                                cv2.FONT_HERSHEY_SIMPLEX, .5, col, 2)
                cv2.putText(canvas, f"Camara {cid}  t={t:.1f}s", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, .6, (255, 255, 255), 2)
                panels.append(canvas)
            view = np.hstack(panels)
            if writer is None:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"),
                                         cams["A"]["fps"] / args.step, (view.shape[1], view.shape[0]))
            writer.write(view)
        if int(t) != int(last_print):
            last_print = t
            print(f"t={t:5.1f}s  ids globales osnet={len(seen['osnet'])} color={len(seen['color'])}", flush=True)
    if writer:
        writer.release()
    if recorded:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(pickle.dumps(recorded))

    summary = {"segundos_procesados": round(t, 1), "tiempo_calculo_s": round(time.time() - started, 1),
               "tracks_locales": {cid: len(ids) for cid, ids in local_ids.items()}}
    for mode in stores:
        both = sum(len(c) > 1 for c in seen[mode].values())
        summary[mode] = {"ids_globales": len(seen[mode]), "ids_vistos_en_A_y_B": both,
                         "observaciones_por_estado": dict(states[mode]),
                         "eventos": dict(Counter(k[0] for k in events[mode]))}
    out_json = ROOT / "data" / "salida_reid" / "resumen.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if writer:
        print("Video:", out_path)


if __name__ == "__main__":
    main()
