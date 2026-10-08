"""One aggregate snapshot report per project and Lima date; no daily rollup."""
import json
import math
import os
import sqlite3
import tempfile
from pathlib import Path

import projects
from automation import LIMA
from automation_artifacts import CHUNK, check_successes, fingerprint, read_artifact, safe_path, verify_pdf
from live_reports import business_report_data, business_pdf_bytes
from task_control import Cancelled, checkpoint


def eligible(capture):
    """Require the observations used by the modern renderer, including its KPIs.

    Empty zone/access lists and observed zero counts are valid. Missing samples
    or KPIs are not evidence of zero activity.
    """
    state, config = capture["state"], capture["config"]
    def number(value):
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    if (not state.get("session") or state.get("status") not in ("running", "paused", "stopped", "ended") or
            not number(state.get("t")) or state["t"] <= 0 or not config.get("unit") or
            not isinstance(config.get("cameras"), list) or
            any(not c.get("id") for c in config["cameras"])):
        return False
    series, zones, totals = state.get("series"), state.get("analytics", {}).get("zones"), state.get("totals", {})
    return (isinstance(series, list) and bool(series) and
            all(number(row.get("t")) and number(row.get("count")) for row in series) and
            all(number(totals.get(k)) for k in ("meanObservedSeconds", "alerts")) and
            isinstance(zones, list) and all(isinstance(z.get("name"), str) and
            all(number(z.get(k)) for k in ("seconds", "visits", "peak")) for z in zones))


def publish_pdf(pdf, target, root):
    """Validated bytes -> same-directory temporary -> fsync -> atomic replace.

    Caller owns a writer lease and the SQLite publication transaction.
    """
    target = safe_path(target, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    safe_path(target, root)
    fd, temporary = tempfile.mkstemp(prefix=".business-", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            for start in range(0, len(pdf), CHUNK):
                checkpoint()
                output.write(pdf[start:start + CHUNK])
            output.flush()
            os.fsync(output.fileno())
        checkpoint()
        safe_path(target, root)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


class ScheduledReports:
    # The callback owns project-scoped durable outcomes. The generic runtime
    # must not manufacture a second reports/service/succeeded artifact record.
    records_execution = True

    def __init__(self, engine, store, renderer=business_pdf_bytes):
        self.engine, self.store, self.renderer = engine, store, renderer
        self.root = engine.data_root / "data" / "reports"
        self.resources = engine.resources
        self.resource_use = engine.resource_use

    def _existing(self, db, pid, date, target, now):
        prior = self.store.get("reports", pid, date, connection=db)
        if prior and prior["status"] == "succeeded":
            return "already_done"
        target = safe_path(target, self.root)
        if target.exists():
            data = read_artifact(target, self.root)
            if not verify_pdf(data):
                raise ValueError("Existing report is not a valid PDF; human review required")
            digest = fingerprint(data)
            checkpoint()
            self.store.publish_success(db, "reports", pid, date, now, str(target), digest)
            return "recovered"
        return None

    def _report(self, capture, pid, date, target, now):
        # Avoid even rendering when recovering a published file after a crash.
        with self.store.publication() as db:
            outcome = self._existing(db, pid, date, target, now)
        if outcome is not None:
            return outcome
        if not eligible(capture):
            self.store.record("reports", pid, date, "no_data", now, preserve_success=True)
            return "no_data"
        self.store.record("reports", pid, date, "running", now, preserve_success=True)
        data = business_report_data(capture["config"], capture["state"])
        data["generated"] = now.isoformat()
        pdf = self.renderer(data)
        checkpoint()
        if not verify_pdf(pdf):
            raise ValueError("Renderer did not produce a structurally valid PDF")
        digest = fingerprint(pdf)
        # A second service/process may have won while we rendered. Recheck both
        # history and the final file under SQLite's write lock before replacing.
        with self.store.publication() as db:
            outcome = self._existing(db, pid, date, target, now)
            if outcome is not None:
                return outcome
            checkpoint()
            publish_pdf(pdf, target, self.root)
            # No cancellation checkpoint between replace and recording success.
            self.store.publish_success(db, "reports", pid, date, now, str(target), digest)
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
        with self.resources.activity():
            capture = self.engine.automation_snapshot()
            pid, date = capture["projectId"], now.date().isoformat()
            if pid is None:
                self.store.audit("reports", json.dumps(dict(date=date, status="no_data", reason="unmanaged_project")), now)
                outcome = "no_data"
            else:
                projects.project_path(self.root.parent.parent, pid)  # Existing project-id validation.
                target = self.root / pid / f"business-{date}.pdf"
                try:
                    safe_path(target, self.root)
                    with self.resource_use(target.parent, write=True):
                        outcome = self._report(capture, pid, date, target, now)
                except Exception as exc:
                    status = "cancelled" if isinstance(exc, Cancelled) else "failed"
                    try:
                        self.store.record("reports", pid, date, status, now,
                                          error=type(exc).__name__, preserve_success=True)
                    except (OSError, sqlite3.Error):
                        pass  # Original failure is reported by the runtime.
                    raise
            # Today's publication takes priority over a potentially long history.
            health = check_successes(self.store, "reports", self.root, now, self.resource_use)
            if outcome == "already_done" and health.get((pid, date)) != "healthy":
                return "artifact_problem"
            return outcome
