"""Bounded shutdown request; resource release waits for actual writer completion."""
import threading
import time


def request_stop(server, automation):
    server.closing = True
    automation.stop_event.set()
    engine = server.engine
    engine.stop_event.set()
    engine.pause_event.clear()
    engine.preview_stop_event.set()
    engine.notifications.stop_event.set()
    counting = getattr(engine, "counting", None)
    if counting:
        counting.stop_event.set()
        counting.pause_event.clear()


def quiescent(server, automation):
    # Repeat cancellation for a request that was already in flight when shutdown
    # began. Never wait on Engine.lock: it may be held by the very writer draining.
    request_stop(server, automation)
    engine = server.engine
    workers = [automation.worker, engine.worker, engine.preview_worker,
               getattr(getattr(engine, "counting", None), "worker", None)]
    requests = getattr(server, "_threads", ())
    if isinstance(requests, (list, tuple)):
        workers.extend(requests)
    return (not automation.run_lock.locked() and not engine.resource_users and
            not engine.notifications.has_writers() and
            not any(w and w.is_alive() for w in workers))


def stop_server(server, automation, timeout, clock=time.monotonic, wait=None):
    deadline = clock() + max(0, timeout)
    wait = wait or threading.Event().wait
    request_stop(server, automation)
    while not quiescent(server, automation):
        remaining = deadline - clock()
        if remaining <= 0:
            return False
        wait(min(0.05, remaining))
    return True
