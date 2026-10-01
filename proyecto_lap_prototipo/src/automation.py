"""Sequential opt-in runtime. Productive tasks are injected by composition."""
import threading
import time
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone

import automation_settings
from automation_store import AutomationStore
from task_control import budget, Cancelled

LIMA = timezone(timedelta(hours=-5), "America/Lima")


class AutomationService:
    def __init__(self, engine, tasks=None, clock=None, interval=60,
                 monotonic=time.monotonic, thread_factory=threading.Thread):
        if not 0 < interval <= 3600:
            raise ValueError("Invalid interval")
        self.engine = engine
        self.tasks = dict(tasks or {})
        if set(self.tasks) - {"reports", "backups", "escalation", "cleanup"}:
            raise ValueError("Unknown task settings section")
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.monotonic = monotonic
        self.interval = interval
        self.thread_factory = thread_factory
        self.store = AutomationStore(engine.settings_root / "automation.sqlite")
        self.stop_event = threading.Event()
        self.run_lock = threading.Lock()
        self.lifecycle_lock = threading.Lock()
        self.worker = None
        self.error = None
        self.runtime = dict(automation_settings.DEFAULTS["runtime"])

    def run_due_tasks(self, now):
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("An aware timestamp is required")
        if not self.run_lock.acquire(blocking=False):
            return {}
        try:
            settings = automation_settings.load(self.engine.settings_root)
            self.runtime = settings["runtime"]
            outcomes = {}
            date = now.astimezone(LIMA).date().isoformat()
            for task, callback in self.tasks.items():
                if self.stop_event.is_set():
                    break
                if not settings[task]["enabled"]:
                    continue
                status, error = "succeeded", None
                records_execution = getattr(callback, "records_execution", False) is True
                try:
                    # Refuse execution when its initial durable record cannot be written.
                    if not records_execution:
                        self.store.record(task, "service", date, "running", now)
                except Exception as exc:
                    self.error = type(exc).__name__
                    outcomes[task] = "failed"
                    continue
                try:
                    resources = getattr(self.engine, "resources", None)
                    owner = resources.activity() if resources else nullcontext()
                    with owner, budget(self.stop_event, self.runtime["task_timeout_seconds"], self.monotonic):
                        outcomes[task] = callback(now.astimezone(LIMA), settings[task])
                except Cancelled:
                    status = outcomes[task] = "cancelled"
                except Exception as exc:
                    status = outcomes[task] = "failed"
                    error = type(exc).__name__
                    self.error = error  # Includes failures of task-owned persistence.
                try:
                    if not records_execution:
                        self.store.finish(task, "service", date, status, now, error)
                except Exception as exc:
                    self.error = type(exc).__name__
            return outcomes
        finally:
            self.run_lock.release()

    def _loop(self):
        while not self.stop_event.is_set():
            try:
                self.run_due_tasks(self.clock())
            except Exception as exc:
                # No Engine.lock: a writer holding it must be able to finish.
                self.error = type(exc).__name__
            if self.stop_event.wait(self.interval):
                break

    def start(self):
        with self.lifecycle_lock:
            if self.worker and self.worker.is_alive():
                return
            if getattr(self.engine, "closing", False):
                return
            self.stop_event.clear()
            self.worker = self.thread_factory(target=self._loop, name="automation", daemon=True)
            self.worker.start()

    def stop(self, timeout=None):
        self.stop_event.set()
        deadline = self.monotonic() + (self.runtime["shutdown_timeout_seconds"] if timeout is None else max(0, timeout))
        worker = self.worker
        if worker and worker is not threading.current_thread():
            worker.join(max(0, deadline - self.monotonic()))
        return not (worker and worker.is_alive()) and not self.run_lock.locked()
