"""Archivo PostGIS de sesiones terminadas; importación transaccional y repetible.

Los JSONL locales siguen siendo el registro recuperable durante la migración.
No se almacena video, credenciales de cámaras ni vectores en este archivo.
"""
import json
import math
import os
from pathlib import Path


def observation_rows(meta, samples):
    floors = {c['id']: c.get('planId', 'custom') for c in meta['cameras']}
    project = meta.get('projectId') or 'local'
    for index, sample in enumerate(samples):
        ordinal = 0
        for camera in sample.get('cameras', []):
            for person in camera.get('people', []):
                point = person.get('point')
                valid = isinstance(point, (list, tuple)) and len(point) == 2 and all(isinstance(v, (int, float)) and math.isfinite(v) for v in point)
                identity = str(person.get('id') or '')
                yield (project, meta['session'], index, ordinal, camera['id'], floors.get(camera['id'], 'custom'),
                       identity, float(sample['t']), bool(person.get('confirmed', bool(identity) and not identity.startswith('T'))),
                       bool(person.get('duplicate')), bool(person.get('predicted')),
                       f'POINT({float(point[0])} {float(point[1])})' if valid else None)
                ordinal += 1


def import_session(folder, dsn=None, insights=None):
    """Retorna None si no hay DSN. Un error revierte toda la sesión, sin borrar los archivos."""
    dsn = dsn or os.environ.get('AEROTRACK_DATABASE_URL')
    if not dsn:
        return None
    import psycopg
    from psycopg.types.json import Jsonb
    folder = Path(folder)
    meta = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if meta['status'] in ('running', 'paused'):
        raise ValueError('Solo se archivan sesiones finalizadas.')
    project, sid = meta.get('projectId') or 'local', meta['session']
    # Lista explícita: nunca enviar las URL de las fuentes a la base analítica.
    public = {k: meta[k] for k in ('module', 'end', 'status', 'created', 'identityDiagnostics', 'inferenceRuntime', 'identity') if k in meta}
    public['cameras'] = [{k: c[k] for k in ('id', 'name', 'planId', 'pairs', 'syncOffset') if k in c} for c in meta['cameras']]
    public['unit'] = meta.get('config', {}).get('unit', 'relative')
    public['testRun'] = bool(meta.get('config', {}).get('testRun'))
    public['validationNote'] = meta.get('config', {}).get('validationNote')
    public['reidModel'] = meta.get('config', {}).get('reidModel', 'osnet.onnx')
    count = 0
    with psycopg.connect(dsn, connect_timeout=5) as connection:
        connection.execute("SET statement_timeout = '60s'")
        connection.execute(Path(__file__).with_name('schema.sql').read_text(encoding='utf-8'))
        # Serializa reimportaciones concurrentes de la misma sesión.
        connection.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (project + '/' + sid,))
        connection.execute('''INSERT INTO aero_sessions(project_id, session_id, created_at, status, metadata, insights)
            VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(project_id,session_id) DO UPDATE
            SET status=excluded.status, metadata=excluded.metadata,
                insights=COALESCE(excluded.insights,aero_sessions.insights), imported_at=now()''',
            (project, sid, meta['created'], meta['status'], Jsonb(public), Jsonb(insights) if insights is not None else None))
        connection.execute('DELETE FROM aero_observations WHERE project_id=%s AND session_id=%s', (project, sid))
        with (folder / 'samples.jsonl').open(encoding='utf-8') as source, connection.cursor() as cursor:
            rows = observation_rows(meta, (json.loads(line) for line in source if line.strip()))
            batch = []
            for row in rows:
                batch.append(row)
                count += 1
                if len(batch) == 1000:
                    cursor.executemany('INSERT INTO aero_observations VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,ST_GeomFromText(%s,0))', batch)
                    batch.clear()
            if batch:
                cursor.executemany('INSERT INTO aero_observations VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,ST_GeomFromText(%s,0))', batch)
        connection.execute('DELETE FROM aero_session_routes WHERE project_id=%s AND session_id=%s', (project, sid))
        for route in meta.get('config', {}).get('cameraRoutes', []) or []:
            connection.execute('INSERT INTO aero_session_routes VALUES (%s,%s,%s,%s,%s,%s,%s)',
                               (project, sid, route['from'], route['to'], route['kind'], route.get('minSeconds', 0), route.get('maxSeconds', 120)))
    return {'project': project, 'session': sid, 'observations': count}


def health():
    """Estado público, sin DSN ni mensajes que puedan revelar contraseñas."""
    dsn = os.environ.get('AEROTRACK_DATABASE_URL')
    if not dsn:
        return {'configured': False, 'connected': False}
    try:
        import psycopg
        with psycopg.connect(dsn, connect_timeout=2, options='-c statement_timeout=2000') as db:
            version = db.execute('SELECT PostGIS_Version()').fetchone()[0]
        return {'configured': True, 'connected': True, 'postgis': version}
    except Exception as exc:
        return {'configured': True, 'connected': False, 'error': type(exc).__name__}
