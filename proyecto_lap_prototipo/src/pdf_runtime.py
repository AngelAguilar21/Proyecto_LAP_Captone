"""PDFium is not thread safe, even across independent documents.

All in-process PDFium entry points share this mutex; waiting is cooperative.
https://pypdfium2.readthedocs.io/en/stable/python_api.html#incompatibility-with-threading
"""
import threading
from functools import wraps
from task_control import checkpoint

PDFIUM_LOCK = threading.Lock()


def serialized_pdfium(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        checkpoint()
        while not PDFIUM_LOCK.acquire(timeout=.05):
            checkpoint()
        try:
            checkpoint()
            return function(*args, **kwargs)
        finally:
            PDFIUM_LOCK.release()
    return wrapped
