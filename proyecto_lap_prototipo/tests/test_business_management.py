"""Negocios con varias puertas: persistencia, aislamiento y vínculos válidos."""
import sys
import tempfile
import unittest
import sqlite3
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import business_data as db


class BusinessManagementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'proyecto.json'
        self.connection = db.connect(self.path)
        self.config = {'planId': 'p3', 'plans': {'p3': {'width': 100, 'height': 100}, 'p2': {'width': 100, 'height': 100}},
                       'cameras': [{'id': 'c1', 'planId': 'p3', 'countLines': [{'id': 'a'}, {'id': 'b'}]},
                                   {'id': 'c2', 'planId': 'p2', 'countLines': [{'id': 'c'}]}]}
        self.business = {'id': 'tienda', 'nombre': 'Duty Free', 'ubicacion': {'planId': 'p3', 'point': [20, 30]},
                         'puertas': [{'camaraId': 'c1', 'lineaId': 'a'}, {'camaraId': 'c1', 'lineaId': 'b'}]}

    def tearDown(self):
        self.connection.close()
        self.tmp.cleanup()

    def test_edit_persists_and_replaces_doors(self):
        db.guardar_negocio(self.connection, self.business, self.config)
        self.business.update(nombre='Duty Free nuevo', puertas=self.business['puertas'][1:])
        self.business['ubicacion']['point'] = [40, 50]
        db.guardar_negocio(self.connection, self.business, self.config)
        self.connection.close()
        self.connection = db.connect(self.path)
        actual = db.listar_negocios(self.connection)[0]
        self.assertEqual(actual['nombre'], 'Duty Free nuevo')
        self.assertEqual(actual['ubicacion']['point'], [40, 50])
        self.assertEqual(actual['puertas'], [{'camaraId': 'c1', 'lineaId': 'b'}])

    def test_conflicting_or_missing_doors_do_not_modify_existing_data(self):
        db.guardar_negocio(self.connection, self.business, self.config)
        for doors in [[{'camaraId': 'c1', 'lineaId': 'a'}], [{'camaraId': 'c1', 'lineaId': 'missing'}], [{'camaraId': 'c2', 'lineaId': 'c'}]]:
            with self.assertRaises(ValueError):
                db.guardar_negocio(self.connection, {**self.business, 'id': 'other', 'nombre': 'Otra', 'puertas': doors}, self.config)
        self.assertEqual(len(db.listar_negocios(self.connection)), 1)

    def test_duplicate_names_and_bad_coordinates(self):
        db.guardar_negocio(self.connection, self.business, self.config)
        with self.assertRaises(ValueError):
            db.guardar_negocio(self.connection, {**self.business, 'id': 'other', 'nombre': ' duty free ', 'puertas': []}, self.config)
        for p in [[-1, 30], [float('nan'), 30], [101, 30]]:
            with self.assertRaises(ValueError):
                db.guardar_negocio(self.connection, {**self.business, 'ubicacion': {'planId': 'p3', 'point': p}}, self.config)

    def test_delete_preserves_other_business_and_project_isolation(self):
        db.guardar_negocio(self.connection, self.business, self.config)
        db.cargar_ventas(self.connection, [('tienda', '2026-09-27', 9, 100)])
        other = db.connect(Path(self.tmp.name) / 'otro.json')
        self.assertEqual(db.listar_negocios(other), [])
        other.close()
        db.eliminar_negocio(self.connection, 'tienda')
        self.assertEqual(db.listar_negocios(self.connection), [])
        for table in ['ventas', 'negocio_puertas', 'negocio_ubicaciones']:
            self.assertEqual(self.connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0], 0)

    def test_old_single_door_is_migrated(self):
        db.crear_negocio(self.connection, 'old', 'Antiguo', 'c1', 'a')
        self.connection.close()
        self.connection = db.connect(self.path)
        self.assertEqual(db.listar_negocios(self.connection)[0]['puertas'], [{'camaraId': 'c1', 'lineaId': 'a'}])

    def test_legacy_database_gets_company_default(self):
        legacy = Path(self.tmp.name) / 'legacy.json'
        self.connection.close()
        raw = sqlite3.connect(db.path_for(legacy))
        raw.execute('CREATE TABLE negocios (id TEXT PRIMARY KEY, nombre TEXT NOT NULL, camara_id TEXT, linea_id TEXT, creado REAL NOT NULL)')
        raw.execute('INSERT INTO negocios VALUES (?,?,?,?,?)', ('legacy', 'Negocio antiguo', None, None, 0))
        raw.commit(); raw.close()
        self.connection = db.connect(legacy)
        self.assertEqual(db.listar_negocios(self.connection)[0]['empresa'], 'Sin empresa')

    def test_official_place_reference_is_persistent_and_not_duplicated(self):
        self.config['plans']['p3']['mapAsset'] = '/maps/lap/3.json'
        catalog = {'features': [{'id': 'poi-1', 'geometry': {'type': 'Point', 'coordinates': [20, 30]}, 'properties': {'class': 'retail'}}]}
        self.business['referencia'] = {'asset': '/maps/lap/3.json', 'featureId': 'poi-1'}
        db.guardar_negocio(self.connection, self.business, self.config, catalog)
        self.assertEqual(db.listar_negocios(self.connection)[0]['referencia'], self.business['referencia'])
        with self.assertRaises(ValueError):
            db.guardar_negocio(self.connection, {**self.business, 'id': 'other', 'nombre': 'Otra', 'puertas': []}, self.config, catalog)
        with self.assertRaises(ValueError):
            db.guardar_negocio(self.connection, {**self.business, 'ubicacion': {'planId': 'p3', 'point': [21, 30]}}, self.config, catalog)
        self.business['referencia'] = None
        self.business['ubicacion']['point'] = [21, 30]
        db.guardar_negocio(self.connection, self.business, self.config)
        self.assertIsNone(db.listar_negocios(self.connection)[0]['referencia'])


if __name__ == '__main__':
    unittest.main()
