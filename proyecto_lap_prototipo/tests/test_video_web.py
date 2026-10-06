"""Copias web de videos y subidas sin duplicar."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import video_web  # noqa: E402


class SubidasSinDuplicar(unittest.TestCase):
    def test_el_mismo_contenido_reutiliza_el_archivo_existente(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            a, b = d / "a.mp4", d / "b.mp4"
            a.write_bytes(b"video")
            self.assertEqual(video_web.deduplicar(d, a, "h1"), a)
            b.write_bytes(b"video")
            self.assertEqual(video_web.deduplicar(d, b, "h1"), a)
            self.assertFalse(b.exists())

    def test_contenido_distinto_se_conserva_y_un_indice_roto_no_falla(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            a, b = d / "a.mp4", d / "b.mp4"
            a.write_bytes(b"uno")
            b.write_bytes(b"dos!")
            (d / "_indice.json").write_text("no es json", encoding="utf-8")
            self.assertEqual(video_web.deduplicar(d, a, "h1"), a)
            self.assertEqual(video_web.deduplicar(d, b, "h2"), b)
            self.assertTrue(a.exists() and b.exists())

    def test_hash_igual_pero_tamano_distinto_no_se_confunde(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            a, b = d / "a.mp4", d / "b.mp4"
            a.write_bytes(b"1234")
            video_web.deduplicar(d, a, "h")
            b.write_bytes(b"12345678")
            self.assertEqual(video_web.deduplicar(d, b, "h"), b)


class CopiaWeb(unittest.TestCase):
    def test_los_formatos_del_navegador_no_se_convierten(self):
        for nombre in ("x.mp4", "x.webm", "x.mov", "x.m4v"):
            self.assertEqual(video_web.copia_web(Path(nombre)), Path(nombre))

    def test_un_avi_sin_copia_devuelve_none(self):
        with tempfile.TemporaryDirectory() as d:
            avi = Path(d) / "x.avi"
            avi.write_bytes(b"x")
            self.assertIsNone(video_web.copia_web(avi))


if __name__ == "__main__":
    unittest.main()
