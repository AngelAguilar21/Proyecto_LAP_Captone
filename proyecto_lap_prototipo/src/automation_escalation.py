"""Supervision of aggregate incidents in the captured active project only."""
from contextlib import closing
from pathlib import Path

import automation_settings
import business_data
from task_control import checkpoint


def _label(value):
    # Labels are untrusted operator input. Do not propagate source URLs or
    # multiline content even if it was mistakenly stored in an aggregate field.
    if not isinstance(value, str) or len(value) > 200 or "://" in value or any(ord(c) < 32 for c in value):
        return "[omitido]"
    return value


class AlertEscalation:
    def __init__(self, engine):
        self.engine = engine

    def __call__(self, now, options):
        options = automation_settings.validate({"escalation": options})["escalation"]
        if not options["enabled"]:
            return {"candidates": 0, "sent": 0, "status": "disabled"}
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("An aware timestamp is required")
        checkpoint()
        with self.engine.lock:
            project_id = self.engine.project_id
            project_path = Path(self.engine.config_path)
        # Protect the captured database through recovery, claim and delivery.
        # No Engine.lock is held during SQLite or SMTP operations.
        with self.engine.resource_use(business_data.path_for(project_path), write=True):
            if not business_data.path_for(project_path).is_file():
                return {"candidates": 0, "sent": 0, "status": "no_incidents"}
            self.engine.notifications.recover(project_path)
            checkpoint()
            cutoff = now.timestamp() - options["delay_minutes"] * 60
            with closing(business_data.connect(project_path)) as db:
                candidates = business_data.incidentes_para_escalar(db, cutoff)
            sent = 0
            for incident_id, kind, zone, created in candidates:
                checkpoint()
                # Whitelist: never serialize detalle, camera configuration or live state.
                body = (f"Incidente: {_label(incident_id)}\nTipo: {_label(kind)}\nZona: {_label(zone or '-')}\n"
                        f"Proyecto: {_label(project_id or 'configuración local')}\n"
                        f"Tiempo pendiente: {(now.timestamp() - created) / 60:.1f} minutos\n\n"
                        "El incidente sigue pendiente. Requiere revisión humana; "
                        "esta notificación no constituye una verificación de lo ocurrido.")
                if self.engine.notifications.send(
                        project_path, incident_id, "AeroTrack · Incidente pendiente de supervisión", body,
                        kind="escalation", blocking=True, recipients=options["recipients"],
                        escalation_due_before=cutoff):
                    sent += 1
            return {"candidates": len(candidates), "sent": sent}
