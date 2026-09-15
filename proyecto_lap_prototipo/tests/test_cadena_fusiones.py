"""
Reproduce el bug real: un id que ya fue adoptado por otro track (fusion A) se
fusiona el mismo, mas tarde, en un tercer id (fusion B). Sin resolver()
con compresion de camino, una referencia guardada antes de la segunda fusion
queda apuntando a un id ya borrado de `personas` -> KeyError.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
import persistence

bd = persistence.crear_bd(":memory:")
personas = {"A": "obj_a", "B": "obj_b", "C": "obj_c"}
redirecciones = {}


def resolver(id_global):
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


# Una referencia externa (simula local_a_global de un track que NO participa
# en las fusiones, pero fue fusionado al id "A" hace rato) guardada ANTES
# de que "A" mismo vuelva a fusionarse.
referencia_guardada = resolver("A")
assert referencia_guardada == "A"

# Fusion 1: A se fusiona en B (alguien mas ya uso "A" como su id, ahora A->B)
r1 = fusionar_en("A", "B", t=1.0)
assert r1 == "B" and "A" not in personas

# Fusion 2: B (que ya absorbio a A) se fusiona en C
r2 = fusionar_en("B", "C", t=2.0)
assert r2 == "C" and "B" not in personas

# La referencia vieja que un track pudo haber guardado como "A" debe resolver
# a "C" sin KeyError, en vez de quedar colgada.
resultado_final = resolver(referencia_guardada)
assert resultado_final == "C", f"esperaba C, dio {resultado_final}"
assert resultado_final in personas, "el id resuelto debe seguir existiendo en personas"

print("[OK] cadena de fusiones A->B->C resuelve correctamente, sin ids colgados")
print("[OK] personas restantes:", list(personas.keys()))
