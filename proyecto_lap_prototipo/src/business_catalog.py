"""Catálogo de locales del plano y métricas de accesos por negocio.

La cartografía aporta entidades; las líneas de cámaras aportan mediciones.
No se deducen entradas a partir de cercanía ni se suman visitantes únicos.
"""
import copy
import json
import time
from collections import defaultdict
from pathlib import Path
import business_data as db


def sync(con, config, public_root):
    plans = dict(config.get('plans') or {})
    plans[config.get('planId', 'custom')] = config
    for pid, plan in plans.items():
        asset = plan.get('mapAsset')
        if asset not in [f'/maps/lap/{n}.json' for n in (1, 2, 3, 4)]:
            continue
        data = json.loads((Path(public_root) / asset.lstrip('/')).read_text(encoding='utf-8'))
        features = [f for f in data['features'] if f['geometry']['type'] == 'Point' and f['properties'].get('name') and f['properties'].get('class') in ('retail', 'food_and_drink')]
        names = defaultdict(list)
        for f in features:
            names[f['properties']['name']].append(str(f['id']))
        with con:
            for f in features:
                fid = str(f['id'])
                existing = con.execute('SELECT negocio_id FROM negocio_referencias WHERE asset=? AND feature_id=?', (asset, fid)).fetchone()
                if existing:
                    continue  # Respeta nombres y cierres modificados por el operador.
                ident = f"lap-{asset.split('/')[-1].split('.')[0]}-{fid}"
                name = f['properties']['name']
                if len(names[name]) > 1:
                    name += f" (local {sorted(names[name]).index(fid)+1})"
                con.execute("INSERT OR IGNORE INTO negocios (id,nombre,camara_id,linea_id,creado,empresa) VALUES (?,?,?,?,?,?)", (ident, name, None, None, time.time(), 'Sin empresa'))
                con.execute('INSERT OR IGNORE INTO negocio_ubicaciones VALUES (?,?,?,?)', (ident, pid, *f['geometry']['coordinates'][:2]))
                con.execute('INSERT OR IGNORE INTO negocio_referencias VALUES (?,?,?)', (ident, asset, fid))
    # Conserva negocios vinculados por versiones anteriores del editor.
    with con:
        for camera in config.get("cameras", []):
            for line in camera.get("countLines", []):
                place = line.get("place")
                if not place or not place.get("point"):
                    continue
                if con.execute("SELECT 1 FROM negocios WHERE id=?", (place["id"],)).fetchone():
                    continue
                con.execute("INSERT INTO negocios (id,nombre,camara_id,linea_id,creado,empresa) VALUES (?,?,?,?,?,?)", (place["id"],place["name"],camera["id"],line["id"],time.time(), 'Sin empresa'))
                con.execute("INSERT INTO negocio_ubicaciones VALUES (?,?,?,?)", (place["id"],place["planId"],*place["point"]))
                con.execute("INSERT INTO negocio_puertas VALUES (?,?,?)", (place["id"],camera["id"],line["id"]))
    return db.listar_negocios(con)


def bind_config(con, config, businesses, restore_legacy=False):
    """Normaliza vínculos por ID. Geometría y dirección se conservan intactas."""
    by_id = {b['id']: b for b in businesses}
    legacy = {(p['camaraId'], p['lineaId']): b for b in businesses for p in b['puertas']}
    config = copy.deepcopy(config)
    for camera in config.get('cameras', []):
        for line in camera.get('countLines', []):
            place = line.get('place')
            business = by_id.get(place.get('id')) if isinstance(place, dict) else None
            if not place and restore_legacy:
                business = legacy.get((camera['id'], line['id']))
            if place and not business:
                raise ValueError('El negocio del acceso ya no está disponible. Selecciónalo de nuevo.')
            if business:
                if business.get('estado') == 'cerrado':
                    raise ValueError('Un acceso está vinculado a un negocio cerrado. Retira o cambia ese vínculo.')
                if business['ubicacion']['planId'] != camera.get('planId', config.get('planId', 'custom')):
                    raise ValueError('La cámara y el negocio deben estar en el mismo nivel.')
                line['place'] = {'id': business['id'], 'name': business['nombre'], **business['ubicacion']}
    return config


def save_bindings(con, config):
    links = [(l['place']['id'], c['id'], l['id']) for c in config.get('cameras', []) for l in c.get('countLines', []) if l.get('place')]
    with con:
        con.execute('DELETE FROM negocio_puertas')
        con.execute('UPDATE negocios SET camara_id=NULL,linea_id=NULL')
        con.executemany('INSERT INTO negocio_puertas VALUES (?,?,?)', links)


def traffic(businesses, analytics, observed_config, current_config=None):
    """Usa conteos ya procesados; rechaza reasignar una línea cuya geometría cambió."""
    observed = {(c['id'], l['id']): l for c in observed_config.get('cameras', []) for l in c.get('countLines', [])}
    current = {(c['id'], l['id']): l for c in (current_config or observed_config).get('cameras', []) for l in c.get('countLines', [])}
    assignment = {(p['camaraId'], p['lineaId']): b['id'] for b in businesses for p in b['puertas']}
    totals = {b['id']: {'id': b['id'], 'nombre': b['nombre'], 'empresa': b.get('empresa') or 'Sin empresa', 'estado': b.get('estado', 'activo'), 'ubicacion': b['ubicacion'], 'accesses': [], 'entries': None, 'exits': None, 'hours': {}, 'events': []} for b in businesses}
    for cid, a in analytics.items():
        for l in a.get('crossings', []):
            key = (cid, l['id'])
            old, now = observed.get(key), current.get(key)
            same = old and now and all(old.get(k) == now.get(k) for k in ('a', 'b', 'entrySide', 'bands'))
            bid = assignment.get(key, (l.get('place') or {}).get('id')) if same else (l.get('place') or {}).get('id')
            if bid not in totals:
                continue
            row = totals[bid]
            entries, exits = l.get('entries', 0), l.get('exits', 0)
            row['entries'] = (row['entries'] or 0) + entries
            row['exits'] = (row['exits'] or 0) + exits
            row['accesses'].append({'cameraId': cid, 'lineId': l['id'], 'name': l['name'], 'entries': entries, 'exits': exits})
            row['events'].extend({**event, 'cameraId': cid, 'lineId': l['id']} for event in l.get('events', []))
            for hour, count in l.get('hours', {}).items():
                bucket = row['hours'].setdefault(hour, {'entries': 0, 'exits': 0})
                for direction in ('entries', 'exits'):
                    bucket[direction] += count.get(direction, 0)
    return list(totals.values())
