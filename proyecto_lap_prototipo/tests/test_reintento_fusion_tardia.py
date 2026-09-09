"""
Simula el escenario real encontrado: un track en camara A y otro en camara B
que nacen lejos entre si (o en momentos distintos) y luego, unos frames mas
tarde, sus posiciones convergen (distancia 0.22, dt 0.77s, como se midio en
los datos reales). Sin reintento, quedarian como 2 ids separados para
siempre -- se fusionan solo una vez, justo al nacer el track.

El reintento NO tiene limite de edad del track: se sigue intentando cada
frame mientras el track no se haya fusionado todavia, confiando en que
intentar_fusionar ya exige una posicion fresca (ventana_temporal_s) del otro
lado. Un limite de edad fijo (probado antes con 2.0s) descartaria fusiones
legitimas cuando la convergencia geometrica tarda mas que eso -- el segundo
escenario de este archivo prueba exactamente ese caso (convergen recien a
los 3s).
"""
import sys
from pathlib import Path

RAIZ = Path(r"C:\Users\PC-01\OneDrive - Universidad ESAN\Escritorio\PROYECTO_LAP_CAPSTONE\Proyecto_LAP_Captone\proyecto_lap_prototipo")
sys.path.insert(0, str(RAIZ / "src"))

import nodes
import persistence
from cross_camera import GestorContinuidad


def simular(pares_ab, umbral_distancia_metros=1.5):
    """pares_ab: lista de (t, xa, ya, xb, yb). Reproduce el bucle de
    reintento sin limite de edad, tal como quedo en main.py."""
    camaras, _ = nodes.cargar_camaras(str(RAIZ / "config" / "camaras.json"))
    gestor = GestorContinuidad(camaras, umbral_distancia_metros=umbral_distancia_metros)
    bd = persistence.crear_bd(":memory:")
    personas = {}
    pendientes = {}       # (camara, track_id) -> True mientras siga sin fusionar
    local_a_global = {}   # (camara, track_id) -> id_global

    def procesar_frame(camara_id, track_id, x, y, t, descriptor=None):
        clave = (camara_id, track_id)
        id_global = local_a_global.get(clave)

        if id_global is None:
            id_global = gestor.intentar_fusionar(camara_id, x, y, t, descriptor)
            if id_global is None:
                persona = nodes.NodoPersona()
                personas[persona.id_global] = persona
                id_global = persona.id_global
                pendientes[clave] = True
            local_a_global[clave] = id_global
        elif clave in pendientes:
            id_fusion = gestor.intentar_fusionar(camara_id, x, y, t, descriptor)
            if id_fusion is not None:
                if id_fusion != id_global:
                    persistence.fusionar_persona(bd, id_global, id_fusion, t)
                    personas.pop(id_global, None)
                    id_global = id_fusion
                    local_a_global[clave] = id_global
                pendientes.pop(clave, None)

        personas[id_global].agregar_posicion(x, y, t, "explanada", camara_id, predicha=False)
        persistence.guardar_posicion(bd, id_global, camara_id, x, y, t, "explanada", predicha=False)
        gestor.actualizar_posicion(id_global, x, y, t, None, camara_id)
        return id_global

    ids_a, ids_b = [], []
    for t, xa, ya, xb, yb in pares_ab:
        ids_a.append(procesar_frame("A", "trackA", x=xa, y=ya, t=t))
        ids_b.append(procesar_frame("B", "trackB", x=xb, y=yb, t=t + 0.05))
    return ids_a, ids_b, bd


# --- Escenario 1 (caso real medido): A nace lejos en t=0, B nace lejos en
# t=0.3; desde t=1.0 convergen al mismo punto real (distancia < 0.3, dentro
# del segundo de margen de intentar_fusionar).
pares_rapido = []
for i in range(10):
    t = i * 0.3
    if t < 1.0:
        pares_rapido.append((t, 0.0, 0.0, 5.0, 5.0))
    else:
        pares_rapido.append((t, 2.0, 2.0, 2.05, 2.02))

ids_a, ids_b, bd = simular(pares_rapido)
print("ids de A a lo largo del tiempo:", ids_a)
print("ids de B a lo largo del tiempo:", ids_b)
assert ids_a[-1] == ids_b[-1], "Deberian terminar con el mismo id_global tras converger"
print(f"[OK] convergencia rapida (~1s): A y B terminan fusionados en {ids_a[-1]}")

ids_en_bd = set(f[0] for f in persistence.cargar_todas_las_posiciones(bd))
assert len(ids_en_bd) == 1
print(f"[OK] historial persistido usa un solo id ({ids_en_bd})")

# --- Escenario 2 (lo que la ventana de gracia fija de 2.0s antes descartaba):
# A y B nacen lejos y se mantienen lejos durante 3s -- mas de lo que
# cualquier ventana de gracia corta habria tolerado -- y recien despues
# convergen. Con el reintento sin limite de edad, deben fusionarse igual.
pares_lento = []
for i in range(30):
    t = i * 0.3
    if t < 3.0:
        pares_lento.append((t, 0.0, 0.0, 5.0, 5.0))
    else:
        pares_lento.append((t, 2.0, 2.0, 2.05, 2.02))

ids_a2, ids_b2, bd2 = simular(pares_lento)
assert ids_a2[-1] == ids_b2[-1], "Debe fusionar aunque la convergencia tarde mas de 2s"
print(f"[OK] convergencia tardia (~3s, fuera de cualquier ventana fija corta): "
      f"A y B terminan fusionados en {ids_a2[-1]}")
