"""Persistent maintenance/restore holds outside the replaceable projects tree."""
import os
import sqlite3
import threading
from contextlib import closing, contextmanager
from pathlib import Path


def blocked(root, project=None, maintenance_only=False):
    path = Path(root) / "restore.sqlite"
    if not path.exists():
        return False
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0)) as db:
            if db.execute("SELECT 1 FROM restores WHERE status NOT IN ('completed','cancelled') LIMIT 1").fetchone():
                return True
            if maintenance_only:
                return False
            if project is None:
                return bool(db.execute("SELECT 1 FROM holds WHERE released_at IS NULL LIMIT 1").fetchone())
            return bool(db.execute("SELECT 1 FROM holds WHERE project=? AND released_at IS NULL",
                                   (Path(project).stem,)).fetchone())
    except (sqlite3.Error, OSError):
        return True  # Corrupt/locked metadata is never permission to send or delete.


class LeaseDrain:
    def __init__(self):
        self.pending = None
        self.worker = None

    def defer_until(self, ready, cleanup):
        """Called only after the bounded shutdown deadline; starts no new work."""
        self.pending = (ready, cleanup)


@contextmanager
def storage_lease(root):
    """Offline restore and the server are mutually exclusive, including on Windows."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    stream = (root / "storage.lock").open("a+b")
    locked = False
    drain = LeaseDrain()
    def release():
        if locked:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_UN)
        stream.close()
    try:
        if stream.seek(0, 2) == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        locked = True
        yield drain
    finally:
        if drain.pending:
            ready, cleanup = drain.pending
            def finish():
                wait = threading.Event().wait
                while not ready():
                    wait(0.05)
                try:
                    cleanup()
                finally:
                    release()
            # A still-active writer must keep the process and storage lease alive.
            drain.worker = threading.Thread(target=finish, name="shutdown-drain", daemon=False)
            try:
                drain.worker.start()
            except Exception:
                finish()  # Never release early even if no drain thread can start.
                raise
        else:
            release()
