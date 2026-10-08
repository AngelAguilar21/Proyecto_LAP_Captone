"""Exporta OSNet-AIN MSMT17 oficial, sin entrenamiento ni reemplazar OSNet ligero.

Dependencias opcionales: requirements-reid-export.txt. Fuente de pesos:
https://kaiyangzhou.github.io/deep-person-reid/MODEL_ZOO.html
"""
import hashlib
import importlib.util
import json
from pathlib import Path


def main():
    import gdown
    import numpy as np
    import onnxruntime as ort
    import torch
    root = Path(__file__).resolve().parents[1]
    weights = root / 'models/osnet_ain_msmt17.pth'
    target = root / 'models/osnet_ain_msmt17.onnx'
    if not weights.exists():
        gdown.download(id='1SigwBE6mPdqiJMqhuIY4aqC7--5CsMal', output=str(weights), quiet=False)
    # Importar solo la arquitectura evita cargar datasets y paquetes de entrenamiento.
    package = importlib.util.find_spec('torchreid')
    source = Path(package.origin).parent / 'reid/models/osnet_ain.py'
    if not source.exists():
        source = Path(package.origin).parent / 'models/osnet_ain.py'
    spec = importlib.util.spec_from_file_location('osnet_ain_architecture', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    state = torch.load(weights, map_location='cpu', weights_only=True)
    state = state.get('state_dict', state)
    state = {key.removeprefix('module.'): value for key, value in state.items()}
    model = module.osnet_ain_x1_0(num_classes=state['classifier.weight'].shape[0], pretrained=False)
    model.load_state_dict(state, strict=True)
    model.eval()
    torch.set_num_threads(4)
    torch.manual_seed(0)
    sample = torch.randn(4, 3, 256, 128)
    temporary = target.with_suffix('.tmp.onnx')
    torch.onnx.export(model, sample, str(temporary), input_names=['images'], output_names=['embeddings'],
                      opset_version=17, dynamo=False)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    session = ort.InferenceSession(str(temporary), options, providers=['CPUExecutionProvider'])
    with torch.inference_mode():
        expected = model(sample).numpy()
    actual = session.run(None, {'images': sample.numpy()})[0]
    np.testing.assert_allclose(actual, expected, rtol=2e-3, atol=2e-4)
    temporary.replace(target)
    with weights.open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    target.with_suffix('.provenance.json').write_text(json.dumps({
        'architecture': 'osnet_ain_x1_0', 'training': 'MSMT17, official pretrained',
        'weightsSha256': sha, 'source': 'https://kaiyangzhou.github.io/deep-person-reid/MODEL_ZOO.html',
        'batch': 4, 'input': [4, 3, 256, 128], 'exportVerified': True,
        'maxAbsoluteError': float(np.abs(actual-expected).max())}, indent=2), encoding='utf-8')
    print('Exportación verificada:', target.name)


if __name__ == '__main__':
    main()
