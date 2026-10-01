"""Bounded cancellation, followed by truthful draining of modern runtime owners.

Call stop_server after serve_forever has returned. No Engine/Counting lock is
acquired here. Native inference/open/read cannot be forcefully interrupted.
"""
import threading
import time
from http.server import ThreadingHTTPServer


def alive(worker):
    return worker is not None and worker.is_alive()


class ManagedHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    connection_timeout_seconds = 5

    def __init__(self, *args, **kwargs):
        self.closing = False
        self.http_workers = set()
        self.http_lock = threading.Lock()
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        request.settimeout(self.connection_timeout_seconds)

        def run():
            try:
                try:
                    with self.engine.resources.activity(writer=False):
                        super(ManagedHTTPServer, self).process_request_thread(request, client_address)
                except ValueError:
                    if not self.closing:
                        raise
            finally:
                self.shutdown_request(request)
                with self.http_lock:
                    self.http_workers.discard(threading.current_thread())

        with self.http_lock:
            if self.closing:
                self.shutdown_request(request)
                return
            worker = threading.Thread(target=run, name="http-request", daemon=True)
            self.http_workers.add(worker)
            try:
                worker.start()
            except Exception:
                self.http_workers.discard(worker)
                self.shutdown_request(request)
                raise


def request_stop(server):
    server.closing = True
    engine = server.engine
    engine.closing = True
    engine.resources.request_stop()
    engine.stop_event.set()
    engine.pause_event.clear()
    engine.preview_stop_event.set()
    for event in tuple(engine.preview_workers.values()):
        event.set()
    counting = getattr(engine, "counting", None)
    if counting is not None:
        counting.resources.request_stop()
        counting.stop_event.set()
        counting.pause_event.clear()
    engine.automation.stop_event.set()
    engine.notifications.stop_event.set()
    engine.mailer.stop_event.set()


def quiescent(server):
    engine = server.engine
    counting = getattr(engine, "counting", None)
    workers = [engine.worker, engine.preview_worker, getattr(engine, "detector_warmup", None),
               engine.automation.worker, getattr(counting, "worker", None),
               getattr(server, "notification_flush_worker", None)]
    workers.extend(tuple(engine.preview_workers))
    return not (any(alive(w) for w in workers) or engine.resources.busy() or
                (counting is not None and counting.resources.busy()) or
                bool(getattr(server, "http_workers", ())) or engine.automation.run_lock.locked() or
                engine.notifications.has_writers() or engine.notifications.pending_results() or
                engine.mailer.has_writers())


def flush_known_results(server):
    notifications = server.engine.notifications
    if notifications.pending_results() and not alive(getattr(server, "notification_flush_worker", None)):
        worker = threading.Thread(target=notifications.retry_pending, name="notification-persistence", daemon=True)
        server.notification_flush_worker = worker
        worker.start()


def stop_server(server, timeout=None, clock=time.monotonic, wait=None):
    """Returns False on deadline. Retains every live owner and never closes it."""
    engine = server.engine
    timeout = engine.automation.runtime["shutdown_timeout_seconds"] if timeout is None else timeout
    deadline = clock() + max(0, timeout)
    wait = wait or threading.Event().wait
    request_stop(server)
    while True:
        if quiescent(server):
            return True
        remaining = deadline - clock()
        if remaining <= 0:
            return False
        flush_known_results(server)
        wait(min(.05, remaining))
        # An already-admitted request may have finished initializing a child.
        request_stop(server)


def defer_close(server, interval=.25):
    """Keep the server and writers owned until they actually drain.

    Persistent disk failures or stuck native workers deliberately leave this
    non-daemon closer alive: timeout is not proof that data is safely closed.
    """
    if alive(getattr(server, "shutdown_worker", None)):
        return server.shutdown_worker

    def drain():
        while not stop_server(server, timeout=interval):
            pass
        server.server_close()

    worker = threading.Thread(target=drain, name="deferred-close", daemon=False)
    server.shutdown_worker = worker
    worker.start()
    return worker
