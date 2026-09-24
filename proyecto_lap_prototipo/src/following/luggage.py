"""Equipaje sin custodia: avisa cuando un bulto lleva demasiado tiempo quieto.

El sistema no decide nada sobre seguridad: marca un objeto que no se movió
durante el tiempo configurado para que una persona vaya a revisarlo. Usa las
clases de equipaje de COCO (mochila, bolso, maleta) del mismo YOLO que ya usa el
seguimiento, y las revisa cada pocos segundos en vez de cada cuadro: un bulto
olvidado no se mueve, así que no hace falta gastar CPU en mirarlo continuamente.

Limitación conocida: con el criterio de «quieto durante X tiempo» también salta
el equipaje que alguien dejó a su lado mientras espera sentado. Por eso el aviso
es para revisión humana, nunca una conclusión.
"""
from concurrent.futures import ThreadPoolExecutor

BAG_CLASSES = {24: "mochila", 26: "bolso", 28: "maleta"}
DEFAULT_INTERVAL = 4.0
DEFAULT_DWELL = 90.0
# Fracción del tamaño del bulto que se admite como ruido del detector antes de
# considerar que de verdad se movió.
STILL_TOLERANCE = .15


def _center(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def _size(box):
    return max(1e-6, max(box[2] - box[0], box[3] - box[1]))


class LuggageWatch:
    """Vigila bultos quietos en las cámaras que lo tengan activado."""

    def __init__(self, cameras, weights=None, image_size=640):
        self.weights = weights
        self.image_size = image_size
        self.cameras = {c["id"]: c for c in cameras}
        self.model = None
        self.error = None
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="equipaje")
        self.pending = None
        self.last_scan = {c["id"]: -1e9 for c in cameras}
        self.tracked = {c["id"]: [] for c in cameras}
        self.serial = 0

    @staticmethod
    def enabled_for(camera):
        return bool(camera.get("luggageWatch"))

    def _detect(self, cid, frame, t):
        if self.model is None:
            from ultralytics import YOLO
            from .detector import DEFAULT_WEIGHTS
            path = self.weights or DEFAULT_WEIGHTS
            self.model = YOLO(str(path), task="detect")
        height, width = frame.shape[:2]
        result = self.model.predict(frame, device="cpu", classes=sorted(BAG_CLASSES),
                                    conf=.35, imgsz=self.image_size, max_det=60, verbose=False)[0]
        boxes = result.boxes.xyxy.cpu().tolist()
        classes = result.boxes.cls.cpu().tolist()
        found = [{"box": [b[0] / width, b[1] / height, b[2] / width, b[3] / height],
                  "kind": BAG_CLASSES.get(int(k), "bulto")}
                 for b, k in zip(boxes, classes)]
        return cid, found, t

    def _merge(self, cid, found, t, dwell):
        """Empareja los bultos vistos ahora con los que ya venía siguiendo."""
        previous = self.tracked.setdefault(cid, [])
        used = set()
        for item in previous:
            best, distance = None, None
            for index, candidate in enumerate(found):
                if index in used:
                    continue
                a, b = _center(item["box"]), _center(candidate["box"])
                gap = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** .5
                # Tolerancia proporcional al tamaño: un bulto lejano se mueve
                # menos píxeles que uno cercano para el mismo desplazamiento.
                if gap <= _size(item["box"]) * .6 and (distance is None or gap < distance):
                    best, distance = index, gap
            if best is None:
                item["missing"] += 1
                continue
            match = found[best]
            used.add(best)
            # Seguir un bulto y considerarlo quieto son cosas distintas: se
            # empareja con tolerancia amplia, pero cualquier desplazamiento real
            # reinicia el cronómetro, que es lo que dispara el aviso.
            if distance is not None and distance > _size(item["box"]) * STILL_TOLERANCE:
                item["since"] = t
            item.update(box=match["box"], kind=match["kind"], lastSeen=t, missing=0)
            item["duration"] = t - item["since"]
            item["alert"] = item["duration"] >= dwell
        for index, candidate in enumerate(found):
            if index in used:
                continue
            self.serial += 1
            previous.append({"id": f"B{self.serial:04d}", "box": candidate["box"], "kind": candidate["kind"],
                             "since": t, "lastSeen": t, "duration": 0., "missing": 0, "alert": False})
        # Un bulto que falta en dos revisiones seguidas es que se lo llevaron.
        self.tracked[cid] = [i for i in previous if i["missing"] < 2]

    def snapshot(self, cid, t=None, dwell=DEFAULT_DWELL, interval=DEFAULT_INTERVAL):
        items = self.tracked.get(cid, [])
        return {
            "items": [{k: v for k, v in item.items() if k != "missing"} for item in items],
            "alerts": [item["id"] for item in items if item["alert"]],
            "dwell": dwell, "interval": interval, "error": self.error,
            "checkedAt": self.last_scan.get(cid),
        }

    def _collect(self):
        """Recoge la revisión terminada, sea de la cámara que sea."""
        if not (self.pending and self.pending.done()):
            return
        future, self.pending = self.pending, None
        try:
            key, found, moment = future.result()
        except Exception as exc:
            self.error = str(exc)
            return
        target = self.cameras.get(key, {})
        self._merge(key, found, moment, float(target.get("luggageDwell") or DEFAULT_DWELL))

    def observe(self, camera, frame, t):
        """Se llama en cada cuadro; solo trabaja cuando toca revisar."""
        cid = camera["id"]
        if not self.enabled_for(camera):
            return None
        dwell = float(camera.get("luggageDwell") or DEFAULT_DWELL)
        interval = float(camera.get("luggageInterval") or DEFAULT_INTERVAL)
        self._collect()
        if self.pending is None and t - self.last_scan.get(cid, -1e9) >= interval:
            self.last_scan[cid] = t
            self.pending = self.pool.submit(self._detect, cid, frame.copy(), t)
        return self.snapshot(cid, t, dwell, interval)

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)
