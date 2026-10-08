"""Buzón persistente: un fallo de PostgreSQL no pierde ni bloquea el análisis."""
import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from .postgis import import_session


class ArchiveQueue:
    def __init__(self, path, importer=import_session):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.importer = importer
        self.stop_event = threading.Event()
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS jobs (folder TEXT PRIMARY KEY, insights TEXT, attempts INTEGER NOT NULL DEFAULT 0, due REAL NOT NULL DEFAULT 0, error TEXT, completed REAL)')
            if 'revision' not in {row[1] for row in db.execute('PRAGMA table_info(jobs)')}:
                db.execute('ALTER TABLE jobs ADD COLUMN revision INTEGER NOT NULL DEFAULT 0')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def enqueue(self, folder, insights=None):
        with self.connect() as db:
            db.execute('INSERT INTO jobs(folder,insights) VALUES (?,?) ON CONFLICT(folder) DO UPDATE SET insights=COALESCE(excluded.insights,jobs.insights), due=0, completed=NULL, revision=revision+1',
                       (str(Path(folder).resolve()), json.dumps(insights) if insights is not None else None))

    def recover(self, replay_root):
        """Descubre cierres que ocurrieron antes de encolar (p. ej. corte de luz)."""
        with self.connect() as db:
            for manifest in Path(replay_root).glob('*/manifest.json'):
                try:
                    meta = json.loads(manifest.read_text(encoding='utf-8'))
                    if meta.get('status') in ('running', 'paused') or not (manifest.parent / 'samples.jsonl').is_file():
                        continue
                    insight_file = manifest.parent / 'insights.json'
                    insights = insight_file.read_text(encoding='utf-8') if insight_file.is_file() else None
                    db.execute('INSERT OR IGNORE INTO jobs(folder,insights) VALUES (?,?)', (str(manifest.parent.resolve()), insights))
                except (OSError, ValueError):
                    continue

    def status(self):
        with self.connect() as db:
            pending, completed = db.execute('SELECT COALESCE(SUM(completed IS NULL),0), COALESCE(SUM(completed IS NOT NULL),0) FROM jobs').fetchone()
        return {'pending': pending, 'archived': completed}

    def run_once(self):
        with self.connect() as db:
            job = db.execute('SELECT folder,insights,attempts,revision FROM jobs WHERE completed IS NULL AND due<=? ORDER BY due LIMIT 1', (time.time(),)).fetchone()
        if not job:
            return False
        folder, insights, attempts, revision = job
        try:
            result = self.importer(folder, insights=json.loads(insights) if insights else None)
            if result is None:
                raise RuntimeError('StorageNotConfigured')
        except Exception as exc:
            # Solo el tipo: mensajes de conexión pueden contener secretos.
            with self.connect() as db:
                db.execute('UPDATE jobs SET attempts=attempts+1,due=?,error=? WHERE folder=? AND revision=?',
                           (time.time() + min(300, 2 ** min(attempts + 1, 8)), type(exc).__name__, folder, revision))
        else:
            with self.connect() as db:
                db.execute('UPDATE jobs SET completed=?,error=NULL WHERE folder=? AND revision=?', (time.time(), folder, revision))
        return True

    def start(self):
        def work():
            while not self.stop_event.is_set():
                try:
                    busy = self.run_once()
                except sqlite3.Error:
                    busy = False
                self.stop_event.wait(0.1 if busy else 2)
        self.thread = threading.Thread(target=work, daemon=True, name='postgis-archive')
        self.thread.start()

    def close(self):
        self.stop_event.set()
        if hasattr(self, 'thread'):
            self.thread.join(timeout=6)
