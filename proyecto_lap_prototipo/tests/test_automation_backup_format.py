"""Hostile ZIP metadata and contents are synthetic, never extracted by name."""
import io
import json
import sqlite3
import stat
import sys
import tempfile
import threading
import unittest
import warnings
import zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from automation import LIMA
from automation_artifacts import fingerprint
from automation_backup_format import (MANIFEST, SQLITE_HEADER, CheckedZipFile,
                                      verify_backup_bytes, write_archive)
from task_control import budget, Cancelled


class BackupFormatTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.files = {"projects/index.json": b'{"active":"p-test","projects":[{"id":"p-test"}]}',
                      "projects/p-test.json": b'{"airport":"Synthetic"}'}
        target = self.root / "synthetic.zip"
        self.now = datetime(2026, 10, 1, 2, tzinfo=LIMA)
        write_archive(target, self.files, self.now)
        self.data = target.read_bytes()
        with zipfile.ZipFile(io.BytesIO(self.data)) as archive:
            self.entries = {name: archive.read(name) for name in archive.namelist()}

    def pack(self, entries, extras=()):
        output = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)  # Intentional duplicate-member fixture.
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
                for name, data in [*entries.items(), *extras]:
                    archive.writestr(name, data)
        return output.getvalue()

    def manifested(self, files):
        manifest = json.loads(self.entries[MANIFEST])
        manifest["files"] = sorted(files)
        manifest["sha256"] = {name: fingerprint(data)[0] for name, data in files.items()}
        return self.pack({**files, MANIFEST: json.dumps(manifest).encode()})

    def test_current_version_validates_and_date_identity_is_checked(self):
        self.assertTrue(verify_backup_bytes(self.data, "2026-10-01"))
        self.assertFalse(verify_backup_bytes(self.data, "2026-10-02"))

    def test_altered_member_with_original_manifest_is_rejected(self):
        entries = {**self.entries, "projects/p-test.json": b'{"airport":"altered"}'}
        self.assertFalse(verify_backup_bytes(self.pack(entries)))

    def test_altered_manifest_metadata_and_unsupported_version_are_rejected(self):
        changes = [{"format": "other"}, {"schema_version": 1}, {"schema_version": True},
                   {"scope": "system"}, {"created": "2026-10-01"}, {"created": None},
                   {"sha256": {}}, {"files": []}, {"unapproved": "extra payload"}]
        for change in changes:
            with self.subTest(change=change):
                manifest = {**json.loads(self.entries[MANIFEST]), **change}
                entries = {**self.entries, MANIFEST: json.dumps(manifest).encode()}
                self.assertFalse(verify_backup_bytes(self.pack(entries)))

    def test_manifest_missing_or_invalid_json_is_rejected(self):
        for manifest in (None, b"{", b"[]", b'{"format":"a","format":"b"}'):
            entries = dict(self.entries)
            if manifest is None:
                entries.pop(MANIFEST)
            else:
                entries[MANIFEST] = manifest
            with self.subTest(manifest=manifest):
                self.assertFalse(verify_backup_bytes(self.pack(entries)))

    def test_unlisted_extra_member_is_rejected(self):
        self.assertFalse(verify_backup_bytes(self.pack({**self.entries, "projects/p-extra.json": b"{}"})))

    def test_duplicate_members_and_duplicate_manifest_are_rejected(self):
        for name in ("projects/p-test.json", MANIFEST):
            with self.subTest(name=name):
                self.assertFalse(verify_backup_bytes(self.pack(self.entries, [(name, self.entries[name])])))

    def test_windows_case_collision_is_rejected(self):
        self.assertFalse(verify_backup_bytes(self.manifested({**self.files, "projects/P-test.json": b"{}"})))

    def test_internal_paths_are_canonical_even_with_consistent_manifest_hashes(self):
        paths = ["../outside.json", "projects/../outside.json", "projects\\p-test.json",
                 "/projects/p-test.json", "C:/projects/p-test.json", "projects/p-test.json:stream",
                 "projects/sub/p-test.json", "projects//p-test.json", "projects/NUL.json",
                 "projects/p-test.json ", "projects/./p-test.json", "projects/p-test\x00.json"]
        for path in paths:
            with self.subTest(path=path):
                self.assertFalse(verify_backup_bytes(self.manifested({**self.files, path: b"{}"})))
        self.assertEqual(list(self.root.iterdir()), [self.root / "synthetic.zip"])

    def test_symlink_directory_and_special_file_semantics_are_rejected(self):
        for mode in (stat.S_IFLNK, stat.S_IFDIR, stat.S_IFIFO):
            entries = dict(self.entries)
            value = entries.pop("projects/p-test.json")
            info = zipfile.ZipInfo("projects/p-test.json")
            info.create_system = 3
            info.external_attr = (mode | 0o600) << 16
            with self.subTest(mode=mode):
                self.assertFalse(verify_backup_bytes(self.pack(entries, [(info, value)])))

    def test_crc_corruption_is_rejected(self):
        data = bytearray(self.pack(self.entries))
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            info = archive.getinfo("projects/p-test.json")
            start = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
        data[start] ^= 1
        self.assertFalse(verify_backup_bytes(bytes(data)))

    def test_truncated_or_non_zip_bytes_are_rejected(self):
        for data in (self.data[:-25], b"PK synthetic invalid", b"", b"not ZIP"):
            with self.subTest(size=len(data)):
                self.assertFalse(verify_backup_bytes(data))

    def test_index_references_and_json_are_checked_after_hashes(self):
        cases = [
            {**self.files, "projects/index.json": b'{"active":"p-missing","projects":[{"id":"p-missing"}]}'},
            {**self.files, "projects/p-test.json": b"invalid JSON"},
            {**self.files, "projects/p-test.json": b"[]"},
            {**self.files, "projects/unindexed.json": b"{}"},
        ]
        for files in cases:
            with self.subTest(files=files):
                self.assertFalse(verify_backup_bytes(self.manifested(files)))

    def test_embedded_sqlite_requires_integrity_not_just_correct_hash(self):
        files = {**self.files, "projects/p-test.negocios.sqlite": SQLITE_HEADER + b"\0" * 300}
        self.assertFalse(verify_backup_bytes(self.manifested(files)))
        database = self.root / "valid.sqlite"
        with sqlite3.connect(database) as db:
            db.execute("CREATE TABLE sample(value TEXT)")
            db.execute("INSERT INTO sample VALUES ('synthetic')")
        db.close()
        files["projects/p-test.negocios.sqlite"] = database.read_bytes()
        self.assertTrue(verify_backup_bytes(self.manifested(files)))

    def test_sqlite_sidecars_are_not_allowed_members_even_when_manifested(self):
        for suffix in ("-wal", "-shm", "-journal", ".tmp"):
            with self.subTest(suffix=suffix):
                self.assertFalse(verify_backup_bytes(self.manifested(
                    {**self.files, "projects/p-test.negocios.sqlite" + suffix: b"synthetic"})))

    def test_cancellation_during_crc_verification_propagates(self):
        event = threading.Event()
        original = zipfile.ZipExtFile.read
        calls = []
        def read(source, *args, **kwargs):
            data = original(source, *args, **kwargs)
            calls.append(1)
            event.set()
            return data
        with patch.object(zipfile.ZipExtFile, "read", new=read):
            with self.assertRaises(Cancelled), budget(event, 60):
                verify_backup_bytes(self.data)
        self.assertEqual(len(calls), 1)
        self.assertTrue(verify_backup_bytes(self.data))
