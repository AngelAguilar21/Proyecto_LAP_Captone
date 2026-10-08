"""Typed graph of configured space. Geographic proximity is not a passage.

Camera edges alone authorize identity candidates. Business ownership and zone
membership explain counts but must never implicitly authorize identity merges.
"""
import hashlib
import json


def build_graph(config, businesses):
    nodes, edges, warnings = {}, [], []
    def node(key, kind, name, **attributes):
        nodes[key] = dict(id=key, kind=kind, name=name, **attributes)
    def edge(source, target, kind, **attributes):
        edges.append(dict(source=source, target=target, kind=kind, **attributes))
    for camera in config.get('cameras', []):
        cid = 'camera:' + camera['id']
        node(cid, 'camera', camera.get('name', camera['id']), planId=camera.get('planId', config.get('planId')), active=camera.get('active', True))
        for zone in camera.get('analysisZones', []):
            zid = cid + ':zone:' + str(zone.get('id', zone.get('name')))
            node(zid, 'zone', zone.get('name', 'Zona'), cameraId=camera['id'])
            edge(cid, zid, 'observes')
            if zone.get('businessId'):
                edge(zid, 'business:' + zone['businessId'], 'associated_with')
        for line in camera.get('countLines', []):
            lid = cid + ':entrance:' + line['id']
            node(lid, 'entrance', line.get('name', line['id']), cameraId=camera['id'], lineId=line['id'], entrySide=line.get('entrySide', 1))
            edge(cid, lid, 'counts')
    for business in businesses:
        bid = 'business:' + business['id']
        node(bid, 'business', business['nombre'], state=business.get('estado', 'activo'))
        for door in business.get('puertas', []):
            lid = 'camera:' + door['camaraId'] + ':entrance:' + door['lineaId']
            edge(lid, bid, 'access_to')
    routes = config.get('cameraRoutes')
    if routes is None:
        routes = [dict(**{'from': c['id'], 'to': target}, kind='legacy', minSeconds=0, maxSeconds=config.get('handoffSeconds',12))
                  for c in config.get('cameras',[]) for target in c.get('links',[])]
    for route in routes:
        edge('camera:' + route['from'], 'camera:' + route['to'], route['kind'],
             minSeconds=route.get('minSeconds',0), maxSeconds=route.get('maxSeconds',120), enabled=bool(config.get('clocksVerified')))
    valid = []
    for relation in edges:
        if relation['source'] in nodes and relation['target'] in nodes:
            valid.append(relation)
        else:
            warnings.append('Relación sin entidad vigente: ' + relation['source'] + ' → ' + relation['target'])
    result = dict(nodes=list(nodes.values()), edges=valid, warnings=warnings,
                  clocksVerified=bool(config.get('clocksVerified')))
    result['revision'] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return result


def persist_graph(connection, graph):
    """Normalized indexed snapshot; no duplicated hand-maintained configuration."""
    connection.executescript('''
        CREATE TABLE IF NOT EXISTS spatial_nodes (id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS spatial_edges (source TEXT NOT NULL REFERENCES spatial_nodes(id),
          target TEXT NOT NULL REFERENCES spatial_nodes(id), kind TEXT NOT NULL, payload TEXT NOT NULL,
          PRIMARY KEY(source,target,kind));
        CREATE INDEX IF NOT EXISTS spatial_edge_target ON spatial_edges(target,kind);
        CREATE TABLE IF NOT EXISTS spatial_revision (id INTEGER PRIMARY KEY, revision TEXT NOT NULL);
    ''')
    old = connection.execute('SELECT revision FROM spatial_revision WHERE id=1').fetchone()
    if old and old[0] == graph['revision']:
        return
    with connection:
        connection.execute('DELETE FROM spatial_edges')
        connection.execute('DELETE FROM spatial_nodes')
        connection.executemany('INSERT INTO spatial_nodes VALUES (?,?,?)', [(n['id'], n['kind'], json.dumps(n)) for n in graph['nodes']])
        connection.executemany('INSERT INTO spatial_edges VALUES (?,?,?,?)', [(e['source'],e['target'],e['kind'],json.dumps(e)) for e in graph['edges']])
        connection.execute('INSERT INTO spatial_revision VALUES (1,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision', (graph['revision'],))
