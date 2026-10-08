import json,sys,tempfile,unittest,threading,urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from live_server import Engine,Handler,default_config
from live_core import validate_config
from replay import ReplayWriter,manifest,directory,public,get,recover_interrupted,_personas_unicas_confirmadas
from urllib.parse import urlparse
from io import BytesIO
from unittest.mock import patch
import cv2
import numpy as np
from following.zone_counts import CountingAnalytics
from types import SimpleNamespace

class WorkspaceTests(unittest.TestCase):
 def test_static_json_is_served_as_bytes_and_api_objects_are_encoded(self):
  from unittest.mock import Mock
  for body in [b'{"floor":3}', {'floor':3}]:
   response=Mock();response.wfile=BytesIO()
   Handler.send_data(response,200,body,'application/json')
   self.assertEqual(json.loads(response.wfile.getvalue()),{'floor':3})
   response.send_header.assert_any_call('Content-Length',str(len(response.wfile.getvalue())))

 def test_interrupted_replay_keeps_last_valid_sample(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);writer=ReplayWriter(root,'abc12345','tracking',[],{})
   writer.append({'t':3,'cameras':[]});writer.output.close()
   recover_interrupted(root)
   self.assertEqual(manifest(root,'abc12345')['status'],'error')
   self.assertEqual(manifest(root,'abc12345')['end'],3)

 def test_video_ranges_allow_seeking_without_loading_whole_file(self):
  class Response:
   def __init__(self,header):
    self.headers={'Range':header};self.wfile=BytesIO();self.result={}
    self.server=SimpleNamespace(engine=SimpleNamespace(lock=threading.RLock(),project_id=None,config={}))
   def send_response(self,status):self.status=status
   def send_header(self,key,value):self.result[key]=value
   def end_headers(self):pass
   def send_data(self,status,data):self.status=status;self.data=data
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'video.mp4').write_bytes(b'0123456789')
   w=ReplayWriter(root,'abc12345','tracking',[{'id':'C','source':'video.mp4'}],{});w.finish('ended')
   for header,expected in [('bytes=2-5',b'2345'),('bytes=-3',b'789')]:
    response=Response(header);get(response,urlparse('/api/replay/video?session=abc12345&camera=C'),root)
    self.assertEqual(response.status,206);self.assertEqual(response.wfile.getvalue(),expected)
    self.assertEqual(int(response.result['Content-Length']),len(expected))
   response=Response('bytes=20-30');get(response,urlparse('/api/replay/video?session=abc12345&camera=C'),root);self.assertEqual(response.status,416)

 def test_independent_cameras_finish_each_video_and_isolate_test_storage(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);cfg=default_config();cfg['cameras']=[]
   for cid,frames in [('C',6),('D',16)]:
    path=root/f'{cid}.avi';writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),10,(320,240))
    self.assertTrue(writer.isOpened())
    for _ in range(frames):writer.write(np.zeros((240,320,3),dtype=np.uint8))
    writer.release();cfg['cameras'].append({'id':cid,'source':str(path),'x':1,'y':1,'pairs':[[0,0,0,0],[1,0,12,0],[1,1,12,8],[0,1,0,8]],'detectionZone':[[0,0],[1,0],[1,1],[0,1]],'height':4,'illustrative':False,'links':[],'offset':0})
   cfg['workArea']=[[0,0],[12,0],[12,8],[0,8]]
   engine=Engine(root/'config.json');engine.configure(cfg)
   fake_detector=SimpleNamespace(detectar=lambda frame:[SimpleNamespace(x=100,y=80,confianza=.9)])
   with patch.object(engine,'load_detector',return_value=fake_detector):
    engine.start({'detector':'yolo','cameraIds':['C','D'],'requireUnified':False,'performance':'precise'});engine.worker.join(15)
    self.assertFalse(engine.worker.is_alive());self.assertEqual(engine.state['status'],'ended')
   self.assertGreaterEqual(engine.state['t'],1.4)
   self.assertTrue((root/'data'/'replays'/engine.state['session']/'manifest.json').is_file())
   samples=[json.loads(line) for line in (root/'data'/'replays'/engine.state['session']/'samples.jsonl').read_text().splitlines()]
   self.assertTrue(any(view['people'] for row in samples for view in row['cameras']))
   self.assertTrue(all(p['point'] is not None for row in samples for view in row['cameras'] for p in view['people']))

 def test_replay_survives_new_reader_and_hides_paths(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);w=ReplayWriter(root,'abc12345','tracking',[{'id':'C','source':'private.mp4'}],{})
   w.append({'t':1,'cameras':[{'id':'C','people':[]}]});w.finish('ended')
   m=manifest(root,'abc12345');self.assertEqual(m['end'],1);self.assertEqual(m['status'],'ended');self.assertNotIn('source',public(m)['cameras'][0])
   with self.assertRaises(ValueError):directory(root,'../config')

 def test_global_report_counts_one_person_once_across_cameras(self):
  sample={'cameras':[
   {'id':'A','people':[{'id':'P00001','confirmed':True},{'id':'P00002','confirmed':True},{'id':'T00003','confirmed':False}]},
   {'id':'B','people':[{'id':'P00001','confirmed':True},{'id':'P00004','confirmed':True,'duplicate':True}]},
  ]}
  self.assertEqual(_personas_unicas_confirmadas(sample),2)
 def test_switch_floor_preserves_other_camera_coordinates(self):
  cfg=default_config();cfg['cameras']=[];cfg['plans']={'custom':{'width':12,'height':8,'background':'','zones':[],'workArea':None}}
  cfg.update(width=1500,height=2200,planId='lap-3',workArea=None,mapAsset='/maps/lap/3.json')
  cfg['cameras']=[{'id':'C','source':'test.mp4','x':6,'y':4,'offset':0,'pairs':[],'links':[],'planId':'custom'}]
  validate_config(cfg)
  cfg['cameras'][0]['x']=100
  with self.assertRaises(ValueError):validate_config(cfg)
 def test_common_camera_mask_limits_counting(self):
  cfg={'interval':1,'cameraZone':[[0,0],[.5,0],[.5,1],[0,1]],'zones':[{'id':'z','name':'Zona','points':[[0,0],[1,0],[1,1],[0,1]],'threshold':2,'dwell':0}]}
  a=CountingAnalytics(cfg);points=a.update([SimpleNamespace(x=20,y=20),SimpleNamespace(x=80,y=20)],100,100,0)
  self.assertEqual(len(points),1);self.assertEqual(a.snapshot()['count'],1)
 def test_zone_save_survives_engine_restart(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'config.json';engine=Engine(path);cfg=default_config();cfg['cameras']=[{'id':'C','source':'test.mp4','x':1,'y':1,'offset':0,'pairs':[],'links':[],'detectionZone':[[.1,.2],[.8,.2],[.9,.9],[.1,.9]]}]
   engine.configure(cfg);self.assertEqual(Engine(path).config['cameras'][0]['detectionZone'],cfg['cameras'][0]['detectionZone'])
if __name__=='__main__':unittest.main()
