"""Artifact health is independent of historical execution success. Never regenerate."""
import hashlib
import math
from contextlib import closing
from pathlib import Path

from automation_cleanup import plain_path
from task_control import checkpoint


def fingerprint(data):
    return hashlib.sha256(data).hexdigest(), len(data)


def verify_pdf(data):
    if not isinstance(data, bytes) or not data.startswith(b"%PDF-") or not data.rstrip().endswith(b"%%EOF"):
        return False
    import pypdfium2 as pdfium
    try:
        with closing(pdfium.PdfDocument(data)) as document:
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
        return True
    except (pdfium.PdfiumError, ValueError, OSError):
        return False


def check_successes(store, task, root, now, validator):
    """Check old dates/scopes too; keep errors visible until human intervention."""
    outcomes = {}
    for row in store.successes(task):
        checkpoint()
        scope, date = row["scope"], row["date"]
        prior = store.health(task, scope, date)
        try:
            path = plain_path(Path(row["artifact"]), root)
            if prior and prior["status"] in ("retired", "retention_pending") and not path.exists():
                status, reason = "retired", "retention"
            elif not path.exists():
                status, reason = "missing", "artifact_missing"
            elif not path.is_file():
                status, reason = "corrupt", "not_a_regular_file"
            else:
                data = path.read_bytes()
                if not validator(data):
                    status, reason = "corrupt", "invalid_structure"
                elif not prior or prior["sha256"] is None:
                    status, reason = "unverifiable", "historical_fingerprint_missing"
                elif fingerprint(data) != (prior["sha256"], prior["size"]):
                    status, reason = "corrupt", "fingerprint_mismatch"
                else:
                    status, reason = "healthy", None
        except (OSError, ValueError, TypeError):
            status, reason = "unverifiable", "artifact_inaccessible_or_unsafe"
        store.set_health(task, scope, date, status, now, reason)
        outcomes[(scope, date)] = status
    return outcomes
