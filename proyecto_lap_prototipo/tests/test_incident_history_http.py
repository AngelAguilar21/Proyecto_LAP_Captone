"""Local HTTP authorization and explicit legacy review; all data is temporary."""
import http.client
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import auth
import business_data
import notifier
from live_server import Engine, Handler, ThreadingHTTPServer


class IncidentHistoryHTTPTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="history-http-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "project.json"
        self.engine = Engine(self.path)
        self.engine.project_id = "project-a"
        self.smtp = self.enterContext(patch.object(notifier, "_send", side_effect=AssertionError("SMTP forbidden")))
        self.addCleanup(self.smtp.assert_not_called)
        with closing(sqlite3.connect(business_data.path_for(self.path))) as db, db:
            db.executescript(business_data.ESQUEMA)
            db.execute("INSERT INTO incidentes VALUES ('legacy','aglomeracion','zone','C',0,8,10,'pendiente','{}',100,200)")
        # Login uses synthetic credentials in a temporary usuarios.local.json.
        auth.crear(self.root, "synthetic-operator", "synthetic-password", "operador")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.engine = self.engine
        self.thread = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=.01), daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)
        self.data = {"id": "legacy", "never_attended": True, "projectId": "project-a"}
        self.operator = self.engine.sessions.abrir("synthetic-operator", "operador")
        self.admin = self.engine.sessions.abrir("synthetic-admin", "administrador")

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)
        self.assertFalse(self.thread.is_alive())

    def request(self, data=None, session=None, token=True, origin=None, method="POST", path="/api/incidents/history"):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-LAP-Token"] = self.engine.token
        if session:
            headers["X-LAP-Session"] = session
        if origin:
            headers["Origin"] = origin
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        try:
            connection.request(method, path, json.dumps(self.data if data is None else data) if method == "POST" else None, headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def history(self):
        return self.engine.incidents()["incidentes"][0]

    def test_requires_csrf_trusted_origin_and_authenticated_session(self):
        for args, status in (({"token": False, "session": self.operator}, 403),
                             ({"origin": "https://external.example.invalid", "session": self.operator}, 403),
                             ({}, 401), ({"session": "invalid"}, 401)):
            with self.subTest(args=args):
                self.assertEqual(self.request(**args)[0], status)
                self.assertFalse(self.history()["review_history_known"])

    def test_bootstrap_without_accounts_does_not_allow_anonymous_history_assertion(self):
        with patch.object(auth, "hay_usuarios", return_value=False):
            self.assertEqual(self.request()[0], 401)
        self.assertFalse(self.history()["review_history_known"])

    def test_operator_can_validate_never_attended_and_listing_exposes_safe_history(self):
        status, result = self.request(session=self.operator)
        self.assertEqual(status, 200)
        row = result["incidentes"][0]
        self.assertTrue(row["review_history_known"])
        self.assertIsInstance(row["history_validated_at"], float)
        self.assertIsNone(row["reviewed_at"])
        self.assertIsNone(row["escalated_at"])
        self.assertEqual(row["estado"], "pendiente")
        self.assertEqual(self.request(session=self.operator)[0], 400)
        self.assertEqual(self.history(), row)

    def test_administrator_can_confirm_previous_attention_as_with_incident_review(self):
        status, result = self.request({**self.data, "never_attended": False}, session=self.admin)
        self.assertEqual(status, 200)
        row = result["incidentes"][0]
        self.assertEqual(row["estado"], "revisado")
        self.assertEqual(row["reviewed_at"], row["history_validated_at"])
        self.assertIsNotNone(row["reviewed_at"])
        self.assertEqual(self.request({"id": "legacy", "estado": "pendiente"}, session=self.admin, path="/api/incidents")[0], 200)
        self.assertEqual(self.history()["reviewed_at"], row["reviewed_at"])

    def test_unknown_role_cannot_validate_history(self):
        unknown = self.engine.sessions.abrir("synthetic-other", "unknown-role")
        self.assertEqual(self.request(session=unknown)[0], 403)
        self.assertFalse(self.history()["review_history_known"])

    def test_boolean_and_explicit_matching_project_are_required(self):
        invalid = [{**self.data, "never_attended": "true"}, {**self.data, "never_attended": 1},
                   {"id": "legacy", "projectId": "project-a"}, {"id": "legacy", "never_attended": True},
                   {**self.data, "projectId": "project-b"}, {**self.data, "projectId": None}]
        for data in invalid:
            with self.subTest(data=data):
                self.assertEqual(self.request(data, session=self.operator)[0], 400)
                self.assertFalse(self.history()["review_history_known"])

    def test_get_does_not_validate_or_modify_history(self):
        self.assertEqual(self.request(method="GET", session=self.operator)[0], 404)
        self.assertFalse(self.history()["review_history_known"])
        self.assertIsNone(self.history()["history_validated_at"])


if __name__ == "__main__":
    unittest.main()
