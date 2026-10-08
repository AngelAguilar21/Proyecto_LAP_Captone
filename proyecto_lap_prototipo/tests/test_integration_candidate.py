"""Integrated candidate checks using temporary stores and loopback HTTP only."""
import copy
from datetime import datetime
import http.client
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import live_server
import notifier
from automation_backups import ProjectBackups
from automation import LIMA
from automation_artifacts import verify_pdf
from automation_cleanup import RetentionCleanup
from automation_escalation import AlertEscalation
from automation_reports import ScheduledReports, eligible
from replay import ReplayWriter
from shutdown_control import ManagedHTTPServer, quiescent


class CandidateIntegrationTests(unittest.TestCase):
    # The normal Python suite needs no ignored frontend build. The explicit
    # post-build smoke sets this to the built dist path to check those assets.
    frontend_root = None

    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="aerotrack-candidate-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.enterContext(patch.object(live_server, "ROOT", self.root))
        self.enterContext(patch.object(live_server, "CONFIG_PATH", self.root / "config/live.local.json"))
        self.smtp = self.enterContext(patch.object(notifier, "_send", side_effect=AssertionError("SMTP forbidden")))
        self.addCleanup(self.smtp.assert_not_called)

    def saved_session(self, *, totals=True, project=True):
        engine = live_server.Engine()
        config = copy.deepcopy(engine.config)
        config.update(airport="Recorded site", floor="Recorded floor", testRun=True)
        engine.configure(config)
        writer = ReplayWriter(self.root, "abcd1234", "unified", [], config,
                              engine.project_id if project else None)
        writer.append({"t": 10, "cameras": [{"id": "synthetic", "people": [
            {"id": "private-temporary-id", "x": 1, "y": 2}, {"id": "another-id"}]}]})
        writer.meta["reportAnalytics"] = {"zones": []}
        if totals:
            writer.meta["totals"] = {"meanObservedSeconds": 5, "alerts": 0}
        writer.finish("ended")
        changed = copy.deepcopy(config)
        changed.update(airport="Current editable site", floor="Current floor", testRun=False)
        engine.configure(changed)
        return engine

    def test_restart_restores_report_evidence_with_its_historical_configuration(self):
        self.saved_session()
        restored = live_server.Engine()
        capture = restored.automation_snapshot()
        self.assertTrue(eligible(capture))
        self.assertEqual(capture["state"]["series"], [{"t": 10, "count": 2}])
        self.assertEqual(capture["state"]["totals"], {"meanObservedSeconds": 5, "alerts": 0})
        self.assertEqual(capture["config"]["airport"], "Recorded site")
        self.assertTrue(capture["state"]["testRun"])
        self.assertEqual(restored.config["airport"], "Current editable site")
        self.assertEqual(restored.snapshot()["people"], [])
        self.assertNotIn("private-temporary-id", json.dumps(capture))
        self.assertNotIn("another-id", json.dumps(capture))
        task = ScheduledReports(restored, restored.automation.store)
        now = datetime(2026, 10, 1, 20, tzinfo=LIMA)
        self.assertEqual(task(now, {"enabled": True, "time": "20:00"}), "succeeded")
        target = self.root / "data/reports" / restored.project_id / "business-2026-10-01.pdf"
        self.assertTrue(verify_pdf(target.read_bytes()))
        self.assertEqual(task(now, {"enabled": True, "time": "20:00"}), "already_done")

    def test_restored_configuration_is_not_reused_for_a_new_session(self):
        self.saved_session()
        restored = live_server.Engine()
        restored.state["session"] = "deadbeef"
        self.assertEqual(restored.automation_snapshot()["config"]["airport"], "Current editable site")

    def test_missing_totals_do_not_invent_reportable_evidence(self):
        self.saved_session(totals=False)
        restored = live_server.Engine()
        self.assertFalse(eligible(restored.automation_snapshot()))
        self.assertEqual(ScheduledReports(restored, restored.automation.store)(
            datetime(2026, 10, 1, 20, tzinfo=LIMA), {"enabled": True, "time": "20:00"}), "no_data")

    def test_malformed_saved_samples_leave_summary_without_reportable_evidence(self):
        self.saved_session()
        path = self.root / "data/replays/abcd1234/samples.jsonl"
        valid = path.read_text(encoding="utf-8")
        for content in ("[]\n", valid + "{broken\n", '{"t":10}\n', '{"t":true,"cameras":[]}\n',
                        '{"t":NaN,"cameras":[]}\n', '{"t":10,"cameras":[{"people":3}]}\n',
                        '{"t":10,"cameras":[{"people":[null]}]}\n',
                        '{"t":10,"cameras":[{"people":[3]}]}\n', ""):
            with self.subTest(content=content):
                path.write_text(content, encoding="utf-8")
                restored = live_server.Engine()
                self.assertEqual(restored.state["session"], "abcd1234")
                self.assertFalse(eligible(restored.automation_snapshot()))
                self.assertEqual(ScheduledReports(restored, restored.automation.store)(
                    datetime(2026, 10, 1, 20, tzinfo=LIMA), {"enabled": True, "time": "20:00"}), "no_data")
        path.unlink()
        restored = live_server.Engine()
        self.assertEqual(restored.state["session"], "abcd1234")
        self.assertFalse(eligible(restored.automation_snapshot()))
        self.assertFalse((self.root / "data/reports").exists())

    def test_public_report_snapshot_keeps_historical_configuration(self):
        self.saved_session()
        server = ManagedHTTPServer(("127.0.0.1", 0), live_server.Handler)
        server.engine = live_server.Engine()
        worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01), daemon=True)
        worker.start()
        connection = http.client.HTTPConnection(*server.server_address, timeout=5)
        try:
            connection.request("GET", "/api/report/session")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            report = json.loads(response.read())
            self.assertEqual(report["config"]["airport"], "Recorded site")
            self.assertEqual(report["state"]["series"], [{"t": 10, "count": 2}])
            self.assertEqual(server.engine.config["airport"], "Current editable site")
        finally:
            connection.close()
            server.shutdown()
            worker.join(5)
            server.server_close()
            self.assertFalse(worker.is_alive())

    def test_legacy_unscoped_replay_is_not_adopted_as_project_report_evidence(self):
        self.saved_session(project=False)
        restored = live_server.Engine()
        self.assertFalse(eligible(restored.automation_snapshot()))

    def test_project_change_clears_restored_report_configuration(self):
        self.saved_session()
        restored = live_server.Engine()
        original = restored.project_id
        restored.new_project("Other project")
        capture = restored.automation_snapshot()
        self.assertNotEqual(capture["projectId"], original)
        self.assertEqual(capture["config"]["airport"], "Other project")
        self.assertFalse(eligible(capture))
        restored.open_project(original)
        self.assertTrue(eligible(restored.automation_snapshot()))

    def test_main_http_auth_projects_calibration_preview_and_shutdown_are_isolated(self):
        if self.frontend_root is None:
            dist = self.root / "dashboard/dist"
            (dist / "assets").mkdir(parents=True)
            (dist / "index.html").write_text('<html><script src="/assets/synthetic.js"></script></html>', encoding="utf-8")
            (dist / "assets/synthetic.js").write_text("/* synthetic routing fixture */", encoding="utf-8")
        else:
            shutil.copytree(self.frontend_root, self.root / "dashboard/dist")
        server_ready = threading.Event()
        servers, errors = [], []
        stopped = False
        source = self.root / "synthetic.mp4"
        source.write_bytes(b"synthetic source; VideoCapture is replaced")
        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        capture = Mock()
        capture.isOpened.return_value = True
        capture.read.side_effect = lambda: (True, frame.copy())
        capture.get.side_effect = lambda prop: {cv2.CAP_PROP_FPS: 25, cv2.CAP_PROP_FRAME_COUNT: 100,
                                               cv2.CAP_PROP_POS_MSEC: 40}.get(prop, 0)

        def open_synthetic(path, *args):
            self.assertEqual(Path(path), source)
            self.assertEqual(args, ())
            return capture

        def server_factory(address, handler, **kwargs):
            self.assertEqual(address, ("127.0.0.1", 0))
            server = ManagedHTTPServer(address, handler, **kwargs)
            serve = server.serve_forever
            def serve_ready():
                server_ready.set()
                serve(poll_interval=.01)
            server.serve_forever = serve_ready
            servers.append(server)
            return server

        def run():
            try:
                live_server.main()
            except BaseException as exc:
                errors.append(exc)
                server_ready.set()

        guarded_tasks = [self.enterContext(patch.object(task, "__call__",
            side_effect=AssertionError("Disabled automation was invoked")))
            for task in (ScheduledReports, ProjectBackups, AlertEscalation, RetentionCleanup)]
        self.enterContext(patch.object(live_server, "ManagedHTTPServer", side_effect=server_factory))
        warmup = self.enterContext(patch.object(live_server.Engine, "warm_detector_async"))
        detector = self.enterContext(patch.object(live_server.Engine, "load_detector",
                                                side_effect=AssertionError("Inference forbidden")))
        video = self.enterContext(patch.object(cv2, "VideoCapture", side_effect=open_synthetic))
        self.enterContext(patch.object(sys, "argv", ["live_server.py", "--port", "0"]))
        worker = threading.Thread(target=run, name="candidate-smoke", daemon=True)
        worker.start()
        session, token = None, None

        def request(path, body=None):
            headers = {"Content-Type": "application/json"}
            if token:
                headers["X-LAP-Token"] = token
            if session:
                headers["X-LAP-Session"] = session
            connection = http.client.HTTPConnection(*servers[0].server_address, timeout=5)
            try:
                connection.request("GET" if body is None else "POST", path,
                                   json.dumps(body) if body is not None else None, headers)
                response = connection.getresponse()
                content = response.read()
                return response.status, (json.loads(content) if "application/json" in response.getheader("Content-Type", "") else content)
            finally:
                connection.close()

        try:
            self.assertTrue(server_ready.wait(10), "Isolated startup did not reach HTTP serve")
            self.assertEqual(errors, [])
            server = servers[0]
            engine = server.engine
            self.assertEqual(set(engine.automation.tasks), {"reports", "backups", "escalation", "cleanup"})
            for name, kind in (("reports", ScheduledReports), ("backups", ProjectBackups),
                               ("escalation", AlertEscalation), ("cleanup", RetentionCleanup)):
                self.assertIsInstance(engine.automation.tasks[name], kind)
            status, html = request("/")
            self.assertEqual(status, 200)
            self.assertEqual(html, (self.root / "dashboard/dist/index.html").read_bytes())
            asset = re.search(rb'src="([^\"]+\.js)"', html)
            self.assertIsNotNone(asset)
            self.assertEqual(request(asset.group(1).decode())[0], 200)
            status, config_response = request("/api/config")
            self.assertEqual(status, 200)
            token = config_response["token"]
            self.assertFalse(request("/api/auth")[1]["configurado"])
            credentials = {"usuario": "synthetic-operator", "clave": "synthetic-password"}
            self.assertEqual(request("/api/auth", {"accion": "crear", **credentials})[0], 200)
            status, login = request("/api/auth", {"accion": "login", **credentials})
            self.assertEqual(status, 200)
            session = login["sesion"]
            self.assertEqual(request("/api/auth")[1]["usuario"], credentials["usuario"])
            self.assertEqual(request("/api/projects", {"action": "create", "name": "Synthetic pilot"})[0], 200)
            status, config_response = request("/api/config")
            self.assertEqual(status, 200)
            config = config_response["config"]
            pairs = [[0, 0, 0, 0], [1, 0, 12, 0], [1, 1, 12, 8], [0, 1, 0, 8]]
            config["cameras"] = [{"id": "C", "source": str(source), "name": "Synthetic camera",
                "x": 1, "y": 1, "height": 3, "offset": 0, "links": [], "pairs": pairs}]
            self.assertEqual(request("/api/calibration-check", {"pairs": pairs})[0], 200)
            self.assertEqual(request("/api/config", config)[0], 200)
            before = engine.config_path.read_bytes()
            invalid = copy.deepcopy(config)
            invalid["cameras"][0]["pairs"] = [[0, 0, 0, 0], [1, 0, 12, 8], [1, 1, 12, 0], [0, 1, 0, 8]]
            status, invalid_check = request("/api/calibration-check", {"pairs": invalid["cameras"][0]["pairs"]})
            self.assertEqual(status, 400)
            self.assertIn("cruza", invalid_check["error"])
            status, rejected = request("/api/config", invalid)
            self.assertEqual(status, 400)
            self.assertIn("cruza", rejected["error"])
            self.assertEqual(engine.config_path.read_bytes(), before)
            self.assertEqual(request("/api/preview", {"action": "start", "camera": "C"})[0], 200)
            deadline = time.monotonic() + 5
            while True:
                status, jpeg = request("/api/frame?camera=C")
                if status == 200 or time.monotonic() >= deadline:
                    break
                threading.Event().wait(.01)
            self.assertEqual(status, 200)
            self.assertEqual(cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR).shape, frame.shape)
            server.shutdown()
            worker.join(10)
            stopped = True
            self.assertFalse(worker.is_alive())
            self.assertTrue(quiescent(server))
            self.assertTrue(engine.closing)
            capture.release.assert_called_once()
            video.assert_called_once()
            detector.assert_not_called()
            warmup.assert_called_once()
            for task in guarded_tasks:
                task.assert_not_called()
            self.assertFalse((self.root / "config/automation.sqlite").exists())
            self.assertFalse((self.root / "data/replays").exists())
            self.assertEqual(errors, [])
        finally:
            if not stopped and servers and server_ready.is_set() and worker.is_alive():
                servers[0].shutdown()
            worker.join(10)
            self.assertFalse(worker.is_alive(), "Synthetic server must close before temporary stores")


if __name__ == "__main__":
    unittest.main()
