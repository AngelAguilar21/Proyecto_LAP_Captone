import copy
import json
from pathlib import Path
import sys
import tempfile
import threading
import queue
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from counting.analytics import CountingAnalytics, validate
from counting.engine import CountingEngine, defaults
from counting.source import VideoSource
from counting.storage import CountStore


def points(n):
    return [SimpleNamespace(x=20+i, y=30, confianza=.9) for i in range(n)]


class AnalyticsTests(unittest.TestCase):
    def config(self):
        c = defaults("video.mp4")
        c["zones"][0].update(threshold=2, dwell=2)
        return c

    def test_overlap_is_not_summed_and_counts_can_repeat_without_ids(self):
        c = self.config()
        c["zones"].append({**copy.deepcopy(c["zones"][0]), "id": "second"})
        a = CountingAnalytics(c)
        for t in (0, 1, 2):
            a.update(points(3), 100, 100, t)
        s = a.snapshot()
        self.assertEqual(s["count"], 3)
        self.assertEqual([z["count"] for z in s["zones"]], [3, 3])
        self.assertEqual(s["personSeconds"], 6)
        self.assertAlmostEqual(sum(map(sum, s["heat"])), 6)

    def test_episode_confirmed_once_and_new_episode_after_clearing(self):
        a = CountingAnalytics(self.config())
        for t in range(4):
            a.update(points(3), 100, 100, t)
        self.assertEqual(len(a.episodes), 1)
        self.assertEqual(a.episodes[0]["confirmed"], 2)
        a.update([], 100, 100, 4)
        self.assertEqual(a.episodes[0]["end"], 4)
        for t in range(5, 8):
            a.update(points(2), 100, 100, t)
        self.assertEqual(len(a.episodes), 2)
        a.finish(8, "fin del video")
        self.assertEqual(a.episodes[1]["end"], 8)
        self.assertFalse(a.snapshot()["zones"][0]["alert"])

    def test_gap_does_not_confirm_persistence_or_add_unobserved_time(self):
        a = CountingAnalytics(self.config())
        a.update(points(3), 100, 100, 0)
        a.update(points(3), 100, 100, 30)
        self.assertEqual(a.episodes, [])
        self.assertEqual(a.observed_seconds, 0)
        self.assertEqual(a.person_seconds, 0)

    def test_invalid_and_outside_points_are_excluded(self):
        c = self.config()
        c["zones"][0]["points"] = [[0,0],[.5,0],[.5,1],[0,1]]
        a = CountingAnalytics(c)
        detections = points(1)+[SimpleNamespace(x=80,y=40), SimpleNamespace(x=-1,y=30), SimpleNamespace(x=float('nan'),y=10)]
        a.update(detections, 100, 100, 0)
        self.assertEqual(a.count, 1)

    def test_validation_rejects_bad_geometry_and_numbers(self):
        for key, value in [("interval", 0), ("confidence", float('nan')), ("maxSide", True)]:
            c = self.config();c[key] = value
            with self.assertRaises(ValueError): validate(c)
        c=self.config();c["zones"][0]["points"]=[[0,0],[1,1],[0,1],[1,0]]
        with self.assertRaises(ValueError): validate(c)
        c=self.config();c["zones"].append(copy.deepcopy(c["zones"][0]))
        with self.assertRaises(ValueError): validate(c)

    def test_zero_duration_alert_and_final_partial_interval(self):
        c=self.config();c["zones"][0]["dwell"]=0
        a=CountingAnalytics(c);a.update(points(2),100,100,0);a.finish(.4,"fin")
        self.assertEqual(len(a.episodes),1)
        self.assertAlmostEqual(a.person_seconds,.8)

    def test_episode_peak_includes_pending_confirmation(self):
        a = CountingAnalytics(self.config())
        for t, count in enumerate((8, 3, 2, 0)):
            a.update(points(count), 100, 100, t)
        self.assertEqual(a.episodes[0]['peak'], 8)
        self.assertEqual(a.episodes[0]['end'], 3)

    def test_last_count_is_distinct_from_peak_and_peak_time(self):
        a = CountingAnalytics(self.config())
        for t, count in enumerate((12, 38, 28)):
            a.update(points(count), 100, 100, t)
        state = a.snapshot()
        self.assertEqual(state['count'], 28)
        self.assertEqual(state['peak'], 38)
        self.assertEqual(state['peakAt'], 1)
        self.assertEqual(state['zones'][0]['peakAt'], 1)

    def test_recording_time_requires_explicit_timezone(self):
        c = self.config()
        c['recordedAt'] = '2026-09-14T09:00:00-05:00'
        self.assertEqual(validate(c)['recordedAt'], c['recordedAt'])
        c['recordedAt'] = '2026-09-14T09:00:00'
        with self.assertRaises(ValueError): validate(c)


class VideoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.video = self.path/"input.avi"
        writer = cv2.VideoWriter(str(self.video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (100,100))
        for i in range(25):
            writer.write(np.full((100,100,3), i*8, np.uint8))
        writer.release()

    def tearDown(self): self.temp.cleanup()

    def test_sampling_uses_source_time(self):
        video=VideoSource(str(self.video), self.path)
        try:
            first,t=video.read(0);second,t2=video.read(1)
            self.assertEqual(t,0);self.assertEqual(t2,1)
            self.assertGreater(second.mean(),first.mean()+60)
            self.assertEqual(video.duration,2.5)
            self.assertIsNone(video.read(3)[0])
        finally: video.close()

    def test_restart_marks_unfinished_session_and_keeps_samples(self):
        store = CountStore(self.path/'counting.sqlite')
        store.save({'session':'unfinished','created':'2026-01-01','status':'running','t':2},
                   {'t':2,'count':4,'zones':[]})
        store.recover_interrupted()
        report = store.report('unfinished')
        self.assertEqual(report['status'], 'error')
        self.assertEqual(report['series'][0]['count'], 4)

    def test_engine_persists_complete_run_and_csv(self):
        detector = SimpleNamespace(umbral=.5, detectar=lambda frame: points(3))
        engine=CountingEngine(ROOT,self.path/"config.json",lambda:detector)
        c=defaults(str(self.video));c["zones"][0].update(threshold=2,dwell=1)
        c['recordedAt'] = '2026-09-14T09:00:00-05:00'
        engine.start(c);engine.worker.join(10)
        self.assertFalse(engine.active())
        s=engine.snapshot()
        self.assertEqual(s["status"],"ended",s.get('error'))
        self.assertEqual(s["samples"],3)
        self.assertEqual(s["count"],3)
        self.assertAlmostEqual(s["personSeconds"],7.5)
        self.assertEqual(len(s["episodes"]),1)
        report=engine.store.report(s["session"])
        self.assertNotIn('points',report)
        self.assertEqual(len(report["series"]),3)
        self.assertIn('episodio',engine.store.csv(s['session']).decode('utf-8-sig'))
        csv = engine.store.csv(s['session']).decode('utf-8-sig')
        self.assertIn('2026-09-14T09:00:01-05:00', csv)
        self.assertIn('Máximo de personas', csv)
        self.assertNotIn('pers·s', csv)
        reopened=CountStore(self.path/"counting.sqlite")
        self.assertEqual(reopened.history()[0]["session"],s["session"])

    def test_pause_stop_and_configuration_lock(self):
        def detect(frame):
            time.sleep(.12)
            return points(1)
        e=CountingEngine(ROOT,self.path/"config.json",lambda:SimpleNamespace(detectar=detect))
        c=defaults(str(self.video));c["interval"]=.2
        e.start(c)
        try:
            deadline=time.monotonic()+5
            while e.snapshot()['status']=='starting' and time.monotonic()<deadline: time.sleep(.02)
            e.pause(True)
            with self.assertRaises(ValueError): e.configure(c)
            time.sleep(.3);before=e.snapshot()['samples'];time.sleep(.2)
            self.assertEqual(before,e.snapshot()['samples'])
            e.pause(False)
        finally:
            e.stop();e.worker.join(5)
        self.assertEqual(e.snapshot()['status'],'stopped')

    def test_http_preview_validation_security_and_report(self):
        sys.path.insert(0, str(ROOT))
        from live_server import Engine, Handler, ThreadingHTTPServer
        parent = Engine(self.path/'live.json')
        parent.counting = CountingEngine(ROOT, self.path/'count.json',
            lambda: SimpleNamespace(detectar=lambda frame: points(2)))
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.engine = parent
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        def request(path, data=None, token=True):
            headers = {'Content-Type': 'application/json'}
            if token: headers['X-LAP-Token'] = parent.token
            return urlopen(Request(f'http://127.0.0.1:{server.server_port}/api/counting/{path}',
                data=json.dumps(data).encode() if data is not None else None, headers=headers), timeout=10)
        try:
            with request('config') as response:
                self.assertEqual(json.load(response)['token'], parent.token)
            with self.assertRaises(HTTPError) as blocked:
                request('config', defaults(str(self.video)), token=False)
            self.assertEqual(blocked.exception.code, 403)
            with self.assertRaises(HTTPError) as invalid:
                request('config', {**defaults(str(self.video)), 'interval': 0})
            self.assertEqual(invalid.exception.code, 400)
            with request('preview', {'source': str(self.video), 'seconds': 1}) as response:
                self.assertEqual(json.load(response)['t'], 1)
            with request('frame') as response:
                self.assertTrue(response.read().startswith(b'\xff\xd8'))
            with request('start', defaults(str(self.video))) as response:
                self.assertTrue(json.load(response)['ok'])
            parent.counting.worker.join(10)
            with request('state') as response:
                state = json.load(response)
            self.assertEqual(state['status'], 'ended')
            with request(f"report?session={state['session']}&format=csv") as response:
                self.assertIn('Unión de zonas', response.read().decode('utf-8-sig'))
            with request('history') as response:
                self.assertEqual(len(json.load(response)), 1)
        finally:
            parent.counting.stop()
            if parent.counting.worker: parent.counting.worker.join(10)
            server.shutdown(); server.server_close(); worker.join(2)

    def test_stream_keeps_latest_frame_and_reports_disconnect(self):
        frames = queue.Queue()
        class Capture:
            def isOpened(self): return True
            def set(self, *args): return True
            def get(self, prop): return 25
            def release(self): pass
            def read(self): return frames.get(timeout=2)
        with patch('counting.source.cv2.VideoCapture', return_value=Capture()):
            source = VideoSource('rtsp://example.test/camera', self.path)
            try:
                for n in (1, 2, 3): frames.put((True, np.full((2,2,3), n, np.uint8)))
                deadline = time.monotonic()+2
                while time.monotonic()<deadline:
                    with source.condition:
                        if source.latest is not None and source.latest[0].mean()==3: break
                    time.sleep(.01)
                self.assertEqual(source.read()[0].mean(), 3)
                frames.put((False, None))
                with self.assertRaisesRegex(ValueError, 'interrumpió'):
                    source.read()
            finally: source.close()


if __name__ == '__main__': unittest.main()
