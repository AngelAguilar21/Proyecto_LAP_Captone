import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live_server import Engine
from replay import ReplayWriter
from resource_control import CURRENT, hold_source


class ResourceControlTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.engine = Engine(self.root / "project.json")
        self.registry = self.engine.resources

    def test_resource_use_is_normalized_and_released_after_exception(self):
        with self.assertRaises(RuntimeError):
            with self.engine.resource_use("data/uploads/fake.mp4") as identity:
                self.assertEqual(identity, self.registry.identity(self.root / "data/uploads/fake.mp4"))
                self.assertEqual(self.engine.resource_users, 1)
                self.assertTrue(self.registry.protected("data/uploads"))
                self.assertTrue(self.registry.protected(identity))
                raise RuntimeError("synthetic")
        self.assertEqual(self.engine.resource_users, 0)
        self.assertFalse(self.registry.busy())

    def test_traversal_and_drive_relative_paths_are_rejected(self):
        paths = ["../outside", "data/../outside"]
        if sys.platform == "win32":
            paths.append("C:relative.mp4")
        for path in paths:
            with self.subTest(path=path), self.assertRaises(ValueError):
                with self.engine.resource_use(path):
                    self.fail("Ambiguous path accepted")

    def test_two_concurrent_readers_are_counted_and_drained(self):
        entered = threading.Barrier(3)
        release = threading.Event()
        def reader():
            with self.engine.resource_use("data/uploads/fake.mp4"):
                entered.wait(3)
                release.wait(3)
        workers = [threading.Thread(target=reader) for _ in range(2)]
        for worker in workers:
            worker.start()
        try:
            entered.wait(3)
            self.assertEqual(self.engine.resource_users, 2)
        finally:
            release.set()
            for worker in workers:
                worker.join(3)
        self.assertEqual(self.engine.resource_users, 0)

    def test_replay_writer_holds_lease_until_finished(self):
        with self.registry.activity():
            writer = ReplayWriter(self.root, "abcd1234", "synthetic", [], {})
            self.assertTrue(self.registry.protected(writer.directory))
            writer.append({"t": 0})
            writer.finish("ended")
            self.assertFalse(self.registry.protected(writer.directory))
        self.assertFalse(self.registry.busy())

    def test_replay_constructor_failure_releases_lease(self):
        with self.registry.activity(), patch.object(ReplayWriter, "save", side_effect=OSError("synthetic")):
            with self.assertRaises(OSError):
                ReplayWriter(self.root, "abcd1234", "synthetic", [], {})
        self.assertEqual(self.engine.resource_users, 0)

    def test_source_lease_is_scoped_and_context_restores_after_error(self):
        with self.assertRaises(RuntimeError):
            with self.registry.activity():
                hold_source("data/uploads/synthetic.mp4", self.root)
                self.assertTrue(self.registry.protected("data/uploads/synthetic.mp4"))
                raise RuntimeError("synthetic")
        self.assertIsNone(CURRENT.get())
        self.assertFalse(self.registry.busy())

    def test_closing_refuses_new_users_but_allows_admitted_writer_to_finish(self):
        with self.registry.activity():
            self.registry.request_stop()
            with self.engine.resource_use("data/replays/final.json", write=True):
                self.assertEqual(self.engine.resource_users, 1)
        with self.assertRaises(ValueError):
            with self.engine.resource_use("new.json"):
                pass
        self.assertFalse(self.registry.busy())
