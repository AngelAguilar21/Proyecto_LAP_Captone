"""Recalcula el mapa desde observaciones guardadas sin modificar el análisis original."""
import copy
from live_core import calibration, project, Occupancy
from following.flow import FlowField
from spatial_scope import accepts


def current_projection(meta, samples, config):
    result = copy.deepcopy(samples)
    cameras = {c['id']: c for c in config['cameras']}
    original = {c['id']: c for c in meta.get('config', {}).get('cameras', [])}
    matrices = {cid: calibration(c.get('pairs', [])) for cid, c in cameras.items()}
    counters, fields, camera_counters = {}, {}, {}
    for sample in result:
        groups = {}
        for observation in sample['cameras']:
            cid = observation['id']
            camera = cameras.get(cid)
            if not camera or (cid in original and camera.get('source') != original[cid].get('source')):
                observation['people'] = []
                continue
            pid = camera.get('planId', 'custom')
            plan = {**config, **(config.get('plans', {}).get(pid, {}) if pid != config.get('planId') else {})}
            counters.setdefault(pid, Occupancy(plan))
            fields.setdefault(pid, FlowField(plan))
            camera_counters.setdefault(cid, Occupancy(plan))
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
                observation['analysis']['map'] = camera_counters[cid].update(observation.get('people', []), sample['t'])
        sample['levels'] = {}
        for pid, counter in counters.items():
            people = groups.get(pid, [])
            sample['levels'][pid] = counter.update(people, sample['t'])
            sample['levels'][pid]['flowVectors'] = fields[pid].update(people, sample['t'])
        sample['analytics'] = sample['levels'].get(config.get('planId'), {'heat': [], 'clusters': [], 'zones': []})
    return result
