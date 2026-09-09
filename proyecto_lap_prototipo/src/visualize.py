"""
Reproduccion de los nodos-persona sobre el plano compartido de la explanada.
Camara A y B ven la misma area desde angulos distintos (no estan "paradas" en
un punto del plano como en un pasillo con extremos), asi que aqui solo se
dibujan las zonas y las personas -- el nombre de ambas camaras va como titulo.
Sirve para validar a ojo, contra los videos originales, que una persona vista
por las dos camaras a la vez termina como un solo punto/ID y no como dos.
"""
from collections import defaultdict

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.patheffects as pe
from matplotlib.animation import FuncAnimation
import numpy as np

COLOR_ZONA = {
    "area_comun": "#cfe8ff",
}

COLOR_ALCANCE = {
    "A": "#c2542f",
    "B": "#2f7cc2",
}


def _dibujar_plano(ax, area_comun, zonas, camaras):
    ax.set_xlim(-1, area_comun["largo_metros"] + 1)
    ax.set_ylim(-1, area_comun["ancho_metros"] + 1)
    ax.set_aspect("equal")
    ax.set_xlabel("metros (plano compartido, calibrado)")
    ax.set_yticks([])
    ax.set_title(" + ".join(f"Camara {c.id}" for c in camaras.values()) + " (vista superpuesta)",
                 fontsize=10, fontweight="bold")

    for zona in zonas:
        poligono = zona["poligono"]
        color = COLOR_ZONA.get(zona["tipo"], "#ffffff")
        parche = patches.Polygon(poligono, closed=True, facecolor=color, edgecolor="#999999", alpha=0.6)
        ax.add_patch(parche)
        cx, cy = poligono.mean(axis=0)
        ax.text(cx, cy, zona["id"], ha="center", va="center", fontsize=8, color="#444444")


def _dibujar_alcances(ax, camaras, alcances):
    """Dibuja el contorno del area util de cada camara (ver marcar_alcance.py)
    proyectado al plano compartido -- muestra a que parte de la explanada
    llega la deteccion de cada camara, no solo donde detecto gente."""
    if not alcances:
        return
    for id_camara, poligono_px in alcances.items():
        camara = camaras.get(id_camara)
        if camara is None or camara.homografia is None:
            continue
        color = COLOR_ALCANCE.get(id_camara, "#888888")
        puntos_plano = [camara.pixel_a_plano(float(px), float(py), 0, 0) for px, py in poligono_px]
        parche = patches.Polygon(puntos_plano, closed=True, fill=False,
                                  edgecolor=color, linewidth=1.6, linestyle=(0, (5, 3)))
        ax.add_patch(parche)
        cx = sum(p[0] for p in puntos_plano) / len(puntos_plano)
        cy = min(p[1] for p in puntos_plano) - 0.25
        ax.text(cx, cy, f"alcance camara {id_camara}", fontsize=7.5, color=color,
                ha="center", style="italic", fontweight="bold")


def filtrar_ruido(filas_posiciones, duracion_min_s=0.5):
    """Descarta ids cuya duracion total rastreada es menor al umbral: son
    parpadeos de deteccion de 1-2 frames de P2PNet (reflejos, jitter), no
    personas reales -- confirmado contra los videos originales. Deja intacta
    la base de datos; solo filtra lo que se dibuja."""
    if not filas_posiciones:
        return filas_posiciones
    tiempos = defaultdict(list)
    for fila in filas_posiciones:
        tiempos[fila[0]].append(fila[4])
    ids_validos = {idp for idp, ts in tiempos.items() if (max(ts) - min(ts)) >= duracion_min_s}
    return [fila for fila in filas_posiciones if fila[0] in ids_validos]


def reproducir(posiciones_por_tiempo, area_comun, zonas, camaras, alcances=None,
                ruta_salida=None, fps=10):
    """posiciones_por_tiempo: lista ordenada de frames, cada uno una lista de
    dicts {id_persona, x, y, predicha}. Genera y opcionalmente guarda una
    animacion matplotlib (mp4 via ffmpeg, ya incluido en el Dockerfile)."""
    fig, ax = plt.subplots(figsize=(10, 7), dpi=120)
    _dibujar_plano(ax, area_comun, zonas, camaras)
    _dibujar_alcances(ax, camaras, alcances or {})

    colores_por_id = {}
    paleta = matplotlib.colormaps["tab10"]

    def color_para(id_persona):
        if id_persona not in colores_por_id:
            colores_por_id[id_persona] = paleta(len(colores_por_id) % 10)
        return colores_por_id[id_persona]

    dispersion = ax.scatter([], [], s=80)
    etiquetas = []

    def actualizar(indice_frame):
        for etiqueta in etiquetas:
            etiqueta.remove()
        etiquetas.clear()

        frame = posiciones_por_tiempo[indice_frame]
        if not frame:
            dispersion.set_offsets(np.empty((0, 2)))
            return dispersion,

        xs = [p["x"] for p in frame]
        ys = [p["y"] for p in frame]
        colores = [color_para(p["id_persona"]) for p in frame]
        dispersion.set_offsets(np.column_stack([xs, ys]))
        dispersion.set_color(colores)
        dispersion.set_edgecolor(["black" if p["predicha"] else "none" for p in frame])
        dispersion.set_linewidths([1.5 if p["predicha"] else 0 for p in frame])

        for p in frame:
            etiqueta = ax.text(p["x"], p["y"] + 0.22, p["id_persona"][:6], fontsize=9,
                                ha="center", fontweight="bold", color=color_para(p["id_persona"]),
                                path_effects=[pe.withStroke(linewidth=2.2, foreground="white")])
            etiquetas.append(etiqueta)
        return dispersion,

    animacion = FuncAnimation(fig, actualizar, frames=len(posiciones_por_tiempo),
                               interval=1000 / fps, blit=False)

    if ruta_salida:
        animacion.save(ruta_salida, fps=fps)
        plt.close(fig)
    else:
        plt.show()
    return animacion


def agrupar_por_tiempo(filas_posiciones, paso_tiempo=0.1):
    """Convierte filas de persistence.cargar_todas_las_posiciones (id_persona,
    camara, x, y, t, zona, predicha) en una lista de frames agrupados por
    bins de tiempo, listos para pasarle a `reproducir`."""
    if not filas_posiciones:
        return []
    t_min = min(fila[4] for fila in filas_posiciones)
    t_max = max(fila[4] for fila in filas_posiciones)
    n_bins = max(1, int((t_max - t_min) / paso_tiempo) + 1)
    frames = [[] for _ in range(n_bins)]
    for id_persona, camara, x, y, t, zona, predicha in filas_posiciones:
        indice = min(int((t - t_min) / paso_tiempo), n_bins - 1)
        frames[indice].append({"id_persona": id_persona, "x": x, "y": y, "predicha": bool(predicha)})
    return frames
