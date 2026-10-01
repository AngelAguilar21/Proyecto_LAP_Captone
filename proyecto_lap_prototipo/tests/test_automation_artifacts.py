"""Artifact checks operate exclusively on generated PDFs and temporary paths."""
import io
import os
import stat
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from reportlab.pdfgen.canvas import Canvas

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from automation_artifacts import check_successes, fingerprint, read_artifact, safe_path, verify_pdf
from automation_reports import publish_pdf
from automation_store import AutomationStore
from resource_control import ResourceRegistry
from task_control import budget, Cancelled


def pdf_bytes(pages=1):
    output = io.BytesIO()
    canvas = Canvas(output, invariant=1)
    for page in range(pages):
        canvas.drawString(30, 100, f"Synthetic page {page}")
        canvas.showPage()
    canvas.save()
    return output.getvalue()


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "reports"
        self.root.mkdir()
        self.path = self.root / "report.pdf"
        self.store = AutomationStore(Path(temp.name) / "automation.sqlite")
        self.resources = ResourceRegistry(Path(temp.name))
        self.now = datetime(2026, 10, 1, tzinfo=timezone.utc)
        self.key = ("reports", "p", "2026-10-01")

    def success(self, path=None):
        data = pdf_bytes()
        self.path.write_bytes(data)
        with self.store.publication() as db:
            self.store.publish_success(db, *self.key, self.now, str(path or self.path), fingerprint(data))
        return self.store.get(*self.key)

    def check(self, validator=verify_pdf):
        return check_successes(self.store, "reports", self.root, self.now, self.resources.use, validator)

    def test_real_multi_page_pdf_passes_but_header_eof_and_truncated_pdf_do_not(self):
        data = pdf_bytes(3)
        self.assertTrue(verify_pdf(data))
        for invalid in (b"%PDF-1.4\n%%EOF", data[:len(data)//2] + b"\n%%EOF", data[:-15], b"not a PDF"):
            with self.subTest(size=len(invalid)):
                self.assertFalse(verify_pdf(invalid))

    def test_invalid_cross_reference_table_is_rejected_even_if_pdfium_repairs_it(self):
        data = pdf_bytes()
        start = data.rindex(b"startxref")
        damaged = data[:start] + b"startxref\n0\n%%EOF\n"
        self.assertFalse(verify_pdf(damaged))

    def test_cancellation_between_pages_propagates_and_releases_pdfium(self):
        import pypdfium2 as pdfium
        from pdf_runtime import PDFIUM_LOCK
        event, calls = threading.Event(), []
        original = pdfium.PdfPage.render
        def render(page, *args, **kwargs):
            bitmap = original(page, *args, **kwargs)
            calls.append(1)
            event.set()
            return bitmap
        data = pdf_bytes(3)
        with patch.object(pdfium.PdfPage, "render", new=render):
            with self.assertRaises(Cancelled), budget(event, 60):
                verify_pdf(data)
        self.assertEqual(len(calls), 1)
        self.assertFalse(PDFIUM_LOCK.locked())
        self.assertTrue(verify_pdf(data))

    def test_validator_and_plan_import_share_cancellable_pdfium_mutex(self):
        from plan_import import _pdf_png
        for entry in (lambda: verify_pdf(b"%PDF-1.4\n%%EOF"), lambda: _pdf_png(b"synthetic", 0)):
            event, lock = threading.Event(), Mock()
            def occupied(**kwargs):
                event.set()
                return False
            lock.acquire.side_effect = occupied
            with patch("pdf_runtime.PDFIUM_LOCK", lock), patch("pypdfium2.PdfDocument") as document:
                with self.assertRaises(Cancelled), budget(event, 60):
                    entry()
            lock.acquire.assert_called_once_with(timeout=.05)
            lock.release.assert_not_called()
            document.assert_not_called()

    def test_paths_cannot_escape_root_or_use_ambiguous_windows_names(self):
        unsafe = [self.root.parent / "outside.pdf", "../outside.pdf", self.root,
                  "p/../../outside.pdf", "report.pdf:secret", "p./report.pdf", "NUL.pdf"]
        if os.name == "nt":
            unsafe.append(self.root.drive + "relative.pdf")
        for path in unsafe:
            with self.subTest(path=path), patch("automation_artifacts.os.open") as opened:
                with self.assertRaises(ValueError):
                    read_artifact(path, self.root)
                opened.assert_not_called()
        self.assertEqual(safe_path("p/report.pdf", self.root), self.root / "p/report.pdf")

    def test_symlink_and_windows_junction_metadata_are_rejected_before_open(self):
        # Simulate lstat metadata, without requiring Windows symlink privileges.
        original = Path.lstat
        for mode, attributes in ((stat.S_IFLNK, 0), (stat.S_IFDIR, 0x400)):
            def metadata(path, *args, **kwargs):
                if path == self.root:
                    return SimpleNamespace(st_mode=mode, st_file_attributes=attributes)
                return original(path, *args, **kwargs)
            with self.subTest(mode=mode), patch.object(Path, "lstat", new=metadata), \
                 patch("automation_artifacts.os.open") as opened:
                with self.assertRaises(ValueError):
                    read_artifact(self.path, self.root)
                opened.assert_not_called()

    def test_hard_link_is_rejected(self):
        original = self.root.parent / "synthetic.pdf"
        original.write_bytes(pdf_bytes())
        os.link(original, self.path)
        with self.assertRaises(ValueError):
            read_artifact(self.path, self.root)
        self.assertEqual(original.read_bytes(), pdf_bytes())

    def test_unsafe_historical_paths_are_unverifiable_without_opening_them(self):
        for path in (self.root.parent / "outside.pdf", "../outside.pdf"):
            with self.subTest(path=path):
                self.success(path)
                # Change metadata only in this disposable test database.
                with self.store.connect() as db:
                    db.execute("UPDATE executions SET artifact=?", (str(path),))
                before = self.store.get(*self.key)
                with patch("automation_artifacts.read_artifact") as read:
                    self.assertEqual(self.check(), {self.key[1:]: "unverifiable"})
                read.assert_not_called()
                self.assertEqual(self.store.get(*self.key), before)

    def test_reader_lease_covers_read_and_validation_then_releases(self):
        self.success()
        original = read_artifact
        def read(path, root):
            self.assertTrue(self.resources.protected(path))
            return original(path, root)
        def validate(data):
            self.assertTrue(self.resources.protected(self.path))
            return verify_pdf(data)
        with patch("automation_artifacts.read_artifact", side_effect=read):
            self.assertEqual(self.check(validate), {self.key[1:]: "healthy"})
        self.assertFalse(self.resources.busy())

    def test_cancellation_during_historical_validation_preserves_history_and_health(self):
        before = self.success()
        health = self.store.health(*self.key)
        def cancel(data):
            self.assertTrue(self.resources.protected(self.path))
            raise Cancelled("synthetic validation deadline")
        with self.assertRaises(Cancelled):
            self.check(cancel)
        self.assertEqual(self.store.get(*self.key), before)
        self.assertEqual(self.store.health(*self.key), health)
        self.assertFalse(self.resources.busy())

    def test_size_is_verified_independently_of_sha256(self):
        before = self.success()
        with self.store.connect() as db:
            db.execute("UPDATE artifact_health SET size=size+1")
        self.assertEqual(self.check(), {self.key[1:]: "corrupt"})
        self.assertEqual(self.store.health(*self.key)["error"], "fingerprint_mismatch")
        self.assertEqual(self.store.get(*self.key), before)

    def test_partially_missing_fingerprint_is_not_filled_from_current_file(self):
        self.success()
        with self.store.connect() as db:
            db.execute("UPDATE artifact_health SET size=NULL")
        digest = self.store.health(*self.key)["sha256"]
        self.assertEqual(self.check(), {self.key[1:]: "unverifiable"})
        self.assertIsNone(self.store.health(*self.key)["size"])
        self.assertEqual(self.store.health(*self.key)["sha256"], digest)

    def test_inaccessible_pdf_is_unverifiable_without_changing_success(self):
        before = self.success()
        with patch("automation_artifacts.read_artifact", side_effect=PermissionError("synthetic")):
            self.assertEqual(self.check(), {self.key[1:]: "unverifiable"})
        self.assertEqual(self.store.get(*self.key), before)
        self.assertFalse(self.resources.busy())

    def test_failure_before_replace_does_not_truncate_previous_final(self):
        self.path.write_bytes(b"previous synthetic evidence")
        with self.resources.use(self.root, write=True), \
             patch("automation_reports.os.fsync", side_effect=OSError("synthetic")):
            with self.assertRaises(OSError):
                publish_pdf(pdf_bytes(), self.path, self.root)
        self.assertEqual(self.path.read_bytes(), b"previous synthetic evidence")
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_cancellation_after_fsync_does_not_publish(self):
        event = threading.Event()
        original = os.fsync
        def sync(fd):
            original(fd)
            event.set()
        with patch("automation_reports.os.fsync", side_effect=sync):
            with self.assertRaises(Cancelled), budget(event, 60), self.resources.use(self.root, write=True):
                publish_pdf(pdf_bytes(), self.path, self.root)
        self.assertFalse(self.path.exists())
        self.assertEqual(list(self.root.glob("*.tmp")), [])
        self.assertFalse(self.resources.busy())
