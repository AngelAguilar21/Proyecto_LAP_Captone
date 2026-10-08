"""Conservative local path checks shared by upload reception and retention."""
import hashlib
import json
import os
import stat
from pathlib import Path, PureWindowsPath

from task_control import checkpoint

CHUNK = 1024 * 1024


def absolute(path):
    raw = os.fspath(path)
    if "\x00" in raw or raw.startswith(("\\\\", "//")):
        raise ValueError("ambiguous_path")
    win = PureWindowsPath(raw)
    if win.drive and not win.is_absolute():
        raise ValueError("drive_relative_path")
    parts = raw.replace("\\", "/").split("/")
    for i, part in enumerate(parts):
        if not part or (i == 0 and part == win.drive):
            continue
        if (part in (".", "..") or ":" in part or part.endswith((".", " ")) or
                "~" in part or PureWindowsPath(part).is_reserved() or any(ord(c) < 32 for c in part)):
            raise ValueError("ambiguous_path_component")
    return Path(os.path.abspath(path))


def plain_path(path, root):
    """Check lexical containment and every existing ancestor without following links."""
    path, root = absolute(path), absolute(root)
    if not path.is_relative_to(root):
        raise ValueError("outside_root")
    for part in (*reversed(path.parents), path):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if (stat.S_ISLNK(info.st_mode) or part.is_junction() or
                getattr(info, "st_file_attributes", 0) & 1024):
            raise ValueError("linked_or_reparse_path")
    return path


def identity(path):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not info.st_ino or
            getattr(info, "st_file_attributes", 0) & 1024):
        raise ValueError("uncertain_file_identity")
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def file_fingerprint(path, root, *, content=False, limit=None):
    path = plain_path(path, root)
    before = identity(path)
    if limit is not None and before[2] > limit:
        raise ValueError("oversized_document")
    digest, chunks = hashlib.sha256(), []
    with path.open("rb") as source:
        opened = os.fstat(source.fileno())
        if (opened.st_dev, opened.st_ino) != before[:2] or opened.st_nlink != 1:
            raise ValueError("file_changed")
        while True:
            checkpoint()
            chunk = source.read(CHUNK)
            if not chunk:
                break
            digest.update(chunk)
            if content:
                chunks.append(chunk)
    plain_path(path, root)
    if identity(path) != before:
        raise ValueError("file_changed")
    return (before, digest.hexdigest()), b"".join(chunks)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result
    def nonfinite(_):
        raise ValueError("nonfinite_json")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def read_json(path, root):
    fingerprint, raw = file_fingerprint(path, root, content=True, limit=16 * CHUNK)
    value = strict_json(raw)
    if not isinstance(value, dict):
        raise ValueError("invalid_document")
    return value, fingerprint
