"""Offline configuration restore. Current operational databases are never rolled back.

No automatic invocation or HTTP endpoint. Call only while the server is stopped.
All staging/previous generations remain under settings_root/restore-work for audit.
"""
import hashlib
import json
import os
import re
import sqlite3
import time
import uuid
import zipfile
from contextlib import closing, contextmanager
from pathlib import Path, PureWindowsPath

from automation_cleanup import plain_path
from operational_history import descends_from, provenance
from restore_guard import blocked, storage_lease


@contextmanager
def journal(root):
    root.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(root / "restore.sqlite")) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS restores (
            id TEXT PRIMARY KEY,status TEXT NOT NULL,created REAL NOT NULL,operator TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,had_projects INTEGER NOT NULL,stage_hashes TEXT,report TEXT);
        CREATE TABLE IF NOT EXISTS holds (
            project TEXT PRIMARY KEY,reason TEXT NOT NULL,restore_id TEXT NOT NULL,
            released_at REAL,reviewer TEXT,evidence TEXT);
        """)
        with db:
            yield db


def read_archive(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len({n.casefold() for n in names}):
            raise ValueError("Duplicate archive member")
        # Reject unsafe names before materializing any entry, including ignored files.
        for name in names:
            if name == "backup-manifest.json":
                continue
            pieces = name.split("/")
            if (len(pieces) != 2 or pieces[0] != "projects" or pieces[1] in (".", "..") or
                    not re.fullmatch(r"[A-Za-z0-9_.-]+", pieces[1]) or PureWindowsPath(pieces[1]).is_reserved()):
                raise ValueError("Unsafe archive member")
        manifest = json.loads(archive.read("backup-manifest.json"))
        if (not isinstance(manifest, dict) or type(manifest.get("schema_version", 1)) is not int or
                manifest.get("schema_version", 1) not in (1, 2)):
            raise ValueError("Unsupported backup schema version")
        hashes = manifest.get("sha256")
        if manifest.get("format") != "aerotrack-projects-v1" or not isinstance(hashes, dict):
            raise ValueError("Unsupported backup format")
        if set(names) != set(hashes) | {"backup-manifest.json"}:
            raise ValueError("Backup manifest mismatch")
        files = {}
        for name, digest in hashes.items():
            data = archive.read(name)
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError("Backup checksum mismatch")
            files[name.removeprefix("projects/")] = data
        index = validate_index(json.loads(files["index.json"]))
        from live_core import validate_config
        for entry in index["projects"]:
            config = json.loads(files[entry["id"] + ".json"])
            validate_config(config)
        return files, manifest, index


def validate_index(index):
    if not isinstance(index, dict) or not isinstance(index.get("projects"), list) or not index["projects"]:
        raise ValueError("Invalid project index")
    ids = []
    for entry in index["projects"]:
        pid = entry.get("id") if isinstance(entry, dict) else None
        if not isinstance(pid, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", pid):
            raise ValueError("Invalid project identity")
        ids.append(pid)
    if len(ids) != len(set(ids)) or index.get("active") not in ids:
        raise ValueError("Invalid active/duplicate project")
    return index


def snapshot(source, target):
    with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as src:
        with closing(sqlite3.connect(target)) as dst:
            src.backup(dst)
            if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Invalid operational database")


def digest_tree(directory):
    hashes = {}
    if directory.exists():
        for path in sorted(directory.iterdir()):
            plain_path(path, directory)
            if not path.is_file():
                raise ValueError("Unexpected nested project storage")
            hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def durable_write(path, data):
    with path.open("wb") as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())


def restore_backup(settings_root, archive_path, operator):
    """Restore configuration; preserve current DBs; hold scopes lacking proof of continuity."""
    root = Path(settings_root).resolve()
    archive = plain_path(Path(archive_path), root)
    if not isinstance(operator, str) or not operator.strip():
        raise ValueError("An operator is required")
    with storage_lease(root):
        if blocked(root, maintenance_only=True):
            raise ValueError("An unfinished restore must be resumed or cancelled")
        files, manifest, backup_index = read_archive(archive)
        projects = plain_path(root / "projects", root)
        had_projects = projects.exists()
        current_index_path = plain_path(projects / "index.json", root)
        current_index = validate_index(json.loads(current_index_path.read_text(encoding="utf-8"))) if current_index_path.exists() else None
        run_id = uuid.uuid4().hex
        work = plain_path(root / "restore-work" / run_id, root)
        work.mkdir(parents=True)
        stage = work / "stage"
        stage.mkdir()
        with journal(root) as db:
            db.execute("INSERT INTO restores VALUES (?,'preparing',?,?,?,?,NULL,NULL)",
                       (run_id, time.time(), operator.strip(), hashlib.sha256(archive.read_bytes()).hexdigest(), int(had_projects)))
        # Source and previous generation are retained; this routine never deletes them.
        durable_write(work / "source.zip", archive.read_bytes())
        report = {"preserved_databases": [], "restored_databases": [], "held_projects": []}
        if had_projects:
            for source in projects.iterdir():
                plain_path(source, root)
                if not source.is_file():
                    raise ValueError("Unexpected project directory")
                if source.name.endswith(("-wal", "-shm", "-journal")):
                    continue
                target = stage / source.name
                with source.open("rb") as stream:
                    is_database = stream.read(16) == b"SQLite format 3\x00"
                if is_database or source.suffix in (".sqlite", ".sqlite3", ".db"):
                    snapshot(source, target)
                    report["preserved_databases"].append(source.name)
                else:
                    durable_write(target, source.read_bytes())
        # Every archive database, including orphans, stays available for human audit.
        extracted = work / "backup-databases"
        extracted.mkdir()
        archived_provenance = {}
        for name, data in files.items():
            if not name.endswith(".negocios.sqlite"):
                continue
            path = extracted / name
            durable_write(path, data)
            with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
                if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("Invalid archived database")
                archived_provenance[name] = provenance(db)
            declared = manifest.get("database_provenance", {}).get("projects/" + name)
            if declared is not None and declared != archived_provenance[name]:
                raise ValueError("Database provenance mismatch")
            if not (stage / name).exists():
                snapshot(path, stage / name)
                report["restored_databases"].append(name)
        scopes = {p["id"] for p in backup_index["projects"]}
        scopes.update(name.removesuffix(".negocios.sqlite") for name in archived_provenance)
        for pid in sorted(scopes):
            name = pid + ".negocios.sqlite"
            trusted = False
            if name in report["preserved_databases"] and archived_provenance.get(name):
                with closing(sqlite3.connect((stage / name).as_uri() + "?mode=ro", uri=True)) as db:
                    trusted = descends_from(db, archived_provenance[name])
            if not trusted:
                report["held_projects"].append(pid)
        # Only configuration JSON is rolled back. Later projects and all current
        # operational files survive, including those not present in the backup.
        for name, data in files.items():
            if name.endswith(".json") and name != "index.json":
                durable_write(stage / name, data)
        restored_ids = {p["id"] for p in backup_index["projects"]}
        if current_index:
            backup_index["projects"].extend(p for p in current_index["projects"] if p["id"] not in restored_ids)
        durable_write(stage / "index.json", json.dumps(backup_index, ensure_ascii=False, indent=2).encode("utf-8"))
        hashes = digest_tree(stage)
        with journal(root) as db:
            for pid in report["held_projects"]:
                db.execute("INSERT INTO holds(project,reason,restore_id) VALUES (?,'continuity_unknown',?) "
                           "ON CONFLICT(project) DO UPDATE SET reason=excluded.reason,restore_id=excluded.restore_id,"
                           "released_at=NULL,reviewer=NULL,evidence=NULL", (pid, run_id))
            db.execute("UPDATE restores SET status='prepared',stage_hashes=?,report=? WHERE id=?",
                       (json.dumps(hashes), json.dumps(report), run_id))
        _publish(root, run_id)
        return {"restore_id": run_id, **report}


def _publish(root, run_id):
    if not re.fullmatch(r"[a-f0-9]{32}", run_id):
        raise ValueError("Invalid restore identity")
    work = plain_path(root / "restore-work" / run_id, root)
    stage, previous, projects = work / "stage", work / "previous", root / "projects"
    for path in (stage, previous, projects):
        plain_path(path, root)
    with journal(root) as db:
        row = db.execute("SELECT status,had_projects,stage_hashes FROM restores WHERE id=?", (run_id,)).fetchone()
        if not row or row[0] not in ("prepared", "publishing", "completed"):
            raise ValueError("Restore is not ready for publication")
        if row[0] == "completed":
            return
        expected = json.loads(row[2])
        if digest_tree(stage if stage.exists() else projects) != expected:
            raise ValueError("Staged/published files changed")
        db.execute("UPDATE restores SET status='publishing' WHERE id=?", (run_id,))
    if stage.exists():
        if row[1] and not previous.exists():
            os.replace(projects, previous)
        elif projects.exists():
            raise ValueError("Unexpected live directory during recovery")
        os.replace(stage, projects)
    with journal(root) as db:
        db.execute("UPDATE restores SET status='completed' WHERE id=?", (run_id,))


def resume_restore(settings_root, run_id):
    root = Path(settings_root).resolve()
    with storage_lease(root):
        _publish(root, run_id)


def cancel_preparation(settings_root, run_id, operator, reason):
    """Cancel only before publication; keep the staging evidence and current data."""
    if not re.fullmatch(r"[a-f0-9]{32}", run_id) or not all(isinstance(v, str) and v.strip() for v in (operator, reason)):
        raise ValueError("Restore identity, operator and reason are required")
    root = Path(settings_root).resolve()
    with storage_lease(root), journal(root) as db:
        row = db.execute("SELECT status,had_projects FROM restores WHERE id=?", (run_id,)).fetchone()
        previous = plain_path(root / "restore-work" / run_id / "previous", root)
        if not row or row[0] != "preparing" or previous.exists() or (root / "projects").exists() != bool(row[1]):
            raise ValueError("Only an unpublished preparation can be cancelled")
        db.execute("UPDATE restores SET status='cancelled',report=? WHERE id=?",
                   (json.dumps({"cancelled_by": operator, "reason": reason}), run_id))


def release_hold(settings_root, project_id, reviewer, evidence):
    """Explicit human reconciliation only; does not change any delivery/review fact."""
    if not all(isinstance(v, str) and v.strip() for v in (reviewer, evidence)):
        raise ValueError("Reviewer and reconciliation evidence are required")
    root = Path(settings_root).resolve()
    with storage_lease(root):
        if blocked(root, maintenance_only=True):
            raise ValueError("Complete restoration before reconciliation")
        with journal(root) as db:
            cursor = db.execute("UPDATE holds SET released_at=?,reviewer=?,evidence=? WHERE project=? AND released_at IS NULL",
                                (time.time(), reviewer.strip(), evidence.strip(), project_id))
            if cursor.rowcount != 1:
                raise ValueError("No pending hold for that project")
