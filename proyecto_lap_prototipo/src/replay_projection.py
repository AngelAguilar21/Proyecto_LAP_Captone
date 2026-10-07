"""Recalcula el mapa desde observaciones guardadas sin modificar el análisis original."""
import copy
from live_core import calibration, project, Occupancy
from following.flow import FlowField
from spatial_scope import accepts, outline_scope


def current_projection(meta, samples, config):
    result = copy.deepcopy(samples)
    cameras = {c['id']: c for c in config['cameras']}
    original = {c['id']: c for c in meta.get('cameras', [])}      # lo que tenía cada cámara cuando se hizo el análisis
    matrices = {cid: calibration(c.get('pairs', [])) for cid, c in cameras.items()}
    counters, fields, camera_counters = {}, {}, {}
    for sample in result:
        groups = {}
        for observation in sample['cameras']:
            cid = observation['id']
            camera = cameras.get(cid)
            if not camera or (original.get(cid, {}).get('source') and camera.get('source') != original[cid]['source']):
                observation['people'] = []
                continue
            pid = camera.get('planId', 'custom')
            plan = {**config, **(config.get('plans', {}).get(pid, {}) if pid != config.get('planId') else {})}
            plan.update(outline_scope(plan))
            counters.setdefault(pid, Occupancy(plan))
            fields.setdefault(pid, FlowField(plan))
            camera_counters.setdefault(cid, Occupancy(plan))
            # Solo cuenta como cambio lo que la grabación registró: una grabación antigua que no guardó la calibración no se
            # puede comparar, y tratarla como «cambiada» rompía siempre la asociación entre cámaras (P00001 se volvía A:P00001 y B:P00001).
            changed = any(k in original.get(cid, {}) and camera.get(k) != original[cid][k] for k in ('pairs', 'planId', 'detectionZone', 'source'))
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
