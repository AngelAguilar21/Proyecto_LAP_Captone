"""Escalate pending incidents on the captured active project, without new threads."""
from contextlib import closing

import business_data


class AlertEscalation:
    def __init__(self, engine):
        self.engine = engine

    def __call__(self, now, settings):
        if not settings["enabled"]:
            return "disabled"
        with self.engine.lock:
            path = self.engine.config_path
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
