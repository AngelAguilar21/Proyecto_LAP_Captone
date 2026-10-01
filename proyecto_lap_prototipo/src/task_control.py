"""Cooperative, nestable monotonic deadlines. Never terminates another thread."""
import math
import time
from contextlib import contextmanager
from contextvars import ContextVar


class Cancelled(Exception):
    pass


CONTROL = ContextVar("automation_control", default=())


@contextmanager
def budget(event, seconds, clock=time.monotonic):
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
        raise ValueError("Invalid task budget")
    token = CONTROL.set((*CONTROL.get(), (event, clock() + seconds, clock)))
    try:
        checkpoint()
        yield
        checkpoint()
    finally:
        CONTROL.reset(token)


def checkpoint():
    for event, deadline, clock in CONTROL.get():
        if event.is_set() or clock() >= deadline:
            raise Cancelled("Task cancelled or deadline reached")
