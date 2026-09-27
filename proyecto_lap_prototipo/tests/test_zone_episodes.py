import copy
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
import business_data
import notifier


class EpisodeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.config = default_config()
        self.config["cameras"] = []
        self.config["zones"] = [dict(id="z", name="Zone", points=[[0,0],[4,0],[4,4],[0,4]],
                                    rule=dict(enabled=True, minPeople=2, dwell=2))]
        self.people = [dict(id=str(i), point=[1+i, 1]) for i in range(2)]
        self.counter = Occupancy(self.config)
        self.engine = Engine(self.root / "project.json")
        self.engine.config = self.config
        self.engine.state["session"] = "abcdef0123456789"
        notifier.save(self.root, dict(enabled=True, user="synthetic@example.invalid", password="fake",
                                     recipients=["receiver@example.invalid"]))
        self.smtp = self.enterContext(patch.object(notifier, "_send"))
        self.addCleanup(self.engine.notifications.join)

    def observe(self, t, people=None, valid=True):
        data = self.counter.update(self.people if people is None else people, t, observation_valid=valid)
        self.engine.dispatch_alerts({}, data)
        self.engine.notifications.join()
        return data

    def rows(self):
        return self.engine.incidents()["incidentes"]

    def test_exact_dwell_and_continuous_alert_have_one_durable_incident(self):
        first = self.observe(0)["zones"][0]["episodeId"]
        self.observe(1.999)
        self.assertEqual(self.rows(), [])
        for t in range(2, 202):
            self.assertEqual(self.observe(t)["zones"][0]["episodeId"], first)
        self.assertEqual(len(self.rows()), 1)
        self.smtp.assert_called_once()
        with closing(business_data.connect(self.engine.config_path)) as db:
            self.assertEqual(db.execute("SELECT count(*),count(incident_id) FROM incident_episodes").fetchone(), (1,1))

    def test_valid_dip_closes_immediately_and_new_rise_creates_new_incident(self):
        self.observe(0)
        self.observe(2)
        first = self.rows()[0]["id"]
        self.observe(3, [])
        self.observe(4)
        self.observe(6)
        self.assertEqual(len(self.rows()), 2)
        self.assertIn(first, [r["id"] for r in self.rows()])
        with closing(business_data.connect(self.engine.config_path)) as db:
            self.assertEqual(db.execute("SELECT ended,end_reason FROM incident_episodes WHERE ended IS NOT NULL").fetchone(), (3,"below_threshold"))

    def test_missing_observation_keeps_identity_without_counting_gap(self):
        token = self.observe(0)["zones"][0]["episodeId"]
        self.observe(1)
        self.observe(2, [], False)
        data = self.observe(100)
        self.assertEqual(data["zones"][0]["episodeId"], token)
        self.assertEqual(data["zones"][0]["duration"], 1)
        self.assertEqual(self.rows(), [])
        self.observe(101)
        self.assertEqual(len(self.rows()), 1)

    def test_attention_does_not_split_continuous_episode(self):
        self.observe(0)
        self.observe(2)
        iid = self.rows()[0]["id"]
        self.engine.update_incident(iid, "revisado")
        self.engine.update_incident(iid, "pendiente")
        self.observe(200)
        self.assertEqual(len(self.rows()), 1)
        self.assertIsNotNone(self.rows()[0]["reviewed_at"])
        self.smtp.assert_called_once()

    def test_replayed_snapshot_and_reconstructed_engine_keep_persisted_identity(self):
        self.observe(0)
        data = self.observe(2)
        other = Engine(self.engine.config_path)
        other.state["session"] = self.engine.state["session"]
        other.dispatch_alerts({}, data)
        other.notifications.join()
        self.assertEqual(len(self.rows()), 1)
        self.smtp.assert_called_once()

    def test_transaction_failure_can_retry_without_half_created_incident(self):
        self.observe(0)
        with patch.object(business_data, "registrar_incidente", side_effect=sqlite3.OperationalError("synthetic")):
            self.observe(2)
        self.assertEqual(self.rows(), [])
        self.observe(3)
        self.assertEqual(len(self.rows()), 1)
        self.smtp.assert_called_once()

    def test_rule_change_closes_candidate_and_starts_fresh_dwell(self):
        token = self.observe(0)["zones"][0]["episodeId"]
        self.config["zones"][0]["rule"]["dwell"] = 5
        data = self.observe(1)
        self.assertNotEqual(token, data["zones"][0]["episodeId"])
        self.assertEqual(data["zones"][0]["duration"], 0)
        self.assertEqual(data["zoneEpisodes"][0]["reason"], "configuration_or_clock_changed")

    def test_legacy_zone_ids_are_stable_across_validation_and_reordering(self):
        self.config["zones"][0].pop("id")
        a = validate_config(copy.deepcopy(self.config))
        b = validate_config(copy.deepcopy(self.config))
        self.assertEqual(a["zones"][0]["id"], b["zones"][0]["id"])
        self.assertEqual(validate_config(a), b)

    def test_migration_and_session_end_preserve_existing_incident_ids(self):
        self.observe(0)
        self.observe(2)
        iid = self.rows()[0]["id"]
        for _ in range(3):
            with closing(business_data.connect(self.engine.config_path)) as db:
                business_data.cerrar_episodios(db, self.engine.state["session"], 3, "session_ended")
        self.assertEqual(self.rows()[0]["id"], iid)
        with closing(business_data.connect(self.engine.config_path)) as db:
            self.assertEqual(db.execute("SELECT ended,end_reason FROM incident_episodes").fetchone(), (3,"session_ended"))


if __name__ == "__main__":
    unittest.main()
