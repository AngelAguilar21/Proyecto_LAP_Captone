"""Insights espaciales con trayectorias sintéticas de resultado conocido (portados de test_historico de AeroVision)."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from insights import (Consolidado, PisoTransitable, Zona, analizar, analizar_replay, asignar_zonas, consolidar, dentro_poligono,  # noqa: E402
                      desde_config, estancias, generar_eventos, kde_grilla, metricas_locales, ocupacion_por_segundo, origen_destino,
                      paso_serie, prefixspan, series_temporales)
from insights import ventas  # noqa: E402
from insights.zonas import expandir_poligono  # noqa: E402

EVENTOS = {"tolerancia_s": 1.0, "dwell_min_s": 5.0, "retorno_min_s": 10.0, "cola_min_s": 8.0,
           "cola_velocidad_max_mps": 0.35, "confianza_sin_transicion": 0.5}


def rect(zid, nombre, tipo, x0, y0, x1, y1, local=None):
    v = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=float)
    return Zona(zid, nombre, tipo, local, (x1 - x0) * (y1 - y0), v)


def consolidado(filas, velocidad=1.0, confianza=0.8):
    """Consolidado a partir de [(global_id, t, zona)] ya ordenadas por persona y tiempo."""
    n = len(filas)
    return Consolidado(global_id=[f[0] for f in filas], t=[f[1] for f in filas], x=np.full(n, 0.5), y=np.full(n, 0.5),
                       velocidad=np.full(n, velocidad), confianza=np.full(n, confianza), observaciones=np.ones(n, int),
                       zona=[f[2] for f in filas])


class Zonas(unittest.TestCase):
    def test_punto_en_poligono_incluye_bordes(self):
        cuadrado = np.array([[0, 0], [4, 0], [4, 4], [0, 4]], dtype=float)
        self.assertEqual(dentro_poligono([2, 5, 4, 0, 4.0000001], [2, 2, 2, 0, 5], cuadrado).tolist(), [True, False, True, True, False])

    def test_prioridad_interior_y_menor_area(self):
        zonas = [rect(1, "Pasillo", "ZONA", 0, 0, 10, 10), rect(2, "Frente", "FRONTAGE", 0, 0, 4, 2, "L"), rect(3, "Tienda", "INTERIOR", 1, 1, 3, 5, "L")]
        z = asignar_zonas([2, 3.5, 8, np.nan, 20], [1.5, 0.5, 8, 1, 1], zonas)
        self.assertEqual(z.tolist(), [3, 2, 1, -1, -1])

    def test_expandir_poligono_deja_una_franja_uniforme(self):
        marco = expandir_poligono(np.array([[0, 0], [4, 0], [4, 2], [0, 2]], float), 1.0)
        self.assertEqual(sorted(map(tuple, marco.round(6).tolist())), [(-1.0, -1.0), (-1.0, 3.0), (5.0, -1.0), (5.0, 3.0)])
        # el sentido de giro del polígono no cambia el resultado
        marco2 = expandir_poligono(np.array([[0, 0], [4, 0], [4, 2], [0, 2]], float)[::-1], 1.0)
        self.assertEqual(sorted(map(tuple, marco2.round(6).tolist())), sorted(map(tuple, marco.round(6).tolist())))


class ZonasDeAeroTrack(unittest.TestCase):
    CONFIG = {"planId": "custom", "zones": [
        {"id": "z1", "name": "Café", "kind": "commercial", "points": [[2, 6], [6, 6], [6, 9], [2, 9]], "business": {"category": "food"}},
        {"id": "z2", "name": "Fila caja", "kind": "queue", "points": [[8, 2], [10, 2], [10, 4], [8, 4]]},
        {"id": "z3", "name": "Pasillo", "kind": "corridor", "points": [[0, 3], [12, 3], [12, 5], [0, 5]]},
        {"id": "z4", "name": "Muro", "kind": "wall", "points": [[0, 0], [12, 0], [12, .2], [0, .2]]}]}

    def test_cada_tipo_de_zona_de_aerotrack_se_traduce(self):
        zonas, locales = desde_config(self.CONFIG, frente=1.0)
        tipos = sorted(z.tipo for z in zonas.values())
        self.assertEqual(tipos, ["COLA", "FRONTAGE", "INTERIOR", "ZONA"])   # el muro no es zona de medición
        self.assertEqual(len(locales), 1)
        interior = next(z for z in zonas.values() if z.tipo == "INTERIOR")
        frente = next(z for z in zonas.values() if z.tipo == "FRONTAGE")
        self.assertEqual(interior.local_id, frente.local_id)
        self.assertGreater(frente.area, interior.area)

    def test_el_local_se_vincula_al_negocio_por_ubicacion_o_nombre(self):
        negocios = [{"id": "n-1", "nombre": "Otro nombre", "ubicacion": {"planId": "custom", "point": [4, 7]}},
                    {"id": "n-2", "nombre": "café", "ubicacion": {"planId": "custom", "point": [11, 11]}}]
        _, locales = desde_config(self.CONFIG, negocios)
        self.assertEqual(locales[0]["negocio_id"], "n-1")                     # por ubicación dentro del polígono
        _, locales = desde_config(self.CONFIG, negocios[1:])
        self.assertEqual(locales[0]["negocio_id"], "n-2")                     # por nombre
        _, locales = desde_config(self.CONFIG, [])
        self.assertIsNone(locales[0]["negocio_id"])
        self.assertTrue(locales[0]["local_id"].startswith("zona:"))


class Piso(unittest.TestCase):
    PISO = [[0, 0], [10, 0], [10, 6], [0, 6]]
    CARPA = [[4, 4], [6, 4], [6, 6], [4, 6]]

    def test_saca_de_obstaculos_y_devuelve_al_piso(self):
        piso = PisoTransitable(self.PISO, [self.CARPA], margen=0.2)
        x, y, movidos = piso.ajustar([5.0, 4.3, 12.0, 2.0, 4.1], [4.5, 5.9, 3.0, 2.0, 3.9])
        self.assertEqual(movidos.tolist(), [True, True, True, False, True])
        self.assertAlmostEqual(y[0], 3.8)
        self.assertAlmostEqual(x[1], 3.8)
        self.assertAlmostEqual(x[2], 9.8)
        self.assertEqual((x[3], y[3]), (2.0, 2.0))
        self.assertTrue(piso.libres(x, y).all())

    def test_el_promedio_de_dos_camaras_tampoco_cae_en_el_obstaculo(self):
        piso = PisoTransitable(self.PISO, [[[4, 2], [6, 2], [6, 3], [4, 3]]], margen=0.2)
        x, y, movidos = piso.ajustar_trayectorias(["a", "a", "b"], [1.0, 1.05, 1.0], [5.0, 5.0, 1.0], [1.7, 3.3, 1.0], 0.2)
        self.assertEqual(movidos.tolist(), [True, True, False])
        self.assertEqual((x[0], y[0]), (x[1], y[1]))
        self.assertTrue(piso.libres(x, y).all())

    def test_sin_plano_no_mueve_nada(self):
        x, y, movidos = PisoTransitable().ajustar([1.0, np.nan], [2.0, np.nan])
        self.assertFalse(movidos.any())
        self.assertEqual(x[0], 1.0)


class Consolidacion(unittest.TestCase):
    def test_une_camaras_y_quita_saltos(self):
        c = consolidar(["a"] * 5, [0.0, 0.05, 0.2, 0.4, 0.6], [0.0, 1.0, 0.1, 30.0, 0.3], [0.0] * 5, [0.9, 0.3, 0.9, 0.9, 0.9], 0.2, 4.0)
        self.assertAlmostEqual(c.x[0], 0.25)                 # (0.9*0 + 0.3*1) / 1.2: pesa más la cámara más confiable
        self.assertNotIn(30.0, c.x.tolist())                 # el salto de 30 en 0,2 s se descarta
        self.assertEqual(len(c), 3)

    def test_varias_personas_quedan_agrupadas(self):
        c = consolidar(["b", "a", "b", "a"], [0.0, 0.0, 0.2, 0.2], [1, 5, 1.1, 5.1], [0, 0, 0, 0], None, 0.2, 4.0)
        self.assertEqual([gid for gid, _ in c.personas()], ["a", "b"])
        self.assertTrue(np.isfinite(c.velocidad).all())


class Eventos(unittest.TestCase):
    def test_recorrido_por_un_local(self):
        zonas = {1: rect(1, "Pasillo", "ZONA", 0, 0, 20, 10), 2: rect(2, "Frente", "FRONTAGE", 0, 10, 4, 12, "L"), 3: rect(3, "Tienda", "INTERIOR", 0, 12, 4, 20, "L")}
        tramos = [(1, 0, 3), (2, 3, 4), (3, 4, 10), (1, 10, 22), (3, 22, 24), (1, 24, 26)]
        zona = np.concatenate([np.full(int(round((b - a) / 0.2)), z) for z, a, b in tramos])
        e = estancias(consolidado([("a", t, z) for t, z in zip(np.arange(0, 26, 0.2), zona)]), 0.2, 1.0)
        self.assertEqual([ev["event_type"] for ev in generar_eventos(e["a"], zonas, EVENTOS)],
                         ["EXPOSURE", "ENTER", "DWELL", "EXIT", "ENTER", "RETURN", "EXIT"])

    def test_salida_breve_no_corta_la_estancia(self):
        zona = np.array([3] * 20 + [-1] * 3 + [3] * 20)
        e = estancias(consolidado([("a", i * 0.2, z) for i, z in enumerate(zona)]), 0.2, 1.0)
        self.assertEqual([x.zona for x in e["a"]], [3])

    def test_roce_breve_del_interior_no_es_visita(self):
        zonas = {1: rect(1, "Pasillo", "ZONA", 0, 0, 20, 10), 2: rect(2, "Frente", "FRONTAGE", 0, 10, 4, 12, "L"), 3: rect(3, "Tienda", "INTERIOR", 0, 12, 4, 20, "L")}
        zona = np.array([2] * 15 + [3] * 3 + [1] * 15 + [2] * 10 + [3] * 2 + [2] * 10)
        cons = consolidado([("a", i * 0.2, z) for i, z in enumerate(zona)])
        e = estancias(cons, 0.2, 1.0, interiores={3})["a"]
        self.assertEqual([x.zona for x in e], [2, 1, 2])
        self.assertNotIn("ENTER", [ev["event_type"] for ev in generar_eventos(e, zonas, EVENTOS)])
        self.assertEqual([x.zona for x in estancias(cons, 0.2, 1.0)["a"]], [2, 3, 1, 2])

    def test_cola_exige_tiempo_y_velocidad_baja(self):
        zonas = {5: rect(5, "Fila", "COLA", 0, 0, 2, 5)}
        lenta = estancias(consolidado([("a", i * 0.2, 5) for i in range(60)], velocidad=0.1), 0.2, 1.0)["a"]
        rapida = estancias(consolidado([("a", i * 0.2, 5) for i in range(60)], velocidad=1.5), 0.2, 1.0)["a"]
        self.assertEqual([e["event_type"] for e in generar_eventos(lenta, zonas, EVENTOS)], ["QUEUE"])
        self.assertEqual(generar_eventos(rapida, zonas, EVENTOS), [])

    def test_captacion_por_cohorte(self):
        zonas = {2: rect(2, "Frente", "FRONTAGE", 0, 0, 1, 1, "L"), 3: rect(3, "Tienda", "INTERIOR", 0, 1, 1, 2, "L")}
        eventos = [{"global_id": "a", "zone_id": 2, "event_type": "EXPOSURE", "inicio_s": 1.0},
                   {"global_id": "a", "zone_id": 3, "event_type": "ENTER", "inicio_s": 2.0},
                   {"global_id": "b", "zone_id": 2, "event_type": "EXPOSURE", "inicio_s": 1.0},
                   {"global_id": "c", "zone_id": 3, "event_type": "ENTER", "inicio_s": 0.5}]   # entró sin pasar por el frente
        m = metricas_locales([{"local_id": "L", "name": "Café"}], zonas, {}, eventos)[0]
        self.assertEqual((m["exposicion"], m["visitas"], m["captados"], m["tasa_captacion"]), (2, 2, 1, 50.0))

    def test_sin_expuestos_la_tasa_no_esta_disponible(self):
        zonas = {3: rect(3, "Tienda", "INTERIOR", 0, 1, 1, 2, "L")}
        m = metricas_locales([{"local_id": "L", "name": "Café"}], zonas, {}, [{"global_id": "c", "zone_id": 3, "event_type": "ENTER", "inicio_s": 0.5}])[0]
        self.assertIsNone(m["tasa_captacion"])


class Rutas(unittest.TestCase):
    def test_prefixspan(self):
        patrones = {tuple(p): s for p, s in prefixspan([[1, 2, 3], [1, 3], [1, 2, 3], [2, 3]], soporte_min=2)}
        self.assertEqual(patrones, {(1, 2): 2, (1, 3): 3, (2, 3): 3, (1, 2, 3): 2})

    def test_origen_destino_cuenta_personas(self):
        od = origen_destino([[1, 2, 1, 2], [1, 2], [2, 3]])
        self.assertEqual((od[(1, 2)], od[(2, 1)], od[(2, 3)]), (2, 1, 1))


class Series(unittest.TestCase):
    def test_intervalos_y_captacion_acumulada(self):
        self.assertEqual((paso_serie(126), paso_serie(3600), paso_serie(8 * 3600)), (10, 300, 1800))
        zonas = {2: rect(2, "Frente", "FRONTAGE", 0, 0, 1, 1, "L"), 3: rect(3, "Tienda", "INTERIOR", 0, 1, 1, 2, "L")}
        filas = [("a", float(t), 2 if t < 4 else 3) for t in np.arange(0, 12, 0.2)] + [("b", float(t), 2) for t in np.arange(10, 14, 0.2)]
        cons = consolidado(filas)
        tramos = estancias(cons, 0.2, 1.0)
        eventos = [e for g in tramos for e in generar_eventos(tramos[g], zonas, EVENTOS)]
        s = series_temporales(cons, ocupacion_por_segundo(cons), tramos, eventos, zonas, [{"local_id": "L", "name": "Café"}])
        self.assertEqual((s["paso_s"], s["intervalos"]), (5, 3))
        self.assertEqual(s["zonas"]["2"]["entradas"], [1, 0, 1])
        self.assertEqual(s["zonas"]["3"]["visitas"], [1, 0, 0])
        self.assertEqual(s["total"]["personas"], [1, 1, 2])
        self.assertEqual(s["total"]["captacion"], [100.0, 100.0, 50.0])
        self.assertEqual(s["locales"]["L"]["captacion"], s["total"]["captacion"])


class KDE(unittest.TestCase):
    def test_conserva_el_peso(self):
        f = kde_grilla([5.1], [5.1], [3.0], origen=[0, 0], columnas=40, filas=40, celda=0.25, h=1.0)
        self.assertAlmostEqual(f.sum() * 0.25 * 0.25, 3.0, places=3)
        self.assertEqual(int(np.argmax(f)), 20 * 40 + 20)


def caminata(gid, trayecto, t0=0.0, dt=0.2):
    """Filas (gid, t, x, y) de alguien que sigue los puntos (x, y, segundos) del trayecto."""
    filas, t = [], t0
    for (x, y, seg) in trayecto:
        for _ in range(int(round(seg / dt))):
            filas.append((gid, t, x, y))
            t += dt
    return filas


def arreglos(filas):
    return {"global_id": np.array([f[0] for f in filas]), "t": np.array([f[1] for f in filas]), "x": np.array([f[2] for f in filas]), "y": np.array([f[3] for f in filas])}


class AnalisisCompleto(unittest.TestCase):
    CONFIG = {"planId": "custom", "width": 12, "height": 10, "unit": "meters", "matchDistance": 1.0, "zones": [
        {"id": "z1", "name": "Café", "kind": "commercial", "points": [[2, 6], [6, 6], [6, 9], [2, 9]]},
        {"id": "z2", "name": "Pasillo", "kind": "corridor", "points": [[0, 2], [12, 2], [12, 5], [0, 5]]}]}

    def filas(self):
        # a: pasillo -> frente del café -> adentro 7 s -> pasillo. b: pasillo -> frente -> pasa de largo. c: solo pasillo.
        a = caminata("a", [(1, 3.5, 2), (4, 5.5, 2), (4, 7.5, 7), (4, 3.5, 2)])
        b = caminata("b", [(10, 3.5, 2), (4, 5.5, 2), (9, 3.5, 2)], t0=1.0)
        c = caminata("c", [(9, 3.5, 6)], t0=2.0)
        return arreglos(a + b + c)

    def test_exposicion_captacion_y_permanencia_del_local(self):
        resultado, eventos = analizar(self.CONFIG, self.filas())
        cafe = next(l for l in resultado["locales"] if l["nombre"] == "Café")
        self.assertEqual((cafe["exposicion"], cafe["visitas"], cafe["captados"], cafe["tasa_captacion"]), (2, 1, 1, 50.0))
        self.assertGreaterEqual(cafe["permanencia_media_s"], 5)
        tipos = {e["event_type"] for e in eventos}
        self.assertTrue({"EXPOSURE", "ENTER", "DWELL", "EXIT"} <= tipos)
        self.assertEqual(resultado["resumen"]["personas"], 3)
        self.assertEqual(resultado["eventos_total"], len(eventos))

    def test_kde_rutas_y_origen_destino(self):
        resultado, _ = analizar(self.CONFIG, self.filas())
        kde = resultado["kde"]
        self.assertEqual(len(kde["ocupacion"]), kde["columnas"] * kde["filas"])
        self.assertGreater(max(kde["ocupacion"]), 0)
        nombres = {(o["desde_nombre"], o["hacia_nombre"]) for o in resultado["origen_destino"]}
        self.assertIn(("Pasillo", "Café (frente)"), nombres)

    def test_sin_zonas_avisa_en_vez_de_inventar(self):
        resultado, eventos = analizar({**self.CONFIG, "zones": []}, self.filas())
        self.assertEqual(eventos, [])
        self.assertTrue(resultado["aviso"])
        self.assertEqual(resultado["locales"], [])

    def test_las_unidades_relativas_escalan_los_umbrales(self):
        from insights import parametros_escalados
        metros = parametros_escalados({"unit": "meters", "matchDistance": 1.0})
        relativo = parametros_escalados({"unit": "relative", "matchDistance": 0.1})
        self.assertAlmostEqual(relativo["consolidacion"]["velocidad_max"], metros["consolidacion"]["velocidad_max"] * 0.1)
        self.assertAlmostEqual(relativo["congestion"]["densidad_min"], metros["congestion"]["densidad_min"] / 0.01)

    def test_congestion_exige_personas_densidad_y_lentitud(self):
        filas = []
        for i in range(5):   # cinco personas casi quietas en el café durante 8 s
            filas += caminata(f"p{i}", [(3.0 + 0.2 * i, 7.5, 8)])
        resultado, _ = analizar(self.CONFIG, arreglos(filas))
        self.assertTrue(any(c["nombre"] == "Café" for c in resultado["congestion"]))


class DesdeReplayYVentas(unittest.TestCase):
    def crear_replay(self, raiz, sid="abcdef12"):
        carpeta = raiz / "data" / "replays" / sid
        carpeta.mkdir(parents=True)
        (carpeta / "manifest.json").write_text(json.dumps({"session": sid, "status": "ended", "module": "demo", "created": "2026-10-03T15:00:00+00:00", "end": 40.0,
                                                           "config": {"testRun": True}, "identity": {"engine": "reid_v2", "finalizada": True}}), encoding="utf-8")
        muestras = []
        for gid, trayecto, t0 in (("P00001", [(1, 3.5, 2), (4, 5.5, 2), (4, 7.5, 7), (4, 3.5, 2)], 0.0), ("P00002", [(10, 3.5, 2), (4, 5.5, 2), (9, 3.5, 2)], 1.0)):
            for _, t, x, y in caminata(gid, trayecto, t0):
                muestras.append({"t": round(t, 2), "cameras": [{"id": "A", "people": [{"id": gid, "point": [x, y], "confirmed": True}]}]})
        muestras.append({"t": 5.0, "cameras": [{"id": "A", "people": [{"id": "T00099", "point": [1, 1], "confirmed": False}]}]})
        with (carpeta / "samples.jsonl").open("w", encoding="utf-8") as f:
            for m in sorted(muestras, key=lambda m: m["t"]):
                f.write(json.dumps(m) + "\n")
        return carpeta

    def test_analiza_una_grabacion_y_guarda_insights_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = self.crear_replay(Path(tmp))
            resultado, eventos, meta = analizar_replay(tmp, "abcdef12", AnalisisCompleto.CONFIG)
            self.assertTrue((carpeta / "insights.json").is_file())
            self.assertEqual(resultado["resumen"]["personas"], 2, "la pasada provisional no cuenta")
            self.assertTrue(resultado["resumen"]["con_fecha"])
            self.assertEqual(resultado["identidad"]["engine"], "reid_v2")
            self.assertTrue(any(h["exposicion"] for h in resultado["por_hora"] if h["local_id"].startswith("zona:")))
            guardado = json.loads((carpeta / "insights.json").read_text(encoding="utf-8"))
            self.assertEqual(guardado["sesion"], "abcdef12")

    def test_guarda_en_sqlite_y_relaciona_con_ventas(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.crear_replay(Path(tmp))
            negocios = [{"id": "n-1", "nombre": "Café", "ubicacion": {"planId": "custom", "point": [4, 7]}}]
            resultado, eventos, _ = analizar_replay(tmp, "abcdef12", AnalisisCompleto.CONFIG, negocios)
            con = sqlite3.connect(":memory:")
            con.executescript("CREATE TABLE commercial_sales (negocio_id TEXT, fecha TEXT, hora INTEGER, monto REAL, transacciones INTEGER, dataset TEXT, import_id TEXT)")
            ventas.guardar(con, "abcdef12", "demo", resultado, eventos)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM insights_events").fetchone()[0], len(eventos))
            self.assertGreaterEqual(con.execute("SELECT COUNT(*) FROM insights_hourly WHERE negocio_id='n-1'").fetchone()[0], 1)
            # Guardar de nuevo reemplaza, no duplica.
            ventas.guardar(con, "abcdef12", "demo", resultado, eventos)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM insights_events").fetchone()[0], len(eventos))
            relacion = ventas.relacion_con_ventas(con, "n-1", "demo")
            self.assertIsNone(relacion["correlaciones"])
            self.assertIn("al menos", relacion["motivo"])
            self.assertIn("no demuestra", relacion["limite"])

    def test_correlacion_solo_con_horas_suficientes_y_es_descriptiva(self):
        con = sqlite3.connect(":memory:")
        con.executescript("CREATE TABLE commercial_sales (negocio_id TEXT, fecha TEXT, hora INTEGER, monto REAL, transacciones INTEGER, dataset TEXT, import_id TEXT)")
        ventas.setup(con)
        for hora in range(8):
            con.execute("INSERT INTO insights_hourly VALUES ('s','n',?,?,?,?,?,?,?)", ("2026-10-01", hora, 10 + hora * 5, 4 + hora, 30.0, 3600.0, "real"))
            con.execute("INSERT INTO commercial_sales VALUES ('n',?,?,?,?,?,?)", ("2026-10-01", hora, 100.0 + hora * 40, 2 + hora, "real", "x"))
        r = ventas.relacion_con_ventas(con, "n", "real")
        self.assertEqual(r["n"], 8)
        self.assertEqual(r["correlaciones"]["exposicion_ventas"], 1.0)
        self.assertEqual(r["horas"][0]["captacion"], 40.0)
        self.assertEqual(r["horas"][0]["conversion"], 50.0)
        # Una hora con menos de 55 minutos observados no cuenta.
        con.execute("UPDATE insights_hourly SET cobertura_s=600 WHERE hora<4")
        self.assertEqual(ventas.relacion_con_ventas(con, "n", "real")["n"], 4)


if __name__ == "__main__":
    unittest.main()
