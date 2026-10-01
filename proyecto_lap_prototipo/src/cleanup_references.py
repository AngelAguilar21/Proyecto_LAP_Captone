"""Read-only inventory of durable references. Uncertainty is never absence."""
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import business_data
from path_security import absolute, plain_path, identity, read_json, strict_json
from task_control import checkpoint

BUSINESS_TABLES = {"negocios", "ventas", "incidentes", "incident_notifications", "incident_replay_links",
                   "trafico_historico", "negocio_ubicaciones", "negocio_puertas", "negocio_referencias",
                   "negocio_estados", "commercial_sales", "commercial_imports", "commercial_traffic",
                   "commercial_incidents", "commercial_bags", "sqlite_sequence"}


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def reference_paths(documents, root):
    refs = set()
    root = absolute(root)
    for document in documents:
        checkpoint()
        for text in strings(document):
            if not text or "://" in text:
                continue
            if "\x00" in text or ".." in text.replace("\\", "/").split("/"):
                raise ValueError("ambiguous_reference")
            if re.fullmatch(r"[a-f0-9]{8,32}", text):
                refs.add(root / "data" / "replays" / text)
            if "/" not in text and "\\" not in text:
                continue
            path = absolute(root / text)
            if any(path.is_relative_to(root / "data" / kind) for kind in ("replays", "uploads")):
                refs.add(path)
    return refs


@contextmanager
def readonly_database(path, root):
    """Never create journals/SHM. A live WAL or journal is deliberately uncertain.

    immutable avoids SQLite writing auxiliary files even for a read-only WAL-mode
    database. It is used ONLY after rejecting uncheckpointed sidecars, and the
    application gates writers during APPLY. External file changes also invalidate
    the read. No database is created, copied, repaired or migrated here.
    """
    path = plain_path(path, root)
    before = identity(path)
    def sidecars():
        for suffix in ("-wal", "-journal", "-shm"):
            file = plain_path(Path(str(path) + suffix), root)
            if file.exists():
                info = identity(file)
                if suffix != "-shm" and info[2]:
                    raise ValueError("uncheckpointed_reference_database")
    sidecars()
    db = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=0)
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        yield db
        checkpoint()
        sidecars()
        if identity(plain_path(path, root)) != before:
            raise ValueError("reference_database_changed")
    finally:
        db.close()


def incident_references(settings_root):
    documents = []
    settings_root = absolute(settings_root)
    for directory in (settings_root, settings_root / "projects"):
        plain_path(directory, settings_root)
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.negocios.sqlite")):
            checkpoint()
            with readonly_database(path, settings_root) as db:
                tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if "incidentes" not in tables or tables - BUSINESS_TABLES:
                    raise ValueError("unknown_incident_schema")
                links = {}
                if "incident_replay_links" in tables:
                    rows = db.execute("SELECT incident_id,resolution,session_id FROM incident_replay_links").fetchall()
                    links = {iid: (resolution, sid) for iid, resolution, sid in rows}
                    if len(links) != len(rows):
                        raise ValueError("duplicate_incident_reference")
                incidents = set()
                for iid, detail in db.execute("SELECT id,detalle FROM incidentes"):
                    checkpoint()
                    incidents.add(iid)
                    value = strict_json(detail or "{}")
                    sid = business_data.replay_session(value)
                    if sid is None or (iid in links and links[iid] != ("linked", sid)):
                        raise ValueError("unknown_incident_reference")
                    documents.extend((value, {"session": sid}))
                if set(links) - incidents:
                    raise ValueError("orphan_incident_reference")
                # Modern business tables may also retain asset/source/import paths.
                for table in sorted(tables - {"incidentes", "incident_replay_links"}):
                    for row in db.execute(f'SELECT * FROM "{table}"'):
                        checkpoint()
                        for value in row:
                            if isinstance(value, str):
                                documents.append(strict_json(value) if value.startswith(("{", "[")) else value)
    return documents


def saved_documents(root, settings_root):
    root, settings_root = absolute(root), absolute(settings_root)
    plain_path(settings_root, root)
    documents = []
    directory = plain_path(settings_root / "projects", root)
    if directory.exists():
        index, _ = read_json(directory / "index.json", root)
        entries = index.get("projects")
        if not isinstance(entries, list) or not entries:
            raise ValueError("invalid_project_index")
        ids = []
        for entry in entries:
            pid = entry.get("id") if isinstance(entry, dict) else None
            if not isinstance(pid, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", pid) or pid == "index":
                raise ValueError("invalid_project_id")
            read_json(directory / (pid + ".json"), root)  # Missing indexed JSON is not absence.
            ids.append(pid)
        if len(set(pid.casefold() for pid in ids)) != len(ids) or index.get("active") not in ids:
            raise ValueError("invalid_project_index")
        for file in sorted(directory.iterdir()):
            plain_path(file, root)
            if file.is_dir() or file.name.endswith((".tmp", ".part")):
                raise ValueError("uncertain_project_storage")
            if file.suffix == ".json":
                documents.append(read_json(file, root)[0])  # Includes retained orphan projects.
            elif not file.name.endswith((".negocios.sqlite", ".negocios.sqlite-wal", ".negocios.sqlite-shm", ".negocios.sqlite-journal")):
                raise ValueError("unknown_project_storage")
    for name in ("live.local.json", "counting.local.json", "camaras.json"):
        path = plain_path(settings_root / name, root)
        if path.exists():
            documents.append(read_json(path, root)[0])
    path = plain_path(settings_root / "counting.sqlite", root)
    if path.exists():
        with readonly_database(path, root) as db:
            for (payload,) in db.execute("SELECT payload FROM sessions"):
                checkpoint()
                value = strict_json(payload)
                if not isinstance(value, dict):
                    raise ValueError("invalid_counting_history")
                documents.append(value)  # Full history; no UI LIMIT 30.
    documents.extend(incident_references(settings_root))
    return documents
