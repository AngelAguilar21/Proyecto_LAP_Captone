import base64
import io
import re
import zipfile
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import commercial_trial as trial


class CommercialTrialTests(unittest.TestCase):
    def test_session_description_uses_saved_camera_names_and_origin(self):
        meta = dict(cameras=[dict(id='A', name='Puerta norte', source='video.mp4'),
                             dict(id='B', name='Puerta sur', sourceKind='recording')],
                    end=59.6, status='stopped')
        summary = trial.session_description(meta)
        self.assertEqual(summary['cameraNames'], ['Puerta norte', 'Puerta sur'])
        self.assertEqual(summary['sourceLabel'], 'Videos grabados')
        self.assertEqual(summary['statusLabel'], 'Detenido por el operador')
        self.assertEqual(summary['duration'], 59.6)
        meta['cameras'] = [dict(id='TOKYO', source='https://example.com/live')]
        self.assertEqual(trial.session_description(meta)['sourceLabel'], 'En vivo')

    def test_xlsx_without_declared_sheet_dimensions(self):
        from openpyxl import Workbook
        book = Workbook()
        sheet = book.active
        sheet.title = 'Historico'
        sheet.append(trial.COLUMNS)
        sheet.append(['shop', '2026-09-30', 6, 250, 10, 50, 60])
        original, modified = io.BytesIO(), io.BytesIO()
        book.save(original)
        with zipfile.ZipFile(original) as src, zipfile.ZipFile(modified, 'w') as dst:
            for name in src.namelist():
                data = src.read(name)
                if name.startswith('xl/worksheets/'):
                    data = re.sub(rb'<dimension[^>]*/>', b'', data)
                dst.writestr(name, data)
        rows, _ = trial.read_history(base64.b64encode(modified.getvalue()).decode(), 'example.xlsx', 'shop')
        self.assertEqual(rows[0]['ventas_pen'], 250)

    def payload(self, text):
        return base64.b64encode(text.encode()).decode()

    def rows(self):
        return trial.read_history(self.payload(trial.example_csv('shop', '2026-10-07', 6)), 'example.csv', 'shop')[0]

    def observed(self):
        return dict(session='saved-video', date='2026-10-07', hour=6, coverage=60, entries=2, exits=1)

    def test_template_and_calculation_do_not_extrapolate_short_video(self):
        result = trial.calculate(self.rows(), self.observed())
        self.assertEqual(result['days'], 8)
        self.assertAlmostEqual(result['estimate'], round(2 * result['rate'], 2))
        self.assertIsNone(result['conversion'])
        self.assertGreater(result['forecast'], result['estimate'])

    def test_reject_other_shop_and_duplicate_hours(self):
        text = trial.example_csv('shop', '2026-10-07', 6)
        with self.assertRaisesRegex(ValueError, 'otra tienda'):
            trial.read_history(self.payload(text), 'x.csv', 'wrong')
        with self.assertRaisesRegex(ValueError, 'duplicadas'):
            trial.read_history(self.payload(text + text.splitlines()[1] + '\n'), 'x.csv', 'shop')

    def test_coverage_future_and_wrong_weekday_cannot_calibrate(self):
        rows = self.rows()
        for row in rows:
            row['cobertura_min'] = 1
        self.assertIsNone(trial.calculate(rows, self.observed())['estimate'])
        rows = self.rows()
        for row in rows:
            row['fecha'] = '2026-10-14'
        self.assertIsNone(trial.calculate(rows, self.observed())['forecast'])

    def test_zero_entries_not_missing(self):
        result = trial.calculate(self.rows(), {**self.observed(), 'entries':0})
        self.assertEqual(result['estimate'], 0)

    def test_less_than_three_dates_has_no_forecast(self):
        result = trial.calculate(self.rows()[:2], self.observed())
        self.assertIsNone(result['estimate'])
        self.assertIsNone(result['historicalConversion'])

    def test_repeat_saves_separate_results_without_sales_tables(self):
        con = sqlite3.connect(':memory:')
        result = trial.calculate(self.rows(), self.observed())
        a = trial.save(con, result, {'id':'shop','nombre':'Shop'}, 'a.csv', 'a')
        b = trial.save(con, result, {'id':'shop','nombre':'Shop'}, 'a.csv', 'a')
        self.assertNotEqual(a['id'], b['id'])
        self.assertEqual(len(trial.saved(con)), 2)
        self.assertIsNone(con.execute("SELECT name FROM sqlite_master WHERE name='commercial_sales'").fetchone())
        con.close()

    def test_observation_only_counts_covered_first_hour(self):
        meta = dict(session='s', created='2026-10-07T11:59:30+00:00', end=120, config={}, cameraAnalytics={'B':{'t':100}})
        shop = dict(accesses=[{'cameraId':'B'}], events=[{'t':10,'direction':'entries'},{'t':31,'direction':'entries'}])
        result = trial.observation(meta, shop)
        self.assertEqual(result['coverage'],30)
        self.assertEqual(result['entries'],1)

    def test_midnight_template_uses_correct_weekday(self):
        rows = trial.read_history(self.payload(trial.example_csv('shop','2026-10-07',23)), 'a.csv', 'shop')[0]
        result = trial.calculate(rows, {**self.observed(), 'hour':23})
        self.assertEqual(result['nextTarget'],'2026-10-08T00:00:00')
        self.assertEqual(result['nextDays'],8)

    def test_nonfinite_and_negative_inputs_rejected(self):
        for invalid in ('nan', '-5', '=1+1'):
            text = 'negocio_id,fecha,hora,ventas_pen,transacciones,entradas,cobertura_min\nshop,2026-09-30,6,' + invalid + ',2,10,60\n'
            with self.assertRaises(ValueError):
                trial.read_history(self.payload(text), 'x.csv', 'shop')


if __name__ == '__main__':
    unittest.main()
