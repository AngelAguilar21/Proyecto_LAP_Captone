"""Synthetic retention fixtures. Every writable path is below TemporaryDirectory."""
import io
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live_server import Engine
from automation_cleanup import RetentionCleanup, plan_cleanup
from automation_store import AutomationStore
from resource_control import ResourceRegistry
from replay import ReplayWriter
import uploads


class CleanupFixture:
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="retention-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.settings = self.root / "config"
        self.settings.mkdir()
        self.engine = Engine(self.settings / "project.json")
        self.engine.data_root = self.root
        self.engine.resources = ResourceRegistry(self.root)
        self.engine.resource_lock = self.engine.resources.lock
        self.engine.config = {"cameras": []}
        self.store = AutomationStore(self.settings / "automation.sqlite")
        self.task = RetentionCleanup(self.engine, self.store)
        self.now = datetime(2026, 9, 30, tzinfo=timezone.utc)
        self.old = self.now.timestamp() - 31 * 86400

    def upload(self, when=None):
        return uploads.receive(self.root, io.BytesIO(b"synthetic-video"), 15, ".mp4",
                               clock=lambda: self.old if when is None else when,
                               resources=self.engine.resources)

    def replay(self, sid="aaaaaaaa", state="ended", when=None, config=None):
        stamp = self.old if when is None else when
        writer = ReplayWriter(self.root, sid, "demo", [], config or {})
        writer.meta["created"] = datetime.fromtimestamp(stamp, timezone.utc).isoformat()
        writer.append({"t": 0, "cameras": []})
        writer.finish(state)
        for file in writer.directory.iterdir():
            os.utime(file, (stamp, stamp))
        return writer.directory

    def plan(self, **kwargs):
        return plan_cleanup(self.root, self.settings, self.now, 30, **kwargs)

    def decision(self, plan, path):
        return next(d for d in plan.decisions if d.path == path.relative_to(self.root).as_posix())

    def outcome(self, outcomes, path):
        return next(d for d in outcomes if d["path"] == path.relative_to(self.root).as_posix())

    def project(self, reference, pid="p-a"):
        directory = self.settings / "projects"
        directory.mkdir(exist_ok=True)
        (directory / "index.json").write_text(json.dumps({"active": pid, "projects": [{"id": pid}]}))
        (directory / (pid + ".json")).write_text(json.dumps(reference))

    def snapshot(self):
        return {str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.rglob("*") if p.is_file()}
