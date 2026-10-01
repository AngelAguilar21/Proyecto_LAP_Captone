"""Process-local file leases and ownership of asynchronous resources.

Retention holds lock while checking protected resources and deleting. Leases
protect ancestors/descendants; they are not an inter-process filesystem lock.
"""
import os
import threading
from collections import Counter
from contextlib import contextmanager, ExitStack
from contextvars import ContextVar
from functools import wraps
from pathlib import Path

CURRENT = ContextVar("resource_owner", default=None)
SCOPE = ContextVar("resource_scope", default=None)


class ResourceRegistry:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.lock = threading.RLock()
        self.users = Counter()
        self.activities = Counter()
        self.activity_owners = Counter()
        self.components = set()
        self.threads = set()
        self.closing = False
        self._stop_requested = set()

    def identity(self, path):
        path = Path(path)
        if ".." in path.parts or (path.drive and not path.is_absolute()):
            raise ValueError("Ambiguous resource path")
        resolved = path.resolve() if path.is_absolute() else (self.root / path).resolve()
        if not path.is_absolute() and not resolved.is_relative_to(self.root):
            raise ValueError("Resource escapes its root")
        return os.path.normcase(str(resolved))

    @contextmanager
    def use(self, path, write=False):
        key = (self.identity(path), "writer" if write else "reader")
        with self.lock:
            if self.closing and CURRENT.get() is not self:
                raise ValueError("Runtime is closing")
            self.users[key] += 1
        try:
            yield key[0]
        finally:
            with self.lock:
                self.users[key] -= 1
                if not self.users[key]:
                    del self.users[key]

    def protected(self, path):
        path = Path(self.identity(path))
        with self.lock:
            return any(path.is_relative_to(Path(p)) or Path(p).is_relative_to(path) for p, _ in self.users)

    @contextmanager
    def activity(self, writer=True):
        kind = "writer" if writer else "reader"
        owner = (threading.get_ident(), kind)
        with self.lock:
            if self.closing and CURRENT.get() is not self:
                raise ValueError("Runtime is closing")
            self.activities[kind] += 1
            self.activity_owners[owner] += 1
        token = CURRENT.set(self)
        try:
            with ExitStack() as stack:
                scope = SCOPE.set(stack)
                try:
                    yield
                finally:
                    SCOPE.reset(scope)
        finally:
            CURRENT.reset(token)
            with self.lock:
                self.activities[kind] -= 1
                self.activity_owners[owner] -= 1
                if not self.activity_owners[owner]:
                    del self.activity_owners[owner]

    def start_thread(self, target, args=(), name=None):
        def run():
            try:
                with self.activity():
                    target(*args)
            except ValueError:
                if not self.closing:
                    raise
        with self.lock:
            if self.closing:
                raise ValueError("Runtime is closing")
            worker = threading.Thread(target=run, name=name, daemon=True)
            self.threads = {w for w in self.threads if w.is_alive()}
            self.threads.add(worker)
            try:
                worker.start()
            except Exception:
                self.threads.discard(worker)
                raise
            return worker

    def track(self, component):
        with self.lock:
            self.components = {c for c in self.components if c.is_alive()}
            self.components.add(component)
            closing = self.closing
        if closing:
            component.request_stop()

    def request_stop(self, *, blocking=True):
        # Close admission immediately, even when retention currently owns lock.
        self.closing = True
        if not self.lock.acquire(blocking=blocking):
            return False
        try:
            components = tuple(self.components)
            if not blocking:
                # Component cancellation may itself acquire a condition/driver
                # lock. It is an owned operation, never a coordinator wait.
                for component in components:
                    if component in self._stop_requested or not component.is_alive():
                        continue
                    worker = threading.Thread(target=component.request_stop,
                                              name="resource-cancellation", daemon=True)
                    self._stop_requested.add(component)
                    self.threads.add(worker)
                    try:
                        worker.start()
                    except Exception:
                        self.threads.discard(worker)
                        self._stop_requested.discard(component)
                        raise
                return True
        finally:
            self.lock.release()
        for component in components:
            component.request_stop()
        return True

    def busy(self, *, blocking=True):
        # An unavailable registry is not evidence of quiescence.
        if not self.lock.acquire(blocking=blocking):
            return True
        try:
            return bool(self.users or any(self.activities.values()) or
                        any(w.is_alive() for w in self.threads) or any(c.is_alive() for c in self.components))
        finally:
            self.lock.release()

    def snapshot(self):
        with self.lock:
            return {"leases": dict(self.users), "activities": dict(self.activities),
                    "threads": sum(w.is_alive() for w in self.threads),
                    "components": sum(c.is_alive() for c in self.components)}


def hold_path(path, write=False):
    registry, stack = CURRENT.get(), SCOPE.get()
    if registry is not None and stack is not None:
        stack.enter_context(registry.use(path, write))


def hold_source(source, root):
    if isinstance(source, str) and source and "://" not in source:
        path = Path(source)
        if ".." in path.parts:
            raise ValueError("Ambiguous source path")
        hold_path(path if path.is_absolute() else Path(root) / path)


def managed_operation(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self.resources.activity():
            return method(self, *args, **kwargs)
    return wrapped


def http_operation(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        engine = self.server.engine
        if getattr(self.server, "closing", False) or engine.resources.closing:
            self.close_connection = True
            return self.send_data(503, {"error": "El servidor está cerrando."})
        reader = method.__name__ == "do_GET" and self.path.startswith(("/api/replay/", "/api/report", "/api/frame"))
        try:
            with engine.resources.activity(writer=not reader):
                if reader and not self.path.startswith("/api/frame"):
                    hold_path(engine.data_root / "data" / "replays")
                return method(self, *args, **kwargs)
        except ValueError:
            if not engine.resources.closing:
                raise
            self.close_connection = True
            return self.send_data(503, {"error": "El servidor está cerrando."})
    return wrapped
