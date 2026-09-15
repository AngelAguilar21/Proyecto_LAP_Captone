import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'src'))
from following.line_counter import LineCounter
from live_core import validate_config
from live_server import default_config
from live_reports import report_data

class AccessTests(unittest.TestCase):
 def line(self):return {'id':'shop','name':'Tienda prueba','a':[.2,.5],'b':[.8,.5],'entrySide':1,'bands':{'negative':[[.2,.3],[.8,.3]],'positive':[[.2,.7],[.8,.7]]}}
 def test_requires_observations_in_both_regions_and_logs_events(self):
  counter=LineCounter([self.line()])
  def at(x,y,t):return counter.update([{'id':'p','pixel':[x,y]}],t)[0]
  at(.5,.1,0)
  self.assertEqual(at(.5,.6,.2)['entries'],0)
  at(.5,.4,2.5)
  result=at(.5,.6,2.7)
  self.assertEqual(result['entries'],1)
  self.assertEqual(result['events'],[{'t':2.7,'direction':'entries'}])
  self.assertEqual(result['hours']['0']['entries'],1)
  self.assertEqual(at(.5,.4,4)['exits'],1)
  counter.update([],7)
  self.assertEqual(at(.5,.6,8)['entries'],1)
 def test_outside_segment_does_not_count(self):
  counter=LineCounter([self.line()])
  counter.update([{'id':'p','pixel':[.9,.4]}],0)
  self.assertEqual(counter.update([{'id':'p','pixel':[.9,.6]}],.2)[0]['entries'],0)
 def test_invalid_confirmation_side_is_rejected(self):
  cfg=default_config();cfg['cameras'][0]['countLines']=[self.line()]
  validate_config(cfg)
  cfg['cameras'][0]['countLines'][0]['bands']['positive']=[[.2,.3],[.8,.3]]
  with self.assertRaisesRegex(ValueError,'opuestos'):validate_config(cfg)
 def test_access_export_preserves_local_and_relative_time(self):
  cfg=default_config();cid=cfg['cameras'][0]['id']
  state={'session':'abc','status':'ended','t':3,'cameraAnalytics':{cid:{'crossings':[{'name':'Local','events':[{'t':2.7,'direction':'entries'}]}]}}}
  rows=report_data(cfg,state,'access-events')['rows']
  self.assertEqual(rows[0][1:],['Local','Entrada',2.7])
if __name__=='__main__':unittest.main()
