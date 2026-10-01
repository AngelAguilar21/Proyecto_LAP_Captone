"""HTTP regressions from the candidate audit; stores and services are synthetic."""
import copy
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import live_server
import auth
import business_data
import notifier
import projects
from shutdown_control import ManagedHTTPServer, stop_server


class AuditHTTPTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="audit-http-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.enterContext(patch.object(live_server, "ROOT", self.root))
        self.enterContext(patch.object(live_server, "CONFIG_PATH", self.root / "config/live.local.json"))
        smtp = self.enterContext(patch.object(notifier, "_send", side_effect=AssertionError("SMTP forbidden")))
        self.addCleanup(smtp.assert_not_called)
        self.enterContext(patch.object(live_server.Engine, "load_detector", side_effect=AssertionError("Inference forbidden")))
        self.engine = live_server.Engine()
        self.engine.configure(copy.deepcopy(self.engine.config))
        self.server = ManagedHTTPServer(("127.0.0.1", 0), live_server.Handler)
        self.server.engine = self.engine
        self.worker = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=.01), daemon=True)
        self.worker.start()
        self.addCleanup(self.close_server)
        self.session = None

    def close_server(self):
        self.server.shutdown()
        self.worker.join(3)
        self.assertFalse(self.worker.is_alive())
        self.assertTrue(stop_server(self.server, timeout=3))
        self.server.server_close()

    def request(self, path, data=None, *, authenticated=True):
        headers = {"Content-Type": "application/json", "X-LAP-Token": self.engine.token}
        if authenticated and self.session:
            headers["X-LAP-Session"] = self.session
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        try:
            connection.request("GET" if data is None else "POST", path,
                               None if data is None else json.dumps(data), headers)
            response = connection.getresponse()
            raw = response.read()
            return response.status, json.loads(raw) if "application/json" in response.getheader("Content-Type", "") else raw
        finally:
            connection.close()

    def login(self):
        credentials = {"usuario": "synthetic-operator", "clave": "synthetic-password"}
        self.assertEqual(self.request("/api/auth", {"accion": "crear", **credentials})[0], 200)
        status, body = self.request("/api/auth", {"accion": "login", **credentials})
        self.assertEqual(status, 200)
        self.session = body["sesion"]

    def test_project_switch_during_save_never_writes_the_new_project(self):
        self.login()
        a = self.engine.new_project("Synthetic A")["active"]
        self.engine.configure(copy.deepcopy(self.engine.config))
        b = self.engine.new_project("Synthetic B")["active"]
        self.engine.configure(copy.deepcopy(self.engine.config))
        self.engine.open_project(a)
        paths = [projects.project_path(self.root, pid) for pid in (a, b)]
        paths += [business_data.path_for(p) for p in paths]
        before = {p: p.read_bytes() for p in paths}
        draft = copy.deepcopy(self.engine.config)
        draft["airport"] = "A draft must not reach B"
        entered, release = threading.Event(), threading.Event()
        original = self.engine.configure
        result, errors = [], []

        def paused(config, *args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise AssertionError("Test barrier not released")
            return original(config, *args, **kwargs)

        def write():
            try:
                result.append(self.request(f"/api/config?project={a}", draft))
            except BaseException as exc:
                errors.append(exc)

        with patch.object(self.engine, "configure", paused):
            writer = threading.Thread(target=write, daemon=True)
            writer.start()
            try:
                self.assertTrue(entered.wait(3))
                self.assertEqual(self.request("/api/projects", {"action": "open", "id": b})[0], 200)
            finally:
                release.set()
                writer.join(5)
            self.assertFalse(writer.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(result[0][0], 400)
        self.assertEqual(self.engine.project_id, b)
        self.assertEqual(self.engine.config["airport"], "Synthetic B")
        self.assertEqual({p: p.read_bytes() for p in paths}, before)
        # Normal save still reaches exactly the selected project.
        normal = copy.deepcopy(self.engine.config)
        normal["airport"] = "B saved normally"
        self.assertEqual(self.request(f"/api/config?project={b}", normal)[0], 200)
        self.assertEqual(json.loads(paths[1].read_text())["airport"], "B saved normally")
        self.assertEqual(paths[0].read_bytes(), before[paths[0]])

    def test_auth_bootstrap_and_authorized_operation_controls(self):
        self.assertFalse(auth.path_for(self.engine.settings_root).exists())
        self.assertFalse(self.request("/api/auth")[1]["configurado"])
        self.login()
        config = copy.deepcopy(self.engine.config)
        config["airport"] = "Authorized synthetic save"
        before = self.engine.config_path.read_bytes()
        self.assertEqual(self.request("/api/config", config, authenticated=False)[0], 401)
        self.assertEqual(self.engine.config_path.read_bytes(), before)
        self.assertEqual(self.request("/api/config", config)[0], 200)
        self.assertEqual(json.loads(self.engine.config_path.read_text())["airport"], config["airport"])

    def test_corrupt_or_invalid_users_cannot_bootstrap_or_mutate(self):
        self.login()
        path = auth.path_for(self.engine.settings_root)
        invalid = ["{broken", "[]", "null", '{}', '{"usuarios":{}}',
                   '{"usuarios":[{}]}', '{"usuarios":[{"usuario":"x","rol":"operador","sal":"bad","hash":"bad"}]}']
        config = copy.deepcopy(self.engine.config)
        config["airport"] = "Must never persist"
        for contents in invalid:
            with self.subTest(contents=contents):
                path.write_text(contents, encoding="utf-8")
                before = {p: p.read_bytes() for p in (self.root / "config").rglob("*") if p.is_file()}
                for endpoint, payload in [("/api/config", config), ("/api/auth", {"accion": "crear", "usuario": "intruder", "clave": "synthetic-password"})]:
                    status, body = self.request(endpoint, payload, authenticated=False)
                    self.assertIn(status, (400, 503))
                    self.assertIn("usuarios", body["error"].lower())
                self.assertEqual(self.request("/api/auth")[0], 503)
                self.assertEqual({p: p.read_bytes() for p in (self.root / "config").rglob("*") if p.is_file()}, before)

    def test_unreadable_users_fail_closed_without_replacing_store(self):
        self.login()
        users = auth.path_for(self.engine.settings_root)
        original = Path.read_text
        before = users.read_bytes(), self.engine.config_path.read_bytes()
        def unreadable(path, *args, **kwargs):
            if path == users:
                raise PermissionError("synthetic unreadable users")
            return original(path, *args, **kwargs)
        with patch.object(Path, "read_text", unreadable):
            status, body = self.request("/api/config", copy.deepcopy(self.engine.config), authenticated=False)
            self.assertIn(status, (400, 503))
            self.assertIn("usuarios", body["error"].lower())
            self.assertNotIn("synthetic unreadable", body["error"])
        self.assertEqual((users.read_bytes(), self.engine.config_path.read_bytes()), before)

    def test_replay_routes_share_project_scope_without_mixing_projection(self):
        from replay import ReplayWriter
        self.login()
        a = self.engine.project_id
        b = self.engine.new_project("Replay project B")["active"]
        source = self.root / "synthetic-video.mp4"
        source.write_bytes(b"synthetic video bytes; decoder never invoked")
        config = copy.deepcopy(self.engine.config)
        config["cameras"] = [{"id":"C","source":str(source),"pairs":[]}]
        for sid, owner in (("abcd0101", a), ("abcd0102", b), ("abcd0103", None)):
            writer = ReplayWriter(self.root, sid, "unified", config["cameras"],
                                  {k:v for k,v in config.items() if k != "cameras"}, owner)
            writer.append({"t":1,"cameras":[{"id":"C","people":[]}]});writer.finish("ended")
        for owner, own, other in ((a,"abcd0101","abcd0102"), (b,"abcd0102","abcd0101")):
            self.assertEqual(self.request("/api/projects", {"action":"open","id":owner})[0],200)
            history = self.request("/api/replay/history")[1]
            self.assertIn(own, [row["session"] for row in history])
            self.assertNotIn(other, [row["session"] for row in history])
            for suffix in ("data", "data&projection=current", "video&camera=C"):
                route, _, query = suffix.partition("&")
                for sid, allowed in ((own, True), (other, False)):
                    with self.subTest(owner=owner, route=suffix, sid=sid):
                        status, body = self.request(f"/api/replay/{route}?session={sid}&{query}")
                        self.assertEqual(status, 200 if allowed else 400)
                        if allowed and route == "video":self.assertEqual(body, source.read_bytes())
            # Existing history policy exposes unknown legacy as unknown. Reading
            # it must not assign a project; current reprojection needs an owner.
            self.assertEqual(self.request("/api/replay/data?session=abcd0103")[0],200)
            self.assertEqual(self.request("/api/replay/data?session=abcd0103&projection=current")[0],400)

    def test_calibration_check_and_config_share_video_and_plan_bounds(self):
        self.login()
        config = copy.deepcopy(self.engine.config)
        config.update(width=12,height=8,planId="custom")
        pairs = [[0,0,0,0],[1,0,12,0],[1,1,12,8],[0,1,0,8]]
        config["cameras"] = [{"id":"C","source":"synthetic.mp4","x":1,"y":1,"height":3,"pairs":pairs}]
        self.assertEqual(self.request("/api/config",config)[0],200)
        before = self.engine.config_path.read_bytes()
        context = {"width":12,"height":8,"planId":"custom","unit":"meters"}
        status, result = self.request("/api/calibration-check",{"pairs":pairs,"context":context})
        self.assertEqual(status,200)
        for label, changed in (("outside_plan", [[0,0,0,0],[1,0,12.5,0],[1,1,12.5,8],[0,1,0,8]]),
                               ("outside_video", [[-.1,0,0,0],[1,0,12,0],[1,1,12,8],[0,1,0,8]])):
            with self.subTest(label=label):
                draft = copy.deepcopy(config);draft["cameras"][0]["pairs"] = changed
                status, result = self.request("/api/calibration-check",{"pairs":changed,"context":context})
                self.assertEqual(status,400)
                self.assertIn("fuera",result["error"].lower())
                self.assertEqual(self.request("/api/config",draft)[0],400)
                self.assertEqual(draft["cameras"][0]["pairs"],changed)
                self.assertEqual(self.engine.config_path.read_bytes(),before)
        self.assertEqual(self.request("/api/calibration-check",{"pairs":pairs,"context":{**context,"width":11}})[0],400)
        self.assertEqual(self.engine.config_path.read_bytes(),before)

    def test_report_http_rejects_complete_line_truncation_without_publishing(self):
        from replay import ReplayWriter
        writer=ReplayWriter(self.root,'abcd0201','unified',[],self.engine.config,self.engine.project_id)
        for t,count in ((10,1),(20,3)):
            writer.append({'t':t,'cameras':[{'id':'C','analysis':None,'people':[{'id':str(i)} for i in range(count)]}]})
        writer.finish('ended')
        status, body=self.request('/api/report/session?session=abcd0201')
        self.assertEqual(status,200)
        self.assertEqual(body['evidenceIntegrity'],'verified')
        self.assertEqual(body['state']['series'],[{'t':10,'count':1},{'t':20,'count':3}])
        status, pdf=self.request('/api/report?session=abcd0201&kind=business&format=pdf')
        from automation_artifacts import verify_pdf
        self.assertEqual(status,200)
        self.assertTrue(verify_pdf(pdf))
        samples=writer.directory/'samples.jsonl'
        samples.write_bytes(samples.read_bytes().splitlines(keepends=True)[0])
        for route in ('/api/report/session','/api/report'):
            with self.subTest(route=route):
                status, body=self.request(route+'?session=abcd0201&kind=business&format=pdf')
                self.assertEqual(status,400)
                self.assertIsInstance(body,dict)
        self.assertFalse(list((self.root/'data/reports').rglob('*.pdf')))


if __name__ == "__main__":
    unittest.main()
