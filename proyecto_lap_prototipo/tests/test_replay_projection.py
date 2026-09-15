import sys,copy,unittest
from pathlib import Path
sys.path.insert(0,str(Path('proyecto_lap_prototipo').resolve()))
sys.path.insert(0,str(Path('proyecto_lap_prototipo/src').resolve()))
from live_server import default_config
from replay_projection import current_projection
class ProjectionTests(unittest.TestCase):
 def test_relocation_rebuilds_heat_without_mutating_history(self):
  c=default_config();c['planId']='custom';c['cameras']=[{'id':'C','source':'x','pairs':[[0,0,10,10],[1,0,20,10],[1,1,20,20],[0,1,10,20]]}]
  old=copy.deepcopy(c);c['cameras'][0]['pairs']=[[a,b,x+30,y+20] for a,b,x,y in c['cameras'][0]['pairs']]
  samples=[{'t':t,'cameras':[{'id':'C','people':[{'id':'P1','pixel':[.5,.5],'point':[15,15]}],'analysis':{}}]} for t in [0,1]]
  result=current_projection({'config':old},samples,c)
  self.assertAlmostEqual(result[-1]['cameras'][0]['people'][0]['point'][0],45)
  self.assertEqual(samples[-1]['cameras'][0]['people'][0]['point'],[15,15])
  self.assertTrue(all(cell['x']>30 for cell in result[-1]['analytics']['heat']))
 def test_lap_work_area_does_not_discard_relocated_camera(self):
  from spatial_scope import accepts
  self.assertTrue(accepts({}, {'mapAsset':'/maps/lap/3.json','workArea':[[0,0],[1,0],[1,1]]},.5,.5,[50,50]))
  self.assertFalse(accepts({}, {'workArea':[[0,0],[1,0],[1,1]]},.5,.5,[50,50]))
 def test_removed_camera_has_no_old_positions(self):
  c=default_config();c['cameras']=[]
  result=current_projection({'config':c},[{'t':0,'cameras':[{'id':'gone','people':[{'point':[1,1]}]}]}],c)
  self.assertEqual(result[0]['cameras'][0]['people'],[])
if __name__=='__main__':unittest.main()
