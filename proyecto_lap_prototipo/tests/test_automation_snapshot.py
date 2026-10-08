import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live_server import Engine


class AutomationSnapshotTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.engine = Engine(Path(temp.name) / "project.json")
        self.engine.project_id = "synthetic-project"
        individual = {"id": "INDIVIDUAL-SECRET", "point": [1, 2], "box": [1, 2, 3, 4],
                      "appearance": "COLOR-SECRET", "history": [[1, 2]]}
        forbidden = {"people": [individual], "points": [individual], "history": [individual],
                     "appearance": individual, "colorSignature": "COLOR-SECRET", "frames": "IMAGE-SECRET",
                     "identityMemory": individual, "associations": individual, "source": "rtsp://user:SECRET@host"}
        aggregate = {**forbidden, "count": 7, "mappedCount": 4,
                     "zones": [{**forbidden, "id": "zone-a", "count": 4, "alert": True}],
                     "zoneEpisodes": [{**forbidden, "id": "episode-a", "start": 0, "end": None, "peak": 7}],
                     "flow": [{**forbidden, "name": "door", "entries": 5, "exits": 2}]}
        self.engine.config.update({**forbidden, "testRun": True,
                                   "cameras": [{**forbidden, "id": "camera-a", "name": "synthetic"}]})
        self.engine.state.update({**forbidden, "session": "session-a", "testRun": True, "analytics": aggregate,
            "levelAnalytics": {"floor-a": copy.deepcopy(aggregate)},
            "cameraAnalytics": {"camera-a": {**forbidden, "occupancy": copy.deepcopy(aggregate),
                "map": copy.deepcopy(aggregate), "dense": {**forbidden, "count": 9, "status": "ready"},
                "crossings": [{**forbidden, "id": "door-a", "entries": 5, "exits": 2}],
                "avie": {**forbidden, "tracks": 3, "state": "dense"}}},
            "totals": {**forbidden, "identities": 12}, "series": [{**forbidden, "t": 1, "count": 7}]})

    def test_keeps_safe_aggregates_session_and_test_run(self):
        snapshot = self.engine.automation_snapshot()
        self.assertEqual(snapshot["projectId"], "synthetic-project")
        state = snapshot["state"]
        self.assertEqual(state["session"], "session-a")
        self.assertTrue(state["testRun"])
        self.assertEqual(state["analytics"]["mappedCount"], 4)
        self.assertEqual(state["analytics"]["zoneEpisodes"][0]["id"], "episode-a")
        self.assertEqual(state["cameraAnalytics"]["camera-a"]["dense"], {"count": 9, "status": "ready"})
        self.assertEqual(state["cameraAnalytics"]["camera-a"]["crossings"][0]["entries"], 5)
        self.assertEqual(state["totals"], {"identities": 12})

    def test_recursive_projection_excludes_every_individual_field_and_secret(self):
        snapshot = self.engine.automation_snapshot()
        forbidden = {"people", "points", "box", "point", "history", "appearance", "colorSignature",
                     "frames", "identityMemory", "associations", "source"}
        def inspect(value):
            if isinstance(value, dict):
                self.assertFalse(forbidden.intersection(value))
                for child in value.values():
                    inspect(child)
            elif isinstance(value, list):
                for child in value:
                    inspect(child)
        inspect(snapshot)
        serialized = json.dumps(snapshot)
        self.assertNotIn("SECRET", serialized)
        self.assertNotIn("INDIVIDUAL", serialized)

    def test_nested_payload_in_allowed_scalar_is_not_copied(self):
        self.engine.state["cameraAnalytics"]["camera-a"]["avie"]["tracks"] = {"id": "INDIVIDUAL"}
        self.engine.state["totals"]["identities"] = ["INDIVIDUAL"]
        snapshot = self.engine.automation_snapshot()
        self.assertNotIn("tracks", snapshot["state"]["cameraAnalytics"]["camera-a"]["avie"])
        self.assertNotIn("identities", snapshot["state"]["totals"])

    def test_result_does_not_share_mutable_structures_with_engine(self):
        snapshot = self.engine.automation_snapshot()
        snapshot["state"]["analytics"]["zones"][0]["count"] = 0
        self.assertEqual(self.engine.state["analytics"]["zones"][0]["count"], 4)

    def test_individual_identifier_cannot_replace_an_aggregate_count(self):
        self.engine.state["totals"]["identities"] = "INDIVIDUAL-SECRET"
        self.engine.state["cameraAnalytics"]["camera-a"]["avie"]["tracks"] = "INDIVIDUAL-SECRET"
        self.assertNotIn("SECRET", json.dumps(self.engine.automation_snapshot()))
