import sys
import tempfile
import unittest
from datetime import datetime,timedelta
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import business_data as db
import commercial as commerce
from bag_signal import VisitMatcher


class CommercialTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.con=db.connect(Path(self.temp.name)/'p.json')
        db.crear_negocio(self.con,'shop','Tienda',None,None,'Grupo AeroRetail')
        self.businesses=db.listar_negocios(self.con)
        commerce.setup(self.con)

    def tearDown(self):
        self.con.close();self.temp.cleanup()

    def test_previous_csv_hourly_sales_are_preserved(self):
        db.cargar_ventas(self.con, [('shop','2026-09-27',10,20), ('shop','2026-09-27',10,30), ('shop','2026-09-27',None,900)])
        commerce.setup(self.con)
        commerce.setup(self.con)
        rows=self.con.execute('SELECT hora,monto FROM commercial_sales').fetchall()
        self.assertEqual(rows, [(10,50)])
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM ventas').fetchone()[0],3)

    def test_atomic_invalid_csv_duplicate_and_dataset_isolation(self):
        header='negocio_id,fecha,hora,monto,moneda\n'
        bad=commerce.import_sales(self.con,header+'shop,2026-09-27,10,100,PEN\nshop,2026-09-27,11,NaN,PEN',self.businesses,'bad.csv')
        self.assertTrue(bad['errors'])
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM commercial_sales').fetchone()[0],0)
        text=header+'shop,2026-09-27,10,100,PEN'
        self.assertTrue(commerce.import_sales(self.con,text,self.businesses,'ok.csv')['imported'])
        self.assertFalse(commerce.import_sales(self.con,text,self.businesses,'duplicate.csv')['imported'])
        self.assertTrue(commerce.import_sales(self.con,text,self.businesses,'test.csv','demo')['imported'])
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM commercial_sales').fetchone()[0],2)

    def test_preview_and_daily_ambiguity(self):
        preview=commerce.import_sales(self.con,'negocio_id;fecha;hora;monto\nshop;2026-09-27;10;25,50',self.businesses,'preview.csv',preview=True)
        self.assertFalse(preview['imported']);self.assertEqual(preview['rows'],1)
        _,errors=commerce.parse_sales('negocio_id,fecha,hora,monto\nshop,2026-09-27,,100',self.businesses)
        self.assertTrue(errors)

    def historical(self):
        for index in range(1,5):
            date=(datetime(2026,9,27)-timedelta(weeks=index)).date().isoformat()
            commerce.import_sales(self.con,f'negocio_id,fecha,hora,monto\nshop,{date},10,200',self.businesses,f'{index}.csv')
            with self.con:
                self.con.execute('INSERT INTO commercial_traffic VALUES (?,?,?,?,?,?,?,?)',(str(index),'shop',date,10,10,8,3600,'real'))

    def test_short_clip_does_not_claim_conversion_and_replays_do_not_duplicate_hours(self):
        self.historical()
        commerce.import_sales(self.con, 'negocio_id,fecha,hora,monto,transacciones\nshop,2026-09-27,10,100,2', self.businesses, 'now.csv')
        with self.con:
            for sid, seconds in [('first',30), ('repeated',60)]:
                self.con.execute('INSERT INTO commercial_traffic VALUES (?,?,?,?,?,?,?,?)',(sid,'shop','2026-09-27',10,4,3,seconds,'real'))
        result = commerce.summary(self.con, self.businesses, [], day='2026-09-27', hour=10)
        row = result['businesses'][0]
        self.assertEqual(row['entries'],4)
        self.assertEqual(row['coverage'],60)
        self.assertEqual(row['session'],'repeated')
        self.assertIsNone(row['conversion'])
        self.assertIsNone(result['empresas'][0]['conversion'])
        self.assertEqual(len(row['hourly']),1)
        self.assertEqual(row['forecast']['estimate'],80)

    def test_forecast_no_future_data_insufficient_history_or_demo_mix(self):
        self.assertIsNone(commerce.forecast(self.con,'shop','2026-09-27',10,5)['estimate'])
        self.historical()
        forecast=commerce.forecast(self.con,'shop','2026-09-27',10,5)
        self.assertEqual(forecast['estimate'],100)
        self.assertEqual(forecast['days'],4)
        self.assertIsNone(commerce.forecast(self.con,'shop','2026-09-27',10,5,'demo')['estimate'])
        with self.con:
            self.con.execute('UPDATE commercial_traffic SET coverage=10')
        self.assertIsNone(commerce.forecast(self.con,'shop','2026-09-27',10,5)['estimate'])

    def test_summary_groups_company_and_exposes_hourly_and_next_forecast(self):
        for index in range(1, 5):
            date=(datetime(2026,9,27)-timedelta(weeks=index)).date().isoformat()
            commerce.import_sales(self.con, f'negocio_id,fecha,hora,monto,transacciones\nshop,{date},10,200,20\nshop,{date},11,300,30', self.businesses, f'{index}.csv')
            with self.con:
                self.con.execute('INSERT INTO commercial_traffic VALUES (?,?,?,?,?,?,?,?)',(str(index),'shop',date,10,10,8,3600,'real'))
                self.con.execute('INSERT INTO commercial_traffic VALUES (?,?,?,?,?,?,?,?)',(str(index)+'-next','shop',date,11,12,9,3600,'real'))
        with self.con:
            self.con.execute('INSERT INTO commercial_traffic VALUES (?,?,?,?,?,?,?,?)',('current','shop','2026-09-27',10,15,11,3600,'real'))
        commerce.import_sales(self.con, 'negocio_id,fecha,hora,monto,transacciones\nshop,2026-09-27,10,150,5', self.businesses, 'current.csv')
        result = commerce.summary(self.con, self.businesses, [], day='2026-09-27', hour=10)
        row = result['businesses'][0]
        self.assertEqual(row['empresa'], 'Grupo AeroRetail')
        self.assertEqual(row['entries'], 15)
        self.assertEqual(row['conversion'], 33.3)
        self.assertEqual(row['hourly'][0]['hour'], 10)
        self.assertEqual(row['forecast']['estimate'], 300)
        self.assertEqual(row['nextForecast']['expectedEntries'], 12)
        self.assertEqual(row['nextForecast']['estimate'], 300)
        self.assertEqual(result['empresas'][0]['name'], 'Grupo AeroRetail')
        self.assertEqual(commerce.summary(self.con, self.businesses, [], day='2026-09-27', hour=10, empresa='Otro')['businesses'], [])

    def test_incident_hour_sales_and_small_sample(self):
        self.historical()
        commerce.import_sales(self.con,'negocio_id,fecha,hora,monto\nshop,2026-09-27,10,240',self.businesses,'current.csv')
        with self.con:
            self.con.execute('INSERT INTO commercial_incidents VALUES (?,?,?,?,?,?)',('i','shop','2026-09-27T10:05:00-05:00',30,12,'real'))
        result=commerce.summary(self.con,self.businesses,[],day='2026-09-27',hour=10)
        incident=result['businesses'][0]['incidents'][0]
        self.assertEqual(incident['differencePercent'],20)
        self.assertEqual(incident['sampleDays'],4)
        with self.con:
            self.con.execute('UPDATE commercial_incidents SET duracion=4000')
        self.assertIsNone(commerce.summary(self.con,self.businesses,[],day='2026-09-27',hour=10)['businesses'][0]['incidents'][0]['differencePercent'])

    def test_recording_without_civil_time_is_not_today(self):
        traffic=[{'id':'shop','entries':1,'exits':0,'events':[{'t':5,'direction':'entries'}],'accesses':[]}]
        meta={'session':'s','module':'unified','created':'2026-09-27T15:00:00Z','end':10,'config':{'sourceMode':'recordings'}}
        self.assertFalse(commerce.save_session(self.con,meta,traffic))
        meta['config']['recordingStartedAt']='2026-09-20T09:59:55-05:00'
        self.assertTrue(commerce.save_session(self.con,meta,traffic))
        self.assertEqual(self.con.execute('SELECT fecha,hora,entradas FROM commercial_traffic WHERE entradas=1').fetchone(),('2026-09-20',10,1))

    def test_video_trial_is_not_real_commercial_traffic(self):
        meta={'session':'trial','module':'unified','created':'2026-09-27T15:00:00Z','end':10,'config':{'sourceMode':'recordings','testRun':True}}
        traffic=[{'id':'shop','entries':1,'exits':0,'events':[{'t':5,'direction':'entries'}],'accesses':[]}]
        self.assertTrue(commerce.save_session(self.con,meta,traffic))
        self.assertEqual(self.con.execute('SELECT dataset FROM commercial_traffic').fetchone()[0],'demo')

    def test_visual_matches_ambiguous_expired_and_object_not_purchase(self):
        matcher=VisitMatcher(ttl=60)
        vector=np.array([1.,0.,0.])
        matcher.observe('shop','entries',0,vector,[], 'entry')
        result=matcher.observe('shop','exits',10,vector,[26], 'exit')
        self.assertTrue(result['matched']);self.assertTrue(result['changed'])
        matcher.observe('shop','entries',20,vector,[], 'one')
        matcher.observe('shop','entries',21,vector,[], 'two')
        self.assertFalse(matcher.observe('shop','exits',30,vector,[26], 'ambiguous')['matched'])
        self.assertFalse(matcher.observe('shop','exits',100,vector,[26], 'expired')['matched'])
        matcher.observe('shop','entries',110,vector,[26], 'existing-bag')
        self.assertFalse(matcher.observe('shop','exits',120,vector,[26], 'same-bag')['changed'])


if __name__=='__main__':
    unittest.main()
