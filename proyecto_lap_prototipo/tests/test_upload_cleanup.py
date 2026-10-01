import hashlib
import io
import json
import os
import stat
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cleanup_fixtures import CleanupFixture
from live_server import Handler
from path_security import plain_path
from task_control import budget, Cancelled
import uploads


class UploadCleanupTests(CleanupFixture, unittest.TestCase):
    def test_complete_upload_publishes_random_name_sizes_hash_and_identity(self):
        path = self.upload()
        self.assertRegex(path.name, r"^[a-f0-9]{32}\.mp4$")
        marker = uploads.metadata_path(path)
        value = json.loads(marker.read_bytes())
        self.assertEqual(set(value), {"format", "version", "status", "path", "completed_at", "expected_size", "final_size", "identity", "sha256"})
        self.assertEqual((value["format"], value["version"], value["status"]), ("aerotrack-upload", 1, "completed"))
        self.assertEqual((value["path"], value["expected_size"], value["final_size"]), (path.name, 15, 15))
        self.assertEqual(value["sha256"], hashlib.sha256(b"synthetic-video").hexdigest())
        self.assertEqual(value["identity"], list(uploads.identity(path)))
        self.assertEqual(uploads.completed_fingerprint(path, self.root)[0], self.old)
        self.assertEqual({p.name for p in path.parent.iterdir()}, {path.name, marker.name})

    def test_invalid_suffix_and_size_rejected_before_creating_storage(self):
        for size, suffix in ((0, ".mp4"), (-1, ".mp4"), (True, ".mp4"), (1024**3+1, ".mp4"), (1, ".exe"), (1, ".mp4:ads")):
            with self.subTest(size=size, suffix=suffix), self.assertRaises(ValueError):
                uploads.receive(self.root, io.BytesIO(b"a"), size, suffix)
        self.assertFalse((self.root / "data").exists())

    def test_truncated_or_failed_source_removes_only_owned_part(self):
        folder = self.root / "data" / "uploads"
        folder.mkdir(parents=True)
        unknown = folder / "unknown.part"
        unknown.write_bytes(b"keep")
        for source in (io.BytesIO(b"short"), Mock(read=Mock(side_effect=OSError("disconnect")))):
            with self.subTest(source=type(source)), self.assertRaises((ValueError, OSError)):
                uploads.receive(self.root, source, 100, ".mp4")
            self.assertEqual(list(folder.iterdir()), [unknown])

    def test_fsync_failure_does_not_publish_completion_and_cleans_part(self):
        with patch.object(uploads.os, "fsync", side_effect=OSError("disk")), self.assertRaises(OSError):
            self.upload()
        self.assertEqual(list((self.root / "data" / "uploads").iterdir()), [])

    def test_short_disk_write_does_not_publish_completion(self):
        original = Path.open
        class ShortWrite:
            def __init__(self, file): self.file = file
            def __enter__(self): return self
            def __exit__(self, *args): self.file.close()
            def write(self, data): return self.file.write(data[:1])
        def open_file(path, mode="r", *args, **kwargs):
            file = original(path, mode, *args, **kwargs)
            return ShortWrite(file) if mode == "xb" else file
        with patch.object(Path, "open", open_file), self.assertRaises(OSError):
            self.upload()
        self.assertEqual(list((self.root / "data" / "uploads").iterdir()), [])

    def test_crash_after_final_replace_leaves_unknown_file_untouched_by_cleanup(self):
        replace = os.replace
        def crash_after_final(source, target):
            replace(source, target)
            if str(target).endswith(".mp4"):
                raise OSError("simulated crash before metadata")
        with patch.object(uploads.os, "replace", side_effect=crash_after_final), self.assertRaises(OSError):
            self.upload()
        path = next((self.root / "data" / "uploads").glob("*.mp4"))
        self.assertFalse(uploads.metadata_path(path).exists())
        self.assertEqual(self.decision(self.plan(), path).reason, "upload_completion_unknown")
        self.task.apply_cleanup(self.task.plan_cleanup(self.now, 30))
        self.assertEqual(path.read_bytes(), b"synthetic-video")

    def test_failure_during_marker_sync_or_publication_leaves_unknown_final(self):
        real_sync, real_replace = os.fsync, os.replace
        for boundary in ("sync", "replace"):
            calls = []
            def sync(fd):
                calls.append(fd)
                if boundary == "sync" and len(calls) == 2:
                    raise OSError("metadata disk failure")
                real_sync(fd)
            def replace(source, target):
                if boundary == "replace" and str(target).endswith(uploads.MARKER):
                    raise OSError("metadata publication failure")
                real_replace(source, target)
            with self.subTest(boundary=boundary), patch.object(uploads.os, "fsync", side_effect=sync), patch.object(uploads.os, "replace", side_effect=replace), self.assertRaises(OSError):
                self.upload()
        self.assertFalse(list(self.root.rglob("*" + uploads.MARKER)))
        self.assertTrue(all(d.reason == "upload_completion_unknown" for d in self.plan().decisions))

    def test_existing_identity_collision_never_overwrites_existing_file(self):
        path = self.upload()
        before = self.snapshot()
        with patch.object(uploads.secrets, "token_hex", return_value=path.stem), self.assertRaises(ValueError):
            self.upload()
        self.assertEqual(self.snapshot(), before)

    def test_altered_marker_is_invalid_without_automatic_repair(self):
        path = self.upload()
        marker = uploads.metadata_path(path)
        original = marker.read_bytes()
        for changes in ({"status": "writing"}, {"path": "other.mp4"}, {"version": True}, {"expected_size": 14},
                        {"completed_at": float("nan")}, {"identity": []}, {"sha256": "bad"}, {"extra": "unexpected"}):
            with self.subTest(changes=changes):
                marker.write_text(json.dumps({**json.loads(original), **changes}))
                before = marker.read_bytes()
                with self.assertRaises(ValueError):
                    uploads.completed_fingerprint(path, self.root)
                self.assertEqual(marker.read_bytes(), before)

    def test_changed_bytes_even_with_updated_identity_fail_hash_validation(self):
        path = self.upload()
        path.write_bytes(b"different-video")
        marker = uploads.metadata_path(path)
        value = json.loads(marker.read_bytes())
        value["identity"] = uploads.identity(path)
        marker.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            uploads.completed_fingerprint(path, self.root)
        self.assertEqual(self.decision(self.plan(), path).disposition, "omitted")

    def test_substituted_file_invalidates_filesystem_identity(self):
        path = self.upload()
        replacement = path.with_suffix(".replacement")
        replacement.write_bytes(path.read_bytes())
        os.replace(replacement, path)
        with self.assertRaises(ValueError):
            uploads.completed_fingerprint(path, self.root)

    def test_marker_changed_during_validation_is_rejected(self):
        path = self.upload()
        original = uploads.file_fingerprint
        marker = uploads.metadata_path(path)
        def changed(file, *args, **kwargs):
            result = original(file, *args, **kwargs)
            if file == path:
                marker.write_bytes(marker.read_bytes() + b" ")
            return result
        with patch.object(uploads, "file_fingerprint", side_effect=changed), self.assertRaises(ValueError):
            uploads.completed_fingerprint(path, self.root)

    def test_hard_link_on_data_or_marker_is_not_eligible(self):
        for marker in (False, True):
            path = self.upload()
            file = uploads.metadata_path(path) if marker else path
            os.link(file, self.root / (file.name + ".link"))
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                uploads.completed_fingerprint(path, self.root)
            self.assertEqual(self.decision(self.plan(), path).disposition, "omitted")

    def test_file_changed_during_last_marker_read_is_rejected(self):
        path = self.upload()
        marker = uploads.metadata_path(path)
        original = uploads.file_fingerprint
        calls = []
        def changed(file, *args, **kwargs):
            result = original(file, *args, **kwargs)
            if file == marker:
                calls.append(file)
                if len(calls) == 2:
                    path.write_bytes(b"different-video")
            return result
        with patch.object(uploads, "file_fingerprint", side_effect=changed), self.assertRaises(ValueError):
            uploads.completed_fingerprint(path, self.root)

    def test_reparse_or_symlink_component_is_rejected_without_following(self):
        path = self.upload()
        original = Path.lstat
        for mode in (stat.S_IFLNK, None):
            def info(file, *args, **kwargs):
                if file == path.parent:
                    return SimpleNamespace(st_mode=mode or stat.S_IFDIR, st_file_attributes=0 if mode else 1024)
                return original(file, *args, **kwargs)
            with self.subTest(mode=mode), patch.object(Path, "lstat", info), self.assertRaises(ValueError):
                uploads.completed_fingerprint(path, self.root)
        self.assertTrue(path.exists())

    def test_paths_with_traversal_ads_or_outside_root_are_rejected(self):
        for path in (str(self.root / "data") + "/../uploads/a.mp4", str(self.root / "data/uploads/a.mp4") + ":ads",
                     self.root.parent / "outside.mp4", str(self.root / "data/uploads/a.mp4") + "\x00"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                plain_path(path, self.root)

    def test_readonly_validation_and_plan_do_not_change_filesystem(self):
        path = self.upload()
        before = self.snapshot()
        first = uploads.completed_fingerprint(path, self.root)
        self.assertEqual(uploads.completed_fingerprint(path, self.root), first)
        self.assertEqual(self.plan(), self.plan())
        self.assertEqual(self.snapshot(), before)

    def test_cancellation_cleans_own_part_and_releases_lease(self):
        event = threading.Event()
        source = io.BytesIO(b"a" * (uploads.CHUNK + 1))
        def read(size):
            event.set()
            return source.read(size)
        with self.assertRaises(Cancelled), budget(event, 60):
            uploads.receive(self.root, SimpleNamespace(read=read), uploads.CHUNK + 1, ".mp4", resources=self.engine.resources)
        self.assertEqual(list((self.root / "data" / "uploads").iterdir()), [])
        self.assertEqual(self.engine.resource_users, 0)

    def handler(self, content=b"synthetic", size=9):
        handler = Handler.__new__(Handler)
        handler.server = SimpleNamespace(engine=self.engine, closing=False)
        handler.path = "/api/upload?name=untrusted-original.mp4"
        handler.headers = {"Content-Length": str(size), "X-LAP-Token": self.engine.token}
        handler.rfile = io.BytesIO(content)
        handler.allowed = Mock(return_value=True)
        handler.send_data = Mock()
        return handler

    def test_http_endpoint_uses_durable_module_and_responds_only_after_marker(self):
        handler = self.handler()
        original = uploads.receive
        def receive(*args, **kwargs):
            source = args[1]
            read = source.read
            def leased_read(size):
                self.assertTrue(self.engine.resources.protected(self.root / "data/uploads"))
                return read(size)
            source.read = leased_read
            return original(*args, **kwargs)
        def response(code, value):
            self.assertEqual(code, 200)
            path = Path(value["path"])
            self.assertEqual(path.parent, self.root / "data/uploads")
            self.assertNotIn("untrusted", path.name)
            self.assertGreater(uploads.completed_fingerprint(path, self.root)[0], 0)
        handler.send_data.side_effect = response
        with patch("live_server.auth.hay_usuarios", return_value=False), patch.object(uploads, "receive", side_effect=receive) as called:
            handler.do_POST()
        called.assert_called_once()
        handler.send_data.assert_called_once()
        self.assertEqual(self.engine.resource_users, 0)

    def test_http_incomplete_upload_is_not_successful(self):
        handler = self.handler(b"short", 100)
        with patch("live_server.auth.hay_usuarios", return_value=False):
            handler.do_POST()
        self.assertEqual(handler.send_data.call_args.args[0], 400)
        self.assertEqual(list((self.root / "data/uploads").iterdir()), [])

    def test_http_authorization_still_blocks_upload_before_reception(self):
        handler = self.handler()
        handler.headers["X-LAP-Token"] = "wrong"
        with patch.object(uploads, "receive") as receive:
            handler.do_POST()
        receive.assert_not_called()
        self.assertEqual(handler.send_data.call_args.args[0], 403)


if __name__ == "__main__":
    unittest.main()
