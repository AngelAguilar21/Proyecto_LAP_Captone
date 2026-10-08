"""Migra con el servidor detenido; conserva originales y respaldo verificable.

Uso: python tools/migrar_operativo.py --migrate
No activa PostgreSQL hasta comparar todas las filas y confirmar la transacción.
"""
import argparse
import json
import shutil
import socket
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from storage import operational
from storage.environment import load_environment

TABLES = ('negocios', 'ventas', 'incidentes', 'trafico_historico', 'negocio_ubicaciones',
          'negocio_puertas', 'negocio_referencias', 'negocio_estados', 'commercial_imports',
          'commercial_sales', 'commercial_traffic', 'commercial_incidents', 'commercial_bags',
          'insights_events', 'insights_hourly')


def migrate(root):
    from psycopg import sql
    from psycopg.types.json import Jsonb
    root = Path(root)
    marker = root / 'config/storage.local.json'
    if marker.exists():
        raise ValueError('La migración ya está activada. No se sobrescribirá PostgreSQL con archivos antiguos.')
    index_path = root / 'config/projects/index.json'
    index = json.loads(index_path.read_text(encoding='utf-8'))
    documents = [index_path, root / 'config/usuarios.local.json']
    documents += [root / 'config/projects' / (p['id'] + '.json') for p in index['projects']]
    # Validar documentos antes de abrir una transacción o crear respaldo.
    payload = [(p, json.loads(p.read_text(encoding='utf-8'))) for p in documents]
    installation = uuid.uuid4().hex
    backup = root / 'config/backups' / ('postgres-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(parents=True, exist_ok=False)
    for path, _ in payload:
        target = backup / path.relative_to(root / 'config')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    report = {'installation': installation, 'created': datetime.now(timezone.utc).isoformat(),
              'documents': len(payload), 'projects': {}, 'backup': str(backup)}
    with operational.connect_db() as db:
        operational.setup_documents(db)
        for path, data in payload:
            key = path.relative_to(root).as_posix()
            db.execute('INSERT INTO public.aero_documents(installation,key,content) VALUES(%s,%s,%s)',
                       (installation, key, Jsonb(data)))
            saved = db.execute('SELECT content FROM public.aero_documents WHERE installation=%s AND key=%s',
                               (installation, key)).fetchone()[0]
            if saved != data:
                raise ValueError('Falló la verificación del documento: ' + path.name)
        for project in index['projects']:
            pid = project['id']
            con = operational.prepare_business(db, installation, pid)
            source = root / 'config/projects' / (pid + '.negocios.sqlite')
            counts = {}
            if source.exists():
                target = backup / 'projects' / source.name
                original = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
                copied = sqlite3.connect(target)
                try:
                    original.backup(copied)
                finally:
                    original.close()
                    copied.close()
                local = sqlite3.connect(target)
                try:
                    tables = {r[0] for r in local.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
                    if tables - set(TABLES):
                        raise ValueError('Tablas sin migración definida: ' + str(tables - set(TABLES)))
                    for table in TABLES:
                        if table not in tables:
                            continue
                        columns = [r[1] for r in local.execute('PRAGMA table_info(' + table + ')')]
                        rows = local.execute('SELECT * FROM ' + table).fetchall()
                        query = sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(
                            sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, columns)),
                            sql.SQL(',').join(sql.Placeholder() for _ in columns))
                        if rows:
                            with db.cursor() as cur:
                                cur.executemany(query, rows)
                        actual = db.execute(sql.SQL('SELECT {} FROM {}').format(
                            sql.SQL(',').join(map(sql.Identifier, columns)), sql.Identifier(table))).fetchall()
                        if sorted(rows, key=repr) != sorted(actual, key=repr):
                            raise ValueError('Filas diferentes después de migrar: ' + table)
                        counts[table] = len(rows)
                    for table in ('ventas', 'trafico_historico'):
                        db.execute(sql.SQL("SELECT setval(pg_get_serial_sequence(%s,'id'),COALESCE(MAX(id),1),MAX(id) IS NOT NULL) FROM {}").format(sql.Identifier(table)), (table,))
                finally:
                    local.close()
            report['projects'][pid] = counts
    # La activación se hace DESPUÉS del commit. Nunca se borran los originales.
    (backup / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    temp = marker.with_suffix('.tmp')
    temp.write_text(json.dumps({'backend': 'postgresql', 'installation': installation}, indent=2), encoding='utf-8')
    temp.replace(marker)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--migrate', action='store_true', required=True)
    args = parser.parse_args()
    load_environment(ROOT.parent)
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', 8765)) == 0:
            raise SystemExit('Detén el servidor de AeroTrack antes de migrar; no se modificó ningún dato.')
    print(json.dumps(migrate(ROOT), ensure_ascii=False, indent=2))
