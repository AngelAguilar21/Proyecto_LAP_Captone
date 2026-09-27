"""Durable completion evidence for new uploads; never infer legacy completion."""
import hashlib
import json
import math
import os
import re
import secrets
import stat
import time
from pathlib import Path

from task_control import checkpoint

SUFFIXES = (".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v")
MARKER = ".completed.json"


def metadata_path(path):
    return path.with_name(path.name + MARKER)


def identity(path):
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("Upload is not an exclusive regular file")
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def receive(root, source, size, suffix, clock=time.time):
    from automation_cleanup import plain_path
    if type(size) is not int or not 0 < size <= 1024**3 or suffix not in SUFFIXES:
        raise ValueError("Invalid upload size or format")
    root = Path(root).absolute()
    directory = plain_path(root / "data" / "uploads", root)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (secrets.token_hex(16) + suffix)
    temporary = target.with_name(target.name + ".part")
    marker = metadata_path(target)
    marker_tmp = marker.with_name(marker.name + ".tmp")
    digest = hashlib.sha256()
    # Exclusive reservation; no existing upload or metadata is reused.
    with temporary.open("xb") as output:
        remaining = size
        while remaining:
            chunk = source.read(min(remaining, 1024 * 1024))
            if not chunk or len(chunk) > remaining:
                raise ValueError("La carga quedó incompleta.")
            output.write(chunk)
            digest.update(chunk)
            remaining -= len(chunk)
        output.flush()
        os.fsync(output.fileno())
    if target.exists() or marker.exists() or marker_tmp.exists():
        raise ValueError("Upload identity collision")
    os.replace(temporary, target)
    completed_at = clock()
    if not math.isfinite(completed_at):
        raise ValueError("Invalid completion timestamp")
    evidence = dict(format="aerotrack-upload", version=1, status="completed",
                    path=target.name, completed_at=completed_at,
                    expected_size=size, final_size=size, identity=identity(target),
                    sha256=digest.hexdigest())
    with marker_tmp.open("x", encoding="utf-8") as output:
        json.dump(evidence, output, sort_keys=True)
        output.flush()
        os.fsync(output.fileno())
    os.replace(marker_tmp, marker)
    return target


def completed_fingerprint(path, root):
    """Read-only validation; bind evidence to the exact file and its bytes."""
    from automation_cleanup import plain_path
    directory = root / "data" / "uploads"
    plain_path(path, root)
    if path.parent != directory or not re.fullmatch(r"[a-f0-9]{32}", path.stem) or path.suffix not in SUFFIXES:
        raise ValueError("Unknown upload identity")
    marker = plain_path(metadata_path(path), root)
    before, meta_before = identity(path), identity(marker)
    raw = marker.read_bytes()
    value = json.loads(raw)
    if (not isinstance(value, dict) or value.get("format") != "aerotrack-upload" or
            type(value.get("version")) is not int or value["version"] != 1 or
            value.get("status") != "completed" or value.get("path") != path.name or
            type(value.get("completed_at")) not in (int, float) or
            not math.isfinite(value["completed_at"]) or value["completed_at"] <= 0 or
            type(value.get("expected_size")) is not int or value["expected_size"] <= 0 or
            type(value.get("final_size")) is not int or
            value["expected_size"] != value["final_size"] or value["final_size"] != before[2] or
            value.get("identity") != before):
        raise ValueError("Invalid upload completion evidence")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            checkpoint()
            digest.update(chunk)
    plain_path(path, root)
    plain_path(marker, root)
    if (identity(path) != before or identity(marker) != meta_before or
            digest.hexdigest() != value.get("sha256")):
        raise ValueError("Upload changed since completion")
    return value["completed_at"], (tuple(before), tuple(meta_before),
                                   digest.hexdigest(), hashlib.sha256(raw).hexdigest())
