"""At most one published commercial report per project and Lima date."""
import os
import tempfile
from pathlib import Path

import projects
from live_reports import business_report_data, business_pdf_bytes


class ScheduledReports:
    def __init__(self, engine, store, renderer=business_pdf_bytes):
        self.engine, self.store, self.renderer = engine, store, renderer

    def __call__(self, now, settings):
        if now.strftime("%H:%M") < settings["time"]:
            return "not_due"
        capture = self.engine.automation_snapshot()
        pid = capture["project_id"]
        if pid is None:
            return "unmanaged"
        projects.project_path(self.engine.data_root, pid)  # Validate the path component.
        date = now.date().isoformat()
        prior = self.store.get("reports", pid, date)
        if prior and prior["status"] == "succeeded":
            return "already_done"
        target = self.engine.data_root / "data" / "reports" / pid / f"business-{date}.pdf"
        if target.exists():
            # Reconcile a crash after atomic publication and before DB commit.
            if not target.read_bytes().startswith(b"%PDF-"):
                raise ValueError("Existing report is not a valid PDF")
            self.store.record("reports", pid, date, "succeeded", now, str(target))
            return "recovered"
        state, config = capture["state"], capture["config"]
        if (not config or not state.get("session") or state.get("status") not in
                ("running", "paused", "stopped", "ended") or not state.get("series") or
                "totals" not in state or "zones" not in state.get("analytics", {}) or
                state.get("t", 0) <= 0):
            self.store.record("reports", pid, date, "no_data", now)
            return "no_data"
        # Both formatting and PDF generation occur after the snapshot lock ends.
        data = business_report_data(config, state)
        data["generated"] = now.isoformat()
        pdf = self.renderer(data)
        if not isinstance(pdf, bytes) or not pdf.startswith(b"%PDF-"):
            raise ValueError("Renderer did not produce a PDF")
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".business-", suffix=".tmp", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(pdf)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)
        self.store.record("reports", pid, date, "succeeded", now, str(target))
        return "succeeded"
