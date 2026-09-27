"""Conservative retention planning. No filesystem mutations during planning."""
import json
import copy
import os
import re
import sqlite3
import stat
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import business_data
from task_control import checkpoint


def incident_references(settings_root):
    """No migrations/writes; old schemas are interpreted conservatively."""
    documents = []
    directories = [settings_root, settings_root / "projects"]
    for directory in directories:
        plain_path(directory, settings_root)
        if not directory.exists():
            continue
        for path in directory.glob("*.negocios.sqlite"):
            plain_path(path, settings_root)
            for suffix in ("-wal", "-shm", "-journal"):
                plain_path(Path(str(path) + suffix), settings_root)
            with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0)) as db:
                db.execute("PRAGMA query_only=ON")
                db.execute("BEGIN")
                tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                # A database with an unknown schema cannot establish absence of references.
                if "incidentes" not in tables:
                    raise ValueError("unknown_incident_schema")
                links = {}
                if "incident_replay_links" in tables:
                    links = {iid: (resolution, sid) for iid, resolution, sid in
                             db.execute("SELECT incident_id,resolution,session_id FROM incident_replay_links")}
                for iid, detail in db.execute("SELECT id,detalle FROM incidentes"):
                    resolution, sid = links.get(iid, (None, None))
                    value = json.loads(detail or "{}")
                    legacy_sid = value.get("sesion") if isinstance(value, dict) else None
                    if resolution is None:
                        sid = legacy_sid
                    elif resolution != "linked" or (legacy_sid is not None and legacy_sid != sid):
                        raise ValueError("unknown_incident_reference")
                    if not isinstance(sid, str) or not re.fullmatch(r"[a-f0-9]{8,32}", sid):
                        raise ValueError("unknown_incident_reference")
                    documents.append({"session": sid})
    return documents


@dataclass(frozen=True)
class Decision:
    path: str
    disposition: str
    reason: str
    fingerprint: tuple = ()


@dataclass(frozen=True)
class CleanupPlan:
    root: Path
    settings_root: Path
    now: datetime
    retention_days: int
    decisions: tuple


def plain_path(path, root):
    checkpoint()
    """Reject links/reparse points on every component; never traverse them."""
    path, root = Path(os.path.abspath(path)), Path(os.path.abspath(root))
    if not path.is_relative_to(root):
        raise ValueError("outside_root")
    if root.resolve() != root:
        raise ValueError("linked_root_ancestor")
    ancestors = []
    parent = path
    while parent != root:
        ancestors.append(parent)
        parent = parent.parent
    for part in (root, *reversed(ancestors)):
        if part.is_symlink() or part.is_junction():
            raise ValueError("linked_path")
        if part.exists() and getattr(part.lstat(), "st_file_attributes", 0) & 1024:
            raise ValueError("reparse_point")
    return path


def read_json(path, root):
    path = plain_path(path, root)
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("invalid_document")
    return result


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
    for document in documents:
        for text in strings(document):
            if not text or "://" in text:
                continue
            if "\x00" in text:
                raise ValueError("invalid_reference")
            candidate = Path(os.path.abspath(root / text))
            if candidate.is_relative_to(root / "data" / "replays") or candidate.is_relative_to(root / "data" / "uploads"):
                if ".." in Path(text).parts:
                    raise ValueError("ambiguous_reference")
                refs.add(candidate)
            # Config/history may retain a session identity rather than a path.
            if re.fullmatch(r"[a-f0-9]{8,32}", text):
                refs.add(root / "data" / "replays" / text)
    return refs


def saved_documents(root, settings_root):
    documents = []
    project_dir = plain_path(settings_root / "projects", settings_root)
    if project_dir.exists():
        index = read_json(project_dir / "index.json", settings_root)
        entries = index.get("projects")
        if not isinstance(entries, list) or not entries:
            raise ValueError("invalid_project_index")
        for entry in entries:
            pid = entry["id"]
            if not isinstance(pid, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", pid):
                raise ValueError("invalid_project_id")
            if not (project_dir / (pid + ".json")).is_file():
                raise ValueError("missing_project")
        for file in project_dir.iterdir():
            plain_path(file, settings_root)
            if file.is_dir() or file.suffix == ".tmp":
                raise ValueError("uncertain_project_storage")
            if file.suffix == ".json":
                documents.append(read_json(file, settings_root))
    for name in ("live.local.json", "counting.local.json"):
        path = plain_path(settings_root / name, settings_root)
        if path.exists():
            documents.append(read_json(path, settings_root))
    database = plain_path(settings_root / "counting.sqlite", settings_root)
    if database.exists():
        for suffix in ("-wal", "-shm", "-journal"):
            plain_path(Path(str(database) + suffix), settings_root)
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
            # All sessions, including those beyond the UI history limit.
            for (payload,) in db.execute("SELECT payload FROM sessions"):
                value = json.loads(payload)
                if not isinstance(value, dict):
                    raise ValueError("invalid_counting_history")
                documents.append(value)
    documents.extend(incident_references(settings_root))
    return documents


def replay_fingerprint(path, root):
    if not path.is_dir():
        raise ValueError("not_a_replay_directory")
    children = sorted(path.iterdir())
    if {p.name for p in children} != {"manifest.json", "samples.jsonl"}:
        raise ValueError("unknown_replay_contents")
    result = []
    for file in children:
        plain_path(file, root)
        info = file.stat()
        if not stat.S_ISREG(info.st_mode) or not info.st_mode & stat.S_IWRITE or not os.access(file, os.W_OK):
            raise ValueError("uncertain_permissions")
        result.append((file.name, info.st_size, info.st_mtime_ns, info.st_ino))
    return tuple(result)


def plan_cleanup(root, settings_root, now, retention_days, *, documents=(), active_sessions=(), busy=False):
    """Return protected/omitted/candidate decisions; never creates or deletes data."""
    if now.tzinfo is None or now.utcoffset() is None or type(retention_days) is not int or retention_days < 1:
        raise ValueError("Invalid retention timestamp/days")
    root, settings_root = Path(os.path.abspath(root)), Path(os.path.abspath(settings_root))
    decisions, candidates, manifests = [], [], []
    uncertainty = None
    cutoff = now.timestamp() - retention_days * 86400
    try:
        references = reference_paths([*documents, *saved_documents(root, settings_root)], root)
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
        references, uncertainty = set(), "uncertain_references"
    for kind in ("replays", "uploads"):
        folder = root / "data" / kind
        try:
            plain_path(folder, root)
            entries = sorted(folder.iterdir()) if folder.exists() else []
        except (OSError, ValueError):
            decisions.append(Decision(f"data/{kind}", "omitted", "unsafe_or_unreadable_root"))
            uncertainty = "uncertain_references"
            continue
        for path in entries:
            relative = path.relative_to(root).as_posix()
            try:
                plain_path(path, root)
                if kind == "uploads":
                    # No durable completion marker exists in the upload protocol.
                    decisions.append(Decision(relative, "omitted", "upload_completion_unknown"))
                    continue
                if not re.fullmatch(r"[a-f0-9]{8,32}", path.name):
                    raise ValueError("unknown_session_name")
                meta = read_json(path / "manifest.json", root)
                if meta.get("session") != path.name or not isinstance(meta.get("cameras"), list) or not isinstance(meta.get("config"), dict):
                    raise ValueError("invalid_manifest")
                if any(not isinstance(camera, dict) or type(camera.get("source")) not in (str, int)
                       for camera in meta["cameras"]):
                    raise ValueError("invalid_camera_reference")
                created = datetime.fromisoformat(meta["created"].replace("Z", "+00:00"))
                if created.tzinfo is None:
                    raise ValueError("unknown_creation_timezone")
                # Do not treat the manifest's own session id as an outside reference.
                manifests.append({k: v for k, v in meta.items() if k != "session"})
                if path.name in active_sessions or meta.get("status") == "running":
                    decisions.append(Decision(relative, "protected", "active_session"))
                    continue
                if meta.get("status") not in ("ended", "stopped", "error"):
                    raise ValueError("unknown_session_status")
                fingerprint = replay_fingerprint(path, root)
                if created.timestamp() > cutoff or any((path / name).stat().st_mtime > cutoff for name, *_ in fingerprint):
                    decisions.append(Decision(relative, "protected", "recent_resource"))
                    continue
                candidates.append(Decision(relative, "candidate", "expired_unreferenced", fingerprint))
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                decisions.append(Decision(relative, "omitted", "unsafe_or_uncertain_resource"))
                uncertainty = "uncertain_references"
    try:
        references.update(reference_paths(manifests, root))
    except (OSError, ValueError):
        uncertainty = "uncertain_references"
    for item in candidates:
        path = root / item.path
        if uncertainty or busy:
            decisions.append(Decision(item.path, "omitted", uncertainty or "resources_in_use"))
        elif any(ref == path or ref.is_relative_to(path) or path.is_relative_to(ref) for ref in references):
            decisions.append(Decision(item.path, "protected", "referenced_resource"))
        else:
            decisions.append(item)
    return CleanupPlan(root, settings_root, now, retention_days, tuple(sorted(decisions, key=lambda d: d.path)))


class RetentionCleanup:
    def __init__(self, engine, store):
        self.engine, self.store = engine, store

    def _capture(self, now, retention_days):
        # Requests register use before opening files or starting background work.
        # Existing requests/active workers cause omission; no waiting for them.
        with self.engine.resource_lock:
            with self.engine.lock:
                busy = bool(self.engine.resource_users)
                for worker in (self.engine.worker, self.engine.preview_worker):
                    busy |= bool(worker and worker.is_alive())
                documents = copy.deepcopy([self.engine.config, self.engine.runtime_config,
                                            self.engine.report_config])
                sessions = set()
                if self.engine.state.get("status") in ("starting", "running", "paused", "stopping"):
                    sessions.add(self.engine.state.get("session"))
                    busy = True
                counting = getattr(self.engine, "counting", None)
                if counting:
                    if counting.lock.acquire(blocking=False):
                        try:
                            busy |= counting.active()
                            documents.extend(copy.deepcopy([counting.config, counting.state]))
                        finally:
                            counting.lock.release()
                    else:
                        busy = True
                path = self.engine.config_path
                root, settings = self.engine.data_root, self.engine.settings_root
            try:
                if path.exists():
                    documents.append(read_json(path, settings))
            except (OSError, ValueError):
                busy = True
            return dict(root=root, settings_root=settings, now=now, retention_days=retention_days,
                        documents=documents, active_sessions=sessions, busy=busy)

    def plan_cleanup(self, now, retention_days):
        with self.engine.resource_lock:
            captured = self._capture(now, retention_days)
            with business_data.reference_lock:
                return plan_cleanup(**captured)

    def apply_cleanup(self, plan):
        """Revalidate each candidate under the request gate; never use recursive rm."""
        if plan.root != Path(os.path.abspath(self.engine.data_root)) or plan.settings_root != Path(os.path.abspath(self.engine.settings_root)):
            raise ValueError("Plan belongs to another workspace")
        with self.engine.resource_lock:
            captured = self._capture(plan.now, plan.retention_days)
            with business_data.reference_lock:
                return self._apply_locked(plan, captured)

    def _apply_locked(self, plan, captured):
        from restore_guard import blocked
        if blocked(self.engine.settings_root):
            return [{"path": d.path, "decision": "omitted", "reason": "restore_hold"} for d in plan.decisions]
        outcomes = []
        fresh = {d.path: d for d in plan_cleanup(**captured).decisions}
        for decision in plan.decisions:
            checkpoint()
            disposition, reason = decision.disposition, decision.reason
            if disposition == "candidate":
                current = fresh.get(decision.path)
                if current != decision:
                    disposition, reason = "omitted", "plan_changed"
                else:
                    path = plan.root / decision.path
                    # The plan is data, not authority: constrain even forged paths.
                    plain_path(path, plan.root / "data" / "replays")
                    if path.parent != plan.root / "data" / "replays":
                        raise ValueError("Invalid candidate depth")
                    self.store.audit("cleanup", json.dumps({"path": decision.path,
                                     "decision": "delete_planned", "reason": reason}), plan.now)
                    try:
                        if replay_fingerprint(path, plan.root) != decision.fingerprint:
                            raise ValueError("changed_resource")
                        # Delete manifest last. A partial failure remains identifiable
                        # and becomes uncertain on the next plan.
                        (path / "samples.jsonl").unlink()
                        (path / "manifest.json").unlink()
                        path.rmdir()
                        disposition, reason = "deleted", "expired_unreferenced"
                    except (OSError, ValueError):
                        disposition, reason = "omitted", "delete_failed_or_changed"
            result = {"path": decision.path, "decision": disposition, "reason": reason}
            self.store.audit("cleanup", json.dumps(result), plan.now)
            outcomes.append(result)
        return outcomes

    def __call__(self, now, settings):
        if not settings["enabled"]:
            return "disabled"
        plan = self.plan_cleanup(now, settings["retention_days"])
        return self.apply_cleanup(plan)
