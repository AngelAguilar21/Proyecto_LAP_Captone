"""Exercise the actual Engine.run with virtual clocks, synthetic sources and temporary data."""
import copy,sys,tempfile,unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,Mock
import cv2
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import live_server
from replay import ReplayWriter

class Clock:
    def __init__(self): self.now=1000.
    def read(self): return self.now

class VirtualEvent:
    def __init__(self,clock,overshoot=0,callback=None):
        self.clock,self.overshoot,self.callback=clock,overshoot,callback
        self.flag=False; self.waits=[]
    def set(self): self.flag=True
    def clear(self): self.flag=False
    def is_set(self): return self.flag
    def wait(self,timeout=None):
        self.waits.append(timeout)
        if self.flag:return True
        if self.callback:self.callback(len(self.waits),timeout)
        if self.flag:return True
        self.clock.now+=timeout+(self.overshoot if timeout>0 else 0)
        return False

class Capture:
    def __init__(self,clock,fps,frame_count):
        self.clock,self.fps,self.frame_count=clock,fps,frame_count
        self.next_index=0;self.reads=[];self.grabs=0;self.released=False
    def isOpened(self):return True
    def get(self,prop):return self.fps if prop==cv2.CAP_PROP_FPS else self.frame_count
    def set(self,prop,value):
        if prop==cv2.CAP_PROP_POS_FRAMES:self.next_index=int(value)
        return True
    def grab(self):
        if self.next_index>=self.frame_count:return False
        self.next_index+=1;self.grabs+=1;return True
    def read(self):
        if self.next_index>=self.frame_count:return False,None
        self.reads.append((self.next_index,self.clock.now));self.next_index+=1
        return True,np.zeros((48,64,3),dtype=np.uint8)
    def release(self):self.released=True

class RecordingCadenceTests(unittest.TestCase):
    def run_engine(self,n=8,work=.05,overshoot=0,stream=False,control=None,fps=25):
        clock=Clock();samples=[];calls=[];holder={}
        def on_wait(number,timeout):
            if control:control(number,timeout,holder['engine'],clock)
        def detect(frame):
            index=len(calls);calls.append(clock.now)
            clock.now+=work[index] if isinstance(work,list) else work
            return []
        with tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
            root=Path(tmp);stack.enter_context(patch.object(live_server,'ROOT',root))
            engine=live_server.Engine(root/'project.json');holder['engine']=engine
            engine.worker=SimpleNamespace(is_alive=lambda:True)
            engine.stop_event=VirtualEvent(clock,overshoot,on_wait)
            engine.state.update(session='abc12345',status='running')
            cap=Capture(clock,fps,100000 if stream else int(round((n-1)*.2,6)*fps)+1)
            profile={'device':'cpu','tier':'synthetic','weights':'synthetic.pt','imgsz':64,'osnetProviders':['CPUExecutionProvider'],'osnetInterval':8,'hint':None,'missingWeights':None}
            stack.enter_context(patch.object(live_server.hardware,'choose',return_value=profile))
            stack.enter_context(patch.object(live_server,'time',SimpleNamespace(perf_counter=clock.read,monotonic=clock.read,time=lambda:1791230000+clock.now)))
            stack.enter_context(patch.object(engine,'load_detector',return_value=SimpleNamespace(detectar=detect)))
            stack.enter_context(patch('following.reid.OSNetEmbedder',return_value=SimpleNamespace(available=True,name='synthetic',fingerprint='synthetic',dimension=256)))
            physical=stack.enter_context(patch.object(cv2,'VideoCapture',return_value=cap))
            network=stack.enter_context(patch('following.source.NetworkCapture',return_value=cap))
            append=ReplayWriter.append
            def record(writer,sample):
                samples.append(copy.deepcopy(sample));append(writer,sample)
                if stream and len(samples)==n:engine.stop_event.set()
            stack.enter_context(patch.object(ReplayWriter,'append',record))
            config=live_server.default_config();config.update(appearanceMemory=False,identityFinalize=False);config['cameras']=[{'id':'C','source':7 if stream else str(root/'synthetic.mp4'),'offset':0,'pairs':[],'height':3}]
            engine.run(config,{'detector':'yolo','combined':True,'performance':'precise'})
            self.assertNotEqual(engine.state['status'],'error',engine.state.get('error'))
            self.assertTrue(cap.released);self.assertFalse(engine.resources.busy())
            self.assertEqual(network.call_count,1 if stream else 0)
            self.assertEqual(physical.call_count,0 if stream else 1)
            return SimpleNamespace(samples=samples,starts=[c-1000 for c in calls],waits=engine.stop_event.waits,reads=cap.reads,grabs=cap.grabs,state=copy.deepcopy(engine.state),generation=engine._resume_generation)

    def test_wait_overshoot_is_deducted_from_next_deadline(self):
        r=self.run_engine(n=20,overshoot=.007)
        self.assertEqual([s['t'] for s in r.samples],[round(i*.2,6) for i in range(20)])
        for i,start in enumerate(r.starts[1:],1):self.assertAlmostEqual(start,i*.2+.007,places=8)
        self.assertAlmostEqual(r.waits[0],.15);self.assertAlmostEqual(r.waits[1],.143)

    def test_work_overrun_recovers_without_skipping_observations(self):
        r=self.run_engine(n=5,work=[.31,.31,.05,.05,.05])
        for a,b in zip(r.starts,[0,.31,.62,.67,.8]):self.assertAlmostEqual(a,b)
        self.assertEqual([s['t'] for s in r.samples],[0,.2,.4,.6,.8])
        self.assertEqual([index for index,t in r.reads],[0,5,10,15,20])
        self.assertEqual(r.waits[:3],[0,0,0])

    def test_sustained_overload_preserves_all_samples_and_reports_lateness(self):
        r=self.run_engine(n=20,work=.27)
        self.assertEqual(len(r.samples),20)
        self.assertEqual([s['t'] for s in r.samples],[round(i*.2,6) for i in range(20)])
        self.assertAlmostEqual(r.starts[-1],19*.27)
        self.assertTrue(all(w==0 for w in r.waits))
        self.assertGreater(r.starts[-1]-r.samples[-1]['t'],1)

    def test_pause_resume_reanchors_and_preserves_timeline(self):
        def control(number,timeout,engine,clock):
            if number==1:engine.pause(True)
            if number==2:clock.now+=5;engine.pause(False)
        r=self.run_engine(n=5,control=control)
        self.assertGreater(r.starts[1],5)
        self.assertAlmostEqual(r.starts[2]-r.starts[1],.2)
        self.assertEqual([s['t'] for s in r.samples],[0,.2,.4,.6,.8])
        self.assertEqual(r.generation,1)

    def test_pause_resume_pulse_between_cycles_is_not_missed(self):
        def control(number,timeout,engine,clock):
            if number==1:engine.pause(True);clock.now+=.075;engine.pause(False)
        r=self.run_engine(n=4,overshoot=.007,control=control)
        self.assertAlmostEqual(r.starts[1],.282)
        self.assertAlmostEqual(r.starts[2]-r.starts[1],.207)
        self.assertEqual(r.generation,1)

    def test_redundant_resume_does_not_reset_deadlines(self):
        r=self.run_engine(n=10,overshoot=.007,control=lambda n,t,e,c:e.pause(False))
        self.assertEqual(r.generation,0)
        self.assertAlmostEqual(r.starts[-1],1.807)

    def test_stop_during_wait_prevents_next_read_and_closes_resources(self):
        r=self.run_engine(n=10,control=lambda n,t,e,c:e.stop())
        self.assertEqual(len(r.samples),1);self.assertEqual(len(r.reads),1)
        self.assertEqual(r.state['status'],'stopped')

    def test_stop_while_paused_closes_without_advancing_timeline(self):
        def control(number,timeout,engine,clock):
            if number==1:engine.pause(True)
            if number==2:engine.stop()
        r=self.run_engine(n=10,control=control)
        self.assertEqual([s['t'] for s in r.samples],[0]);self.assertEqual(r.state['status'],'stopped')

    def test_end_of_file_ends_without_extra_published_sample(self):
        r=self.run_engine(n=7)
        self.assertEqual(len(r.samples),7);self.assertEqual(r.samples[-1]['t'],1.2)
        self.assertEqual(r.state['status'],'ended');self.assertEqual(r.state['cameras'][0]['status'],'ended')

    def test_recording_source_indices_ignore_wall_clock_overload(self):
        r=self.run_engine(n=10,work=.27,fps=59.94005994005994)
        self.assertEqual([index for index,t in r.reads],[int(round(i*.2,6)*59.94005994005994) for i in range(10)])

    def test_live_keeps_relative_wait_wall_clock_and_no_grabs(self):
        r=self.run_engine(n=8,stream=True,overshoot=.007)
        for i,s in enumerate(r.samples):self.assertAlmostEqual(s['t'],i*.207)
        self.assertEqual(r.grabs,0);self.assertEqual([i for i,t in r.reads],list(range(8)))
        self.assertAlmostEqual(r.waits[0],.15)

    def test_live_resume_keeps_elapsed_wall_time_without_catchup(self):
        def control(number,timeout,engine,clock):
            if number==1:engine.pause(True);clock.now+=2;engine.pause(False)
        r=self.run_engine(n=4,stream=True,overshoot=.007,control=control)
        self.assertGreater(r.samples[1]['t'],2)
        self.assertAlmostEqual(r.starts[2]-r.starts[1],.207)

if __name__=='__main__':unittest.main()
