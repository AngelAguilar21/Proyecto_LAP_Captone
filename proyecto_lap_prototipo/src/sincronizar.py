"""
Utilidad de sincronizacion manual entre camera_A.mp4 y camera_B.mp4.

Si los dos videos no arrancaron exactamente al mismo tiempo, ubica un mismo
evento visible en ambos (alguien cruzando un punto marcado, una puerta, una
sena) y anota en que numero de frame ocurre en cada video. Esta utilidad
calcula el offset a pasarle a main.py.

Uso:
    # 1) explorar un video frame a frame para anotar el numero de un evento
    python sincronizar.py --explorar ../data/camera_A.mp4

    # 2) con los dos numeros de frame ya anotados, calcular el offset
    python sincronizar.py --frame-a 120 --frame-b 95
"""
import argparse

import cv2


def calcular_offset(frame_evento_a: int, frame_evento_b: int):
    diferencia = frame_evento_a - frame_evento_b
    if diferencia == 0:
        return None, 0
    camara_adelantada = "A" if diferencia > 0 else "B"
    return camara_adelantada, abs(diferencia)


def explorar_frames(ruta_video: str):
    """Ventana con una barra deslizante para ubicar el numero de frame de un
    evento visible, con flechas para avanzar/retroceder de a uno."""
    captura = cv2.VideoCapture(ruta_video)
    total_frames = int(captura.get(cv2.CAP_PROP_FRAME_COUNT))
    ventana = "Explorar frames - flechas izq/der para +-1, 'q' para salir"
    cv2.namedWindow(ventana)

    indice = 0

    def _ir_a(pos):
        nonlocal indice
        indice = pos

    cv2.createTrackbar("frame", ventana, 0, max(total_frames - 1, 1), _ir_a)

    while True:
        captura.set(cv2.CAP_PROP_POS_FRAMES, indice)
        ok, frame = captura.read()
        if not ok:
            break
        cv2.putText(frame, f"frame: {indice}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.imshow(ventana, frame)
        cv2.setTrackbarPos("frame", ventana, indice)
        tecla = cv2.waitKey(0) & 0xFF
        if tecla == ord("q"):
            break
        elif tecla in (81, 2424832):  # flecha izquierda
            indice = max(0, indice - 1)
        elif tecla in (83, 2555904):  # flecha derecha
            indice = min(total_frames - 1, indice + 1)

    captura.release()
    cv2.destroyAllWindows()
    print(f"Ultimo frame visto: {indice}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--explorar", metavar="VIDEO", default=None,
                         help="Abre el video en una ventana para ubicar el frame del evento de referencia.")
    parser.add_argument("--frame-a", type=int, default=None)
    parser.add_argument("--frame-b", type=int, default=None)
    args = parser.parse_args()

    if args.explorar:
        explorar_frames(args.explorar)
    elif args.frame_a is not None and args.frame_b is not None:
        camara_adelantada, offset = calcular_offset(args.frame_a, args.frame_b)
        if camara_adelantada is None:
            print("Los videos ya estan sincronizados (mismo frame para el evento).")
        else:
            print(f"Camara {camara_adelantada} esta {offset} frames adelantada.")
            print(f"Usar en main.py: --offset-camara {camara_adelantada} --offset-frames {offset}")
    else:
        parser.print_help()
