"""Real replay writer/reader contracts, without sources or operational stores."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import live_server
import notifier
from replay import ReplayWriter
from replay import report_snapshot, recover_interrupted
from replay_projection import current_projection
from automation import LIMA
from automation_reports import ScheduledReports
from automation_store import AutomationStore
from datetime import datetime
from unittest.mock import Mock


class AuditRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="audit-recovery-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.enterContext(patch.object(live_server, "ROOT", self.root))
        self.enterContext(patch.object(live_server, "CONFIG_PATH", self.root / "config/live.local.json"))
        smtp = self.enterContext(patch.object(notifier, "_send", side_effect=AssertionError("SMTP forbidden")))
        self.addCleanup(smtp.assert_not_called)
        self.engine = live_server.Engine()
        self.config = copy.deepcopy(self.engine.config)
        self.config["cameras"] = [{"id": "C", "source": "synthetic-not-opened.mp4", "x": 1, "y": 1,
                                    "height": 3, "offset": 0, "links": [], "pairs": []}]
        self.engine.configure(self.config)

    def saved(self, sid):
        writer = ReplayWriter(self.root, sid, "unified", self.config["cameras"],
                              {k: v for k, v in self.config.items() if k != "cameras"}, self.engine.project_id)
        writer.append({"t": 10, "cameras": [{"id": "C", "people": [{"id": "synthetic"}]}]})
        writer.meta["cameraAnalytics"] = {"C": {"occupancy": {"count": 1}}}
        writer.meta["totals"] = {"meanObservedSeconds": 5, "alerts": 0}
        writer.finish("ended")
        return writer

    def test_invalid_historical_metadata_does_not_prevent_startup_or_hide_valid_replay(self):
        good = self.saved("abcd0001")
        bad = self.saved("abcd0002")
        valid = copy.deepcopy(bad.meta)
        variants = []
        for key in ("created", "config", "end"):
            value = copy.deepcopy(valid)
            value.pop(key)
            variants.append(("missing_" + key, value))
        for key, value in (("created", 3), ("created", "not-a-date"), ("config", []),
                           ("end", "bad"), ("end", True), ("cameraAnalytics", []),
                           ("cameraAnalytics", {"C": []}), ("levelAnalytics", [])):
            variants.append(("invalid_" + key, {**valid, key: value}))
        variants += [("array", []), ("null", None), ("malformed", "{broken")]
        good_bytes = good.path.read_bytes()
        for name, value in variants:
            with self.subTest(name=name):
                bad.path.write_text(value if name == "malformed" else json.dumps(value), encoding="utf-8")
                bad_bytes = bad.path.read_bytes()
                restored = live_server.Engine()
                self.assertIsNone(restored.config_error)
                self.assertEqual(restored.state["session"], good.meta["session"])
                self.assertEqual(restored.state["series"], [{"t": 10, "count": 1}])
                self.assertTrue(any("abcd0002" in item["detail"] for item in restored.snapshot()["audit"]))
                self.assertEqual(bad.path.read_bytes(), bad_bytes)
                self.assertEqual(good.path.read_bytes(), good_bytes)

    def test_valid_writer_metadata_restores_latest_session(self):
        first = self.saved("abcd0001")
        second = self.saved("abcd0002")
        restored = live_server.Engine()
        self.assertEqual(restored.state["session"], second.meta["session"])
        self.assertEqual(restored.state["series"], [{"t": 10, "count": 1}])
        self.assertEqual(restored.report_identity, (self.engine.project_id, second.meta["session"]))

    def two_samples(self):
        writer = ReplayWriter(self.root, "abcd0020", "unified", self.config["cameras"],
                              {k: v for k, v in self.config.items() if k != "cameras"}, self.engine.project_id)
        for t, count in ((10, 1), (20, 3)):
            writer.append({"t": t, "cameras": [{"id": "C", "people": [{"id": str(i)} for i in range(count)]}]})
        writer.meta["totals"] = {"meanObservedSeconds": 5, "alerts": 0}
        writer.finish("ended")
        return writer

    def test_complete_line_truncation_cannot_publish_a_scheduled_report(self):
        writer = self.two_samples()
        config, state, _ = report_snapshot(self.root, "abcd0020", self.engine.project_id, strict=True)
        self.assertEqual(state["series"], [{"t": 10, "count": 1}, {"t": 20, "count": 3}])
        samples = writer.directory / "samples.jsonl"
        samples.write_bytes(samples.read_bytes().splitlines(keepends=True)[0])
        with self.assertRaises(ValueError):
            report_snapshot(self.root, "abcd0020", self.engine.project_id, strict=True)
        restored = live_server.Engine()
        renderer = Mock(side_effect=AssertionError("Incomplete evidence must not render"))
        task = ScheduledReports(restored, AutomationStore(self.root / "tasks.sqlite"), renderer)
        self.assertEqual(task(datetime(2026, 10, 1, 20, tzinfo=LIMA), {"enabled": True, "time": "20:00"}), "no_data")
        renderer.assert_not_called()
        self.assertFalse(list((self.root / "data/reports").rglob("*.pdf")))

    def test_report_rejects_malformed_tail_and_inconsistent_finalization(self):
        writer = self.two_samples()
        samples = writer.directory / "samples.jsonl"
        good_bytes, good_meta = samples.read_bytes(), copy.deepcopy(writer.meta)
        for kind in ("malformed_tail", "changed_end", "changed_status", "unfinished"):
            with self.subTest(kind=kind):
                samples.write_bytes(good_bytes + (b'{broken' if kind == "malformed_tail" else b''))
                meta = copy.deepcopy(good_meta)
                if kind == "changed_end": meta["end"] = 25
                if kind == "changed_status": meta["status"] = "stopped"
                if kind == "unfinished": meta["completion"] = None
                writer.path.write_text(json.dumps(meta), encoding="utf-8")
                before = writer.path.read_bytes(), samples.read_bytes()
                with self.assertRaises(ValueError):
                    report_snapshot(self.root, "abcd0020", self.engine.project_id, strict=True)
                self.assertEqual((writer.path.read_bytes(), samples.read_bytes()), before)

    def test_completion_allows_end_after_last_sample_and_marks_legacy_unknown(self):
        # End is a session bound, not necessarily an observation timestamp.
        writer = ReplayWriter(self.root, "abcd0030", "unified", self.config["cameras"],
                              {k:v for k,v in self.config.items() if k != "cameras"}, self.engine.project_id)
        for t in (0, 0, .2, 1.7): writer.append({"t":t, "cameras":[{"id":"C", "people":[]}]})
        writer.meta["end"] = 2
        writer.finish("stopped")
        _, state, meta = report_snapshot(self.root, "abcd0030", self.engine.project_id, strict=True)
        self.assertEqual(state["series"][-1], {"t":1.7, "count":0})
        self.assertEqual(meta["evidenceIntegrity"], "verified")
        meta.pop("evidenceIntegrity")
        meta.pop("evidenceVersion")
        meta.pop("completion")
        writer.path.write_text(json.dumps(meta), encoding="utf-8")
        before = writer.path.read_bytes()
        self.assertEqual(report_snapshot(self.root, "abcd0030", self.engine.project_id, strict=True)[2]["evidenceIntegrity"], "unknown")
        self.assertEqual(writer.path.read_bytes(), before)

    def test_engine_writer_camera_contract_preserves_identity_and_source_guard(self):
        # Use the same snapshot contract as Engine, then the real writer/reader.
        import replay
        config = copy.deepcopy(self.config)
        config.update(width=12, height=8, planId="custom")
        camera = config["cameras"][0]
        camera.update(planId="custom", pairs=[[0,0,0,0],[1,0,12,0],[1,1,12,8],[0,1,0,8]])
        recorded = replay.camera_snapshot(config["cameras"])
        writer = ReplayWriter(self.root, "abcd0040", "unified", recorded,
                              {k:v for k,v in config.items() if k != "cameras"}, self.engine.project_id)
        samples = [{"t":10,"cameras":[{"id":"C","people":[{"id":"P1","pixel":[.5,.5],"point":[6,4],"association":"estimated"}]}]}]
        writer.append(samples[0]); writer.finish("ended")
        before = copy.deepcopy(samples)
        same = current_projection(writer.meta, samples, config)[0]["cameras"][0]["people"][0]
        self.assertEqual((same["id"], same["association"]), ("P1", "estimated"))
        moved = copy.deepcopy(config)
        moved["cameras"][0]["pairs"] = [[u,v,x+1,y] for u,v,x,y in camera["pairs"]]
        changed = current_projection(writer.meta, samples, moved)[0]["cameras"][0]["people"][0]
        self.assertEqual((changed["id"],changed["association"]), ("C:P1","local"))
        self.assertAlmostEqual(changed["point"][0],7)
        config["cameras"][0]["source"] = "different-synthetic.mp4"
        self.assertEqual(current_projection(writer.meta, samples, config)[0]["cameras"][0]["people"], [])
        self.assertEqual(samples, before)

    def test_projection_legacy_compatibility_ambiguity_and_live_redaction(self):
        from replay import camera_snapshot
        camera = {"id":"C","source":"synthetic.mp4","pairs":[[0,0,0,0],[1,0,12,0],[1,1,12,8],[0,1,0,8]],"planId":"custom"}
        config={**self.config,"planId":"custom","cameras":[camera]}
        samples=[{"t":1,"cameras":[{"id":"C","people":[{"id":"P1","pixel":[.5,.5],"association":"estimated"}]}]}]
        legacy={"config":copy.deepcopy(config)}
        self.assertEqual(current_projection(legacy,samples,config)[0]["cameras"][0]["people"][0]["id"],"P1")
        legacy['cameras']=[{**camera,'source':'different.mp4'}]
        with self.assertRaises(ValueError):current_projection(legacy,samples,config)
        with self.assertRaises(ValueError):current_projection({'config':{}},samples,config)
        private='rtsp://synthetic-user:synthetic-secret@example.invalid/source'
        snapshot=camera_snapshot([{**camera,'source':private}])
        self.assertNotIn(private,json.dumps(snapshot))
        self.assertNotIn('synthetic-secret',json.dumps(snapshot))
        with self.assertRaises(ValueError):current_projection({'cameras':snapshot},samples,config)


if __name__ == "__main__":
    unittest.main()
