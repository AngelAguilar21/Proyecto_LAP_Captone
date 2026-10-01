"""Recalcula el mapa desde observaciones guardadas sin modificar el análisis original."""
import copy
from live_core import calibration, project, Occupancy
from following.flow import FlowField
from spatial_scope import accepts
from zone_episodes import plan_observed


def current_projection(meta, samples, config):
    result = copy.deepcopy(samples)
    config = copy.deepcopy(config)
    cameras = {c['id']: c for c in config['cameras']}
    recorded = meta.get('cameras')
    legacy = meta.get('config', {}).get('cameras')
    if recorded is not None and legacy is not None:
        # Two explicit but contradictory identities must not be guessed.
        old = {c['id']: c for c in legacy}
        if set(old)!={c['id'] for c in recorded} or any(c['id'] not in old or any(c[k] != old[c['id']][k]
               for k in ('source','pairs','planId','detectionZone') if k in c and k in old[c['id']]) for c in recorded):
            raise ValueError('Configuración histórica de cámaras ambigua.')
    original = {c['id']: c for c in (recorded if recorded is not None else legacy or [])}
    matrices = {cid: calibration(c.get('pairs', [])) for cid, c in cameras.items()}
    counters, fields, camera_counters = {}, {}, {}
    for sample in result:
        groups = {}
        observed = set()
        for observation in sample['cameras']:
            cid = observation['id']
            camera = cameras.get(cid)
            if cid in original and original[cid].get('sourceKind') == 'live':
                raise ValueError('La fuente LIVE histórica no tiene identidad verificable para reproyección actual.')
            if not camera or (cid in original and camera.get('source') != original[cid].get('source')):
                observation['people'] = []
                continue
            if cid not in original:
                raise ValueError('No hay configuración histórica verificable para esta cámara.')
            pid = camera.get('planId', 'custom')
            plan = {**config, **(config.get('plans', {}).get(pid, {}) if pid != config.get('planId') else {}), 'planId': pid}
            counters.setdefault(pid, Occupancy(plan, episode_namespace='projection:'+meta.get('session', 'legacy')))
            fields.setdefault(pid, FlowField(plan))
            camera_counters.setdefault(cid, Occupancy(plan, scope='camera-map:'+cid,
                                                      episode_namespace='projection:'+meta.get('session', 'legacy')))
            if observation.get('observed', True):
                observed.add(cid)
            changed = any(camera.get(k) != original.get(cid, {}).get(k) for k in ('pairs', 'planId', 'detectionZone', 'source'))
            for person in observation.get('people', []):
                pixel = person.get('pixel')
                person['point'] = project(matrices[cid], *pixel) if matrices[cid] is not None and pixel else None
                if pixel and not accepts(camera,plan,*pixel,person['point']):
                    person['point'] = None
                # Una nueva calibración no valida las asociaciones entre cámaras antiguas.
                if changed:
                    person['id'] = cid + ':' + person['id']
                    person['association'] = 'local'
                if person['point']:
                    groups.setdefault(pid, []).append(person)
            if observation.get('analysis'):
                observation['analysis']['map'] = camera_counters[cid].update(observation.get('people', []), sample['t'], observation_valid=matrices[cid] is not None and cid in observed)
        sample['levels'] = {}
        for pid, counter in counters.items():
            people = groups.get(pid, [])
            sources = [{**c, 'projects': matrices[c['id']] is not None} for c in cameras.values() if c.get('active', True)]
            sample['levels'][pid] = counter.update(people, sample['t'], observation_valid=plan_observed(sources, observed, pid))
            sample['levels'][pid]['flowVectors'] = fields[pid].update(people, sample['t'])
        sample['analytics'] = sample['levels'].get(config.get('planId'), {'heat': [], 'clusters': [], 'zones': []})
    return result
