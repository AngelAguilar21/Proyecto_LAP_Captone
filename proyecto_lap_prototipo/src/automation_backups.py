"""JSON cut under Engine.lock; independent SQLite snapshots; verified ZIP."""
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from pathlib import Path
from task_control import checkpoint


def regular_files(root):
    if root.is_symlink() or root.is_junction():
        raise ValueError("Linked project storage is not backed up automatically")
    for path in sorted(root.iterdir()):
        checkpoint()
        if path.is_symlink() or path.is_junction():
            raise ValueError("Linked project entry")
        if path.is_dir():
            yield from regular_files(path)
        elif path.is_file():
            yield path
        else:
            raise ValueError("Unknown project entry")


def verify_backup(path):
    try:
        if path.is_symlink() or path.is_junction():
            return False
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read("backup-manifest.json"))
            hashes = manifest["sha256"]
            if manifest.get("format") != "aerotrack-projects-v1" or not isinstance(hashes, dict):
                return False
            if set(archive.namelist()) != set(hashes) | {"backup-manifest.json"}:
                return False
            if len(archive.namelist()) != len(hashes) + 1 or archive.testzip() is not None:
                return False
            return all(name.startswith("projects/") and ".." not in name.split("/") and
                       hashlib.sha256(archive.read(name)).hexdigest() == digest
                       for name, digest in hashes.items())
    except (OSError, ValueError, KeyError, zipfile.BadZipFile):
        return False


class ProjectBackups:
    def __init__(self, engine, store):
        self.engine, self.store = engine, store

    def capture(self):
        root = self.engine.settings_root / "projects"
        files, databases = {}, []
        with self.engine.lock:
            if not root.exists():
                return None
            for path in regular_files(root):
                if path.name.endswith(("-wal", "-shm", "-journal", ".tmp")):
                    continue
                name = "projects/" + path.relative_to(root).as_posix()
                with path.open("rb") as source:
                    header = source.read(16)
                if header == b"SQLite format 3\x00" or path.suffix in (".sqlite", ".sqlite3", ".db"):
                    databases.append((name, path))
                else:
                    files[name] = path.read_bytes()
                    if path.suffix == ".json":
                        json.loads(files[name])
            index = json.loads(files["projects/index.json"])
            for project in index["projects"]:
                if "projects/" + project["id"] + ".json" not in files:
                    raise ValueError("Project index references a missing configuration")
        return files, databases

    def __call__(self, now, settings):
        checkpoint()
        if now.strftime("%H:%M") < settings["time"]:
            return "not_due"
        date = now.date().isoformat()
        previous = self.store.get("backups", "projects", date)
        if previous and previous["status"] == "succeeded":
            self.retain(settings["retention"], now)
            return "already_done"
        directory = self.engine.settings_root / "backups"
        target = directory / f"projects-{date}.zip"
        if target.exists():
            if not verify_backup(target):
                raise ValueError("Existing backup failed verification")
            self.store.record("backups", "projects", date, "succeeded", now, str(target))
            self.retain(settings["retention"], now)
            return "recovered"
        captured = self.capture()
        if captured is None:
            self.store.record("backups", "projects", date, "no_data", now)
            return "no_data"
        files, databases = captured
        directory.mkdir(parents=True, exist_ok=True)
        # All temporary snapshots live beside the destination, not in project data.
        with tempfile.TemporaryDirectory(prefix=".projects-", dir=directory) as temporary:
            temporary = Path(temporary)
            provenance = {}
            for number, (name, source) in enumerate(databases):
                checkpoint()
                destination = temporary / f"snapshot-{number}.sqlite"
                with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src:
                    with closing(sqlite3.connect(destination)) as dst:
                        src.backup(dst, pages=128, progress=lambda *args: checkpoint())
                        if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                            raise ValueError("SQLite snapshot failed verification")
                        from operational_history import provenance as database_provenance
                        provenance[name] = database_provenance(dst)
                files[name] = destination.read_bytes()
            archive_path = temporary / "projects.zip"
            hashes = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name, data in files.items():
                    checkpoint()
                    archive.writestr(name, data)
                archive.writestr("backup-manifest.json", json.dumps({
                    "format": "aerotrack-projects-v1", "created": now.isoformat(), "sha256": hashes,
                    "schema_version": 2, "database_provenance": provenance}))
            if not verify_backup(archive_path):
                raise ValueError("ZIP verification failed")
            with archive_path.open("rb+") as output:
                os.fsync(output.fileno())
            checkpoint()
            os.replace(archive_path, target)
        self.store.record("backups", "projects", date, "succeeded", now, str(target))
        self.retain(settings["retention"], now)
        return "succeeded"

    def retain(self, count, now):
        directory = self.engine.settings_root / "backups"
        valid = sorted((p for p in directory.glob("projects-*.zip")
                        if re.fullmatch(r"projects-\d{4}-\d{2}-\d{2}\.zip", p.name)
                        and verify_backup(p)), reverse=True)
        for path in valid[count:]:
            checkpoint()
            # Only exact, verified final archives inside our backup directory.
            if path.resolve().parent != directory.resolve():
                continue
            self.store.audit("backups", "retention_planned:" + path.name, now)
            path.unlink()
            self.store.audit("backups", "retention_deleted:" + path.name, now)
