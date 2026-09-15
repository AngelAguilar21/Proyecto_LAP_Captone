"""API, lifecycle and generalized configuration checks without modifying user data."""
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from live_server import Engine, Handler, ThreadingHTTPServer, default_config
from live_core import validate_config, Occupancy
from live_reports import export, report_data
from plan_import import import_plan


class AeroTrackTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(prefix="aerotrack-test-")
        self.engine=Engine(Path(self.directory.name)/"config.json")
        self.server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        self.server.engine=self.engine
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base=f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.engine.stop()
        if self.engine.worker:
            self.engine.worker.join(timeout=12)
        self.server.shutdown()
        self.server.server_close()
        self.directory.cleanup()

    def request(self,path,data=None,token=True):
        headers={"Content-Type":"application/json"}
        if token:
            headers["X-LAP-Token"]=self.engine.token
        return urlopen(Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers),timeout=15)

    def wait_status(self,status,timeout=15):
        until=time.monotonic()+timeout
        while time.monotonic()<until:
            snapshot=self.engine.snapshot()
            if snapshot["status"]==status:
                return snapshot
            if snapshot["status"]=="error":
                self.fail(snapshot.get("error"))
            time.sleep(.05)
        self.fail(f"No se alcanzó {status}: {self.engine.snapshot()['status']}")

    def test_dynamic_config_supports_zero_one_and_five_cameras(self):
        config=default_config()
        original=config["cameras"][0]
        for count in (0,1,5):
            config["cameras"]=[{**copy.deepcopy(original),"id":f"C-{i}","source":"","links":[]} for i in range(count)]
            self.assertEqual(len(validate_config(config)["cameras"]),count)
            self.assertEqual(self.request('/api/config',config).status,200)
        restored=json.loads(self.engine.config_path.read_text(encoding='utf-8'))
        self.assertEqual(len(restored['cameras']),5)

    def test_unknown_source_and_empty_camera_set_are_reported(self):
        config=default_config()
        config["cameras"]=[]
        self.engine.configure(config)
        with self.assertRaises(ValueError):
            self.engine.start({"detector":"demo"})

    def test_csrf_blocks_cross_origin_mutations(self):
        with self.assertRaises(HTTPError) as missing:
            self.request('/api/start',{"detector":"demo"},False)
        self.assertEqual(missing.exception.code,403)
        req=Request(self.base+'/api/start',data=b'{"detector":"demo"}',headers={"Content-Type":"application/json","X-LAP-Token":self.engine.token,"Origin":"https://untrusted.example"})
        with self.assertRaises(HTTPError) as external:
            urlopen(req,timeout=5)
        self.assertEqual(external.exception.code,403)

    def test_demo_pause_resume_and_identity_purge(self):
        self.request('/api/start',{"detector":"demo"})
        state=self.wait_status('running')
        self.assertEqual(len(state['people']),18)
        self.request('/api/pause',{})
        self.wait_status('paused')
        before=self.engine.snapshot()['t']
        time.sleep(.3)
        self.assertEqual(self.engine.snapshot()['t'],before)
        self.request('/api/resume',{})
        self.wait_status('running')
        self.request('/api/stop',{})
        state=self.wait_status('stopped')
        self.assertEqual(state['people'],[])
        self.assertEqual(state['events'],[])
        self.assertTrue(state['identityDeleted'])
        self.assertGreater(state['totals']['identities'],0)

    def test_running_configuration_locked_but_rules_dynamic(self):
        self.engine.start({"detector":"demo"})
        self.wait_status('running')
        with self.assertRaises(HTTPError) as locked:
            self.request('/api/config',self.engine.config)
        self.assertEqual(locked.exception.code,400)
        self.request('/api/settings',{"minPeople":12,"radius":2,"dwell":10})
        self.assertEqual(self.engine.runtime_config['minPeople'],12)
        with self.assertRaises(HTTPError):
            self.request('/api/settings',{"width":100})

    def test_zone_metrics_survive_as_aggregates(self):
        config=default_config()
        config['zones']=[{"name":"Acceso","points":[[0,0],[4,0],[4,4],[0,4]],"rule":{"enabled":True,"minPeople":2,"dwell":1}}]
        occupancy=Occupancy(config)
        people=[{"id":"P-1","point":[1,1]},{"id":"P-2","point":[2,2]}]
        occupancy.update(people,0)
        result=occupancy.update(people,1)
        zone=result['zones'][0]
        self.assertTrue(zone['alert'])
        self.assertEqual(zone['seconds'],2)
        self.assertEqual(zone['visits'],2)
        self.assertEqual(zone['peak'],2)

    def test_csv_xlsx_and_pdf_exports_have_real_content(self):
        self.engine.start({"detector":"demo"})
        self.wait_status('running')
        time.sleep(.3)
        self.engine.pause(True)
        snapshot=self.engine.snapshot()
        csv,mime=export(self.engine.config,snapshot,'zones','csv')
        self.assertIn('SIMULACIÓN'.encode(),csv)
        self.assertIn('text/csv',mime)
        xlsx,_=export(self.engine.config,snapshot,'zones','xlsx')
        from openpyxl import load_workbook
        wb=load_workbook(io.BytesIO(xlsx))
        self.assertEqual(wb.active.cell(5,1).value,'Sector')
        self.assertIsInstance(wb.active.cell(6,6).value,(int,float))
        pdf,_=export(self.engine.config,snapshot,'zones','pdf')
        self.assertTrue(pdf.startswith(b'%PDF-'))
        self.assertGreater(len(pdf),1000)

    def test_trajectory_export_is_unavailable_after_session_ends(self):
        state={"session":"test","status":"stopped"}
        with self.assertRaises(ValueError):
            report_data(default_config(),state,'trajectories')

    def test_real_video_capture_processes_three_sources(self):
        import cv2
        import numpy as np
        path=Path(self.directory.name)/'empty.avi'
        writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),10,(320,240))
        self.assertTrue(writer.isOpened())
        for _ in range(20):
            writer.write(np.zeros((240,320,3),dtype=np.uint8))
        writer.release()
        cfg=default_config()
        original=cfg['cameras'][0]
        cfg['cameras']=[{**copy.deepcopy(original),'id':f'C-{i}','source':str(path),'links':[]} for i in range(3)]
        self.engine.configure(cfg)
        self.engine.start({'detector':'hog'})
        self.wait_status('ended',timeout=20)
        self.assertEqual(len(self.engine.source_checks),3)
        self.assertEqual(len(self.engine.frames),3)
        self.assertTrue(all(c['status']=='ended' for c in self.engine.snapshot()['cameras']))
        self.assertEqual(self.request('/api/frame?camera=C-0').status,200)

    def test_plan_image_import_preserves_aspect_and_dxf_maps_geometry(self):
        from PIL import Image
        image=Image.new('RGB',(400,200),'white')
        buffer=io.BytesIO()
        image.save(buffer,format='PNG')
        result=import_plan(buffer.getvalue(),'plan.png',12)
        self.assertEqual(result['height'],6)
        self.assertTrue(result['background'].startswith('data:image/jpeg;base64,'))
        dxf='0\nSECTION\n2\nENTITIES\n0\nLWPOLYLINE\n8\nSALA\n90\n4\n70\n1\n10\n0\n20\n0\n10\n12\n20\n0\n10\n12\n20\n8\n10\n0\n20\n8\n0\nENDSEC\n0\nEOF\n'
        result=import_plan(dxf.encode(),'plan.dxf',12)
        self.assertEqual(result['height'],8)
        self.assertEqual(result['zones'][0]['name'],'SALA')
        self.assertEqual(result['zones'][0]['points'][0],[0,8])


if __name__=='__main__':
    unittest.main()
