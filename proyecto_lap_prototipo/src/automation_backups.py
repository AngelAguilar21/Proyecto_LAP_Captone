"""Opt-in project backups: component snapshots, verified ZIP, bounded retention."""
import os
import re
import sqlite3
import stat
import tempfile
import threading
from contextlib import closing, contextmanager
from datetime import date as calendar_date
from pathlib import Path

from automation import LIMA
from automation_artifacts import check_successes, fingerprint, read_artifact, safe_path
from automation_backup_format import (SQLITE_HEADER, integrity_check, member_kind,
                                      strict_json, validate_index, verify_backup_bytes, write_archive)
from task_control import Cancelled, checkpoint

BACKUP_LOCK = threading.Lock()  # Same-process instances; SQLite also guards final transitions.


@contextmanager
def cooperative_lock(lock):
    checkpoint()
    while not lock.acquire(timeout=.05):
        checkpoint()
    try:
        checkpoint()
        yield
    finally:
        lock.release()


def file_identity(path, root):
    info = safe_path(path, root).stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("Expected a regular file without hard links")
    return info


def unchanged(first, second):
    return (os.path.samestat(first, second) and first.st_size == second.st_size and
            first.st_mtime_ns == second.st_mtime_ns and first.st_ctime_ns == second.st_ctime_ns)


def sqlite_snapshot(source, destination, root, expected):
    before = file_identity(source, root)
    if not os.path.samestat(before, expected):
        raise ValueError("Project database replaced during capture")
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=.2)) as src:
        with closing(sqlite3.connect(destination)) as dst:
            src.backup(dst, pages=128, progress=lambda *args: checkpoint(), sleep=.01)
            integrity_check(dst)
    if not os.path.samestat(before, file_identity(source, root)):
        raise ValueError("Project database replaced during snapshot")
    checkpoint()


def backup_date(name):
    match = re.fullmatch(r"projects-(\d{4}-\d{2}-\d{2})\.zip", name)
    if not match:
        raise ValueError("Not a canonical backup name")
    value = match[1]
    if calendar_date.fromisoformat(value).isoformat() != value:
        raise ValueError("Invalid backup date")
    return value


class InvalidBackup(ValueError):
    pass


class ProjectBackups:
    records_execution = True

    def __init__(self, engine, store):
        self.engine, self.store = engine, store
        self.source = engine.settings_root / "projects"
        self.root = engine.settings_root / "backups"
        self.resources, self.resource_use = engine.resources, engine.resource_use

    def capture(self):
        """JSON cut only holds Engine.lock; SQLite snapshots are taken later."""
        files, databases = {}, []
        safe_path(self.source / "index.json", self.source)
        with cooperative_lock(self.engine.lock):
            if not self.source.exists():
                return None
            paths = sorted(self.source.iterdir())
            if not paths:
                return None
            for path in paths:
                checkpoint()
                info = file_identity(path, self.source)
                # Only sidecars/temporary names of demonstrated stores are excluded.
                suffix = next((s for s in ("-wal", "-shm", "-journal", ".tmp") if path.name.endswith(s)), None)
                if suffix:
                    member_kind("projects/" + path.name[:-len(suffix)])
                    continue
                name = "projects/" + path.name
                kind = member_kind(name)  # Unknown stores need an explicit scope decision.
                with path.open("rb") as source:
                    header = source.read(16)
                if kind == "sqlite":
                    if header != SQLITE_HEADER:
                        raise ValueError("Project SQLite header missing or damaged")
                    databases.append((name, path, info))
                else:
                    content = read_artifact(path, self.source)
                    if not isinstance(strict_json(content), dict):
                        raise ValueError("Project JSON must be an object")
                    files[name] = content
            if not validate_index(files, allow_empty=True):
                return None
        return files, databases

    def verify(self, data, date=None):
        # Scratch SQLite verification is covered by its own writer lease.
        safe_path(self.root / "verification", self.root)
        with tempfile.TemporaryDirectory(prefix=".verify-", dir=self.root) as folder:
            with self.resource_use(folder, write=True):
                return verify_backup_bytes(data, date, Path(folder))

    def identity(self, row, path):
        return (row["scope"] == "projects" and path.parent == self.root and
                backup_date(path.name) == row["date"])

    def _existing(self, db, target, date, now):
        previous = self.store.get("backups", "projects", date, connection=db)
        if previous and previous["status"] == "succeeded":
            return "already_done"
        target = safe_path(target, self.root)
        if target.exists():
            data = read_artifact(target, self.root)
            if not self.verify(data, date):
                raise InvalidBackup("Existing backup is invalid; evidence preserved")
            digest = fingerprint(data)
            checkpoint()
            self.store.publish_success(db, "backups", "projects", date, now, str(target), digest)
            return "recovered"
        return None

    def _publish(self, target, date, now):
        with self.store.publication() as db:
            outcome = self._existing(db, target, date, now)
        if outcome:
            return outcome
        self.store.record("backups", "projects", date, "running", now, preserve_success=True)
        safe_path(target, self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        safe_path(target, self.root)
        with tempfile.TemporaryDirectory(prefix=".projects-", dir=self.root) as folder:
            temporary = Path(folder)
            with self.resource_use(temporary, write=True):
                with self.resource_use(self.source):
                    captured = self.capture()
                    if captured is None:
                        self.store.record("backups", "projects", date, "no_data", now, preserve_success=True)
                        return "no_data"
                    files, databases = captured
                    for number, (name, source, identity) in enumerate(databases):
                        checkpoint()
                        destination = temporary / f"snapshot-{number}.sqlite"
                        sqlite_snapshot(source, destination, self.source, identity)
                        files[name] = read_artifact(destination, temporary)
                archive = temporary / "projects.zip"
                write_archive(archive, files, now)
                data = read_artifact(archive, temporary)
                if not self.verify(data, date):
                    raise InvalidBackup("Generated ZIP failed verification")
                digest = fingerprint(data)
                with archive.open("rb+") as output:
                    output.flush()
                    os.fsync(output.fileno())
                with self.store.publication() as db:
                    outcome = self._existing(db, target, date, now)
                    if outcome:
                        return outcome
                    checkpoint()
                    safe_path(target, self.root)
                    os.replace(archive, target)
                    # No cooperative cancellation between publication and commit.
                    self.store.publish_success(db, "backups", "projects", date, now, str(target), digest)
        return "succeeded"

    def __call__(self, now, settings):
        if settings.get("enabled") is not True:
            return "disabled"
        checkpoint()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("An aware timestamp is required")
        now = now.astimezone(LIMA)
        if now.strftime("%H:%M") < settings["time"]:
            return "not_due"
        count = settings["retention"]
        if type(count) is not int or count < 1:
            raise ValueError("Invalid backup retention")
        date = now.date().isoformat()
        target = self.root / f"projects-{date}.zip"
        with self.resources.activity(), cooperative_lock(BACKUP_LOCK):
            try:
                safe_path(target, self.root)
                with self.resource_use(target, write=True):
                    outcome = self._publish(target, date, now)
            except Exception as exc:
                try:
                    if isinstance(exc, InvalidBackup):
                        self.store.set_health("backups", "projects", date, "corrupt", now, "invalid_structure")
                    self.store.record("backups", "projects", date,
                                      "cancelled" if isinstance(exc, Cancelled) else "failed", now,
                                      error=type(exc).__name__, preserve_success=True)
                except (OSError, sqlite3.Error):
                    pass  # Keep the original exception visible to AutomationService.
                raise
            health = check_successes(self.store, "backups", self.root, now, self.resource_use,
                                     self.verify, retention=True, identity=self.identity)
            self.retain(count, now)
            if outcome == "already_done" and health.get(("projects", date)) != "healthy":
                return "artifact_problem"
            return outcome

    def _owned(self, db, path, date):
        row = self.store.get("backups", "projects", date, connection=db)
        health = db.execute("SELECT * FROM artifact_health WHERE task='backups' AND scope='projects' AND date=?",
                            (date,)).fetchone()
        if (not row or row["status"] != "succeeded" or not health or
                health["status"] not in ("healthy", "retention_pending") or
                health["sha256"] is None or health["size"] is None or
                safe_path(row["artifact"], self.root) != path):
            return None
        return health["sha256"], health["size"]

    def retain(self, count, now):
        """Only owned, verified canonical artifacts can be counted or retired."""
        if not self.root.exists():
            return
        valid = []
        for path in sorted(self.root.iterdir(), reverse=True):
            checkpoint()
            try:
                date = backup_date(path.name)
                safe_path(path, self.root)
                with self.resource_use(path):
                    before = file_identity(path, self.root)
                    data = read_artifact(path, self.root)
                    digest = fingerprint(data)
                    if not self.verify(data, date) or not unchanged(before, file_identity(path, self.root)):
                        continue
                    with self.store.publication() as db:
                        if self._owned(db, path, date) != digest:
                            continue
                valid.append((path, date, before, digest))
            except (OSError, ValueError, TypeError):
                continue  # Unknown/suspect files are evidence, not deletion candidates.
        for path, date, identity, digest in valid[count:]:
            checkpoint()
            # No Engine.lock or compression here. Close the local lease admission
            # race only over bounded DB transitions and the final unlink.
            with self.resources.lock:
                if self.resources.protected(path):
                    continue
                with self.resource_use(path, write=True):
                    with self.store.publication() as db:
                        if (self._owned(db, path, date) != digest or
                                not unchanged(identity, file_identity(path, self.root))):
                            continue
                        self.store.set_health("backups", "projects", date, "retention_pending", now, "retention",
                                              connection=db, event="retention_planned")
                    # The intention is committed BEFORE unlink. A crash with the
                    # file absent can now reconcile to retired, not accidental missing.
                    checkpoint()
                    failure = None
                    with self.store.publication() as db:
                        if (self._owned(db, path, date) != digest or
                                not unchanged(identity, file_identity(path, self.root))):
                            continue
                        try:
                            path.unlink()
                        except OSError as exc:
                            failure = exc
                            self.store.set_health("backups", "projects", date, "retention_pending", now,
                                                  "unlink_failed:" + type(exc).__name__, connection=db,
                                                  event="retention_failed")
                        else:
                            self.store.set_health("backups", "projects", date, "retired", now, "retention",
                                                  connection=db, event="retention_deleted")
                    if failure:
                        raise failure
