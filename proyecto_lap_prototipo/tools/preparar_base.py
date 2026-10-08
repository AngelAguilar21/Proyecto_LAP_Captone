"""Inicia PostgreSQL local con secreto generado; no imprime la conexión."""
import os
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'proyecto_lap_prototipo/src'))
from storage.environment import load_environment


def main():
    load_environment(ROOT)
    if not os.environ.get('AEROTRACK_DB_PASSWORD'):
        password = secrets.token_hex(24)
        with (ROOT / '.env').open('a', encoding='utf-8') as stream:
            stream.write('\nAEROTRACK_DB_PASSWORD=' + password + '\n')
        os.environ['AEROTRACK_DB_PASSWORD'] = password
        load_environment(ROOT)
    subprocess.run(['docker', 'compose', '-f', str(ROOT / 'compose.postgis.yml'), 'up', '-d', '--wait'], cwd=ROOT, check=True)
    import psycopg
    with psycopg.connect(os.environ['AEROTRACK_DATABASE_URL'], connect_timeout=5) as db:
        db.execute((ROOT / 'proyecto_lap_prototipo/src/storage/schema.sql').read_text(encoding='utf-8'))
    print('PostgreSQL/PostGIS listo. Ejecuta iniciar_sistema.cmd. No borres el volumen Docker para conservar tus datos.')


if __name__ == '__main__':
    main()
