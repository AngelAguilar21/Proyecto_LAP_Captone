"""Reagrupación al cerrar la sesión: la evidencia física manda sobre el parecido visual.

Con la sesión completa se vuelve a decidir qué tracklets son la misma persona:
1. Dos tracklets de cámaras distintas que estuvieron juntos en el plano (mediana de distancia pequeña durante varios
   segundos) son la misma persona, si ninguno tiene otro candidato casi igual de cerca (en un grupo apretado la
   posición no distingue a una persona de su vecina y no se une nada por el plano). Dos que coinciden en el tiempo pero quedan lejos, o dos de la misma cámara que
   coinciden en el tiempo, no pueden serlo (choque).
2. Después se respeta lo que el asociador decidió en vivo (mismo `global_id`) y se vuelve a unir salvo choque o poco
   parecido entre sus prototipos Re-ID.
3. Agrupamiento global por apariencia (OSNet): con toda la sesión a la vista se juntan, de más a menos parecidos, los grupos
   cuyo prototipo Re-ID promedio supera `min_parecido_global`, sin juntar nunca dos que choquen (la misma cámara a la vez,
   o dos cámaras a la vez en lugares muy distintos del plano). Es el esquema de DeepCC (Ristani y Tomasi, 2018) y del AI City
   Challenge 2023: agrupar tramos por apariencia con restricciones. Aquí la apariencia manda; el plano solo veta.
4. Cuentan como persona los grupos con suficientes vistas y tiempo visible; se renumeran de 1 a N por orden de aparición.

Portado de AeroVision (mapa_2d.ReagrupadorMapa) sin filas de video: trabaja con las series de posición de cada tracklet.
Las distancias se expresan como fracción de la distancia de solape (`escala`), que en AeroTrack sale de matchDistance.
Sin geometría coherente entre cámaras (`usar_posicion=False`) solo actúan los pasos 2 y 3.
"""
from collections import defaultdict

import numpy as np

# Proporciones de AeroVision (0,7 / 1,0 / 2,0 m con una distancia de solape de 1,5 m).
AMBIGUEDAD = 0.6   # el mejor candidato debe estar a menos de esta fracción de la distancia del segundo
MEDIANA_JUNTOS = 0.47
CERCA = 0.67
SEPARADOS = 1.33


class _Grupos:
    """Conjuntos disjuntos de tracklets que nunca juntan dos tracklets que chocan."""

    def __init__(self, uids, choques, gate=None):
        self.de = {u: u for u in uids}
        self.miembros = {u: {u} for u in uids}
        self.choques = choques
        self.gate = gate

    def unir(self, a, b, aceptar=None):
        """Une los grupos de a y b; False si algún par choca o si aceptar(miembros_a, miembros_b) lo rechaza."""
        ga, gb = self.de[a], self.de[b]
        if ga == gb:
            return True
        if any((x, y) in self.choques for x in self.miembros[ga] for y in self.miembros[gb]):
            return False
        if self.gate is not None and not self.gate(self.miembros[ga], self.miembros[gb]):
            return False
        if aceptar is not None and not aceptar(self.miembros[ga], self.miembros[gb]):
            return False
        if len(self.miembros[ga]) < len(self.miembros[gb]):
            ga, gb = gb, ga
        for u in self.miembros.pop(gb):
            self.de[u] = ga
            self.miembros[ga].add(u)
        return True


def _segundos_visibles(intervalos):
    """Duración de la unión de intervalos (inicio, fin)."""
    total, (inicio, fin) = 0.0, min(intervalos)
    for a, b in sorted(intervalos):
        if a > fin:
            total, inicio, fin = total + fin - inicio, a, b
        else:
            fin = max(fin, b)
    return total + fin - inicio


class ReagrupadorPlano:
    """Reagrupa tracklets con su posición en el plano y, solo si no la contradice, con el Re-ID."""

    def __init__(self, escala=1.6, fps=5.0, min_juntos_s=2.0, min_parecido=0.50, min_muestras=5, min_visible_s=2.0, usar_posicion=True,
                 min_parecido_global=0.60, min_vistas_global=2, factor_separados=SEPARADOS, pair_gate=None, group_gate=None):
        self.pair_gate = pair_gate
        self.group_gate = group_gate
        self.min_parecido_global, self.min_vistas_global = min_parecido_global, min_vistas_global
        self.escala, self.fps = float(escala), float(fps)
        self.max_mediana, self.cerca, self.separados = MEDIANA_JUNTOS * escala, CERCA * escala, factor_separados * escala
        self.min_juntos_s, self.min_parecido = min_juntos_s, min_parecido
        self.min_muestras, self.min_visible_s, self.usar_posicion = min_muestras, min_visible_s, usar_posicion

    def __call__(self, tracklets, series, prototipos):
        """tracklets: [{uid, camera, gid, inicio, fin, muestras}], series: {uid: [(t, x, y)]}, prototipos: {uid: vector}.

        Devuelve {"publico": {uid: n}, "cambios": [...], "personas": N, "uniones_plano": n, "separados": n}.
        """
        datos = self._recorridos(tracklets, series)
        juntos, choques = self._pares(datos)
        gate = (lambda a, b: self.group_gate([datos[u] for u in a], [datos[u] for u in b])) if self.group_gate else None
        grupos = _Grupos(sorted(datos), choques, gate)
        for _, _, a, b in sorted(juntos):
            grupos.unir(a, b)
        separados = self._aplicar_reid(datos, grupos, prototipos)
        por_apariencia = self._agrupar_apariencia(datos, grupos, prototipos)
        contados = self._contar(datos, grupos)
        resultado = self._publicar(datos, grupos, contados, separados, len(juntos))
        resultado["uniones_apariencia"] = por_apariencia
        return resultado

    def _recorridos(self, tracklets, series):
        datos = {}
        for t in tracklets:
            serie = series.get(t["uid"], [])
            ticks = np.array([int(round(p[0] * self.fps)) for p in serie], dtype=np.int64)
            xy = np.array([[p[1], p[2]] for p in serie], dtype=np.float64).reshape(-1, 2)
            orden = np.argsort(ticks, kind="stable")
            ticks, xy = ticks[orden], xy[orden]
            _, unicos = np.unique(ticks, return_index=True)
            datos[t["uid"]] = {"camara": t["camera"], "gid": t["gid"], "t0": t["inicio"], "t1": t["fin"],
                               "muestras": t["muestras"], "ticks": ticks[unicos], "xy": xy[unicos]}
        return datos

    def _pares(self, datos):
        """Pares 'juntos' (-ticks compartidos, mediana, a, b) y conjunto de pares que chocan."""
        uids = sorted(datos)
        juntos, choques = [], set()
        medianas = defaultdict(dict)   # tracklet -> {otro tracklet de otra cámara: mediana de distancia}
        for i, a in enumerate(uids):
            for b in uids[i + 1:]:
                da, db = datos[a], datos[b]
                if self.pair_gate is not None and not self.pair_gate(da, db):
                    choques.update({(a, b), (b, a)})
                    continue
                if da["t1"] < db["t0"] - 1e-9 or db["t1"] < da["t0"] - 1e-9:
                    continue
                if da["camara"] == db["camara"]:
                    choques.update({(a, b), (b, a)})
                    continue
                if not self.usar_posicion:
                    continue
                _, ia, ib = np.intersect1d(da["ticks"], db["ticks"], assume_unique=True, return_indices=True)
                if len(ia) < self.fps:
                    continue
                distancia = np.linalg.norm(da["xy"][ia] - db["xy"][ib], axis=1)
                mediana = float(np.median(distancia))
                medianas[a][b] = medianas[b][a] = mediana
                if mediana > self.separados:
                    choques.update({(a, b), (b, a)})
                elif (len(ia) >= self.min_juntos_s * self.fps and mediana <= self.max_mediana
                      and np.mean(distancia < self.cerca) >= 0.9):
                    juntos.append((-len(ia), mediana, a, b))
        return [j for j in juntos if self._sin_rival(medianas, j[2], j[3]) and self._sin_rival(medianas, j[3], j[2])], choques

    @staticmethod
    def _sin_rival(medianas, a, b):
        """True si, entre los tracklets de la cámara de b, ningún otro está casi tan cerca de a como b."""
        otros = [d for u, d in medianas[a].items() if u != b and u.split("/")[0] == b.split("/")[0]]
        return not otros or medianas[a][b] <= AMBIGUEDAD * min(otros)

    def _aplicar_reid(self, datos, grupos, prototipos):
        """Vuelve a unir los tracklets de cada identidad viva salvo choque o poco parecido; devuelve los que quedan aparte."""
        def parecidos(miembros_a, miembros_b):
            A = [prototipos[u] for u in miembros_a if u in prototipos]
            B = [prototipos[u] for u in miembros_b if u in prototipos]
            return not A or not B or float((np.stack(A) @ np.stack(B).T).mean()) >= self.min_parecido

        por_gid = defaultdict(list)
        for uid, d in datos.items():
            por_gid[d["gid"]].append(uid)
        separados = []
        for gid, del_gid in sorted(por_gid.items()):
            anclas = []
            for uid in sorted(del_gid, key=lambda u: (-datos[u]["muestras"], u)):
                if not any(grupos.unir(ancla, uid, parecidos) for ancla in anclas):
                    anclas.append(uid)
            separados += [(gid, uid) for uid in anclas[1:]]
        return separados

    def _agrupar_apariencia(self, datos, grupos, prototipos):
        """Agrupamiento jerárquico (enlace promedio) por parecido OSNet entre grupos, con los choques como restricción.

        El parecido promedio ponderado por vistas entre dos grupos es (S_a . S_b) / (W_a W_b), con S la suma de los prototipos
        (unitarios) ponderados por su número de vistas y W la suma de pesos; al juntar dos grupos las sumas se suman.
        Devuelve cuántas uniones hizo."""
        pesos = {u: float(datos[u]["muestras"]) for u in datos if u in prototipos and datos[u]["muestras"] >= self.min_vistas_global}
        reps = [g for g, ms in grupos.miembros.items() if any(u in pesos for u in ms)]
        if len(reps) < 2:
            return 0
        n = len(reps)
        suma = np.stack([sum(pesos[u] * np.asarray(prototipos[u], np.float64) for u in grupos.miembros[g] if u in pesos) for g in reps])
        peso = np.array([sum(pesos[u] for u in grupos.miembros[g] if u in pesos) for g in reps])
        conflicto = np.zeros((n, n), bool)
        for i in range(n):
            for j in range(i + 1, n):
                if any((x, y) in grupos.choques for x in grupos.miembros[reps[i]] for y in grupos.miembros[reps[j]]):
                    conflicto[i, j] = conflicto[j, i] = True
        vivo = np.ones(n, bool)
        uniones = 0
        while True:
            sim = (suma @ suma.T) / np.outer(peso, peso)
            sim[~vivo, :] = -np.inf
            sim[:, ~vivo] = -np.inf
            sim[conflicto] = -np.inf
            np.fill_diagonal(sim, -np.inf)
            i, j = np.unravel_index(int(np.argmax(sim)), sim.shape)
            if not np.isfinite(sim[i, j]) or sim[i, j] < self.min_parecido_global:
                break
            suma[i] += suma[j]
            peso[i] += peso[j]
            conflicto[i] |= conflicto[j]
            conflicto[:, i] |= conflicto[:, j]
            conflicto[i, i] = False
            vivo[j] = False
            grupos.unir(reps[i], reps[j])
            uniones += 1
        return uniones

    def _contar(self, datos, grupos):
        """Grupos que cuentan como persona, ordenados por aparición."""
        contados = [ms for ms in grupos.miembros.values()
                    if sum(datos[u]["muestras"] for u in ms) >= self.min_muestras
                    and _segundos_visibles([(datos[u]["t0"], datos[u]["t1"]) for u in ms]) >= self.min_visible_s]
        return sorted(contados, key=lambda ms: (min(datos[u]["t0"] for u in ms), min(ms)))

    @staticmethod
    def _publicar(datos, grupos, contados, separados, n_juntos):
        publico = {u: i + 1 for i, ms in enumerate(contados) for u in ms}
        cambios = []
        for ms in contados:
            antes = sorted({datos[u]["gid"] for u in ms})
            if len(antes) != 1:
                cambios.append({"id": publico[next(iter(ms))], "cambio": "unión", "antes": [f"G{g}" for g in antes],
                                "camaras": sorted({datos[u]["camara"] for u in ms}), "tracklets": sorted(ms)})
        for gid, uid in separados:
            cambios.append({"id": publico.get(uid), "cambio": f"separado de G{gid}", "antes": [f"G{gid}"],
                            "camaras": [datos[uid]["camara"]], "tracklets": [uid]})
        return {"publico": publico, "cambios": cambios, "personas": len(contados), "uniones_plano": n_juntos,
                "separados": len(separados), "pasadas_breves": len(grupos.miembros) - len(contados)}
