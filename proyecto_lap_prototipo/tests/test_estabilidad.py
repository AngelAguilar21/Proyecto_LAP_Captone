import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import auth
from replay import aligerar, ultima_muestra


def muestra(t):
    return {'t': t, 'analytics': {'heat': [1] * 50}, 'levels': {'custom': {'heat': [1] * 50}},
            'cameras': [{'id': 'A', 'analysis': {'occupancy': {}}, 'people': [{'id': 'P1', 'point': [t, t], 'history': [[0, 0, 0]]}]}]}


class GrabacionesLargasTests(unittest.TestCase):
    def test_una_grabacion_corta_no_se_recorta(self):
        muestras = [muestra(t) for t in range(300)]
        salida, paso = aligerar(muestras)
        self.assertEqual(paso, 1)
        self.assertTrue(all('analytics' in s for s in salida))

    def test_una_larga_conserva_todas_las_posiciones_y_el_analisis_solo_cada_cierto_paso(self):
        muestras = [muestra(t) for t in range(2000)]
        salida, paso = aligerar(muestras)
        self.assertGreater(paso, 1)
        self.assertEqual(len(salida), 2000)
        self.assertEqual([s['cameras'][0]['people'][0]['point'] for s in salida], [[t, t] for t in range(2000)])
        completas = [s for s in salida if 'analytics' in s]
        self.assertLessEqual(len(completas), 2000 // paso + 2)
        self.assertIn('analytics', salida[0])
        self.assertIn('analytics', salida[-1], 'la última muestra lleva el acumulado final')
        self.assertNotIn('analysis', salida[1]['cameras'][0])
        self.assertNotIn('history', salida[1]['cameras'][0]['people'][0])

    def test_la_ultima_muestra_se_lee_del_final_aunque_la_linea_final_este_cortada(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / 'samples.jsonl'
            ruta.write_text('\n'.join(json.dumps(muestra(t)) for t in range(50)) + '\n{"t": 50, "cam', encoding='utf-8')
            self.assertEqual(ultima_muestra(ruta)['t'], 49)
            ruta.write_text('', encoding='utf-8')
            self.assertIsNone(ultima_muestra(ruta))


class SesionesPersistentesTests(unittest.TestCase):
    def test_la_sesion_sobrevive_a_un_reinicio_y_el_archivo_no_guarda_el_token(self):
        with tempfile.TemporaryDirectory() as carpeta:
            archivo = Path(carpeta) / 'sesiones.local.json'
            token = auth.Sesiones(archivo).abrir('operador', 'operador')
            self.assertNotIn(token, archivo.read_text(encoding='utf-8'))
            reiniciado = auth.Sesiones(archivo)
            self.assertEqual(reiniciado.leer(token)['usuario'], 'operador')
            self.assertIsNone(reiniciado.leer('otro-token'))
            reiniciado.cerrar(token)
            self.assertIsNone(auth.Sesiones(archivo).leer(token))

    def test_una_sesion_vencida_no_se_recupera(self):
        with tempfile.TemporaryDirectory() as carpeta:
            archivo = Path(carpeta) / 'sesiones.local.json'
            sesiones = auth.Sesiones(archivo)
            token = sesiones.abrir('operador', 'operador')
            for dato in sesiones.activas.values():
                dato['expira'] = time.time() - 1
            sesiones._guardar()
            self.assertIsNone(auth.Sesiones(archivo).leer(token))

    def test_sin_archivo_funciona_como_antes(self):
        sesiones = auth.Sesiones()
        token = sesiones.abrir('operador', 'operador')
        self.assertEqual(sesiones.leer(token)['rol'], 'operador')


if __name__ == '__main__':
    unittest.main()
