"""
Orquesta el pipeline completo sobre los dos videos de la explanada:
lectura sincronizada -> deteccion de cabezas (P2PNet) -> tracking mono-camara
(ByteTrack sobre puntos) -> mapeo al plano compartido -> fusion entre camaras
(misma persona vista por A y B a la vez) -> persistencia -> visualizacion.

Camara A y camara B ven la MISMA explanada desde angulo/altura distintos
(campo de vision superpuesto), no dos extremos de un pasillo con hueco en
medio -- ver src/cross_camera.py para el porque del cambio de enfoque.

Requisitos previos (ver src/detection.py y src/calibrar_camara.py):
  1. git submodule update --init external/P2PNet
  2. python src/aplicar_parche_p2pnet.py (compatibilidad con torch/torchvision
     modernos -- P2PNet es codigo de 2021, ver el propio script para el detalle).
  3. Checkpoint preentrenado: external/P2PNet/weights/SHTechA.pth ya viene
     incluido en el repo oficial, no hace falta descargar nada aparte.
  4. Copiar los dos videos a data/camera_A.mp4 y data/camera_B.mp4.
  5. Calibrar cada camara con calibrar_camara.py usando la loseta del piso
     como referencia de distancia real, con el MISMO origen y ejes para las
     dos camaras (imprescindible: sin un plano compartido consistente, la
     fusion entre camaras compara posiciones que no significan lo mismo).
  6. (Recomendado) Marcar el area util de cada camara con marcar_alcance.py:
     P2PNet detecta sobre el frame completo, y sin este filtro tambien
     detecta cosas fuera de la explanada (el reflejo del vidrio del
     edificio, la pared, el techo), generando identificadores falsos que
     nunca se fusionan con nada.

Uso basico:
    python main.py --pesos-p2pnet external/P2PNet/weights/SHTechA.pth --mostrar-visualizacion
"""
import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))

import cv2  # noqa: E402

import nodes  # noqa: E402
import persistence  # noqa: E402
import visualize  # noqa: E402
from cross_camera import GestorContinuidad  # noqa: E402
from detection import DetectorP2PNet  # noqa: E402
from tracking import ByteTrackPuntos  # noqa: E402


def procesar(args):
    camaras, area_comun = nodes.cargar_camaras(args.config_camaras, args.calibracion)
    zonas = nodes.cargar_zonas(args.zonas)
    alcances = nodes.cargar_alcances(args.alcance)
    if alcances:
        print(f"Alcance manual cargado para: {sorted(alcances.keys())}")
    else:
        print("Sin alcance manual configurado -- se detecta en el frame completo de cada camara "
              "(ver src/marcar_alcance.py para restringir la zona util).")

    detector = DetectorP2PNet(args.pesos_p2pnet, umbral=args.umbral_deteccion)
    gestor = GestorContinuidad(camaras, umbral_distancia_metros=args.umbral_distancia_fusion)
    bd = persistence.crear_bd(args.salida_bd)

    estado_camaras = {}
    for id_camara, camara in camaras.items():
        captura = cv2.VideoCapture(camara.video_path)
        if not captura.isOpened():
            raise RuntimeError(f"No se pudo abrir el video de la camara {id_camara}: {camara.video_path}")
        estado_camaras[id_camara] = {
            "captura": captura,
            "tracker": ByteTrackPuntos(),
            "sustractor": nodes.crear_sustractor_fondo(),
            "fps": captura.get(cv2.CAP_PROP_FPS) or 25.0,
            "local_a_global": {},  # track.id (local a esta camara) -> id_global
            "ancho": int(captura.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "alto": int(captura.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "poligono_alcance": alcances.get(id_camara),
            "pendientes": {},  # track.id -> t_creacion, mientras el id asignado siga siendo provisional
        }

    # Reloj compartido entre las dos camaras: asume que ambas grabaron al
    # mismo fps nominal (dos telefonos filmando el mismo evento). El desfase
    # de arranque, si existe, se corrige saltando frames en una de ellas
    # (ver src/sincronizar.py para encontrar el offset).
    fps_global = next(iter(estado_camaras.values()))["fps"]

    if args.offset_camara and args.offset_frames:
        for _ in range(args.offset_frames):
            estado_camaras[args.offset_camara]["captura"].read()

    personas = {}  # id_global -> nodes.NodoPersona
    redirecciones = {}  # id_viejo -> id_nuevo, cuando una fusion tardia junta dos ids que ya existian

    def resolver(id_global):
        """Sigue la cadena de redirecciones hasta el id_global vivo. Hace
        falta porque un id que ya fue adoptado por un track (via fusion)
        puede el mismo terminar fusionado en otro mas tarde; sin esto, una
        referencia guardada en local_a_global quedaria apuntando a un id
        que ya no existe en `personas`."""
        while id_global in redirecciones:
            id_global = redirecciones[id_global]
        return id_global

    def fusionar_en(id_viejo, id_nuevo, t):
        id_viejo, id_nuevo = resolver(id_viejo), resolver(id_nuevo)
        if id_viejo == id_nuevo:
            return id_nuevo
        persistence.fusionar_persona(bd, id_viejo, id_nuevo, t)
        personas.pop(id_viejo, None)
        redirecciones[id_viejo] = id_nuevo
        return id_nuevo

    indice_frame = 0

    while True:
        alguna_activa = False
        t = indice_frame / fps_global

        for id_camara, camara in camaras.items():
            estado = estado_camaras[id_camara]
            ok, frame = estado["captura"].read()
            if not ok:
                continue
            alguna_activa = True

            mascara_fg = estado["sustractor"].apply(frame)
            detecciones = detector.detectar(frame)
            poligono = estado["poligono_alcance"]
            if poligono is not None:
                detecciones = [d for d in detecciones if nodes.dentro_del_alcance(d.x, d.y, poligono)]
            tracks_activos, _nuevos, expirados = estado["tracker"].actualizar(detecciones, t)

            for track in tracks_activos:
                x_plano, y_plano = camara.pixel_a_plano(*track.posicion, estado["ancho"], estado["alto"])
                descriptor = nodes.extraer_descriptor(frame, mascara_fg, track.posicion)

                id_global = estado["local_a_global"].get(track.id)
                if id_global is not None:
                    id_global = resolver(id_global)
                    estado["local_a_global"][track.id] = id_global  # compresion de camino

                if id_global is None:
                    # Track nuevo en esta camara: puede ser una persona que la
                    # otra camara ya esta viendo en el mismo lugar (fusionar)
                    # o alguien genuinamente nuevo en el sistema.
                    id_global = gestor.intentar_fusionar(id_camara, x_plano, y_plano, t, descriptor)
                    if id_global is None:
                        persona = nodes.NodoPersona()
                        personas[persona.id_global] = persona
                        id_global = persona.id_global
                        estado["pendientes"][track.id] = t
                    else:
                        id_global = resolver(id_global)
                        personas[id_global].actualizar_descriptor(descriptor)
                    estado["local_a_global"][track.id] = id_global
                else:
                    personas[id_global].actualizar_descriptor(descriptor)
                    if track.id in estado["pendientes"]:
                        # Todavia no se fusiono con la otra camara: reintentar
                        # cada frame con la posicion actual (no solo la de
                        # nacimiento), sin cortar por edad del track. El
                        # filtro real de seguridad ya esta en
                        # intentar_fusionar (ventana_temporal_s de 1s contra
                        # el dato mas fresco de la otra camara): cortar aqui
                        # ademas, a una edad fija, solo descarta fusiones
                        # legitimas cuando la convergencia geometrica tarda
                        # mas de ese margen (angulo oblicuo, persona que
                        # entra por un borde de la otra camara mas tarde).
                        id_fusion = gestor.intentar_fusionar(id_camara, x_plano, y_plano, t, descriptor)
                        if id_fusion is not None:
                            id_fusion = resolver(id_fusion)
                            if id_fusion != id_global:
                                id_global = fusionar_en(id_global, id_fusion, t)
                                estado["local_a_global"][track.id] = id_global
                                personas[id_global].actualizar_descriptor(descriptor)
                            estado["pendientes"].pop(track.id, None)

                zona = nodes.punto_en_zona((x_plano, y_plano), zonas)
                personas[id_global].agregar_posicion(x_plano, y_plano, t, zona, id_camara, predicha=False)
                persistence.guardar_posicion(bd, id_global, id_camara, x_plano, y_plano, t, zona, predicha=False)
                gestor.actualizar_posicion(id_global, x_plano, y_plano, t, personas[id_global].descriptor, id_camara)

            for track in expirados:
                estado["local_a_global"].pop(track.id, None)
                estado["pendientes"].pop(track.id, None)

        gestor.purgar_antiguos(t)
        bd.commit()  # una vez por frame, no por deteccion: ver persistence.guardar_posicion

        if not alguna_activa:
            break
        indice_frame += 1
        if args.max_frames and indice_frame >= args.max_frames:
            break

    bd.commit()
    for estado in estado_camaras.values():
        estado["captura"].release()

    print(f"Procesamiento terminado: {len(personas)} nodos-persona globales, "
          f"{indice_frame} frames por camara.")

    if args.salida_video or args.mostrar_visualizacion:
        filas = persistence.cargar_todas_las_posiciones(bd)
        filas = visualize.filtrar_ruido(filas, duracion_min_s=args.duracion_min_visualizacion)
        frames_animacion = visualize.agrupar_por_tiempo(filas)
        visualize.reproducir(frames_animacion, area_comun, zonas, camaras, alcances,
                              ruta_salida=args.salida_video)


def construir_parser():
    raiz = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pesos-p2pnet", required=True,
                         help="Checkpoint preentrenado de P2PNet (ver external/P2PNet, README oficial).")
    parser.add_argument("--config-camaras", default=str(raiz / "config" / "camaras.json"))
    parser.add_argument("--calibracion", default=str(raiz / "config" / "calibracion.json"))
    parser.add_argument("--alcance", default=str(raiz / "config" / "alcance.json"),
                         help="Poligono por camara (ver src/marcar_alcance.py) que restringe donde se buscan "
                              "cabezas, para descartar reflejos/fondo. Si el archivo no existe, no se filtra.")
    parser.add_argument("--zonas", default=str(raiz / "data" / "plano_zonas.json"))
    parser.add_argument("--salida-bd", default=str(raiz / "data" / "historial.sqlite"))
    parser.add_argument("--salida-video", default=None, help="Ruta .mp4 para guardar la visualizacion.")
    parser.add_argument("--mostrar-visualizacion", action="store_true")
    parser.add_argument("--duracion-min-visualizacion", type=float, default=0.5,
                         help="Segundos: ids rastreados por menos tiempo que esto se tratan como "
                              "parpadeos de deteccion y se excluyen solo del video/consola, no de la BD.")
    parser.add_argument("--umbral-deteccion", type=float, default=0.5)
    parser.add_argument("--umbral-distancia-fusion", type=float, default=1.5,
                         help="Metros: que tan cerca deben estar dos detecciones de camaras distintas "
                              "para considerarlas la misma persona.")
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--offset-camara", choices=["A", "B"], default=None,
                         help="Si un video arranca antes que el otro, cual hay que adelantar.")
    parser.add_argument("--offset-frames", type=int, default=0)
    return parser


if __name__ == "__main__":
    procesar(construir_parser().parse_args())
