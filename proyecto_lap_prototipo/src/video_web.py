"""Copias de video que el navegador sí reproduce.

Chrome no reproduce AVI (MJPEG) ni MKV, así que en «Videos y resultados» las cámaras salían en negro con solo las cajas.
Los análisis siguen leyendo el archivo original; para reproducir se crea una copia VP8 en `.webm` junto al original
(`<carpeta>/web/<nombre>.webm`) con el encoder que ya trae OpenCV, sin dependencias nuevas.
"""
import json
import threading
from pathlib import Path

import cv2

NAVEGADOR = {".mp4", ".m4v", ".webm", ".mov"}
_en_curso = {}
_lock = threading.Lock()


def copia_web(path):
    """Ruta de la copia reproducible de `path` (la misma si ya lo es) o None si todavía no existe."""
    path = Path(path)
    if path.suffix.lower() in NAVEGADOR:
        return path
    copia = path.parent / "web" / (path.stem + ".webm")
    if copia.is_file() and copia.stat().st_size > 0 and copia.stat().st_mtime >= path.stat().st_mtime:
        return copia
    return None


def preparar(path):
    """Empieza a convertir `path` en segundo plano si hace falta. Devuelve True si ya hay copia lista."""
    path = Path(path)
    if copia_web(path) is not None:
        return True
    with _lock:
        hilo = _en_curso.get(str(path))
        if hilo is None or not hilo.is_alive():
            hilo = threading.Thread(target=_convertir, args=(path,), daemon=True, name=f"webm-{path.stem[:8]}")
            _en_curso[str(path)] = hilo
            hilo.start()
    return False


def convirtiendo(path):
    hilo = _en_curso.get(str(Path(path)))
    return bool(hilo and hilo.is_alive())


def _convertir(path):
    destino = path.parent / "web" / (path.stem + ".webm")
    temporal = destino.with_suffix(".parcial.webm")
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            return
        ancho, alto = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not fps or fps != fps or fps <= 0:
            fps = 25.
        destino.parent.mkdir(parents=True, exist_ok=True)
        salida = cv2.VideoWriter(str(temporal), cv2.VideoWriter_fourcc(*"VP80"), fps, (ancho, alto))
        if not salida.isOpened():
            return
        try:
            while True:
                ok, cuadro = cap.read()
                if not ok:
                    break
                salida.write(cuadro)
        finally:
            salida.release()
        if temporal.is_file() and temporal.stat().st_size > 0:
            temporal.replace(destino)
    except (OSError, cv2.error):
        pass
    finally:
        cap.release()
        try:
            if temporal.exists():
                temporal.unlink()
        except OSError:
            pass


def deduplicar(carpeta, archivo, sha256):
    """Si ya hay un video subido con el mismo contenido, borra `archivo` y devuelve el existente; si no, lo registra.

    Subir dos veces el mismo video (por ejemplo al rehacer un proyecto) guardaba una copia de varios GB cada vez.
    El índice (`_indice.json`, hash -> nombre) solo conoce lo subido desde que existe; no recorre archivos antiguos."""
    carpeta, archivo = Path(carpeta), Path(archivo)
    indice = carpeta / "_indice.json"
    try:
        tabla = json.loads(indice.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        tabla = {}
    previo = carpeta / tabla.get(sha256, "")
    if tabla.get(sha256) and previo.is_file() and previo != archivo and previo.stat().st_size == archivo.stat().st_size:
        archivo.unlink()
        return previo
    tabla[sha256] = archivo.name
    indice.write_text(json.dumps(tabla), encoding="utf-8")
    return archivo
