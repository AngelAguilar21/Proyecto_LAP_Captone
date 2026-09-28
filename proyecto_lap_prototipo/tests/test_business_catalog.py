import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import business_data as db
import business_catalog as catalog
from following.line_counter import LineCounter


class BusinessCatalogTest(unittest.TestCase):
    def test_import_is_idempotent_and_preserves_operator_name(self):
        with tempfile.TemporaryDirectory() as directory:
            con = db.connect(Path(directory) / 'project.json')
            config = {'planId': 'lap-3', 'mapAsset': '/maps/lap/3.json', 'cameras': []}
            rows = catalog.sync(con, config, ROOT / 'dashboard/public')
            self.assertGreater(len(rows), 50)
            first = rows[0]
            with con:
                con.execute('UPDATE negocios SET nombre=? WHERE id=?', ('Nombre actualizado', first['id']))
                con.execute('INSERT INTO negocio_estados VALUES (?,?)', (first['id'], 'cerrado'))
            again = catalog.sync(con, config, ROOT / 'dashboard/public')
            self.assertEqual(len(rows), len(again))
            restored = next(b for b in again if b['id'] == first['id'])
            self.assertEqual(restored['nombre'], 'Nombre actualizado')
            self.assertEqual(restored['estado'], 'cerrado')
            con.close()

    def test_crossings_aggregate_multiple_doors_and_unmeasured_is_not_zero(self):
        line = dict(id='door', name='Puerta', a=[.2,.5], b=[.8,.5], entrySide=1, place={'id':'shop'})
        counter = LineCounter([line])
        counter.update([{'id':'person', 'pixel':[.5,.45]}], 0)
        result = counter.update([{'id':'person', 'pixel':[.5,.55]}], 1)
        config = {'cameras':[{'id':'C1','countLines':[line]},{'id':'C2','countLines':[line]}]}
        businesses = [dict(id='shop',nombre='Tienda',ubicacion=None,puertas=[{'camaraId':'C1','lineaId':'door'},{'camaraId':'C2','lineaId':'door'}]), dict(id='other',nombre='Otra tienda',ubicacion=None,puertas=[])]
        rows = catalog.traffic(businesses, {'C1':{'crossings':result},'C2':{'crossings':result}}, config)
        self.assertEqual(rows[0]['entries'], 2)
        self.assertEqual(rows[0]['exits'], 0)
        self.assertIsNone(rows[1]['entries'])
        self.assertEqual(len(rows[0]['accesses']), 2)


if __name__ == '__main__':
    unittest.main()
