"""
Utilidad de calibracion: click sobre un frame real de una camara para marcar
puntos conocidos del piso (las losetas de la explanada son perfectas: usa
sus esquinas y el tamano real de la loseta como unidad de medida) y su
posicion real en el plano compartido (metros). Calcula la homografia
pixel -> plano que usa nodes.NodoCamara.

IMPORTANTE -- camara A y camara B ven la MISMA explanada desde angulos
distintos, no dos tramos separados: hay que calibrarlas con el MISMO origen
(0, 0) y los MISMOS ejes x/y (p.ej. "origen = esquina del panel plateado de
la pared, eje x hacia la calle, eje y a lo largo de la pared"). Si cada
camara se calibra con su propio origen arbitrario, sus posiciones en metros
no van a ser comparables y la fusion entre camaras (cross_camera.py) va a
fallar aunque cada homografia individualmente este bien calculada.

¿NO CONOCES EL TAMANO REAL DE LA LOSETA? No hace falta medirla para este
prototipo: la fusion entre camaras solo necesita que las dos usen la MISMA
unidad de medida, no que esa unidad sea literalmente "metros". Cuenta
losetas en vez de medir con cinta: si el origen es la esquina de una loseta,
el punto que esta 3 losetas a la derecha y 2 hacia abajo se ingresa como
"3,2" (en vez de "1.8,1.2"). El pipeline va a funcionar igual de bien; solo
las distancias/velocidades reportadas van a estar en "losetas" en vez de
metros hasta que alguien mida una loseta real y se pueda escalar (ver
"metros_por_unidad" en config/camaras.json).

Uso:
    python calibrar_camara.py --video ../data/camera_A.mp4 --camara A
    python calibrar_camara.py --video ../data/camera_B.mp4 --camara B

Como funciona (dos pasos, para no tener que cambiar de ventana a mitad de
camino -- si escribias en la ventana del video no pasaba nada porque el
programa esperaba la respuesta en la TERMINAL):

  PASO 1 (ventana de la imagen): click en cada punto del piso que quieras
    usar de referencia (esquinas de loseta). Cada click queda marcado y
    numerado sobre la imagen. 'u' deshace el ultimo punto si te equivocas.
    Cuando tengas al menos 4 puntos (mejor si son mas y no estan en linea
    recta), presiona 'q' para cerrar la ventana y pasar al paso 2.

  PASO 2 (en esta misma terminal): para cada punto que marcaste, en el mismo
    orden, se te va a preguntar su posicion real "x,y" (en metros si los
    conoces, o en numero de losetas contadas desde tu origen elegido).
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

_puntos_pixel = []


def _click(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        _puntos_pixel.append([x, y])


def _marcar_puntos(ruta_video: str, camara_id: str, indice_frame: int) -> np.ndarray:
    captura = cv2.VideoCapture(ruta_video)
    captura.set(cv2.CAP_PROP_POS_FRAMES, indice_frame)
    ok, frame = captura.read()
    captura.release()
    if not ok:
        raise RuntimeError(f"No se pudo leer el frame {indice_frame} de {ruta_video}")

    ventana = f"Camara {camara_id}: click en puntos del piso | 'u' deshacer | 'q' terminar"
    cv2.namedWindow(ventana)
    cv2.setMouseCallback(ventana, _click)

    print(f"\n--- PASO 1: marcando puntos sobre {ruta_video} (frame {indice_frame}) ---")
    print("Click en cada punto de referencia del piso. 'u' deshace el ultimo. 'q' cuando termines.\n")

    while True:
        vista = frame.copy()
        for i, (px, py) in enumerate(_puntos_pixel, start=1):
            cv2.circle(vista, (px, py), 6, (0, 0, 255), -1)
            cv2.putText(vista, str(i), (px + 8, py - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        cv2.putText(vista, f"puntos marcados: {len(_puntos_pixel)}  ('u'=deshacer, 'q'=continuar)",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.imshow(ventana, vista)
        tecla = cv2.waitKey(20) & 0xFF
        if tecla == ord("q"):
            break
        elif tecla == ord("u") and _puntos_pixel:
            _puntos_pixel.pop()
    cv2.destroyAllWindows()

    if len(_puntos_pixel) < 4:
        raise RuntimeError(f"Solo se marcaron {len(_puntos_pixel)} puntos; se necesitan al menos 4.")
    return np.array(_puntos_pixel, dtype=np.float32)


def _pedir_posiciones_reales(puntos_pixel: np.ndarray) -> np.ndarray:
    print(f"\n--- PASO 2: escribe aqui la posicion real de cada uno de los {len(puntos_pixel)} puntos ---")
    print("Formato 'x,y' -- en metros si los conoces, o en numero de losetas si no.\n")
    puntos_plano = []
    for i, (px, py) in enumerate(puntos_pixel, start=1):
        while True:
            entrada = input(f"  Punto {i} (pixel {int(px)},{int(py)}) -> posicion real 'x,y': ").strip()
            try:
                x_r, y_r = (float(v) for v in entrada.split(","))
                break
            except ValueError:
                print("    Formato invalido, se esperaba algo como '3,2'. Intenta de nuevo.")
        puntos_plano.append([x_r, y_r])
    return np.array(puntos_plano, dtype=np.float32)


def calibrar(ruta_video: str, camara_id: str, ruta_calibracion: str, indice_frame: int = 0):
    puntos_pixel = _marcar_puntos(ruta_video, camara_id, indice_frame)
    puntos_plano = _pedir_posiciones_reales(puntos_pixel)

    homografia, _ = cv2.findHomography(puntos_pixel, puntos_plano)
    if homografia is None:
        raise RuntimeError("No se pudo calcular la homografia (¿puntos colineales o repetidos?). Repite la calibracion.")

    ruta = Path(ruta_calibracion)
    datos = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    datos[camara_id] = homografia.tolist()
    ruta.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nHomografia de camara {camara_id} guardada en {ruta}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--video", required=True)
    parser.add_argument("--camara", required=True, choices=["A", "B"])
    parser.add_argument("--frame", type=int, default=0)
    parser.add_argument("--calibracion", default=str(
        Path(__file__).resolve().parent.parent / "config" / "calibracion.json"))
    argumentos = parser.parse_args()
    calibrar(argumentos.video, argumentos.camara, argumentos.calibracion, argumentos.frame)
