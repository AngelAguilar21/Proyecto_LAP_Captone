"""Inicializa mapas y configuración de una instalación nueva sin datos personales."""
import json
from live_server import ROOT, default_config
from live_core import validate_config


def main():
    target = ROOT / 'config' / 'live.local.json'
    if target.exists():
        print('La configuración existente se conserva.')
        return
    config = default_config()
    plans = {}
    for floor in range(1, 5):
        data = json.loads((ROOT / 'dashboard/public/maps/lap' / f'{floor}.json').read_text(encoding='utf-8'))
        plans[f'lap-{floor}'] = {'width': data['width'], 'height': data['height'], 'floor': f'LAP · Nivel {floor}',
                                'unit': 'meters', 'mapAsset': f'/maps/lap/{floor}.json', 'mapConfigured': True,
                                'background': '', 'zones': [], 'planLines': []}
    config.update(plans['lap-3'])
    config.update(planId='lap-3', plans=plans, cameras=[], radius=2, setupComplete=False)
    validate_config(config)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x', encoding='utf-8') as output:
        json.dump(config, output, ensure_ascii=False, indent=2)
    print('Mapas LAP preparados. Añade tus propias cámaras desde Configuración.')


if __name__ == '__main__':
    main()
