"""One optional worker; run_due_tasks is directly usable without threads."""
import threading
from datetime import datetime, timedelta, timezone

import automation_settings
from automation_store import AutomationStore

# Lima has a fixed UTC-05 offset for the current operational dates. This avoids
# requiring a system IANA database or an additional tzdata package on Windows.
LIMA = timezone(timedelta(hours=-5), "America/Lima")


class AutomationService:
    def __init__(self, engine, tasks=None, clock=None, interval=60, thread_factory=threading.Thread):
        if interval <= 0:
            raise ValueError("interval must be positive")
        self.engine = engine
        self.tasks = dict(tasks or {})
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.interval = interval
        self.thread_factory = thread_factory
        self.store = AutomationStore(engine.settings_root / "automation.sqlite")
        if tasks is None:
            from automation_reports import ScheduledReports
            from automation_backups import ProjectBackups
            from automation_escalation import AlertEscalation
            self.tasks["reports"] = ScheduledReports(engine, self.store)
            self.tasks["backups"] = ProjectBackups(engine, self.store)
            self.tasks["escalation"] = AlertEscalation(engine)
        self.stop_event = threading.Event()
        self.run_lock = threading.Lock()
        self.lifecycle_lock = threading.Lock()
        self.worker = None

    def run_due_tasks(self, now):
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("An aware timestamp is required")
        if not self.run_lock.acquire(blocking=False):
            return {}
        try:
            settings = automation_settings.load(self.engine.settings_root)
            outcomes = {}
            for task, callback in self.tasks.items():
                if self.stop_event.is_set():
                    break
                if not settings[task]["enabled"]:
                    continue
                try:
                    outcomes[task] = callback(now.astimezone(LIMA), settings[task])
                except Exception as exc:
                    outcomes[task] = "failed"
                    self.store.record(task, "service", now.astimezone(LIMA).date().isoformat(),
                                      "failed", now, error=type(exc).__name__)
            return outcomes
        finally:
            self.run_lock.release()

    def _loop(self):
        while not self.stop_event.is_set():
            try:
                self.run_due_tasks(self.clock())
            except Exception as exc:
                # Malformed settings or storage errors never enable tasks.
                with self.engine.lock:
                    self.engine.record("Automatizaciones", type(exc).__name__)
            if self.stop_event.wait(self.interval):
                break

    def start(self):
        with self.lifecycle_lock:
            if self.worker and self.worker.is_alive():
                return
            self.stop_event.clear()
            self.worker = self.thread_factory(target=self._loop, name="automation", daemon=True)
            self.worker.start()

    def stop(self):
        with self.lifecycle_lock:
            self.stop_event.set()
            worker = self.worker
        if worker:
            worker.join()
