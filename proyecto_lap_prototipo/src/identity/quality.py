"""Calidad de las vistas: cuándo un recuadro sirve para calcular el vector de apariencia.

Portado de AeroVision (camaras_reid.vistas_confiables y recortar), sin dependencias
de notebook. Un recuadro cortado por el borde, muy pequeño, de baja confianza o
tapado por otra persona produce un vector que mezcla gente: es mejor no usarlo.
"""
import numpy as np

NIVEL_MISMO_SUELO = 0.06     # dos personas cuyos pies difieren menos de esto (x altura del recuadro) están a la misma distancia
COLOR_RELLENO_BGR = (104, 116, 124)   # media de ImageNet: tras normalizar vale 0, no aporta nada al vector


def tapadores(cajas, otras=None, nivel=NIVEL_MISMO_SUELO):
    """Por caja: (fracción visible, rectángulos tapados por otras personas).

    Una persona tapa a otra si sus pies están más abajo en la imagen (más cerca de la cámara) o a la misma altura; en ese caso
    se cuenta la parte del recuadro que cubre. A la persona de atrás se le tapa lo que oculta la de adelante; la de adelante no
    pierde nada. `otras` son las cajas con que comparar (por defecto, las mismas). Una caja no se tapa a sí misma (a <= 1 px)."""
    cajas = np.asarray(cajas, dtype=np.float32).reshape(-1, 4)
    otras_cajas = cajas if otras is None else np.asarray(otras, dtype=np.float32).reshape(-1, 4)
    resultado = []
    for caja in cajas:
        alto = max(float(caja[3] - caja[1]), 1.0)
        ancho = max(float(caja[2] - caja[0]), 1.0)
        rejilla = np.zeros((24, 12), bool)
        rectangulos = []
        for otra in otras_cajas:
            if np.all(np.abs(caja - otra) <= 1 + 1e-5 * np.abs(otra)) or otra[3] < caja[3] - nivel * alto:
                continue      # la misma detección, o una persona detrás de esta: no la tapa
            x1, y1 = max(caja[0], otra[0]), max(caja[1], otra[1])
            x2, y2 = min(caja[2], otra[2]), min(caja[3], otra[3])
            if x2 <= x1 or y2 <= y1:
                continue
            rectangulos.append((float(x1), float(y1), float(x2), float(y2)))
            rejilla[int((y1 - caja[1]) / alto * 24):int(np.ceil((y2 - caja[1]) / alto * 24)),
                    int((x1 - caja[0]) / ancho * 12):int(np.ceil((x2 - caja[0]) / ancho * 12))] = True
        resultado.append((1.0 - float(rejilla.mean()), rectangulos))
    return resultado


def rellenar(recorte, rectangulos, origen):
    """Copia del recorte con los rectángulos (en coordenadas del frame) rellenados con un gris neutro. `origen` = (x, y) del recorte."""
    if not rectangulos:
        return recorte
    salida = recorte.copy()
    alto, ancho = salida.shape[:2]
    for x1, y1, x2, y2 in rectangulos:
        a, b = max(0, int(x1 - origen[0])), max(0, int(y1 - origen[1]))
        c, d = min(ancho, int(np.ceil(x2 - origen[0]))), min(alto, int(np.ceil(y2 - origen[1])))
        if c > a and d > b:
            salida[b:d, a:c] = COLOR_RELLENO_BGR
    return salida


def recortar(imagen, fila, tapados=None):
    """Recorte con un margen pequeño alrededor del recuadro (como save_one_box de Ultralytics).

    `tapados`: rectángulos del frame (de `tapadores`) que se rellenan con gris neutro dentro del recorte."""
    cx, cy = (fila["x1"] + fila["x2"]) / 2, (fila["y1"] + fila["y2"]) / 2
    ancho, alto = (fila["x2"] - fila["x1"]) * 1.02 + 10, (fila["y2"] - fila["y1"]) * 1.02 + 10
    h, w = imagen.shape[:2]
    x0, y0 = max(0, int(cx - ancho / 2)), max(0, int(cy - alto / 2))
    recorte = imagen[y0:min(h, int(cy + alto / 2)), x0:min(w, int(cx + ancho / 2))]
    return rellenar(recorte, tapados, (x0, y0)) if tapados and recorte.size else recorte


def vistas_confiables(filas, forma, min_conf=0.55, min_alto=40, max_iou=0.2, margen_borde=4, occluders=None, min_visible=None):
    """Índices de filas aptas para Re-ID: buena confianza, altura suficiente, lejos del borde y sin oclusión.

    `forma` es (alto, ancho) del frame. `occluders` son otras cajas que tapan (por defecto, las demás filas).
    Con `min_visible` (0 a 1) la oclusión no descarta por solape de cajas sino por la fracción del recuadro que sigue visible
    después de tapar lo que cubren las personas de adelante (ver `tapadores`): el recorte se rellena y el vector no mezcla ropa.
    """
    alto_f, ancho_f = forma[0], forma[1]
    cajas = np.array([[f[k] for k in ("x1", "y1", "x2", "y2")] for f in filas], np.float32).reshape(-1, 4)
    otras_cajas = cajas if occluders is None else np.asarray(occluders, dtype=np.float32).reshape(-1, 4)
    aptas = []
    for indice, (fila, caja) in enumerate(zip(filas, cajas)):
        if fila["confidence"] < min_conf or caja[3] - caja[1] < min_alto or caja[2] - caja[0] < 8:
            continue
        if (caja[0] < margen_borde or caja[1] < margen_borde
                or caja[2] > ancho_f - margen_borde or caja[3] > alto_f - margen_borde):
            continue
        if min_visible is not None:
            if tapadores(caja[None], otras_cajas)[0][0] < min_visible:
                continue
            aptas.append(indice)
            continue
        # Contra todas las demás cajas a la vez. La propia detección (a <= 1 px) no se tapa a sí misma.
        otras = otras_cajas[~np.all(np.abs(caja - otras_cajas) <= 1 + 1e-5 * np.abs(otras_cajas), axis=1)]
        if len(otras):
            ancho = np.maximum(0, np.minimum(caja[2], otras[:, 2]) - np.maximum(caja[0], otras[:, 0]))
            alto = np.maximum(0, np.minimum(caja[3], otras[:, 3]) - np.maximum(caja[1], otras[:, 1]))
            interseccion = ancho * alto
            area = max(0.0, caja[2] - caja[0]) * max(0.0, caja[3] - caja[1])
            areas = np.maximum(0, otras[:, 2] - otras[:, 0]) * np.maximum(0, otras[:, 3] - otras[:, 1])
            iou = interseccion / (area + areas - interseccion + 1e-8)
            if np.any(iou > max_iou) or np.any(interseccion / max(1, np.prod(caja[2:] - caja[:2])) > max_iou):
                continue
        aptas.append(indice)
    return aptas
