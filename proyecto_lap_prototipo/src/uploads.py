"""Publish completion evidence only after receiving and syncing every byte."""
import hashlib
import json
import math
import os
import re
import secrets
import time
from contextlib import nullcontext
from pathlib import Path

from path_security import absolute, plain_path, identity, file_fingerprint, strict_json, CHUNK
from resource_control import CURRENT
from task_control import checkpoint

SUFFIXES = (".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v")
MARKER = ".completed.json"
MAX_SIZE = 2 ** 63 - 1
_dedup_lock = __import__('threading').Lock()


def metadata_path(path):
    return path.with_name(path.name + MARKER)


def deduplicate_completed(root, target):
    """Reuse only a verified completed upload; keep retention evidence consistent."""
    root = absolute(root)
    target = plain_path(target, root)
    directory = target.parent
    with _dedup_lock:
        _, (target_fp, marker_fp) = completed_fingerprint(target, root)
        sha = target_fp[1]
        index = plain_path(directory / '_indice.json', root)
        try:
            _, raw = file_fingerprint(index, root, content=True, limit=65536)
            table = strict_json(raw)
            if not isinstance(table, dict): table = {}
        except (OSError, ValueError):
            table = {}
        name = table.get(sha)
        if isinstance(name, str) and name == Path(name).name and name not in ('', '.', '..'):
            try:
                previous = plain_path(directory / name, root)
                _, (previous_fp, _) = completed_fingerprint(previous, root)
                previous_sha = previous_fp[1]
                if previous != target and previous_sha == sha:
                    if identity(target) != target_fp[0] or identity(metadata_path(target)) != marker_fp[0]:
                        raise ValueError('Upload changed during deduplication')
                    target.unlink()
                    metadata_path(target).unlink()
                    return previous
            except (OSError, ValueError):
                pass
        table[sha] = target.name
        temporary = plain_path(directory / ('_indice.' + secrets.token_hex(16) + '.tmp'), root)
        with temporary.open('x', encoding='utf-8') as output:
            json.dump(table, output, sort_keys=True, allow_nan=False)
            output.flush()
            os.fsync(output.fileno())
        plain_path(index, root)
        os.replace(temporary, index)
    return target


def _discard_owned(path, root, owned):
    # Only the temporary file created by this operation, never an unknown final.
    if owned is None:
        return
    try:
        if identity(plain_path(path, root))[:2] == owned:
            path.unlink()
    except (OSError, ValueError):
        pass  # Uncertain ownership or disk failure leaves an omitted temporary.


def receive(root, source, size, suffix, clock=time.time, resources=None):
    if type(size) is not int or not 0 < size <= MAX_SIZE or suffix not in SUFFIXES:
        raise ValueError("Invalid upload size or format")
    root = absolute(root)
    directory = plain_path(root / "data" / "uploads", root)
    registry = resources or CURRENT.get()
    with registry.use(directory, write=True) if registry else nullcontext():
        directory.mkdir(parents=True, exist_ok=True)
        plain_path(directory, root)
        target = directory / (secrets.token_hex(16) + suffix)
        part = target.with_name(target.name + ".part")
        marker = metadata_path(target)
        temporary = marker.with_name(marker.name + ".tmp")
        for path in (target, part, marker, temporary):
            plain_path(path, root)
            if path.exists():
                raise ValueError("Upload identity collision")
        part_id = marker_id = None
        try:
            digest = hashlib.sha256()
            with part.open("xb") as output:
                part_id = identity(part)[:2]
                remaining = size
                while remaining:
                    checkpoint()
                    chunk = source.read(min(remaining, CHUNK))
                    if not chunk or len(chunk) > remaining:
                        raise ValueError("La carga quedó incompleta.")
                    if output.write(chunk) != len(chunk):
                        raise OSError("Incomplete disk write")
                    digest.update(chunk)
                    remaining -= len(chunk)
                output.flush()
                os.fsync(output.fileno())
            checkpoint()
            if identity(plain_path(part, root))[:3] != (*part_id, size):
                raise ValueError("Upload size or identity changed")
            for path in (target, marker, temporary):
                plain_path(path, root)
                if path.exists():
                    raise ValueError("Upload identity collision")
            os.replace(part, target)
            completed_at = clock()
            if type(completed_at) not in (int, float) or not math.isfinite(completed_at) or completed_at <= 0:
                raise ValueError("Invalid completion timestamp")
            final_id = identity(plain_path(target, root))
            if final_id[:3] != (*part_id, size):
                raise ValueError("Published upload identity changed")
            evidence = dict(format="aerotrack-upload", version=1, status="completed", path=target.name,
                            completed_at=completed_at, expected_size=size, final_size=final_id[2],
                            identity=final_id, sha256=digest.hexdigest())
            checkpoint()
            with temporary.open("x", encoding="utf-8") as output:
                marker_id = identity(temporary)[:2]
                json.dump(evidence, output, sort_keys=True, allow_nan=False)
                output.flush()
                os.fsync(output.fileno())
            checkpoint()
            if identity(plain_path(target, root)) != final_id:
                raise ValueError("Upload changed before completion")
            plain_path(marker, root)
            if marker.exists():
                raise ValueError("Upload marker collision")
            os.replace(temporary, marker)
            return target
        finally:
            _discard_owned(part, root, part_id)
            _discard_owned(temporary, root, marker_id)


def completed_fingerprint(path, root):
    """Read-only: no inference, metadata repair or legacy completion conversion."""
    root = absolute(root)
    path = plain_path(path, root)
    if (path.parent != root / "data" / "uploads" or path.suffix not in SUFFIXES or
            not re.fullmatch(r"[a-f0-9]{32}", path.stem)):
        raise ValueError("Unknown upload identity")
    marker = metadata_path(path)
    meta_fp, raw = file_fingerprint(marker, root, content=True, limit=65536)
    value = strict_json(raw)
    fields = {"format", "version", "status", "path", "completed_at", "expected_size", "final_size", "identity", "sha256"}
    if (not isinstance(value, dict) or set(value) != fields or value["format"] != "aerotrack-upload" or
            type(value["version"]) is not int or value["version"] != 1 or value["status"] != "completed" or
            value["path"] != path.name or type(value["completed_at"]) not in (int, float) or
            not math.isfinite(value["completed_at"]) or value["completed_at"] <= 0 or
            type(value["expected_size"]) is not int or not 0 < value["expected_size"] <= MAX_SIZE or
            type(value["final_size"]) is not int or value["final_size"] != value["expected_size"] or
            not isinstance(value["identity"], list) or any(type(n) is not int for n in value["identity"])):
        raise ValueError("Invalid upload completion evidence")
    data_fp, _ = file_fingerprint(path, root)
    if (list(data_fp[0]) != value["identity"] or data_fp[0][2] != value["final_size"] or
            data_fp[1] != value["sha256"] or file_fingerprint(marker, root)[0] != meta_fp):
        raise ValueError("Upload changed since completion")
    if identity(plain_path(path, root)) != data_fp[0] or identity(plain_path(marker, root)) != meta_fp[0]:
        raise ValueError("Upload changed during validation")
    return value["completed_at"], (data_fp, meta_fp)
