"""Versioned project archive verification. This is not a restore interface."""
import io
import json
import re
import sqlite3
import stat
import tempfile
import zipfile
import zlib
from contextlib import closing
from datetime import datetime
from pathlib import Path, PureWindowsPath

import projects
from automation import LIMA
from automation_artifacts import CHUNK, fingerprint
from task_control import Cancelled, checkpoint

FORMAT = "aerotrack-projects-v1"
SCHEMA_VERSION = 2
MANIFEST = "backup-manifest.json"
SQLITE_HEADER = b"SQLite format 3\x00"


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError("Non-finite JSON value")
    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid_constant)


def member_kind(name):
    """Only the flat project families demonstrated by current production code."""
    if (not isinstance(name, str) or not name.startswith("projects/") or name.count("/") != 1 or
            "\\" in name or ":" in name or any(ord(c) < 32 for c in name)):
        raise ValueError("Unsafe project member")
    base = name.split("/")[1]
    if base.endswith((".", " ")) or PureWindowsPath(base).is_reserved():
        raise ValueError("Ambiguous project member")
    if base == "index.json":
        return "json"
    suffix = next((s for s in (".negocios.sqlite", ".json") if base.endswith(s)), None)
    if suffix is None:
        raise ValueError("Unknown project store; scope needs review")
    pid = base[:-len(suffix)]
    projects.project_path(Path("."), pid)
    return "sqlite" if suffix == ".negocios.sqlite" else "json"


def validate_index(files, allow_empty=False):
    index = strict_json(files["projects/index.json"])
    if not isinstance(index, dict) or not isinstance(index.get("projects"), list):
        raise ValueError("Invalid project index")
    ids = []
    for entry in index["projects"]:
        if not isinstance(entry, dict):
            raise ValueError("Invalid project entry")
        pid = entry.get("id")
        projects.project_path(Path("."), pid)
        name = "projects/" + pid + ".json"
        member_kind(name)
        if pid == "index" or name not in files or not isinstance(strict_json(files[name]), dict):
            raise ValueError("Project index references a missing or invalid configuration")
        ids.append(pid)
    if len({pid.casefold() for pid in ids}) != len(ids):
        raise ValueError("Duplicate project identity")
    if not ids:
        if not allow_empty or index.get("active") is not None:
            raise ValueError("Empty or invalid project index")
    elif index.get("active") not in ids:
        raise ValueError("Invalid active project")
    expected = {"projects/index.json", *("projects/" + pid + ".json" for pid in ids)}
    if set(files) != expected:
        raise ValueError("Unindexed JSON requires a project-scope review")
    return ids


def integrity_check(connection):
    """SQLite callbacks cannot propagate Python exceptions directly."""
    cancelled = []
    def progress():
        try:
            checkpoint()
            return 0
        except Cancelled as exc:
            cancelled.append(exc)
            return 1
    checkpoint()
    connection.set_progress_handler(progress, 1000)
    try:
        try:
            rows = connection.execute("PRAGMA integrity_check").fetchall()
        except sqlite3.Error:
            if cancelled:
                raise cancelled[0]
            raise
        if rows != [("ok",)]:
            raise ValueError("SQLite integrity check failed")
        checkpoint()
    finally:
        connection.set_progress_handler(None, 0)


def read_member(archive, info):
    chunks = []
    with archive.open(info) as source:
        while True:
            checkpoint()
            chunk = source.read(CHUNK)
            if not chunk:
                break
            chunks.append(chunk)
    return b"".join(chunks)


class CheckedZipFile(zipfile.ZipFile):
    def testzip(self):
        """ZipFile.testzip's CRC check, with cooperative chunk checkpoints."""
        for info in self.infolist():
            try:
                with self.open(info) as source:
                    while True:
                        checkpoint()
                        if not source.read(CHUNK):
                            break
            except zipfile.BadZipFile:
                return info.filename
        return None


def verify_backup_bytes(data, expected_date=None, workspace=None):
    """Check exact members, CRC, hashes, JSON references and embedded SQLite.

    workspace, when supplied, is a caller-owned temporary directory with a lease.
    Archive member names are never used as extraction destinations.
    """
    if workspace is None:
        with tempfile.TemporaryDirectory(prefix="aerotrack-verify-") as folder:
            return verify_backup_bytes(data, expected_date, Path(folder))
    try:
        with CheckedZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            names = [i.filename for i in infos]
            if len(set(n.casefold() for n in names)) != len(names) or names.count(MANIFEST) != 1:
                return False
            for info in infos:
                checkpoint()
                if (info.orig_filename != info.filename or info.is_dir() or info.flag_bits & 1 or info.external_attr & 0x10 or
                        stat.S_IFMT(info.external_attr >> 16) not in (0, stat.S_IFREG)):
                    return False
                if info.filename != MANIFEST:
                    member_kind(info.filename)
            if archive.testzip() is not None:
                return False
            manifest = strict_json(read_member(archive, MANIFEST))
            if (not isinstance(manifest, dict) or set(manifest) != {"format", "schema_version", "created", "scope", "files", "sha256"} or
                    manifest.get("format") != FORMAT or
                    type(manifest.get("schema_version")) is not int or manifest["schema_version"] != SCHEMA_VERSION or
                    manifest.get("scope") != "projects"):
                return False
            created = datetime.fromisoformat(manifest["created"])
            if created.tzinfo is None or created.utcoffset() is None:
                return False
            if expected_date is not None and created.astimezone(LIMA).date().isoformat() != expected_date:
                return False
            hashes, members = manifest["sha256"], manifest["files"]
            if (not isinstance(hashes, dict) or not isinstance(members, list) or
                    any(not isinstance(n, str) for n in members) or
                    members != sorted(hashes) or set(names) != set(members) | {MANIFEST}):
                return False
            json_files = {}
            for number, name in enumerate(members):
                checkpoint()
                digest = hashes[name]
                if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                    return False
                content = read_member(archive, name)
                if fingerprint(content)[0] != digest:
                    return False
                if member_kind(name) == "json":
                    if not isinstance(strict_json(content), dict):
                        return False
                    json_files[name] = content
                else:
                    if not content.startswith(SQLITE_HEADER):
                        return False
                    target = Path(workspace) / f"verify-{number}.sqlite"
                    try:
                        with target.open("xb") as output:
                            for start in range(0, len(content), CHUNK):
                                checkpoint()
                                output.write(content[start:start + CHUNK])
                        with closing(sqlite3.connect(target.as_uri() + "?mode=ro", uri=True, timeout=.2)) as db:
                            integrity_check(db)
                    finally:
                        target.unlink(missing_ok=True)
            validate_index(json_files)
            return True
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error, zipfile.BadZipFile, RuntimeError, EOFError, zlib.error):
        return False


def write_archive(path, files, now):
    members = sorted(files)
    manifest = dict(format=FORMAT, schema_version=SCHEMA_VERSION, created=now.isoformat(), scope="projects",
                    files=members, sha256={name: fingerprint(files[name])[0] for name in members})
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in [*((name, files[name]) for name in members),
                              (MANIFEST, json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode("utf-8"))]:
            checkpoint()
            info = zipfile.ZipInfo(name, now.timetuple()[:6])
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o600) << 16
            with archive.open(info, "w") as destination:
                for start in range(0, len(content), CHUNK):
                    checkpoint()
                    destination.write(content[start:start + CHUNK])
    checkpoint()
