"""Transactional safety facts and lineage, without message contents or secrets."""
import json
import sqlite3


def migrate(db):
    db.execute("BEGIN IMMEDIATE")
    with db:
        db.execute("CREATE TABLE IF NOT EXISTS operational_identity "
                   "(singleton INTEGER PRIMARY KEY CHECK(singleton=1), storage_id TEXT NOT NULL)")
        db.execute("INSERT OR IGNORE INTO operational_identity VALUES (1,lower(hex(randomblob(16))))")
        db.execute("CREATE TABLE IF NOT EXISTS operational_events "
                   "(seq INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT UNIQUE NOT NULL,"
                   "entity TEXT NOT NULL,entity_id TEXT NOT NULL,facts TEXT NOT NULL)")
        columns = {
            "incidentes": ("id", ("estado", "review_history_known", "reviewed_at", "history_validated_at")),
            "incident_notifications": ("incident_id", ("notification_kind", "status", "sent_at", "attempts")),
        }
        for table, (key, fields) in columns.items():
            trigger = "journal_" + table + "_insert"
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='trigger' AND name=?", (trigger,)).fetchone()
            if not exists:
                # Establish facts at upgrade, never invent a historical event time.
                for row in db.execute(f"SELECT {key}," + ",".join(fields) + f" FROM {table}").fetchall():
                    db.execute("INSERT INTO operational_events(event_id,entity,entity_id,facts) "
                               "VALUES (lower(hex(randomblob(16))),?,?,?)",
                               (table, row[0], json.dumps(dict(zip(fields, row[1:])))))
            args = ",".join(f"'{f}',NEW.{f}" for f in fields)
            for action in ("insert", "update"):
                when = "" if action == "insert" else " WHEN " + " OR ".join(f"OLD.{f} IS NOT NEW.{f}" for f in fields)
                db.execute(f"CREATE TRIGGER IF NOT EXISTS journal_{table}_{action} AFTER {action.upper()} ON {table}"
                           f"{when} BEGIN INSERT INTO operational_events(event_id,entity,entity_id,facts) "
                           f"VALUES (lower(hex(randomblob(16))),'{table}',NEW.{key},json_object({args})); END")


def provenance(db):
    try:
        identity = db.execute("SELECT storage_id FROM operational_identity WHERE singleton=1").fetchone()
        anchor = db.execute("SELECT seq,event_id FROM operational_events ORDER BY seq DESC LIMIT 1").fetchone()
        return {"storage_id": identity[0], "seq": anchor[0] if anchor else 0,
                "event_id": anchor[1] if anchor else None} if identity else None
    except sqlite3.OperationalError:
        return None


def descends_from(db, ancestor):
    current = provenance(db)
    if not current or not ancestor or current["storage_id"] != ancestor["storage_id"]:
        return False
    if ancestor["seq"] == 0:
        return True
    anchor = db.execute("SELECT event_id FROM operational_events WHERE seq=?", (ancestor["seq"],)).fetchone()
    return bool(anchor and anchor[0] == ancestor["event_id"])
