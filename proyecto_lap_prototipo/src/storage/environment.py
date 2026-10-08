"""Carga únicamente variables propias; nunca ejecuta el contenido de .env."""
import os
from pathlib import Path
from urllib.parse import quote


def load_environment(root):
    path = Path(root) / '.env'
    if path.is_file():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            key, separator, value = line.partition('=')
            key = key.strip()
            if separator and key.startswith('AEROTRACK_'):
                os.environ.setdefault(key, value.strip().strip('\"\''))
    if not os.environ.get('AEROTRACK_DATABASE_URL') and os.environ.get('AEROTRACK_DB_PASSWORD'):
        password = quote(os.environ['AEROTRACK_DB_PASSWORD'], safe='')
        os.environ['AEROTRACK_DATABASE_URL'] = f'postgresql://aerotrack:{password}@127.0.0.1:5433/aerotrack'
