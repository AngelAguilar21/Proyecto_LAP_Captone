"""Cooperative deadlines for sequential tasks; no thread is forcibly terminated."""
import time
from contextlib import contextmanager
from contextvars import ContextVar


class Cancelled(Exception):
    pass


CONTROL = ContextVar("automation_control", default=None)


@contextmanager
def budget(event, seconds, clock=time.monotonic):
    token = CONTROL.set((event, clock() + seconds, clock))
    try:
        checkpoint()
        yield
    finally:
        CONTROL.reset(token)


def checkpoint():
    control = CONTROL.get()
    if control:
        event, deadline, clock = control
        if event.is_set() or clock() >= deadline:
            raise Cancelled("Task cancelled or deadline reached")
