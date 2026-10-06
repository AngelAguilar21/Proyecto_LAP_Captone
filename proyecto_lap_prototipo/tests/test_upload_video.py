"""La carga de videos no tiene tope de peso: solo exige espacio libre en el disco."""
import http.client
import json
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from live_server import Engine, Handler, RESERVA_DISCO, ThreadingHTTPServer, validar_tamano_de_video  # noqa: E402

GB = 1024 ** 3


class Tamano(unittest.TestCase):
    def test_no_hay_tope_de_peso(self):
        validar_tamano_de_video(1 * GB + 1, 100 * GB)
        validar_tamano_de_video(50 * GB, 100 * GB)

    def test_exige_espacio_libre_con_reserva(self):
        with self.assertRaisesRegex(ValueError, "No hay espacio"):
            validar_tamano_de_video(3 * GB, 3 * GB + RESERVA_DISCO - 1)
        validar_tamano_de_video(3 * GB, 3 * GB + RESERVA_DISCO)

    def test_vacio_o_sin_tamano(self):
        for size in (0, -5):
            with self.assertRaises(ValueError):
                validar_tamano_de_video(size, 100 * GB)


class CargaPorHttp(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="aerotrack-upload-")
        self.engine = Engine(Path(self.directory.name) / "config.json")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.engine = self.engine
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.creados = []

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.directory.cleanup()
        for ruta in self.creados:
            Path(ruta).unlink(missing_ok=True)

    def enviar(self, declarado, cuerpo, nombre="prueba.mp4"):
        """POST /api/upload declarando `declarado` bytes y enviando `cuerpo`; devuelve (código, JSON)."""
        conexion = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=20)
        conexion.putrequest("POST", f"/api/upload?name={nombre}")
        conexion.putheader("Content-Length", str(declarado))
        conexion.putheader("X-LAP-Token", self.engine.token)
        conexion.endheaders()
        conexion.send(cuerpo)
        if len(cuerpo) < declarado:
            conexion.sock.shutdown(socket.SHUT_WR)    # el cliente se corta antes de terminar
        respuesta = conexion.getresponse()
        datos = json.loads(respuesta.read())
        conexion.close()
        if "path" in datos:
            self.creados.append(datos["path"])
        return respuesta.status, datos

    def test_un_video_pequeno_se_guarda(self):
        codigo, datos = self.enviar(3 * 1024 * 1024, b"\0" * (3 * 1024 * 1024))
        self.assertEqual(codigo, 200)
        self.assertEqual(Path(datos["path"]).stat().st_size, 3 * 1024 * 1024)

    def test_declarar_mas_de_1_gb_ya_no_se_rechaza_por_peso(self):
        antes = set((ROOT / "data" / "uploads").glob("*"))
        with patch("live_server.shutil.disk_usage") as disco:
            disco.return_value.free = 10 * 1024 * GB
            codigo, datos = self.enviar(int(1.5 * GB), b"\0" * 1024 * 1024)
        self.assertEqual(codigo, 400)
        self.assertIn("incompleta", datos["error"])        # pasó la validación de tamaño y falló porque el cliente se cortó
        self.assertNotIn("1 GB", datos["error"])
        self.assertEqual(set((ROOT / "data" / "uploads").glob("*")), antes, "la carga incompleta no deja archivos")

    def test_sin_espacio_en_disco_se_rechaza_antes_de_recibir(self):
        with patch("live_server.shutil.disk_usage") as disco:
            disco.return_value.free = 2 * GB
            codigo, datos = self.enviar(5 * GB, b"\0" * 1024)
        self.assertEqual(codigo, 400)
        self.assertIn("No hay espacio", datos["error"])


if __name__ == "__main__":
    unittest.main()
