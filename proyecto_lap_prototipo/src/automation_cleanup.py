"""Conservative PLAN/APPLY retention of completed uploads and finished replays."""
import copy
import json
import os
import re
import sqlite3
import stat
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import business_data
from cleanup_references import incident_references, saved_documents, reference_paths
from path_security import absolute, plain_path, file_fingerprint, read_json
from task_control import Cancelled, checkpoint
from uploads import MARKER, metadata_path, completed_fingerprint

ACTIVE = {"starting", "running", "paused", "stopping"}
REPLAY_FILES = ("samples.jsonl", "manifest.json")  # data first, manifest last
UNCERTAIN = (OSError, ValueError, TypeError, KeyError, AttributeError, sqlite3.Error)


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


def replay_fingerprint(path, root):
    path = plain_path(path, root)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or not info.st_ino:
        raise ValueError("not_a_replay_directory")
    before = (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns)
    if {p.name for p in path.iterdir()} != set(REPLAY_FILES):
        raise ValueError("unknown_replay_contents")
    fingerprints = []
    for name in REPLAY_FILES:
        file = plain_path(path / name, root)
        if not file.lstat().st_mode & stat.S_IWRITE or not os.access(file, os.W_OK):
            raise ValueError("uncertain_permissions")
        fingerprints.append((name, file_fingerprint(file, root)[0]))
    plain_path(path, root)
    info = path.lstat()
    if before != (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns):
        raise ValueError("replay_changed")
    return before, tuple(fingerprints)


def plan_cleanup(root, settings_root, now, retention_days, *, documents=(), active_sessions=(),
                 busy=False, leased_paths=()):
    """No DB creation/migration, no renames, repairs, deletion or audit writes."""
    if now.tzinfo is None or now.utcoffset() is None or type(retention_days) is not int or not 1 <= retention_days <= 3650:
        raise ValueError("Invalid retention timestamp/days")
    root, settings_root = absolute(root), absolute(settings_root)
    cutoff = now.timestamp() - retention_days * 86400
    decisions, candidates, manifests = [], [], []
    uncertainty = None
    try:
        refs = reference_paths([*documents, *saved_documents(root, settings_root)], root)
    except UNCERTAIN:
        refs, uncertainty = set(), "uncertain_references"
    for kind in ("replays", "uploads"):
        folder = root / "data" / kind
        checkpoint()
        try:
            plain_path(folder, root)
            entries = sorted(folder.iterdir()) if folder.exists() else []
        except UNCERTAIN:
            decisions.append(Decision(f"data/{kind}", "omitted", "unsafe_or_unreadable_root"))
            uncertainty = "uncertain_references"
            continue
        for path in entries:
            checkpoint()
            relative = path.relative_to(root).as_posix()
            try:
                plain_path(path, root)
                if kind == "uploads":
                    if path.name.endswith(MARKER):
                        owner = plain_path(path.with_name(path.name[:-len(MARKER)]), root)
                        if owner.exists():
                            continue  # Marker is evaluated only together with its final file.
                    if not plain_path(metadata_path(path), root).exists():
                        decisions.append(Decision(relative, "omitted", "upload_completion_unknown"))
                        continue
                    try:
                        completed_at, fingerprint = completed_fingerprint(path, root)
                    except UNCERTAIN:
                        decisions.append(Decision(relative, "omitted", "upload_completion_invalid"))
                        continue
                    if completed_at >= cutoff:  # age must be strictly greater than retention
                        decisions.append(Decision(relative, "protected", "recent_resource"))
                    else:
                        candidates.append(Decision(relative, "candidate", "expired_unreferenced", fingerprint))
                    continue
                if not re.fullmatch(r"[a-f0-9]{8,32}", path.name):
                    raise ValueError("unknown_session_identity")
                meta, meta_fp = read_json(path / "manifest.json", root)
                if (meta.get("session") != path.name or not isinstance(meta.get("cameras"), list) or
                        not isinstance(meta.get("config"), dict) or any(
                            not isinstance(c, dict) or type(c.get("source")) not in (str, int) for c in meta["cameras"])):
                    raise ValueError("invalid_manifest")
                manifests.append({k: v for k, v in meta.items() if k != "session"})
                created = datetime.fromisoformat(meta["created"].replace("Z", "+00:00"))
                if created.tzinfo is None or created.utcoffset() is None:
                    raise ValueError("unknown_creation_timezone")
                if path.name in active_sessions or meta.get("status") in ACTIVE:
                    decisions.append(Decision(relative, "protected", "active_session"))
                    continue
                if meta.get("status") not in ("ended", "stopped", "error"):
                    raise ValueError("unknown_session_status")
                fingerprint = replay_fingerprint(path, root)
                if dict(fingerprint[1])["manifest.json"] != meta_fp:
                    raise ValueError("manifest_changed")
                newest_write = max(fp[0][3] / 1e9 for _, fp in fingerprint[1])
                if created.timestamp() >= cutoff or newest_write >= cutoff:
                    decisions.append(Decision(relative, "protected", "recent_resource"))
                else:
                    candidates.append(Decision(relative, "candidate", "expired_unreferenced", fingerprint))
            except UNCERTAIN:
                decisions.append(Decision(relative, "omitted", "unsafe_or_uncertain_resource"))
                uncertainty = "uncertain_references"  # Unknown manifest may contain more references.
    try:
        refs.update(reference_paths(manifests, root))
    except UNCERTAIN:
        uncertainty = "uncertain_references"
    for item in candidates:
        path = root / item.path
        if any(path == p or path.is_relative_to(p) or p.is_relative_to(path) for p in leased_paths):
            decisions.append(Decision(item.path, "protected", "resource_in_use"))
        elif uncertainty or busy:
            decisions.append(Decision(item.path, "omitted", uncertainty or "resources_in_use"))
        elif any(path == p or path.is_relative_to(p) or p.is_relative_to(path) for p in refs):
            decisions.append(Decision(item.path, "protected", "referenced_resource"))
        else:
            decisions.append(item)
    return CleanupPlan(root, settings_root, now, retention_days, tuple(sorted(decisions, key=lambda d: d.path)))


class RetentionCleanup:
    def __init__(self, engine, store):
        self.engine, self.store = engine, store

    @contextmanager
    def _gate(self):
        """Never wait for quiescence; block new cooperating work only while held."""
        locks = [self.engine.resource_lock, self.engine.lock]
        held = []
        try:
            for lock in locks:
                if not lock.acquire(blocking=False):
                    yield False
                    return
                held.append(lock)
            counting = getattr(self.engine, "counting", None)
            if counting is not None:
                if not counting.lock.acquire(blocking=False):
                    yield False
                    return
                held.append(counting.lock)
            if not business_data.reference_lock.acquire(blocking=False):
                yield False
                return
            held.append(business_data.reference_lock)
            yield True
        finally:
            for lock in reversed(held):
                lock.release()

    def _capture(self, now, days):
        engine, registry = self.engine, self.engine.resources
        owner = threading.get_ident()
        busy = registry.closing or engine.closing
        # Exclude this task's own runtime activity, not other requests/writers.
        busy |= sum(registry.activities.values()) != sum(registry.activity_owners.values())
        busy |= any(n for (tid, _), n in registry.activity_owners.items() if tid != owner)
        busy |= any(t.is_alive() and t is not threading.current_thread() for t in registry.threads)
        busy |= any(c.is_alive() for c in registry.components)
        for name in ("worker", "preview_worker", "detector_warmup"):
            worker = getattr(engine, name, None)
            busy |= bool(worker and worker.is_alive())
        busy |= engine.notifications.has_writers() or bool(engine.notifications.pending_results())
        documents = copy.deepcopy([engine.config, engine.runtime_config, getattr(engine, "report_config", None)])
        sessions = set()
        if engine.state.get("status") in ACTIVE:
            sessions.add(engine.state.get("session"))
            busy = True
        counting = getattr(engine, "counting", None)
        if counting is not None:
            busy |= counting.active()
            documents.extend(copy.deepcopy([counting.config, counting.state]))
        if engine.config_path.exists():
            try:
                documents.append(read_json(engine.config_path, engine.data_root)[0])
            except UNCERTAIN:
                busy = True
        return dict(root=engine.data_root, settings_root=engine.settings_root, now=now,
                    retention_days=days, documents=documents, active_sessions=sessions,
                    busy=busy, leased_paths=tuple(absolute(p) for p, _ in registry.users))

    def plan_cleanup(self, now, retention_days):
        with self._gate() as acquired:
            if acquired:
                captured = self._capture(now, retention_days)
            else:
                captured = dict(root=self.engine.data_root, settings_root=self.engine.settings_root,
                                now=now, retention_days=retention_days, busy=True)
        return plan_cleanup(**captured)

    def _audit(self, plan, decision, status, reason):
        self.store.audit("cleanup", json.dumps({"path": decision.path, "decision": status, "reason": reason}), plan.now)

    def apply_cleanup(self, plan):
        if plan.root != absolute(self.engine.data_root) or plan.settings_root != absolute(self.engine.settings_root):
            raise ValueError("Plan belongs to another workspace")
        outcomes = []
        for decision in plan.decisions:
            checkpoint()
            disposition, reason = decision.disposition, decision.reason
            if disposition == "candidate":
                with self._gate() as acquired:
                    current = None
                    if acquired:
                        fresh = plan_cleanup(**self._capture(plan.now, plan.retention_days))
                        current = next((d for d in fresh.decisions if d.path == decision.path), None)
                    if current != decision:
                        disposition, reason = "omitted", "plan_changed"
                    else:
                        path = plain_path(plan.root / decision.path, plan.root)
                        is_upload = path.parent == plan.root / "data" / "uploads"
                        parent = plan.root / "data" / ("uploads" if is_upload else "replays")
                        if path.parent != parent:
                            raise ValueError("Invalid candidate depth")
                        self._audit(plan, decision, "delete_planned", reason)
                        try:
                            checkpoint()
                            # Audit/storage can fail or take time. Revalidate after it too.
                            fresh = plan_cleanup(**self._capture(plan.now, plan.retention_days))
                            if next((d for d in fresh.decisions if d.path == decision.path), None) != decision:
                                raise ValueError("plan_changed")
                            if is_upload:
                                if completed_fingerprint(path, plan.root)[1] != decision.fingerprint:
                                    raise ValueError("upload_changed")
                                path.unlink()
                                checkpoint()
                                if file_fingerprint(metadata_path(path), plan.root)[0] != decision.fingerprint[1]:
                                    raise ValueError("marker_changed")
                                plain_path(metadata_path(path), plan.root).unlink()
                            else:
                                if replay_fingerprint(path, plan.root) != decision.fingerprint:
                                    raise ValueError("replay_changed")
                                for name in REPLAY_FILES:
                                    checkpoint()
                                    if file_fingerprint(path / name, plan.root)[0] != dict(decision.fingerprint[1])[name]:
                                        raise ValueError("replay_file_changed")
                                    plain_path(path / name, plan.root).unlink()
                                plain_path(path, plan.root).rmdir()
                            disposition, reason = "deleted", "expired_unreferenced"
                        except Cancelled:
                            self._audit(plan, decision, "omitted", "delete_failed_or_changed")
                            raise
                        except UNCERTAIN:
                            disposition, reason = "omitted", "delete_failed_or_changed"
            self._audit(plan, decision, disposition, reason)
            outcomes.append(dict(path=decision.path, decision=disposition, reason=reason))
        return outcomes

    def __call__(self, now, settings):
        if not settings["enabled"]:
            return "disabled"
        return self.apply_cleanup(self.plan_cleanup(now, settings["retention_days"]))
