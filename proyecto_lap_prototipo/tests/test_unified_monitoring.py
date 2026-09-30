import sys, unittest, tempfile, json
from pathlib import Path
from types import SimpleNamespace
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'src'))
from following.line_counter import LineCounter
from following.flow import FlowField
from following.combined import CombinedAnalysis
from live_core import IdentityStore,validate_config,Occupancy
from live_server import default_config,Engine
from replay import ReplayWriter
from live_reports import report_data


class UnifiedTests(unittest.TestCase):
    def test_direction_finite_segment_jitter_and_reappearance(self):
        counter=LineCounter([{'id':'door','name':'Puerta','a':[.2,.5],'b':[.8,.5],'entrySide':1}])
        def sample(x,y,t):return counter.update([{'id':'P','pixel':[x,y]}],t)[0]
        sample(.5,.4,0)
        self.assertEqual(sample(.5,.504,.2)['entries'],0)
        self.assertEqual(sample(.5,.6,.4)['entries'],1)
        self.assertEqual(sample(.5,.4,1.6)['exits'],1)
        sample(.9,.4,3)
        self.assertEqual(sample(.9,.6,3.2)['entries'],1)
        counter.update([],6)
        self.assertEqual(sample(.5,.4,7)['exits'],1)

    def test_combined_reuses_p2pnet_points_without_second_inference(self):
        camera={'id':'C','detectionZone':[[0,0],[.5,0],[.5,1],[0,1]]}
        camera['analysisZones']=[{'id':'small','name':'Sector','points':[[0,0],[.1,0],[.1,1],[0,1]],'threshold':2,'dwell':1}]
        analysis=CombinedAnalysis([camera],ROOT)
        frame=np.zeros((100,100,3),dtype=np.uint8)
        people=[{'id':'A','pixel':[25,50]},{'id':'B','pixel':[75,50]}]
        # Escena normal: sin muestra de densidad, P2PNet no participa.
        result=analysis.observe(camera,frame,people,0)
        self.assertEqual(result['occupancy']['count'],1)
        self.assertEqual(result['dense']['status'],'idle')
        self.assertEqual(result['dense']['count'],0)
        self.assertFalse(result['denseEnabled'])
        self.assertFalse(result['avie']['p2pRequested'])
        self.assertEqual(result['occupancy']['zones'][1]['count'],0)
        # Escena densa: se reutiliza la muestra asíncrona sin una segunda inferencia.
        density={'status':'ready','t':2,'count':1,'points':[(.25,.5)]}
        result=analysis.observe(camera,frame,people,2,density=density)
        self.assertTrue(result['denseEnabled'])
        self.assertEqual(result['dense']['points'],[(.25,.5)])
        self.assertEqual(result['occupancy']['peak'],1)
        self.assertEqual(analysis.close()['C']['dense']['count'],1)

    def test_late_identity_requires_sustained_mutual_evidence(self):
        cfg=default_config();cfg['clocksVerified']=False
        store=IdentityStore(cfg)
        color=np.ones((8,8),dtype=np.float32)/64
        rows=[{'camera':'A','local':1,'point':[1,1],'color':color},{'camera':'B','local':1,'point':[1.03,1],'color':color}]
        initial=store.update(rows,0);self.assertEqual(len({r['id'] for r in initial}),2)
        cfg['clocksVerified']=True
        for t in (.2,.4):self.assertEqual(len({r['id'] for r in store.update(rows,t)}),2)
        self.assertEqual(len({r['id'] for r in store.update(rows,.6)}),1)

    def test_separate_levels_never_share_an_identity(self):
        cfg=default_config();cfg['clocksVerified']=True
        cfg['cameras'][0]['planId']='lap-2';cfg['cameras'][1]['planId']='lap-3'
        store=IdentityStore(cfg)
        rows=store.update([{'camera':'A','local':1,'point':[1,1],'color':None},{'camera':'B','local':1,'point':[1,1],'color':None}],0)
        self.assertEqual(len({r['id'] for r in rows}),2)

    def test_flow_field_keeps_opposite_directions_and_ignores_lost_tracks(self):
        field=FlowField({'radius':2})
        field.update([{'id':'A','point':[1,1]},{'id':'B','point':[1.8,1]}],0)
        values=field.update([{'id':'A','point':[1.2,1]},{'id':'B','point':[1.6,1]}],.2)
        self.assertEqual(len(values),2)
        self.assertEqual({round(v['dx']) for v in values},{-1,1})
        field.update([],4)
        self.assertEqual(sum(v['samples'] for v in field.update([{'id':'A','point':[3,1]}],5)),2)

    def test_integrated_report_keeps_counts_and_crossings_distinct(self):
        cfg=default_config()
        state={'session':'test','status':'ended','t':10,'analytics':{'flow':[]},'cameraAnalytics':{'A':{'t':10,'occupancy':{'count':2,'peak':9,'peakAt':3,'mean':4.5},'crossings':[{'name':'Puerta','entries':3,'exits':1,'lastCrossing':8}]}}}
        row=report_data(cfg,state,'cameras')['rows'][0]
        self.assertEqual(row[2:4],[2,9]);self.assertEqual(row[-2:],[3,1])
        self.assertEqual(report_data(cfg,state,'crossings')['rows'][0][1:3],[3,1])

    def test_airport_heat_uses_local_cells_not_terminal_sized_cells(self):
        cfg=default_config();cfg.update(width=1400,height=2000,unit='meters')
        counter=Occupancy(cfg)
        result=counter.update([{'id':'A','point':[1,1]},{'id':'B','point':[5,1]}],0)
        self.assertEqual(len(result['heat']),2)
        self.assertTrue(all(cell['size']==2 for cell in result['heat']))

    def test_restart_restores_summary_without_restarting_camera_or_people(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cfg=default_config();path=root/'config.json';path.write_text(json.dumps(cfg),encoding='utf-8')
            writer=ReplayWriter(root,'1234abcd','unified',[],cfg)
            writer.meta['cameraAnalytics']={'A':{'t':0,'occupancy':{'count':3}}}
            writer.meta['levelAnalytics']={'custom':{'heat':[],'zones':[],'clusters':[],'mappedCount':3}}
            writer.finish('ended')
            engine=Engine(path)
            self.assertEqual(engine.state['status'],'ended');self.assertEqual(engine.state['cameraAnalytics']['A']['occupancy']['count'],3)
            self.assertEqual(engine.state['people'],[]);self.assertIsNone(engine.worker);self.assertEqual(engine.frames,{})

    def test_invalid_access_line_is_rejected(self):
        cfg=default_config();cfg['cameras'][0]['countLines']=[{'id':'x','name':'Puerta','a':[0,0],'b':[0,0],'entrySide':1}]
        with self.assertRaisesRegex(ValueError,'extremos'):validate_config(cfg)

if __name__=='__main__':unittest.main()
