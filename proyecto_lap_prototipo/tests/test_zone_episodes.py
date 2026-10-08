"""Aggregate source-time episodes; only temporary configuration/SQLite and fake SMTP."""
import copy
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live_server import Engine, default_config
from live_core import Occupancy, validate_config
from zone_episodes import ZoneEpisodes, ensure_zone_ids, plan_observed
import business_data
import notifier


def configuration():
    config = default_config()
    config.update(cameras=[], planId="custom", zones=[{
        "id": "z", "name": "Puerta", "points": [[0, 0], [4, 0], [4, 4], [0, 4]],
        "rule": {"enabled": True, "minPeople": 2, "dwell": 2}}])
    return config


def people(count=2):
    return [{"id": str(i), "camera": "C", "point": [1 + i * .1, 1]} for i in range(count)]


class ZoneEpisodeTests(unittest.TestCase):
    def setUp(self):
        self.config = configuration()
        self.zone = self.config["zones"][0]
        self.counter = Occupancy(self.config)

    def update(self, t, count=2, valid=True):
        return self.counter.update(people(count), t, observation_valid=valid)

    def test_below_threshold_and_disabled_rule_do_not_start(self):
        self.assertEqual(self.update(0, 1)["zoneEpisodes"], [])
        self.zone["rule"]["enabled"] = False
        self.assertEqual(self.update(1)["zoneEpisodes"], [])

    def test_exact_dwell_and_many_updates_keep_one_id_and_update_peak(self):
        first = self.update(0)["zoneEpisodes"][0]
        self.assertFalse(first["alert"])
        self.assertFalse(self.update(1.999)["zoneEpisodes"][0]["alert"])
        for t in (2, 3, 10, 100, 200):
            data = self.update(t, 5)
            self.assertEqual(len(data["zoneEpisodes"]), 1)
            current = data["zoneEpisodes"][0]
            self.assertEqual(current["id"], first["id"])
            self.assertEqual((current["start"], current["last"], current["duration"], current["peak"]), (0, t, t, 5))
            self.assertTrue(current["alert"])
            self.assertEqual(data["zones"][0]["episodeId"], first["id"])

    def test_valid_dip_closes_immediately_and_next_rise_has_new_id(self):
        first = self.update(0)["zoneEpisodes"][0]["id"]
        ended = self.update(1, 1)
        self.assertEqual(ended["zoneEpisodes"][0]["end"], 1)
        self.assertEqual(ended["zoneEpisodes"][0]["reason"], "below_threshold")
        self.assertIsNone(ended["zones"][0]["episodeId"])
        self.assertNotEqual(self.update(2)["zones"][0]["episodeId"], first)

    def test_missing_observation_preserves_identity_and_excludes_gap(self):
        first = self.update(0)["zones"][0]["episodeId"]
        self.update(1)
        gap = self.update(2, 0, False)
        self.assertIsNone(gap["zones"][0]["count"])
        self.assertFalse(gap["zones"][0]["observed"])
        self.assertFalse(gap["zoneEpisodes"][0]["observed"])
        self.assertIsNone(gap["zoneEpisodes"][0]["end"])
        resumed = self.update(100)
        self.assertEqual(resumed["zones"][0]["episodeId"], first)
        self.assertEqual(resumed["zoneEpisodes"][0]["duration"], 1)
        self.assertFalse(resumed["zones"][0]["alert"])
        self.assertTrue(self.update(101)["zones"][0]["alert"])

    def test_invalid_observation_cannot_start_an_episode(self):
        self.assertEqual(self.update(0, 10, False)["zoneEpisodes"], [])

    def test_invalid_sample_after_alert_keeps_history_without_current_alert(self):
        self.update(0)
        self.update(2)
        gap = self.update(3, 0, False)
        self.assertTrue(gap["zoneEpisodes"][0]["alert"])
        self.assertFalse(gap["zones"][0]["alert"])
        self.assertIsNone(gap["zoneEpisodes"][0]["end"])

    def test_material_rule_and_geometry_changes_close_and_restart_dwell(self):
        for field, value in (("dwell", 5), ("minPeople", 3), ("points", [[0, 0], [5, 0], [5, 4], [0, 4]])):
            with self.subTest(field=field):
                config = configuration()
                counter = Occupancy(config)
                first = counter.update(people(3), 0)["zones"][0]["episodeId"]
                target = config["zones"][0] if field == "points" else config["zones"][0]["rule"]
                target[field] = value
                data = counter.update(people(3), 1)
                self.assertEqual(data["zoneEpisodes"][0]["reason"], "configuration_changed")
                self.assertNotEqual(data["zones"][0]["episodeId"], first)
                self.assertEqual(data["zones"][0]["duration"], 0)

    def test_disable_closes_even_without_observation(self):
        self.update(0)
        self.zone["rule"]["enabled"] = False
        data = self.update(1, 0, False)
        self.assertEqual(data["zoneEpisodes"][0]["reason"], "disabled")
        self.assertEqual(data["zoneEpisodes"][0]["end"], 1)
        self.assertIsNone(data["zones"][0]["episodeId"])

    def test_material_change_during_gap_closes_without_inventing_new_episode(self):
        self.update(0)
        self.zone["rule"]["dwell"] = 10
        data = self.update(2, 0, False)
        self.assertEqual(len(data["zoneEpisodes"]), 1)
        self.assertEqual(data["zoneEpisodes"][0]["reason"], "configuration_changed")
        self.assertIsNone(data["zones"][0]["episodeId"])

    def test_clock_reversal_after_invalid_sample_starts_fresh_nonnegative_duration(self):
        self.update(10)
        self.update(12)
        self.update(100, 0, False)
        data = self.update(50)
        old, new = data["zoneEpisodes"]
        self.assertEqual((old["end"], old["reason"], old["duration"]), (12, "clock_reversed", 2))
        self.assertEqual((new["start"], new["duration"]), (50, 0))
        self.assertNotEqual(new["id"], old["id"])

    def test_renaming_and_reordering_preserve_identity(self):
        first = self.update(0)["zones"][0]["episodeId"]
        self.zone["name"] = "Nuevo nombre"
        self.config["zones"].insert(0, {**copy.deepcopy(self.zone), "id": "other"})
        data = self.update(1)
        self.assertEqual(data["zones"][1]["episodeId"], first)
        self.assertEqual(data["zoneEpisodes"][0]["zone"], "Nuevo nombre")

    def test_removed_zone_closes_and_keeps_history(self):
        self.update(0)
        self.config["zones"] = []
        data = self.update(2)
        self.assertEqual(data["zones"], [])
        self.assertEqual(data["zoneEpisodes"][0]["reason"], "zone_removed")

    def test_source_end_closes_at_last_observed_source_time(self):
        self.update(0)
        self.update(2)
        self.update(100, 0, False)
        self.counter.zone_episodes.finish()
        episode = self.counter.zone_episodes.snapshot()[0]
        self.assertEqual((episode["end"], episode["reason"]), (2, "session_ended"))

    def test_snapshot_is_detached_json_serializable_and_aggregate_only(self):
        data = self.update(0)
        episode = json.loads(json.dumps(data))["zoneEpisodes"][0]
        self.assertEqual(set(episode), {"id", "scope", "zoneId", "zone", "zoneName", "start", "last",
            "duration", "peak", "end", "reason", "signature", "observed", "alert", "threshold", "dwell", "count"})
        self.assertEqual((episode["zone"], episode["zoneId"], episode["scope"]), ("Puerta", "z", "plan:custom"))
        data["zoneEpisodes"][0]["peak"] = 999
        self.assertEqual(self.counter.zone_episodes.snapshot()[0]["peak"], 2)


class ZoneIdentityTests(unittest.TestCase):
    def test_plan_without_zones_does_not_assign_its_scope_to_primary_legacy_zone(self):
        config = configuration()
        config["zones"][0].pop("id")
        expected = copy.deepcopy(config)
        ensure_zone_ids(expected)
        config["plans"] = {"lap-2": {"width": 12, "height": 8}}
        validate_config(config)
        self.assertEqual(config["zones"][0]["id"], expected["zones"][0]["id"])

    def test_legacy_ids_are_order_independent_and_persist_through_edits(self):
        config = configuration()
        config["zones"][0].pop("id")
        other = copy.deepcopy(config["zones"][0])
        other["points"] = [[5, 0], [6, 0], [6, 4], [5, 4]]
        config["zones"].append(other)
        reversed_config = copy.deepcopy(config)
        reversed_config["zones"].reverse()
        validate_config(config)
        validate_config(reversed_config)
        ids = [z["id"] for z in config["zones"]]
        self.assertEqual(ids, [z["id"] for z in reversed(reversed_config["zones"])])
        self.assertNotEqual(*ids)
        config["zones"][0]["name"] = "Renamed"
        config["zones"][0]["points"][0] = [0, .1]
        self.assertFalse(ensure_zone_ids(config))
        self.assertEqual(config["zones"][0]["id"], ids[0])

    def test_same_legacy_name_and_geometry_on_different_plans_get_distinct_ids(self):
        config = configuration()
        config["zones"][0].pop("id")
        config["plans"] = {"lap-2": {"zones": copy.deepcopy(config["zones"])}}
        validate_config(config)
        self.assertNotEqual(config["zones"][0]["id"], config["plans"]["lap-2"]["zones"][0]["id"])

    def test_duplicate_ids_are_rejected_in_each_plan(self):
        for secondary in (False, True):
            with self.subTest(secondary=secondary):
                config = configuration()
                zones = [copy.deepcopy(config["zones"][0])] * 2
                if secondary:
                    config["plans"] = {"lap-2": {"zones": zones}}
                else:
                    config["zones"] = zones
                with self.assertRaises(ValueError):
                    validate_config(config)

    def test_invalid_zone_id_is_rejected(self):
        for value in (123, [], " ", "x" * 201):
            with self.subTest(value=value):
                config = configuration()
                config["zones"][0]["id"] = value
                with self.assertRaises(ValueError):
                    validate_config(config)

    def test_engine_saves_legacy_ids_on_load_without_other_config_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "project.json"
            config = configuration()
            config["zones"][0].pop("id")
            config["plans"] = {"lap-2": {"zones": copy.deepcopy(config["zones"])}}
            path.write_text(json.dumps(config), encoding="utf-8")
            engine = Engine(path)
            self.assertIsNone(engine.config_error)
            saved = json.loads(path.read_text(encoding="utf-8"))
            first = saved["zones"][0]["id"]
            self.assertEqual(Engine(path).config["zones"][0]["id"], first)
            saved["zones"][0].pop("id")
            saved["plans"]["lap-2"]["zones"][0].pop("id")
            self.assertEqual(saved, config)

    def test_partial_missing_uncalibrated_or_ended_sources_are_not_valid_zero_counts(self):
        cameras = [{"id": "A", "planId": "custom", "projects": True},
                   {"id": "B", "planId": "custom", "projects": True},
                   {"id": "C", "planId": "lap-2", "projects": True}]
        self.assertTrue(plan_observed(cameras, {"A", "B"}, "custom"))
        self.assertFalse(plan_observed(cameras, {"A"}, "custom"))
        self.assertFalse(plan_observed(cameras, set(), "custom"))
        self.assertTrue(plan_observed(cameras, {"C"}, "lap-2"))
        self.assertFalse(plan_observed(cameras, {"A", "B"}, "lap-3"))
        cameras[0]["projects"] = False
        self.assertFalse(plan_observed(cameras, {"A", "B"}, "custom"))


class ZoneDeliveryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.config = configuration()
        self.counter = Occupancy(self.config)
        self.engine = Engine(self.root / "project.json")
        self.engine.config = self.config
        self.engine.state.update(session="abcdef0123456789", t=0)
        notifier.save(self.root, dict(enabled=True, user="sender@example.invalid", password="synthetic",
                                     recipients=["receiver@example.invalid"]))
        self.smtp = self.enterContext(patch.object(notifier, "_send"))
        self.addCleanup(self.engine.notifications.join)

    def update(self, t, count=2, valid=True):
        data = self.counter.update(people(count), t, observation_valid=valid)
        self.engine.state["t"] = t
        self.engine.dispatch_alerts({}, data)
        self.assertTrue(self.engine.notifications.join(5))
        return data

    def rows(self):
        with closing(business_data.connect(self.engine.config_path)) as db:
            return db.execute("SELECT id,pico,duracion,estado FROM incidentes ORDER BY inicio").fetchall()

    def test_many_dispatches_update_one_incident_and_one_durable_original(self):
        first = self.update(0)["zones"][0]["episodeId"]
        self.update(1.999)
        self.assertEqual(self.rows(), [])
        for t in (2, 3, 10, 100, 200):
            self.update(t, 5)
        expected = "abcdef0123456789:zona:plan:custom:" + first
        self.assertEqual(self.rows(), [(expected, 5, 200, "pendiente")])
        with closing(business_data.connect(self.engine.config_path)) as db:
            self.assertEqual(db.execute("SELECT incident_id,notification_kind,status,attempts FROM incident_notifications").fetchall(),
                             [(expected, "original", "sent", 1)])
        self.smtp.assert_called_once()

    def test_second_episode_allows_second_original_notification(self):
        self.update(0)
        self.update(2)
        self.update(3, 0)
        self.update(4)
        self.update(6)
        self.assertEqual(len(self.rows()), 2)
        self.assertNotEqual(self.rows()[0][0], self.rows()[1][0])
        self.assertEqual(self.smtp.call_count, 2)

    def test_missing_observation_does_not_create_another_incident(self):
        self.update(0)
        self.update(2)
        self.update(3, 0, False)
        self.update(100)
        self.update(101)
        self.assertEqual(self.rows()[0][2], 3)
        self.assertEqual(len(self.rows()), 1)
        self.smtp.assert_called_once()

    def test_reconstructed_engine_and_serialized_snapshot_do_not_resend(self):
        self.update(0)
        data = json.loads(json.dumps(self.update(2)))
        other = Engine(self.engine.config_path)
        other.state["session"] = self.engine.state["session"]
        other.dispatch_alerts({}, data)
        self.assertTrue(other.notifications.join(5))
        self.assertEqual(len(self.rows()), 1)
        self.smtp.assert_called_once()

    def test_two_plans_with_same_zone_id_name_and_even_episode_token_do_not_collide(self):
        self.counter.update(people(), 0)
        a = self.counter.update(people(), 2)
        config = {**copy.deepcopy(self.config), "planId": "lap-2"}
        other = Occupancy(config)
        other.update(people(), 0)
        b = other.update(people(), 2)
        self.assertNotEqual(a["zoneEpisodes"][0]["scope"], b["zoneEpisodes"][0]["scope"])
        b["zoneEpisodes"][0]["id"] = a["zoneEpisodes"][0]["id"]
        self.engine.dispatch_alerts({}, a, {"custom": a, "lap-2": b})
        self.assertTrue(self.engine.notifications.join(5))
        self.assertEqual(len(self.rows()), 2)
        self.assertEqual(self.smtp.call_count, 2)

    def test_reviewed_incident_is_not_reopened_or_split(self):
        self.update(0)
        self.update(2)
        with closing(business_data.connect(self.engine.config_path)) as db:
            business_data.actualizar_estado_incidente(db, self.rows()[0][0], "revisado")
        self.update(200, 8)
        self.assertEqual(self.rows()[0][1:], (2, 2, "revisado"))
        self.assertEqual(len(self.rows()), 1)
        self.smtp.assert_called_once()

    def test_transaction_failure_retries_without_half_created_incident(self):
        self.update(0)
        with patch.object(business_data, "registrar_incidente", side_effect=sqlite3.OperationalError("synthetic")):
            self.update(2)
        self.assertEqual(self.rows(), [])
        self.smtp.assert_not_called()
        self.update(3)
        self.assertEqual(len(self.rows()), 1)
        self.smtp.assert_called_once()

    def test_replay_and_report_preserve_episode_ids_and_legacy_payload(self):
        from replay import ReplayWriter, report_snapshot
        from live_reports import report_data
        self.update(0)
        data = self.update(2)
        data["flow"] = []
        writer = ReplayWriter(self.root, self.engine.state["session"], "tracking", [], self.config)
        writer.append({"t": 2, "analytics": data, "cameras": [], "levels": {"custom": data}})
        writer.meta["reportAnalytics"] = data
        writer.finish("ended")
        config, state, meta = report_snapshot(self.root, self.engine.state["session"], None)
        self.assertEqual(state["analytics"]["zoneEpisodes"], data["zoneEpisodes"])
        report = report_data(config, state, "occupancy")
        self.assertEqual(report["rows"][0][:2], ["Puerta", 2])
        self.assertEqual(meta["config"]["zones"][0]["id"], "z")


class ZoneReplayProjectionTests(unittest.TestCase):
    def test_projection_is_repeatable_scoped_and_missing_sample_is_not_zero_evidence(self):
        from replay_projection import current_projection
        config = configuration()
        config["plans"] = {"lap-2": {"zones": copy.deepcopy(config["zones"])}}
        config["cameras"] = [{"id": "C", "planId": "lap-2", "source": "synthetic",
                              "pairs": [[0, 0, 0, 0], [1, 0, 4, 0], [1, 1, 4, 4], [0, 1, 0, 4]]}]
        observation = {"id": "C", "people": [{"id": "a", "pixel": [.25, .25]},
                                               {"id": "b", "pixel": [.5, .5]}], "analysis": {}}
        samples = [{"t": t, "cameras": [copy.deepcopy(observation)] if t != 2 else []} for t in (0, 1, 2, 100, 101)]
        original = copy.deepcopy(samples)
        before = copy.deepcopy(config)
        meta = {"session": "abcd1234", "config": config}
        a = current_projection(meta, samples, config)
        b = current_projection(meta, samples, config)
        self.assertEqual(a, b)
        self.assertEqual(config, before)
        self.assertEqual(samples, original)
        episodes = [s["levels"]["lap-2"]["zoneEpisodes"][0] for s in a]
        self.assertEqual(len({e["id"] for e in episodes}), 1)
        self.assertTrue(all(e["scope"] == "plan:lap-2" for e in episodes))
        self.assertFalse(episodes[2]["observed"])
        self.assertEqual(episodes[3]["duration"], 1)
        self.assertEqual(episodes[4]["duration"], 2)
        # A frame can exist without a completed inference. Preserve that fact.
        samples[2]["cameras"] = [{**copy.deepcopy(observation), "observed": False}]
        missing_analysis = current_projection(meta, samples, config)
        e = missing_analysis[3]["levels"]["lap-2"]["zoneEpisodes"][0]
        self.assertEqual(e["duration"], 1)
        self.assertIsNone(e["end"])


class ZonePipelineTests(unittest.TestCase):
    def test_engine_pipeline_partial_sources_preserve_episode_and_session_end_closes_it(self):
        import cv2
        import numpy as np
        from types import SimpleNamespace
        from replay import manifest

        class Capture:
            def __init__(self, samples):
                self.samples = iter(samples)
            def isOpened(self): return True
            def set(self, *args): return True
            def get(self, key):
                return 5 if key == cv2.CAP_PROP_FPS else 5
            def read(self):
                value = next(self.samples, None)
                return (value is not None, value)
            def grab(self): return True
            def release(self): pass

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = configuration()
            config["zones"][0]["points"] = [[0, 0], [12, 0], [12, 8], [0, 8]]
            config["zones"][0]["rule"]["dwell"] = 0
            config.update(appearanceMemory=False,identityFinalize=False,clutterFilter=False)
            config["cameras"] = [{"id": cid, "source": cid + ".synthetic", "planId": "custom",
                "x": 1, "y": 1, "offset": 0, "links": [], "height": 4,
                "pairs": [[0, 0, 0, 0], [1, 0, 12, 0], [1, 1, 12, 8], [0, 1, 0, 8]]} for cid in ("C", "D")]
            engine = Engine(root / "project.json")
            engine.configure(config)
            engine.state.update(session="abcd1234", status="running")
            notifier.save(root, dict(enabled=True, user="sender@example.invalid", password="synthetic",
                                     recipients=["receiver@example.invalid"]))
            frame = np.zeros((240, 320, 3), dtype=np.uint8)
            captures = [Capture([frame.copy()] * 5), Capture([frame.copy()] * 2)]
            detector = SimpleNamespace(detectar=lambda frame: [SimpleNamespace(x=100, y=80, confianza=.9)])
            track=SimpleNamespace(id=1,posicion=(100,80),score=.9,ultima_caja=None,apariencia=None)
            tracker=SimpleNamespace(tracks_activos=[track],tracks_perdidos=[],actualizar=lambda *args:([track],[],[]))
            motor=SimpleNamespace(events=[],min_visible=None,necesita_vista=lambda *args:False,resumen=lambda:{'engine':'synthetic'},
                update=lambda observations,t,**kw:[{**o,'id':o['camera']+':1','association':'synthetic','history':[],
                    'confirmed':True,'duplicate':False} for o in observations])
            with patch.object(cv2, "VideoCapture", side_effect=captures), \
                 patch('tracking.BoTSortPuntos',return_value=tracker), \
                 patch('identity.crear_motor_identidad',return_value=motor), \
                 patch('following.reid.OSNetEmbedder',return_value=SimpleNamespace(available=True,name='synthetic',dimension=256)), \
                 patch.object(engine, "load_detector", return_value=detector), \
                 patch.object(engine.stop_event, "wait", return_value=False), \
                 patch.object(notifier, "_send") as smtp:
                engine.run(copy.deepcopy(config), {"detector": "yolo","performance":"precise"})
                self.assertTrue(engine.notifications.join(5))
            self.assertEqual(engine.state["status"], "ended", engine.state.get("error"))
            samples = [json.loads(s) for s in (root / "data/replays/abcd1234/samples.jsonl").read_text().splitlines()]
            episodes = [s["analytics"]["zoneEpisodes"] for s in samples]
            self.assertTrue(all(len(e) == 1 for e in episodes))
            self.assertEqual(len({e[0]["id"] for e in episodes}), 1)
            self.assertFalse(episodes[-1][0]["observed"])
            self.assertIsNone(episodes[-1][0]["end"])
            final = manifest(root, "abcd1234")["reportAnalytics"]["zoneEpisodes"][0]
            self.assertEqual(final["reason"], "session_ended")
            self.assertEqual(final["end"], final["last"])
            with closing(business_data.connect(engine.config_path)) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM incidentes").fetchone()[0], 1)
            smtp.assert_called_once()


if __name__ == "__main__":
    unittest.main()
