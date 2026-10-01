"""Modern workers, synthetic captures/mail, temporary storage and loopback only."""
import copy
import http.client
import sqlite3
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live_server import Engine, Handler, default_config
from automation import AutomationService
import automation_settings
import business_data
import notifier
from counting.engine import CountingEngine, defaults
from counting.source import VideoSource
from following.adaptive import AsyncDensitySampler
from following.source import NetworkCapture
from identity_memory import IdentityMemory
from resource_control import http_operation, hold_path
from shutdown_control import ManagedHTTPServer, stop_server, quiescent, defer_close
from task_control import checkpoint


class Capture:
    def __init__(self, read=None):
        self.read = read or (lambda: (True, np.zeros((48, 64, 3), dtype=np.uint8)))
        self.release = Mock()
    def isOpened(self): return True
    def set(self, *args): return True
    def get(self, prop): return 25 if prop == cv2.CAP_PROP_FPS else 100
    def grab(self): return True


class AutomationShutdownTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.engine = Engine(self.root / "project.json")
        self.server = SimpleNamespace(engine=self.engine, server_close=Mock())
        self.errors = []
        self.addCleanup(self.check_errors)

    def check_errors(self):
        self.assertEqual(self.errors, [])

    def worker(self, target):
        def run():
            try:
                target()
            except BaseException as exc:
                self.errors.append(exc)
        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        self.addCleanup(worker.join, 4)
        return worker

    def gate(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def block():
            entered.set()
            if not release.wait(4):
                raise RuntimeError("Synthetic worker was not released")
        return entered, release, block

    def test_idle_shutdown_and_default_registry_are_inert(self):
        self.assertEqual(self.engine.automation.tasks, {})
        self.assertTrue(stop_server(self.server, 0))
        self.assertTrue(quiescent(self.server))
        self.assertFalse((self.root / "automation.sqlite").exists())
        with self.assertRaises(ValueError):
            self.engine.preview_start("camera")

    def test_startup_error_stops_inert_service_and_closes_server(self):
        import live_server
        server = SimpleNamespace(socket=Mock(), server_bind=Mock(), server_activate=Mock(), server_close=Mock())
        with patch.object(live_server, "ManagedHTTPServer", return_value=server), \
             patch.object(live_server, "Engine", return_value=self.engine), \
             patch.object(self.engine, "warm_detector_async", side_effect=OSError("synthetic startup error")), \
             patch.object(sys, "argv", ["live_server.py"]):
            with self.assertRaises(OSError):
                live_server.main()
        self.assertFalse(self.engine.automation.worker.is_alive())
        server.server_close.assert_called_once()
        self.assertFalse((self.root / "automation.sqlite").exists())

    def test_global_budget_never_waits_on_engine_lock_or_drops_main_worker(self):
        entered, release, block = self.gate()
        def writer():
            with self.engine.lock, self.engine.resources.activity():
                block()
        self.engine.worker = self.worker(writer)
        self.assertTrue(entered.wait(2))
        now = [0.]
        waits = []
        def wait(seconds):
            waits.append(seconds)
            now[0] += seconds
        try:
            self.assertFalse(stop_server(self.server, 1, clock=lambda: now[0], wait=wait))
            self.assertAlmostEqual(sum(waits), 1)
            self.assertTrue(self.engine.worker.is_alive())
            self.server.server_close.assert_not_called()
        finally:
            release.set()
            self.engine.worker.join(3)
        self.assertTrue(stop_server(self.server, 0))

    def test_automation_worker_cancels_cooperatively_and_persists(self):
        automation_settings.save(self.root, {"reports": {"enabled": True}})
        entered = threading.Event()
        def task(*_):
            entered.set()
            self.engine.automation.stop_event.wait(3)
            checkpoint()
        self.engine.automation = AutomationService(self.engine, {"reports": task},
            clock=lambda: datetime(2026, 1, 1, 12, tzinfo=timezone.utc))
        self.engine.automation.start()
        self.addCleanup(self.engine.automation.stop, 3)
        self.assertTrue(entered.wait(2))
        self.assertTrue(stop_server(self.server, 3))
        row = self.engine.automation.store.get("reports", "service", "2026-01-01")
        self.assertEqual(row["status"], "cancelled")

    def test_registry_lock_cannot_delay_signals_or_exhaust_global_shutdown_budget(self):
        entered, release, block = self.gate()
        def writer():
            with self.engine.resources.activity(), self.engine.resource_use("owned.json", write=True):
                with self.engine.resources.lock:
                    block()
        holder = self.worker(writer)
        self.assertTrue(entered.wait(2))
        result, returned = [], threading.Event()
        def stop():
            result.append(stop_server(self.server, .02))
            returned.set()
        stopper = self.worker(stop)
        try:
            # Generous scheduling tolerance; holder remains blocked until finally.
            # This checks ordering, not a fragile millisecond performance target.
            timely = returned.wait(.5)
            signals = [self.engine.stop_event.is_set(), self.engine.automation.stop_event.is_set(),
                       self.engine.notifications.stop_event.is_set(), self.engine.mailer.stop_event.is_set()]
            still_owned = holder.is_alive()
            self.server.server_close.assert_not_called()
        finally:
            release.set()
            holder.join(3)
            stopper.join(3)
        self.assertTrue(timely, "Registry lock prevented the coordinator returning at its deadline")
        self.assertEqual(signals, [True] * 4)
        self.assertTrue(still_owned)
        self.assertEqual(result, [False])
        self.assertTrue(stop_server(self.server, 1))
        self.assertTrue(stop_server(self.server, 0))
        self.assertTrue(quiescent(self.server))

    def test_component_cancellation_lock_cannot_block_the_coordinator(self):
        entered, release, block = self.gate()
        class Component:
            def is_alive(self): return not release.is_set()
            def request_stop(self): block()
        self.engine.resources.track(Component())
        result, returned = [], threading.Event()
        def stop():
            result.append(stop_server(self.server, .02))
            returned.set()
        stopper = self.worker(stop)
        try:
            self.assertTrue(entered.wait(2))
            timely = returned.wait(.5)
            signaled = self.engine.stop_event.is_set()
            self.server.server_close.assert_not_called()
        finally:
            release.set()
            stopper.join(3)
        self.assertTrue(timely)
        self.assertTrue(signaled)
        self.assertEqual(result, [False])
        self.assertTrue(stop_server(self.server, 2))

    def prepare_mail(self):
        notifier.save(self.root, {"enabled": True, "user": "synthetic@example.invalid",
            "password": "synthetic-secret", "recipients": ["fake@example.invalid"]})
        with closing(business_data.connect(self.engine.config_path)) as db:
            business_data.registrar_incidente(db, "synthetic-incident", "aglomeracion", "zone", "C", 0)

    def test_notification_inflight_acceptance_is_persisted_after_stop(self):
        self.prepare_mail()
        entered, release, block = self.gate()
        with patch.object(notifier, "_send", side_effect=lambda *_: block()) as smtp:
            self.engine.notifications.send(self.engine.config_path, "synthetic-incident", "synthetic", "body")
            try:
                self.assertTrue(entered.wait(2))
                self.assertFalse(stop_server(self.server, 0))
                self.assertTrue(self.engine.notifications.has_writers())
            finally:
                release.set()
                self.engine.notifications.join(3)
            self.assertTrue(stop_server(self.server, 2))
            row = self.engine.notifications.get(self.engine.config_path, "synthetic-incident")
            self.assertEqual(row["status"], "sent")
            self.assertIsNotNone(row["sent_at"])
            smtp.assert_called_once()

    def test_pending_accepted_result_blocks_close_until_persistence_recovers(self):
        self.prepare_mail()
        service = self.engine.notifications
        with patch.object(notifier, "_send") as smtp:
            with patch.object(service, "_write_result", side_effect=sqlite3.OperationalError("synthetic disk")):
                self.assertFalse(service.send(self.engine.config_path, "synthetic-incident", "synthetic", "body", blocking=True))
                self.assertEqual(service.pending_results(), 1)
                self.assertFalse(stop_server(self.server, 0))
            self.assertTrue(stop_server(self.server, 3))
            self.assertEqual(service.pending_results(), 0)
            self.assertEqual(service.get(self.engine.config_path, "synthetic-incident")["status"], "sent")
            smtp.assert_called_once()

    def test_legacy_async_mailer_is_also_owned_until_send_finishes(self):
        self.prepare_mail()
        entered, release, block = self.gate()
        with patch.object(notifier, "_send", side_effect=lambda *_: block()):
            self.engine.mailer.send("synthetic", "body")
            workers = tuple(self.engine.mailer.workers)
            try:
                self.assertTrue(entered.wait(2))
                self.assertFalse(stop_server(self.server, 0))
            finally:
                release.set()
                for worker in workers:
                    worker.join(3)
            self.assertTrue(stop_server(self.server, 0))
            self.assertEqual(self.engine.mailer.sent, 1)

    def test_slow_preview_timeout_and_replacement_cannot_publish_old_state(self):
        entered, release, block = self.gate()
        new_waiting, new_release = threading.Event(), threading.Event()
        calls = [0]
        def old_read():
            block()
            return True, b"OLD"
        def new_read():
            calls[0] += 1
            if calls[0] > 1:
                new_waiting.set()
                new_release.wait(4)
            return True, b"NEW"
        old, new = Capture(old_read), Capture(new_read)
        self.engine.config["cameras"] = [{"id": "C", "source": "old.synthetic"}]
        original_stop = self.engine.preview_stop
        with patch.object(cv2, "VideoCapture", side_effect=[old, new]), \
             patch.object(self.engine, "_preview_jpeg", side_effect=lambda frame: frame), \
             patch.object(self.engine, "preview_stop", side_effect=lambda: original_stop(0)):
            self.engine.preview_start("C")
            first, first_event = self.engine.preview_worker, self.engine.preview_stop_event
            try:
                self.assertTrue(entered.wait(2))
                self.assertFalse(original_stop(0))
                self.assertIs(self.engine.preview_worker, first)
                self.engine.config["cameras"][0]["source"] = "new.synthetic"
                self.engine.preview_start("C")
                second = self.engine.preview_worker
                self.assertIsNot(first_event, self.engine.preview_stop_event)
                self.assertTrue(first_event.is_set())
                self.assertIn(first, self.engine.preview_workers)
                self.assertTrue(new_waiting.wait(2))
                before = copy.deepcopy(self.engine.preview_state)
                release.set()
                first.join(3)
                self.assertFalse(first.is_alive())
                self.assertEqual(self.engine.frames["C"], b"NEW")
                self.assertEqual(self.engine.preview_state, before)
                self.assertTrue(second.is_alive())
            finally:
                self.engine.preview_stop_event.set()
                release.set()
                new_release.set()
                for worker in tuple(self.engine.preview_workers):
                    worker.join(3)
        old.release.assert_called_once()
        new.release.assert_called_once()
        self.assertFalse(self.engine.resources.busy())

    def test_async_density_active_inference_remains_owned_after_close_timeout(self):
        entered, release, block = self.gate()
        detector = SimpleNamespace(detectar=lambda frame: (block() or []))
        with self.engine.resources.activity():
            sampler = AsyncDensitySampler(lambda: detector)
            sampler.submit("C", np.zeros((2, 2, 3)), 0)
        try:
            self.assertTrue(entered.wait(2))
            sampler.submit("queued", np.zeros((2, 2, 3)), 1)
            self.assertFalse(sampler.close(0))
            sampler.submit("after-close", np.zeros((2, 2, 3)), 2)
            self.assertFalse(stop_server(self.server, 0))
        finally:
            release.set()
            self.assertTrue(sampler.close(3))
        self.assertEqual(sampler.latest("queued"), {"status": "idle"})
        self.assertEqual(sampler.latest("after-close"), {"status": "idle"})
        self.assertTrue(stop_server(self.server, 0))

    def test_network_reader_timeout_retains_capture_until_native_read_returns(self):
        entered, release, block = self.gate()
        capture = Capture(lambda: (block() or (True, "synthetic-frame")))
        with patch.object(cv2, "VideoCapture", return_value=capture):
            with self.engine.resources.activity():
                network = NetworkCapture("rtsp://synthetic.invalid/never-opened", self.root)
            try:
                self.assertTrue(entered.wait(2))
                self.assertFalse(network.source.close(0))
                self.assertTrue(network.is_alive())
                self.assertFalse(stop_server(self.server, 0))
                capture.release.assert_not_called()
                self.assertEqual(network.read(), (False, None))
            finally:
                release.set()
                network.source.close(3)
        capture.release.assert_called_once()
        self.assertTrue(stop_server(self.server, 0))

    def test_warmup_initialization_is_known_while_native_load_is_blocked(self):
        entered, release, block = self.gate()
        with patch.object(self.engine, "load_detector", side_effect=lambda *_: block()):
            self.engine.warm_detector_async()
            try:
                self.assertTrue(entered.wait(2))
                self.assertFalse(stop_server(self.server, 0))
                self.assertTrue(self.engine.detector_warmup.is_alive())
            finally:
                release.set()
                self.engine.detector_warmup.join(3)
        self.assertTrue(stop_server(self.server, 0))

    def test_counting_source_initialization_is_cancelled_and_owned(self):
        entered, release, block = self.gate()
        video = SimpleNamespace(live=True, duration=None, fps=25, started=0, close=Mock())
        def source(*_):
            block()
            return video
        counting = CountingEngine(self.root, self.root / "counting.json", detector_factory=lambda: SimpleNamespace(umbral=.5))
        counting.resources = self.engine.resources
        self.engine.counting = counting
        with patch("counting.engine.VideoSource", side_effect=source):
            counting.start(defaults("synthetic.mp4"))
            try:
                self.assertTrue(entered.wait(2))
                self.assertFalse(stop_server(self.server, 0))
                self.assertTrue(counting.stop_event.is_set())
                self.assertTrue(counting.worker.is_alive())
                video.close.assert_not_called()
            finally:
                release.set()
                counting.worker.join(3)
        video.close.assert_called_once()
        self.assertEqual(counting.state["status"], "stopped", counting.state.get("error"))
        self.assertTrue(stop_server(self.server, 0))

    def test_main_pipeline_keeps_identity_connection_until_writer_finally(self):
        entered, release, block = self.gate()
        capture = Capture(lambda: (block() or (True, np.zeros((48, 64, 3), dtype=np.uint8))))
        memories = []
        def memory(*args, **kwargs):
            result = IdentityMemory(*args, **kwargs)
            result.close = Mock(wraps=result.close)
            memories.append(result)
            return result
        config = default_config()
        config["cameras"] = [{"id": "C", "source": "synthetic.mp4", "offset": 0, "pairs": [], "height": 3}]
        self.engine.state.update(session="abcd1234", status="running")
        with patch.object(cv2, "VideoCapture", return_value=capture), \
             patch.object(self.engine, "load_detector", return_value=SimpleNamespace(detectar=lambda frame: [])), \
             patch("live_server.IdentityMemory", side_effect=memory):
            self.engine.worker = self.worker(lambda: self.engine.run(config, {"detector": "p2pnet"}))
            try:
                self.assertTrue(entered.wait(3), self.engine.state.get("error"))
                self.assertEqual(len(memories), 1)
                self.assertFalse(stop_server(self.server, 0))
                memories[0].close.assert_not_called()
            finally:
                release.set()
                self.engine.worker.join(4)
        self.assertFalse(self.engine.worker.is_alive())
        memories[0].close.assert_called_once()
        capture.release.assert_called_once()
        self.assertTrue(stop_server(self.server, 0))

    def test_deferred_close_runs_only_after_known_writer_drains(self):
        entered, release, block = self.gate()
        def writer():
            with self.engine.resources.activity(), self.engine.resource_use("data/uploads/synthetic.mp4", write=True):
                block()
        worker = self.worker(writer)
        closer = None
        try:
            self.assertTrue(entered.wait(2))
            self.assertFalse(stop_server(self.server, 0))
            closer = defer_close(self.server, .02)
            self.assertIs(defer_close(self.server), closer)
            self.server.server_close.assert_not_called()
            self.assertTrue(closer.is_alive())
        finally:
            release.set()
            worker.join(3)
            if closer:
                closer.join(3)
        self.assertFalse(closer.is_alive())
        self.server.server_close.assert_called_once()

    def test_published_camera_aggregates_are_isolated_from_next_inference(self):
        from following.combined import CombinedAnalysis
        entered, release, block = self.gate()
        captures = [0]
        analyses = []
        def read():
            captures[0] += 1
            if captures[0] == 2:
                block()
            return True, np.zeros((48, 64, 3), dtype=np.uint8)
        def combined(*args):
            instance = CombinedAnalysis(*args)
            analyses.append(instance)
            return instance
        config = default_config()
        config["cameras"] = [{"id": "C", "source": "synthetic.mp4", "offset": 0, "pairs": [], "height": 3}]
        self.engine.state.update(session="abcd1234", status="running")
        with patch.object(cv2, "VideoCapture", return_value=Capture(read)), \
             patch.object(self.engine, "load_detector", return_value=SimpleNamespace(detectar=lambda frame: [])), \
             patch("following.combined.CombinedAnalysis", side_effect=combined):
            self.engine.worker = self.worker(lambda: self.engine.run(config, {"detector": "p2pnet", "combined": True}))
            try:
                self.assertTrue(entered.wait(3), self.engine.state.get("error"))
                snapshot = self.engine.automation_snapshot()
                # Represents producer mutations before publication of the next tick.
                analyses[0].snapshots["C"]["occupancy"]["count"] = 999
                analyses[0].snapshots["C"]["dense"]["count"] = 999
                self.assertEqual(self.engine.automation_snapshot(), snapshot)
            finally:
                self.engine.stop_event.set()
                release.set()
                self.engine.worker.join(4)
        self.assertFalse(self.engine.worker.is_alive())

    def test_http_writer_lease_outlives_deadline_and_refuses_new_requests(self):
        entered, release, block = self.gate()
        class SyntheticHandler(Handler):
            @http_operation
            def do_POST(handler):
                hold_path(self.root / "data/uploads/synthetic.mp4", write=True)
                block()
                handler.send_data(200, {"ok": True})
        server = ManagedHTTPServer(("127.0.0.1", 0), SyntheticHandler)
        server.engine = self.engine
        loop = self.worker(lambda: server.serve_forever(poll_interval=.01))
        responses = []
        def client():
            connection = http.client.HTTPConnection(*server.server_address, timeout=4)
            try:
                connection.request("POST", "/synthetic")
                response = connection.getresponse()
                responses.append((response.status, response.read()))
            finally:
                connection.close()
        request = self.worker(client)
        try:
            self.assertTrue(entered.wait(2))
            server.shutdown()
            loop.join(2)
            self.assertFalse(stop_server(server, 0))
            self.assertTrue(self.engine.resources.protected("data/uploads/synthetic.mp4"))
            self.assertTrue(server.http_workers)
            handler = SimpleNamespace(server=server, path="/api/config", send_data=Mock())
            Handler.do_GET(handler)
            self.assertEqual(handler.send_data.call_args.args[0], 503)
        finally:
            release.set()
            request.join(3)
            server.shutdown()
            loop.join(2)
            self.assertTrue(stop_server(server, 3))
            server.server_close()
        self.assertEqual(responses[0][0], 200)
        self.assertFalse(server.http_workers)

    def test_http_idle_connection_has_timeout_and_drains(self):
        import socket
        server = ManagedHTTPServer(("127.0.0.1", 0), Handler)
        server.engine = self.engine
        server.connection_timeout_seconds = .1
        admitted = threading.Event()
        original = server.process_request
        def process(*args):
            original(*args)
            admitted.set()
        server.process_request = process
        loop = self.worker(lambda: server.serve_forever(poll_interval=.01))
        client = socket.create_connection(server.server_address, timeout=2)
        try:
            self.assertTrue(admitted.wait(2))
            server.shutdown()
            self.assertTrue(stop_server(server, 3))
        finally:
            client.close()
            server.shutdown()
            loop.join(2)
            server.server_close()
