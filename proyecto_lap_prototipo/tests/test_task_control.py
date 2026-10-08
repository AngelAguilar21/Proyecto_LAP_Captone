import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from task_control import Cancelled, budget, checkpoint


class TaskControlTests(unittest.TestCase):
    def test_deadline_uses_injected_monotonic_clock(self):
        now = [10.]
        with self.assertRaises(Cancelled):
            with budget(threading.Event(), 2, lambda: now[0]):
                now[0] = 11.99
                checkpoint()
                now[0] = 12.
                checkpoint()
        checkpoint()  # Context must be restored after an exception.

    def test_stop_event_cancels_without_waiting(self):
        stop = threading.Event()
        with self.assertRaises(Cancelled):
            with budget(stop, 100):
                stop.set()
                checkpoint()

    def test_nested_budget_cannot_extend_parent(self):
        now = [0.]
        with self.assertRaises(Cancelled):
            with budget(threading.Event(), 1, lambda: now[0]):
                with budget(threading.Event(), 99, lambda: now[0]):
                    now[0] = 2.
                    checkpoint()

    def test_exit_checks_non_cooperative_return_and_clears_context(self):
        now = [0.]
        with self.assertRaises(Cancelled):
            with budget(threading.Event(), 1, lambda: now[0]):
                now[0] = 2.
        checkpoint()

    def test_invalid_budget_is_rejected(self):
        for seconds in (-1, float("nan"), float("inf")):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                with budget(threading.Event(), seconds):
                    self.fail("Invalid deadline admitted")
