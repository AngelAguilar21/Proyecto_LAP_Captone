"""Report artifact validation and health, independent of historical success."""
import hashlib
import math
import os
import stat
from contextlib import closing
from pathlib import Path, PureWindowsPath

from pdf_runtime import serialized_pdfium
from task_control import checkpoint

CHUNK = 1024 * 1024


def safe_path(value, root):
    """Confine lexical paths; reject symlinks, junctions and reparse points.

    This is not protection against an adversary replacing directories between
    system calls. The reports directory must be controlled by the application.
    """
    if not isinstance(value, (str, Path)) or not str(value):
        raise ValueError("Invalid artifact path")
    path, root = Path(value), Path(root)
    if not root.is_absolute() or ".." in root.parts or ".." in path.parts:
        raise ValueError("Invalid artifact root or traversal")
    if path.drive and not path.is_absolute():
        raise ValueError("Drive-relative artifact path")
    path = path if path.is_absolute() else root / path
    if not path.is_relative_to(root) or path == root:
        raise ValueError("Artifact outside report root")
    for part in path.parts[1:]:
        if ":" in part or part.endswith((".", " ")) or PureWindowsPath(part).is_reserved():
            raise ValueError("Ambiguous artifact path")
    for component in (*reversed(path.parents), path):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            raise ValueError("Linked artifact path")
    return path


def fingerprint(data):
    digest = hashlib.sha256()
    for start in range(0, len(data), CHUNK):
        checkpoint()
        digest.update(data[start:start + CHUNK])
    checkpoint()
    return digest.hexdigest(), len(data)


def read_artifact(path, root):
    """Caller holds a resource lease for the entire read/validation operation."""
    path = safe_path(path, root)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("Artifact must be an unlinked regular file")
        chunks = []
        while True:
            checkpoint()
            chunk = source.read(CHUNK)
            if not chunk:
                break
            chunks.append(chunk)
        safe_path(path, root)
        if not os.path.samestat(info, path.stat()):
            raise ValueError("Artifact changed during read")
    return b"".join(chunks)


@serialized_pdfium
def verify_pdf(data):
    if not isinstance(data, bytes) or not data.startswith(b"%PDF-") or not data.rstrip().endswith(b"%%EOF"):
        return False
    import pypdfium2 as pdfium
    try:
        with closing(pdfium.PdfDocument(data)) as document:
            checkpoint()
            if not len(document) or not pdfium.raw.FPDF_DocumentHasValidCrossReferenceTable(document):
                return False
            for number in range(len(document)):
                checkpoint()
                with closing(document[number]) as page:
                    width, height = page.get_size()
                    if not all(math.isfinite(x) and x > 0 for x in (width, height)):
                        return False
                    with closing(page.render(scale=min(.15, 1024 / max(width, height)))) as bitmap:
                        if bitmap.width <= 0 or bitmap.height <= 0:
                            return False
                checkpoint()
        return True
    except (pdfium.PdfiumError, ValueError, OSError):
        return False


def check_successes(store, task, root, now, resource_use, validator=verify_pdf, *, retention=False, identity=None):
    outcomes = {}
    for row in store.successes(task):
        checkpoint()
        scope, date = row["scope"], row["date"]
        prior = store.health(task, scope, date)
        if retention and prior and prior["status"] == "retired":
            outcomes[(scope, date)] = "retired"
            continue  # Reappearing retired files have no automatic deletion authority.
        pending = retention and prior and prior["status"] == "retention_pending"
        try:
            path = safe_path(row["artifact"], root)
            if identity is not None and not identity(row, path):
                raise ValueError("Unexpected artifact identity")
            with resource_use(path):
                data = read_artifact(path, root)
                if not validator(data):
                    status, reason = "corrupt", "invalid_structure"
                elif not prior or prior["sha256"] is None or prior["size"] is None:
                    status, reason = "unverifiable", "historical_fingerprint_missing"
                elif fingerprint(data) != (prior["sha256"], prior["size"]):
                    status, reason = "corrupt", "fingerprint_mismatch"
                else:
                    status, reason = ("retention_pending", prior["error"]) if pending else ("healthy", None)
        except FileNotFoundError:
            status, reason = ("retired", "retention") if pending else ("missing", "artifact_missing")
        except (OSError, ValueError, TypeError):
            status, reason = "unverifiable", "artifact_inaccessible_or_unsafe"
        checkpoint()
        if pending and status == "retired":
            store.set_health(task, scope, date, status, now, reason, event="retention_deleted")
        else:
            store.set_health(task, scope, date, status, now, reason)
        outcomes[(scope, date)] = status
    return outcomes
