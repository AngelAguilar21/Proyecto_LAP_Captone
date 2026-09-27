"""Los dos roles administran proyectos, y cada proyecto tiene nombre propio.

Crear y eliminar un proyecto es gestionar el espacio de trabajo; configurar su
plano y sus cámaras sigue siendo solo del operador. Y como cada proyecto es un
espacio distinto, dos no pueden llamarse igual: con nombres repetidos la lista
deja de servir para elegir.
"""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path('proyecto_lap_prototipo').resolve()))
sys.path.insert(0, str(Path('proyecto_lap_prototipo/src').resolve()))
import projects
from live_server import Handler


class NombresUnicosTests(unittest.TestCase):
    def indice(self, *nombres):
        return {"active": None, "projects": [{"id": f"p-{i}", "name": n} for i, n in enumerate(nombres)]}

    def test_rechaza_un_nombre_ya_usado(self):
        index = self.indice("Universidad", "Terminal A")
        with self.assertRaises(ValueError) as caso:
            projects.check_name(index, "Universidad")
        self.assertIn("Universidad", str(caso.exception))

    def test_no_distingue_mayusculas_ni_espacios_de_sobra(self):
        index = self.indice("Universidad ESAN")
        for intento in ("universidad esan", "  UNIVERSIDAD   ESAN  ", "Universidad  ESAN"):
            with self.assertRaises(ValueError, msg=intento):
                projects.check_name(index, intento)

    def test_acepta_un_nombre_libre_y_lo_normaliza(self):
        index = self.indice("Universidad")
        self.assertEqual(projects.check_name(index, "  Pabellón   A  "), "Pabellón A")

    def test_renombrar_no_choca_consigo_mismo(self):
        index = self.indice("Universidad", "Terminal A")
        # el mismo proyecto puede conservar su nombre al reescribirlo
        self.assertEqual(projects.check_name(index, "Universidad", ignore="p-0"), "Universidad")
        # pero no tomar el del otro
        with self.assertRaises(ValueError):
            projects.check_name(index, "Terminal A", ignore="p-0")

    def test_exige_nombre_y_limita_el_largo(self):
        index = self.indice("Universidad")
        for vacio in ("", "   ", "\t\n"):
            with self.assertRaises(ValueError):
                projects.check_name(index, vacio)
        with self.assertRaises(ValueError):
            projects.check_name(index, "x" * 81)
        self.assertEqual(len(projects.check_name(index, "x" * 80)), 80)


class RolesTests(unittest.TestCase):
    def test_configurar_sigue_siendo_solo_del_operador(self):
        # la frontera real: el administrador no toca plano, cámaras ni calibración
        for ruta in ("/api/config", "/api/import-plan", "/api/upload", "/api/plan-lines"):
            self.assertIn(ruta, Handler.SOLO_OPERADOR)

    def test_gestionar_proyectos_no_esta_restringido_al_operador(self):
        self.assertNotIn("/api/projects", Handler.SOLO_OPERADOR)

    def test_el_endpoint_de_proyectos_no_filtra_por_rol(self):
        # antes rechazaba con 403 cualquier accion distinta de 'open' si el rol no
        # era operador; esa comprobacion ya no debe existir en el codigo.
        import inspect
        fuente = inspect.getsource(Handler.do_POST)
        self.assertNotIn("solo puede abrir proyectos", fuente)
        bloque = fuente[fuente.index('/api/projects'):]
        bloque = bloque[:bloque.index("engine.delete_project")]
        self.assertNotIn('sesion["rol"]', bloque, "el endpoint de proyectos volvió a mirar el rol")
        for accion in ("create", "open", "rename"):
            self.assertIn(f'action == "{accion}"', bloque)


if __name__ == '__main__':
    unittest.main()
