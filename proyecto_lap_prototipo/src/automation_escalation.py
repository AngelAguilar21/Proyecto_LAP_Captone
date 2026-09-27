"""Escalate only explicitly supervised projects, independently of the UI selection."""
from contextlib import closing
import json
import sqlite3

import business_data
from automation_cleanup import plain_path


class AlertEscalation:
    def __init__(self, engine):
        self.engine = engine

    def __call__(self, now, settings):
        if not settings["enabled"]:
            return "disabled"
        ids = tuple(settings.get("project_ids", ()))
        if not ids:
            return "no_supervised_projects"
        root = self.engine.settings_root
        with self.engine.lock:
            index_path = plain_path(root / "projects" / "index.json", root)
            index = json.loads(index_path.read_text(encoding="utf-8"))
            indexed = {p["id"] for p in index["projects"]}
        result = {"candidates": 0, "sent": 0}
        errors = {}
        for pid in ids:
            try:
                if pid not in indexed:
                    raise ValueError("Supervised project is not indexed")
                path = plain_path(root / "projects" / (pid + ".json"), root / "projects")
                if not path.is_file():
                    raise ValueError("Supervised configuration is missing")
                plain_path(business_data.path_for(path), root / "projects")
                outcome = self._project(path, now, settings)
                if isinstance(outcome, dict):
                    for key in result:
                        result[key] += outcome[key]
            except (OSError, ValueError, sqlite3.Error) as exc:
                errors[pid] = type(exc).__name__
        if errors:
            result["errors"] = errors
        return result

    def _project(self, path, now, settings):
        # Do not create a business database merely because a task ticked.
        if not business_data.path_for(path).exists():
            return "no_incidents"
        notifications = self.engine.notifications
        notifications.recover(path)
        cutoff = now.timestamp() - settings["delay_minutes"] * 60
        with closing(business_data.connect(path)) as db:
            incidents = db.execute(
                "SELECT id, tipo, zona FROM incidentes i WHERE estado='pendiente' "
                "AND review_history_known=1 AND reviewed_at IS NULL AND creado<=? "
                "AND NOT EXISTS (SELECT 1 FROM incident_notifications n WHERE n.incident_id=i.id "
                "AND n.notification_kind='escalation' AND n.status<>'failed') ORDER BY creado, id",
                (cutoff,)).fetchall()
        sent = 0
        for iid, kind, zone in incidents:
            sent += bool(notifications.send(
                path, iid, "AeroTrack: incidente pendiente de atención",
                f"Incidente: {iid}\nTipo: {kind}\nZona: {zone or '-'}\nRequiere revisión humana.",
                kind="escalation", blocking=True, recipients=settings["recipients"],
                escalation_due_before=cutoff))
        return {"candidates": len(incidents), "sent": sent}
