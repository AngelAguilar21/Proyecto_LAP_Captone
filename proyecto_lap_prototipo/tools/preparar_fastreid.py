"""Export official FastReID BoT R50 MSMT17 for evaluation, not automatic adoption.

Clone https://github.com/JDAI-CV/fast-reid under referencias-locales/fast-reid.
Optional dependencies: requirements-fastreid-export.txt. Input matches OSNet:
RGB float, (pixel/255 - ImageNet mean)/std. Normalization stays outside ONNX.
"""
import hashlib
import json
import sys
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parent/'referencias-locales/fast-reid'
URL='https://github.com/JDAI-CV/fast-reid/releases/download/v0.1.1/msmt_bot_R50.pth'


def main():
    import numpy as np
    import torch
    import onnxruntime as ort
    sys.path.insert(0,str(REPO))
    from fastreid.config import get_cfg
    from fastreid.modeling import build_model
    weights=ROOT/'models/fastreid_msmt17.pth'
    target=ROOT/'models/fastreid_msmt17.onnx'
    if not weights.exists():
        temporary=weights.with_suffix('.download')
        urllib.request.urlretrieve(URL,temporary)
        temporary.replace(weights)
    state=torch.load(weights,map_location='cpu',weights_only=True)['model']
    # Official v0.1.1 names, renamed in the current EmbeddingHead; strict load
    # still checks every backbone and BN tensor, never silently skips weights.
    state={k.replace('heads.bnneck.','heads.bottleneck.0.').replace('heads.classifier.weight','heads.weight'):v for k,v in state.items()}
    config=get_cfg()
    config.merge_from_file(str(REPO/'configs/MSMT17/bagtricks_R50.yml'))
    config.MODEL.DEVICE='cpu'
    config.MODEL.BACKBONE.PRETRAIN=False
    config.MODEL.HEADS.NUM_CLASSES=state['heads.weight'].shape[0]
    model=build_model(config)
    for key, expected in [('pixel_mean',np.array([.485,.456,.406])*255),('pixel_std',np.array([.229,.224,.225])*255)]:
        value=state.pop(key)
        np.testing.assert_allclose(value.numpy().reshape(-1),expected,rtol=1e-5)
    model.load_state_dict(state,strict=True)
    model.eval()
    # Explicit preprocessing contract: do not run Baseline.preprocess_image twice.
    class Encoder(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.backbone=model.backbone
            self.heads=model.heads
        def forward(self,x):
            return self.heads(self.backbone(x))
    encoder=Encoder().eval()
    torch.set_num_threads(2)
    torch.manual_seed(7)
    x=torch.randn(1,3,256,128)
    temporary=target.with_suffix('.tmp.onnx')
    torch.onnx.export(encoder,x,str(temporary),input_names=['images'],output_names=['embeddings'],opset_version=17,dynamo=False)
    options=ort.SessionOptions(); options.intra_op_num_threads=2
    inference=ort.InferenceSession(str(temporary),options,providers=['CPUExecutionProvider'])
    with torch.inference_mode(): expected=encoder(x).numpy()
    actual=inference.run(None,{'images':x.numpy()})[0]
    np.testing.assert_allclose(actual,expected,atol=3e-4,rtol=3e-3)
    temporary.replace(target)
    with weights.open('rb') as f: sha=hashlib.file_digest(f,'sha256').hexdigest()
    target.with_suffix('.provenance.json').write_text(json.dumps(dict(source=URL,weightsSha256=sha,architecture='FastReID BoT ResNet50',training='MSMT17 official',input='RGB/ImageNet normalized',dimension=int(actual.shape[-1]),exportVerified=True,maxAbsoluteError=float(np.max(np.abs(actual-expected)))),indent=2),encoding='utf-8')
    print('Exportación verificada:',target.name)

if __name__=='__main__':main()
