"""
Utilidad para marcar manualmente, sobre un frame real, el poligono de la
imagen donde SI vale la pena buscar cabezas con P2PNet. Todo lo que quede
fuera del poligono se descarta antes de pasarlo al tracker.

Por que hace falta: P2PNet detecta sobre el frame completo, incluido el
reflejo del vidrio del edificio (gente/calle reflejada), la pared, el techo
visible, etc. Esas detecciones fuera de la zona real generan identificadores
nuevos que nunca se fusionan con nada (porque no corresponden a una persona
real caminando por la explanada), inflando el conteo y ensuciando el
seguimiento. Marcar el area util de antemano evita ese ruido de raiz.

Uso:
    python marcar_alcance.py --video ../data/camera_A.mp4 --camara A
    python marcar_alcance.py --video ../data/camera_B.mp4 --camara B

Pasos:
  1. Click en cada esquina del area donde SI debe buscarse gente (p.ej. el
     piso de la explanada, sin el vidrio ni la pared). El orden de los
     clicks define el contorno del poligono.
  2. 'u' deshace el ultimo punto si te equivocas.
  3. 'q' cierra el poligono (uniendo el ultimo punto con el primero) y lo
     guarda en config/alcance.json.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

_puntos = []


def _click(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        _puntos.append([x, y])


def marcar(ruta_video: str, camara_id: str, ruta_alcance: str, indice_frame: int = 0):
    captura = cv2.VideoCapture(ruta_video)
    captura.set(cv2.CAP_PROP_POS_FRAMES, indice_frame)
    ok, frame = captura.read()
    captura.release()
    if not ok:
        raise RuntimeError(f"No se pudo leer el frame {indice_frame} de {ruta_video}")

    ventana = f"Camara {camara_id}: click en el contorno del area util | 'u' deshacer | 'q' guardar"
    cv2.namedWindow(ventana)
    cv2.setMouseCallback(ventana, _click)

    print(f"\nMarcando area util para camara {camara_id} sobre {ruta_video} (frame {indice_frame})")
    print("Click en cada esquina del piso/zona real (sin vidrio, sin pared). 'u' deshace, 'q' guarda.\n")

    while True:
        vista = frame.copy()
        if len(_puntos) >= 2:
            overlay = vista.copy()
            cv2.fillPoly(overlay, [np.array(_puntos, dtype=np.int32)], (0, 200, 0))
            vista = cv2.addWeighted(overlay, 0.25, vista, 0.75, 0)
        for i, (px, py) in enumerate(_puntos, start=1):
            cv2.circle(vista, (px, py), 5, (0, 0, 255), -1)
            cv2.putText(vista, str(i), (px + 8, py - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        if len(_puntos) >= 2:
            cv2.polylines(vista, [np.array(_puntos, dtype=np.int32)], True, (0, 255, 0), 2)
        cv2.putText(vista, f"puntos: {len(_puntos)}  ('u'=deshacer, 'q'=guardar)",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.imshow(ventana, vista)
        tecla = cv2.waitKey(20) & 0xFF
        if tecla == ord("q"):
            break
        elif tecla == ord("u") and _puntos:
            _puntos.pop()
    cv2.destroyAllWindows()

    if len(_puntos) < 3:
        raise RuntimeError(f"Solo se marcaron {len(_puntos)} puntos; se necesitan al menos 3 para un poligono.")

    ruta = Path(ruta_alcance)
    datos = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    datos[camara_id] = _puntos
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nAlcance de camara {camara_id} guardado en {ruta} ({len(_puntos)} puntos)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--video", required=True)
    parser.add_argument("--camara", required=True, choices=["A", "B"])
    parser.add_argument("--frame", type=int, default=0)
    parser.add_argument("--alcance", default=str(
        Path(__file__).resolve().parent.parent / "config" / "alcance.json"))
    argumentos = parser.parse_args()
    marcar(argumentos.video, argumentos.camara, argumentos.alcance, argumentos.frame)
