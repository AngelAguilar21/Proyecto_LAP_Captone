"""Eventos espaciales por persona: EXPOSURE, ENTER, DWELL, EXIT, RETURN y QUEUE.

Portado de AeroVision (historico/eventos.py) sin pandas. Trabaja sobre un Consolidado con la zona de cada posición.
"""
from dataclasses import dataclass

import numpy as np


@dataclass
class Estancia:
    """Tramo continuo de una persona dentro de una misma zona (o fuera de todas: zona -1)."""
    global_id: str
    zona: int
    inicio_s: float
    fin_s: float
    confianza: float
    velocidad_mediana: float | None

    @property
    def duracion_s(self):
        return self.fin_s - self.inicio_s


def estancias(consolidado, paso_s, tolerancia_s, interiores=()):
    """Tramos por persona a partir de la zona de cada posición consolidada.

    Una salida más corta que `tolerancia_s` entre dos tramos de la misma zona se considera ruido del borde y los une (una
    persona que roza el límite no genera EXIT + ENTER). Por la misma razón, un tramo más corto que `tolerancia_s` en una
    de las zonas `interiores` pasa al tramo vecino: quien roza el borde de un local al caminar por su frente no cuenta
    como visita.
    """
    salida = {}
    for gid, sl in consolidado.personas():
        t, z = consolidado.t[sl], consolidado.zona[sl]
        conf, vel = consolidado.confianza[sl], consolidado.velocidad[sl]
        cortes = np.flatnonzero(np.diff(z)) + 1
        tramos = [[int(z[a]), a, b] for a, b in zip(np.r_[0, cortes], np.r_[cortes, len(z)])]
        unidos = True
        while unidos and len(tramos) >= 3:
            unidos = False
            for i in range(1, len(tramos) - 1):
                antes, despues = tramos[i - 1], tramos[i + 1]
                if antes[0] == despues[0] and t[despues[1]] - t[antes[2] - 1] - paso_s < tolerancia_s:
                    tramos[i - 1:i + 2] = [[antes[0], antes[1], despues[2]]]
                    unidos = True
                    break
        breve = lambda tramo: tramo[0] in interiores and t[tramo[2] - 1] + paso_s - t[tramo[1]] < tolerancia_s
        i = 0
        while len(tramos) > 1 and i < len(tramos):
            if not breve(tramos[i]):
                i += 1
            elif i == 0:
                tramos[0:2] = [[tramos[1][0], tramos[0][1], tramos[1][2]]]
            else:
                antes = tramos[i - 1]
                antes[2] = tramos.pop(i)[2]
                if i < len(tramos) and tramos[i][0] == antes[0]:
                    antes[2] = tramos.pop(i)[2]
        lista = []
        for zona, a, b in tramos:
            v = vel[a:b][np.isfinite(vel[a:b])]
            lista.append(Estancia(gid, zona, float(t[a]), float(t[b - 1] + paso_s), float(np.mean(conf[a:b])),
                                  float(np.median(v)) if len(v) else None))
        salida[gid] = lista
    return salida


def generar_eventos(estancias_persona, zonas, p):
    """Eventos de una persona según las reglas operativas de la metodología.

    - EXPOSURE: cruce por la zona FRONTAGE de un local.
    - ENTER: paso desde el exterior o FRONTAGE hacia INTERIOR. Si la persona aparece ya dentro (no se vio la transición),
      cuenta con confianza reducida.
    - DWELL: permanencia en INTERIOR de al menos `dwell_min_s`.
    - EXIT: paso desde INTERIOR hacia afuera (no hay EXIT si la trayectoria termina dentro).
    - RETURN: nuevo ENTER al mismo local tras un EXIT y al menos `retorno_min_s`.
    - QUEUE: permanencia en una zona COLA con velocidad reducida.
    """
    eventos, ultima_salida, tramos = [], {}, estancias_persona
    for i, e in enumerate(tramos):
        z = zonas.get(e.zona)
        if z is None:
            continue
        base = {"global_id": e.global_id, "zone_id": z.id}
        if z.tipo == "FRONTAGE":
            eventos.append({**base, "event_type": "EXPOSURE", "inicio_s": e.inicio_s, "fin_s": e.fin_s, "confianza": e.confianza})
        elif z.tipo == "INTERIOR":
            confianza = e.confianza * (1.0 if i > 0 else p["confianza_sin_transicion"])
            eventos.append({**base, "event_type": "ENTER", "inicio_s": e.inicio_s, "fin_s": None, "confianza": confianza})
            salida_previa = ultima_salida.get(z.local_id)
            if salida_previa is not None and e.inicio_s - salida_previa >= p["retorno_min_s"]:
                eventos.append({**base, "event_type": "RETURN", "inicio_s": e.inicio_s, "fin_s": None, "confianza": confianza})
            if e.duracion_s >= p["dwell_min_s"]:
                eventos.append({**base, "event_type": "DWELL", "inicio_s": e.inicio_s, "fin_s": e.fin_s, "confianza": e.confianza})
            if i < len(tramos) - 1:
                eventos.append({**base, "event_type": "EXIT", "inicio_s": e.fin_s, "fin_s": None, "confianza": e.confianza})
                ultima_salida[z.local_id] = e.fin_s
        elif z.tipo == "COLA":
            lenta = e.velocidad_mediana is not None and e.velocidad_mediana <= p["cola_velocidad_max_mps"]
            if e.duracion_s >= p["cola_min_s"] and lenta:
                eventos.append({**base, "event_type": "QUEUE", "inicio_s": e.inicio_s, "fin_s": e.fin_s, "confianza": e.confianza})
    return eventos
