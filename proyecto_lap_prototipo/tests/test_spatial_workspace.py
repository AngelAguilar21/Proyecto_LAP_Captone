import copy
import io
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

import cv2
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from live_server import Engine, default_config
from live_core import validate_config, Occupancy
from spatial_scope import accepts
from plan_import import plan_lines_from_bytes


class SpatialWorkspaceTests(unittest.TestCase):
    def test_mirrors_and_outside_floor_are_rejected(self):
        c={'detectionZone':[[0,0],[.5,0],[.5,1],[0,1]]}
        cfg={'workArea':[[0,0],[5,0],[5,5],[0,5]]}
        self.assertTrue(accepts(c,cfg,.25,.5,(2,2)))
        self.assertFalse(accepts(c,cfg,.8,.5,(2,2)))
        self.assertFalse(accepts(c,cfg,.25,.5,(8,2)))
        self.assertFalse(accepts(c,cfg,.25,.5,None))

    def test_el_alcance_de_proyectos_antiguos_ya_no_descarta_personas(self):
        c={'restrictCoverage':True,'coverageShape':'free','coveragePolygon':[[0,0],[1,0],[0,1]]}
        self.assertTrue(accepts(c,{},.5,.5,(9,9)))

    def test_invalid_work_area_and_vectors_rejected(self):
        cfg=default_config()
        cfg['workArea']=[[0,0],[1,1],[0,1],[1,0]]
        with self.assertRaises(ValueError):validate_config(cfg)
        cfg.pop('workArea')
        cfg['planLines']=[[0,0,float('nan'),1]]
        with self.assertRaises(ValueError):validate_config(cfg)

    def test_line_extraction_returns_real_vector_coordinates(self):
        from PIL import Image,ImageDraw
        image=Image.new('RGB',(400,300),'white')
        ImageDraw.Draw(image).rectangle((30,40,360,260),outline='black',width=4)
        data=io.BytesIO();image.save(data,format='PNG')
        result=plan_lines_from_bytes(data.getvalue(),12)
        self.assertGreater(len(result['planLines']),3)
        self.assertTrue(all(0<=v<=1 for line in result['planLines'] for v in line))

    def test_unified_start_rejects_missing_camera_masks(self):
        with tempfile.TemporaryDirectory() as d:
            engine=Engine(Path(d)/'config.json')
            cfg=default_config();cfg['clocksVerified']=True
            for c in cfg['cameras']:c['pairs']=[[0,0,0,0],[1,0,12,0],[1,1,12,8],[0,1,0,8]]
            engine.configure(cfg)
            with self.assertRaisesRegex(ValueError,'Delimita'):
                engine.start({'detector':'yolo','requireUnified':True})

    def test_live_pipeline_filters_before_creating_ids_and_stops_together(self):
        # Synthetic detector outputs deliberately include a reflection outside the mask.
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'source.avi'
            writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),10,(320,240))
            self.assertTrue(writer.isOpened())
            for _ in range(16):writer.write(np.zeros((240,320,3),dtype=np.uint8))
            writer.release()
            engine=Engine(Path(d)/'config.json');cfg=default_config();cfg['clocksVerified']=True
            for c in cfg['cameras']:
                c['source']=str(path);c['pairs']=[[0,0,0,0],[1,0,12,0],[1,1,12,8],[0,1,0,8]]
                c['detectionZone']=[[0,0],[.5,0],[.5,1],[0,1]]
            cfg['cameras'][1]['offset']=.4
            engine.configure(cfg)
            rows=[];last=0
            fake_detector=SimpleNamespace(detectar=lambda frame:[SimpleNamespace(x=50,y=100,confianza=.9),SimpleNamespace(x=250,y=100,confianza=.9)])
            with patch.object(engine,'load_detector',return_value=fake_detector):
                engine.start({'detector':'yolo','requireUnified':True})
                try:
                    deadline=time.monotonic()+20
                    while time.monotonic()<deadline:
                        s=engine.snapshot()
                        if s['status']=='error':self.fail(s['error'])
                        if s['status']=='ended':break
                        rows+=s.get('people',[]);last=max(last,s['t'])
                        time.sleep(.02)
                finally:
                    engine.stop();engine.worker.join(10)
            self.assertTrue(rows)
            self.assertTrue(all(p['pixel'][0]<160 for p in rows))
            self.assertTrue(all(p['point'] is not None and 0<=p['point'][0]<=12 for p in rows))
            self.assertLess(last,1.4)
            self.assertFalse(engine.worker.is_alive())


if __name__=='__main__':unittest.main()
