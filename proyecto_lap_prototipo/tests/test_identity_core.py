"""Núcleo de identidad portado de AeroVision: vistas confiables, tracklets, fusión, separación y confirmación.

Personas sintéticas: cada una es un rectángulo de un color y un Re-ID falso le da un vector fijo más ruido
(misma persona ~0,8 de similitud, distintas ~0). Sin video, sin modelo, sin disco.
"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from identity import AsociadorMulticamara, vistas_confiables  # noqa: E402
from identity.quality import COLOR_RELLENO_BGR, recortar, rellenar, tapadores  # noqa: E402
from following.reid import OSNetEmbedder  # noqa: E402
from identity.engine import ASOCIACION_DEFECTO  # noqa: E402

DIM = 512
FORMA = (720, 1280)


def unitario(v):
    return v / np.linalg.norm(v)


class ReIDFalso:
    """Vector de la persona según el color del recorte, con ruido como el de un Re-ID real."""

    def __init__(self, bases, semilla=7, ruido=0.5):
        self.bases, self.rng, self.ruido = bases, np.random.default_rng(semilla), ruido

    def __call__(self, crops):
        salida = []
        for crop in crops:
            color = tuple(int(c) for c in np.median(crop.reshape(-1, 3), axis=0))
            salida.append(unitario(self.bases[color] + self.rng.normal(0, self.ruido / np.sqrt(DIM), DIM)))
        return np.array(salida, np.float32)


def bases_sinteticas():
    rng = np.random.default_rng(3)
    a = unitario(rng.normal(size=DIM))
    return {
        (0, 0, 220): a,                                       # A
        (0, 200, 0): unitario(rng.normal(size=DIM)),          # B, otra persona
        (200, 0, 0): unitario(rng.normal(size=DIM)),          # C, otra persona
        (0, 180, 180): unitario(0.99 * a + np.sqrt(1 - 0.99 ** 2) * unitario(rng.normal(size=DIM))),  # A' casi igual a A (0,99)
    }


A, B, C, A_PARECIDA = (0, 0, 220), (0, 200, 0), (200, 0, 0), (0, 180, 180)


def registro(camaras=("c1", "c2"), solapes=(), transiciones=(), modo="visual_temporal", **asociacion):
    """Registro mínimo del asociador: cámaras, solapes (pares) y transiciones (origen, destino, t_min, t_max)."""
    return {"mode": modo, "cameras": {c: {"calibrada": modo == "calibrado"} for c in camaras},
            "overlaps": [list(p) for p in solapes],
            "transitions": [{"from": a, "to": b, "t_min_s": lo, "t_max_s": hi, "max_distance_m": 30.0} for a, b, lo, hi in transiciones],
            "association": {**ASOCIACION_DEFECTO, "overlap_distance_m": 1.5, "max_speed_m_s": 4.0, **asociacion}}


class Escena:
    """Hace avanzar el tiempo de un asociador con personas en sus cámaras."""

    def __init__(self, asociador):
        self.asociador, self.t = asociador, 0.0

    def ver(self, segundos, personas, fps=10):
        """personas: {cid: [(local_id, color, x, punto?)]}. Devuelve el global_id final de cada (cid, local_id)."""
        ids = {}
        for _ in range(int(round(segundos * fps))):
            frames, filas = {}, {}
            for cid, lista in personas.items():
                frame = np.zeros((*FORMA, 3), np.uint8)
                for item in lista:
                    local_id, color, x = item[:3]
                    frame[300:460, x:x + 60] = color
                frames[cid] = frame
                filas[cid] = [{"local_id": item[0], "x1": float(item[2]), "y1": 300.0, "x2": float(item[2] + 60),
                               "y2": 460.0, "confidence": 0.9, "punto": item[3] if len(item) > 3 else None} for item in lista]
            self.asociador.actualizar(self.t, frames, filas)
            for cid, lista in filas.items():
                for fila in lista:
                    ids[(cid, fila["local_id"])] = fila["global_id"]
            self.t += 1 / fps
        return ids

    def esperar(self, segundos):
        self.t += segundos


def asociador(config=None, bases=None, **params):
    return AsociadorMulticamara(ReIDFalso(bases or bases_sinteticas()), config or registro(**params))


def referencia(rows, shape, min_conf=0.55, min_alto=40, max_iou=0.2, margen_borde=4, occluders=None):
    """La versión de AeroVision anterior a vectorizar, comparando cada caja con cada otra."""
    height, width = shape[0], shape[1]
    boxes = np.array([[r[k] for k in ("x1", "y1", "x2", "y2")] for r in rows], np.float32).reshape(-1, 4)
    others = boxes if occluders is None else np.asarray(occluders, dtype=np.float32).reshape(-1, 4)
    keep = []
    for index, (row, box) in enumerate(zip(rows, boxes)):
        if row["confidence"] < min_conf or box[3] - box[1] < min_alto or box[2] - box[0] < 8:
            continue
        if box[0] < margen_borde or box[1] < margen_borde or box[2] > width - margen_borde or box[3] > height - margen_borde:
            continue
        tapada = False
        for other in others:
            if np.allclose(box, other, atol=1):
                continue
            inter = np.prod(np.maximum(0, np.minimum(box[2:], other[2:]) - np.maximum(box[:2], other[:2])))
            union = np.prod(box[2:] - box[:2]) + np.prod(other[2:] - other[:2]) - inter
            if (inter / union if union > 0 else 0.) > max_iou or inter / max(1, np.prod(box[2:] - box[:2])) > max_iou:
                tapada = True
                break
        if not tapada:
            keep.append(index)
    return keep


def cajas(rng, n, ancho=1024, alto=576):
    x1, y1 = rng.uniform(-20, ancho, n), rng.uniform(-20, alto, n)
    return np.stack([x1, y1, x1 + rng.uniform(4, 120, n), y1 + rng.uniform(10, 200, n)], 1).astype(np.float32)


class VistasConfiablesPortadas(unittest.TestCase):
    """Test de AeroVision (test_vistas_confiables): igual que caja por caja, con cajas al azar."""

    def test_igual_que_caja_por_caja(self):
        rng = np.random.default_rng(3)
        for caso in range(150):
            n = int(rng.integers(0, 45))
            b = cajas(rng, n)
            rows = [{"x1": x1, "y1": y1, "x2": x2, "y2": y2, "confidence": float(c)}
                    for (x1, y1, x2, y2), c in zip(b, rng.uniform(0.1, 1, n))]
            extra = cajas(rng, int(rng.integers(0, 15)))
            occ = np.concatenate([b + rng.uniform(-1, 1, b.shape).astype(np.float32), extra]) if caso % 2 else None
            for params in ({}, {"min_conf": 0.15, "min_alto": 16, "max_iou": 0.4, "margen_borde": -1}):
                self.assertEqual(vistas_confiables(rows, (576, 1024), occluders=occ, **params),
                                 referencia(rows, (576, 1024), occluders=occ, **params), f"caso {caso} {params}")


class RecorteConscienteDeOclusion(unittest.TestCase):
    """Personas que van juntas: se rellena lo que tapa la de adelante en vez de descartar el recorte."""

    ATRAS = (100.0, 100.0, 200.0, 300.0)       # pies en y=300
    ADELANTE = (160.0, 120.0, 260.0, 340.0)    # pies en y=340: más cerca de la cámara; cubre 40 px del ancho de ATRAS

    def test_el_de_atras_pierde_lo_que_tapa_el_de_adelante_y_el_de_adelante_nada(self):
        (visible_atras, rects), (visible_adelante, rects_adelante) = tapadores([self.ATRAS, self.ADELANTE])
        self.assertEqual(rects, [(160.0, 120.0, 200.0, 300.0)])
        self.assertAlmostEqual(visible_atras, 1 - (40 * 180) / (100 * 200), delta=0.06)
        self.assertEqual((visible_adelante, rects_adelante), (1.0, []))

    def test_a_la_misma_distancia_los_dos_se_tapan(self):
        a, b = (100.0, 100.0, 200.0, 300.0), (180.0, 100.0, 280.0, 300.0)
        (va, ra), (vb, rb) = tapadores([a, b])
        self.assertLess(va, 1.0)
        self.assertLess(vb, 1.0)
        self.assertTrue(ra and rb)

    def test_sin_solape_o_la_misma_caja_no_hay_oclusion(self):
        self.assertEqual(tapadores([(0, 0, 50, 100), (200, 0, 250, 100)]), [(1.0, []), (1.0, [])])
        self.assertEqual(tapadores([(0, 0, 50, 100), (0.5, 0, 50.5, 100)])[0][1], [])

    def test_el_solape_leve_pasa_con_min_visible_y_no_con_la_regla_antigua(self):
        filas = [{"x1": c[0], "y1": c[1], "x2": c[2], "y2": c[3], "confidence": 0.9} for c in (self.ATRAS, self.ADELANTE)]
        self.assertEqual(vistas_confiables(filas, FORMA), [])
        self.assertEqual(vistas_confiables(filas, FORMA, min_visible=0.6), [0, 1])

    def test_si_casi_no_se_ve_se_descarta(self):
        casi_tapada = (110.0, 110.0, 190.0, 290.0)      # dentro de la caja de adelante, que está más cerca
        grande = (90.0, 90.0, 210.0, 330.0)
        filas = [{"x1": c[0], "y1": c[1], "x2": c[2], "y2": c[3], "confidence": 0.9} for c in (casi_tapada, grande)]
        self.assertEqual(vistas_confiables(filas, FORMA, min_visible=0.6), [1])

    def test_rellenar_no_toca_el_original_y_respeta_el_origen(self):
        imagen = np.full((100, 100, 3), 200, np.uint8)
        recorte = imagen[20:80, 30:90]
        relleno = rellenar(recorte, [(50.0, 40.0, 70.0, 60.0)], (30, 20))
        self.assertTrue((relleno[20:40, 20:40] == COLOR_RELLENO_BGR).all())
        self.assertTrue((relleno[0:10, 0:10] == 200).all())
        self.assertTrue((imagen == 200).all(), "el frame original no cambia")

    def test_recortar_con_tapados(self):
        imagen = np.full((200, 200, 3), 200, np.uint8)
        fila = {"x1": 50.0, "y1": 50.0, "x2": 150.0, "y2": 150.0}
        sin = recortar(imagen, fila)
        con = recortar(imagen, fila, [(100.0, 50.0, 150.0, 150.0)])
        self.assertEqual(sin.shape, con.shape)
        self.assertTrue((sin == 200).all())
        self.assertTrue((con[10:100, 60:100] == COLOR_RELLENO_BGR).all())
        self.assertTrue((con[:, :20] == 200).all())

    def test_osnet_recibe_el_recorte_relleno(self):
        embedder = OSNetEmbedder()
        imagen = np.full((200, 200, 3), 30, np.uint8)
        completo = embedder._crop(imagen, (50, 50, 150, 150))
        relleno = embedder._crop(imagen, (50, 50, 150, 150), [(100.0, 50.0, 150.0, 150.0)])
        self.assertGreater(np.abs(completo).mean(), 1.0)
        self.assertLess(np.abs(relleno[:, :, -40:]).mean(), 0.1, "la zona tapada queda en la media: no aporta al vector")

    def test_una_vista_parcial_que_no_encaja_no_parte_el_tracklet(self):
        bases = bases_sinteticas()
        for parcial, cortes in ((True, 0), (False, 1)):
            escena = Escena(asociador(registro(), bases))
            escena.ver(2, {"c1": [(1, A, 300)]})
            track = next(iter(escena.asociador.tracklets.values()))
            self.assertGreaterEqual(track.n_muestras, 3)
            muestras = track.n_muestras
            otra = bases[B].astype(np.float32)
            for _ in range(3):
                escena.asociador._agregar_vista(track, otra, escena.t, track.orientacion(), parcial)
            self.assertEqual(escena.asociador.stats["cambios_de_persona"], cortes, f"parcial={parcial}")
            if parcial:
                self.assertEqual(track.n_muestras, muestras, "la vista parcial descartada no entra al prototipo")
                self.assertEqual(len(track.pendientes), 0)

    def test_min_visible_invalido_es_error(self):
        for malo in (0.0, 1.5, -0.2):
            with self.assertRaises(ValueError, msg=str(malo)):
                AsociadorMulticamara(ReIDFalso(bases_sinteticas()), registro(min_visible=malo))

    def test_el_asociador_acepta_min_visible_y_une_a_la_misma_persona(self):
        escena = Escena(asociador(registro(solapes=[("c1", "c2")], transiciones=[("c1", "c2", 0, 30)], min_visible=0.6)))
        ids = escena.ver(5, {"c1": [(1, A, 300)], "c2": [(7, A, 600)]})
        self.assertEqual(ids[("c1", 1)], ids[("c2", 7)])


class ConfirmacionDeID(unittest.TestCase):
    def test_un_id_publico_exige_vistas_y_duracion(self):
        escena = Escena(asociador())
        corto = escena.ver(1.0, {"c1": [(1, A, 300)]})
        self.assertIsNone(corto[("c1", 1)], "una pasada de 1 s no se cuenta")
        largo = escena.ver(3.0, {"c1": [(1, A, 300)]})
        self.assertEqual(largo[("c1", 1)], 1)
        self.assertEqual(escena.asociador.resumen()["identidades_globales"], 1)

    def test_pasada_breve_no_se_cuenta(self):
        escena = Escena(asociador())
        escena.ver(1.2, {"c1": [(1, A, 300)]})
        escena.esperar(5)
        escena.ver(4, {"c1": [(2, B, 700)]})
        resumen = escena.asociador.resumen()
        self.assertEqual(resumen["identidades_globales"], 1)
        self.assertEqual(resumen["pasadas_breves_no_contadas"], 1)

    def test_personas_distintas_reciben_ids_distintos_y_consecutivos(self):
        escena = Escena(asociador())
        ids = escena.ver(4, {"c1": [(1, A, 100), (2, B, 500), (3, C, 900)]})
        self.assertEqual(sorted(ids.values()), [1, 2, 3])


class CorteDeTracklet(unittest.TestCase):
    def test_cambio_de_persona_dentro_del_mismo_id_local_parte_el_tracklet(self):
        escena = Escena(asociador())
        escena.ver(3, {"c1": [(1, A, 300)]})
        # ByteTrack conserva el id local pero ahora hay otra persona (B) en la caja.
        escena.ver(3, {"c1": [(1, B, 300)]})
        a = escena.asociador
        self.assertEqual(a.stats["cambios_de_persona"], 1)
        primero, segundo = (a.tracklets[u] for u in sorted(a.tracklets))
        self.assertIsNotNone(primero.sucesor)
        self.assertNotEqual(primero.global_id, segundo.global_id)
        self.assertGreaterEqual(segundo.inicio_s, primero.fin_s)

    def test_la_misma_persona_no_se_parte(self):
        escena = Escena(asociador())
        escena.ver(8, {"c1": [(1, A, 300)]})
        self.assertEqual(escena.asociador.stats["cambios_de_persona"], 0)

    def test_hueco_mayor_que_el_permitido_abre_otro_tracklet(self):
        escena = Escena(asociador())
        escena.ver(3, {"c1": [(1, A, 300)]})
        escena.esperar(5)  # mayor que tracklet_gap_s
        escena.ver(1, {"c1": [(1, A, 300)]})
        self.assertEqual(len(escena.asociador.tracklets), 2)


class FusionMutua(unittest.TestCase):
    def config(self):
        return registro(solapes=[("c1", "c2")], transiciones=[("c1", "c2", 0, 30), ("c2", "c1", 0, 30)])

    def test_la_misma_persona_en_dos_camaras_solapadas_es_una_identidad(self):
        escena = Escena(asociador(self.config()))
        ids = escena.ver(5, {"c1": [(1, A, 300)], "c2": [(7, A, 600)]})
        self.assertEqual(ids[("c1", 1)], ids[("c2", 7)])
        self.assertIsNotNone(ids[("c1", 1)])
        self.assertEqual(escena.asociador.resumen()["identidades_multicamara"], 1)
        self.assertGreaterEqual(escena.asociador.stats["fusiones"], 1)

    def test_personas_distintas_en_dos_camaras_no_se_fusionan(self):
        escena = Escena(asociador(self.config()))
        ids = escena.ver(5, {"c1": [(1, A, 300)], "c2": [(7, B, 600)]})
        self.assertNotEqual(ids[("c1", 1)], ids[("c2", 7)])
        self.assertEqual(escena.asociador.stats["fusiones"], 0)

    def test_dos_personas_en_c1_se_emparejan_cada_una_con_la_suya_de_c2(self):
        escena = Escena(asociador(self.config()))
        ids = escena.ver(5, {"c1": [(1, A, 100), (2, B, 600)], "c2": [(5, B, 200), (6, A, 800)]})
        self.assertEqual(ids[("c1", 1)], ids[("c2", 6)])
        self.assertEqual(ids[("c1", 2)], ids[("c2", 5)])
        self.assertNotEqual(ids[("c1", 1)], ids[("c1", 2)])

    def test_traspaso_sin_solape_dentro_de_la_ventana_de_transicion(self):
        escena = Escena(asociador(registro(transiciones=[("c1", "c2", 0, 20)])))
        antes = escena.ver(4, {"c1": [(1, A, 300)], "c2": []})[("c1", 1)]
        escena.esperar(5)
        despues = escena.ver(4, {"c1": [], "c2": [(4, A, 600)]})[("c2", 4)]
        self.assertEqual(antes, despues)

    def test_traspaso_fuera_de_la_ventana_no_se_une(self):
        escena = Escena(asociador(registro(transiciones=[("c1", "c2", 0, 5)])))
        antes = escena.ver(4, {"c1": [(1, A, 300)], "c2": []})[("c1", 1)]
        escena.esperar(30)
        despues = escena.ver(4, {"c1": [], "c2": [(4, A, 600)]})[("c2", 4)]
        self.assertNotEqual(antes, despues)

    def test_sin_transicion_declarada_no_hay_union_entre_camaras(self):
        escena = Escena(asociador(registro()))
        antes = escena.ver(4, {"c1": [(1, A, 300)], "c2": []})[("c1", 1)]
        escena.esperar(5)
        despues = escena.ver(4, {"c1": [], "c2": [(4, A, 600)]})[("c2", 4)]
        self.assertNotEqual(antes, despues)


class RechazoPorAmbiguedad(unittest.TestCase):
    def test_dos_candidatas_casi_iguales_no_se_fusionan(self):
        # A' es casi idéntica a A: con A y A' visibles en c1 a la vez, la que aparece en c2 no puede decidirse.
        config = registro(solapes=[("c1", "c2")], transiciones=[("c1", "c2", 0, 30), ("c2", "c1", 0, 30)])
        escena = Escena(AsociadorMulticamara(ReIDFalso(bases_sinteticas(), ruido=0.05), config))
        ids = escena.ver(5, {"c1": [(1, A, 100), (2, A_PARECIDA, 600)], "c2": [(9, A, 300)]})
        propios = escena.asociador.stats
        self.assertGreaterEqual(propios["ambiguos"], 1, "debió registrar la ambigüedad")
        self.assertNotEqual(ids[("c1", 1)], ids[("c1", 2)])


class SeparacionDeConflictos(unittest.TestCase):
    def test_una_identidad_que_deja_de_ser_posible_se_separa(self):
        # c1 y c2 NO se solapan. El tracklet de c2 coincide en el tiempo con el de c1: no pueden ser la misma persona.
        a = asociador(registro(transiciones=[("c1", "c2", 0, 30)]))
        escena = Escena(a)
        escena.ver(3, {"c1": [(1, A, 300)], "c2": []})
        t1 = a.locales[("c1", 1)]
        # Se fuerza una unión inválida (como la que dejaría un solape retirado) y se comprueba que el asociador la deshace.
        escena.ver(3, {"c1": [(1, A, 300)], "c2": [(4, A, 600)]})
        t2 = a.locales[("c2", 4)]
        self.assertNotEqual(t1.global_id, t2.global_id)
        a.globales[t1.global_id].add(t2.uid)
        a.globales.pop(t2.global_id)
        t2.global_id = t1.global_id
        a._separar_conflictos({t1.global_id})
        self.assertNotEqual(t1.global_id, t2.global_id)
        self.assertEqual(a.stats["separaciones"], 1)


class CompuertaFisica(unittest.TestCase):
    """Modo calibrado: la posición en el plano manda sobre el parecido visual."""

    def config(self):
        return registro(solapes=[("c1", "c2")], transiciones=[("c1", "c2", 0, 30), ("c2", "c1", 0, 30)], modo="calibrado")

    def test_misma_persona_en_el_mismo_punto_se_une(self):
        escena = Escena(asociador(self.config()))
        ids = escena.ver(5, {"c1": [(1, A, 300, (5.0, 5.0))], "c2": [(7, A, 600, (5.2, 5.1))]})
        self.assertEqual(ids[("c1", 1)], ids[("c2", 7)])

    def test_misma_apariencia_en_puntos_lejanos_no_se_une(self):
        escena = Escena(asociador(self.config()))
        ids = escena.ver(5, {"c1": [(1, A, 300, (2.0, 2.0))], "c2": [(7, A, 600, (9.0, 7.0))]})
        self.assertNotEqual(ids[("c1", 1)], ids[("c2", 7)])

    def test_sin_posicion_cae_a_visual_temporal(self):
        escena = Escena(asociador(self.config()))
        ids = escena.ver(5, {"c1": [(1, A, 300)], "c2": [(7, A, 600)]})
        self.assertEqual(ids[("c1", 1)], ids[("c2", 7)])

    def test_un_salto_imposible_no_corrompe_la_trayectoria(self):
        escena = Escena(asociador(self.config()))
        escena.ver(2, {"c1": [(1, A, 300, (1.0, 1.0))]})
        escena.ver(0.1, {"c1": [(1, A, 300, (30.0, 30.0))]})
        track = escena.asociador.locales[("c1", 1)]
        self.assertTrue(all(math.dist(p[1:], (1.0, 1.0)) < 1.0 for p in track.posiciones))


import math  # noqa: E402


class AyudaDeGeometria(unittest.TestCase):
    """geometry_relief: la misma persona vista a la vez en el mismo punto del plano se une con menos parecido exigido."""

    def config(self, **extra):
        return registro(solapes=[("c1", "c2")], transiciones=[("c1", "c2", 0, 30), ("c2", "c1", 0, 30)], modo="calibrado", **extra)

    def nuevo(self, **extra):
        return AsociadorMulticamara(ReIDFalso(bases_sinteticas(), ruido=2.5), self.config(split_threshold=-1.0, **extra))   # ruido alto: parecido lejos de 1

    def parecido(self):
        """Parecido entre prototipos de A visto por c1 y por c2 (con el ruido fijo del Re-ID de prueba)."""
        escena = Escena(self.nuevo(threshold=-0.5, average_threshold=-1.0))
        escena.ver(5, {"c1": [(1, A, 300, (5.0, 5.0))], "c2": [(7, A, 600, (5.2, 5.1))]})
        t1, t2 = (t for t in escena.asociador.tracklets.values())
        return float(t1.prototipo() @ t2.prototipo())

    def ids(self, punto_c2, **extra):
        umbral = round(self.parecido() + 0.03, 3)
        escena = Escena(self.nuevo(threshold=umbral, average_threshold=-1.0, **extra))
        return escena.ver(5, {"c1": [(1, A, 300, (5.0, 5.0))], "c2": [(7, A, 600, punto_c2)]})

    def test_sin_ayuda_el_umbral_alto_impide_la_union(self):
        ids = self.ids((5.2, 5.1))
        self.assertNotEqual(ids[("c1", 1)], ids[("c2", 7)])

    def test_con_ayuda_y_en_el_mismo_punto_se_une(self):
        ids = self.ids((5.2, 5.1), geometry_relief=0.1)
        self.assertEqual(ids[("c1", 1)], ids[("c2", 7)])

    def test_con_ayuda_pero_a_otra_distancia_no_se_une(self):
        ids = self.ids((6.1, 5.9), geometry_relief=0.1)       # 1,2 m: dentro de la compuerta física, fuera de lo que cuenta como mismo punto
        self.assertNotEqual(ids[("c1", 1)], ids[("c2", 7)])

    def test_parametros_invalidos(self):
        for malo in ({"geometry_relief": -0.1}, {"geometry_relief": 0.9}, {"geometry_close": 0.0}, {"geometry_close": 1.5}):
            with self.assertRaises(ValueError, msg=str(malo)):
                asociador(self.config(**malo))


class ValidacionDeParametros(unittest.TestCase):
    def test_umbral_fuera_de_rango_es_error(self):
        with self.assertRaises(ValueError):
            asociador(registro(threshold=1.5))

    def test_tiempos_hacia_atras_son_error(self):
        a = asociador()
        escena = Escena(a)
        escena.ver(1, {"c1": [(1, A, 300)]})
        with self.assertRaises(ValueError):
            a.actualizar(0.0, {"c1": np.zeros((*FORMA, 3), np.uint8)}, {"c1": []})

    def test_registro_con_camara_inexistente_en_transicion_es_error(self):
        with self.assertRaises(ValueError):
            asociador(registro(transiciones=[("c1", "zz", 0, 5)]))


if __name__ == "__main__":
    unittest.main()
