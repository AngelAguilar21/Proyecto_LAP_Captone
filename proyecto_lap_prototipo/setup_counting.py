"""Aplica parches de compatibilidad y comprueba P2PNet; no descarga dependencias."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/"src"))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Solo comprobar, sin aplicar parches.')
    args=parser.parse_args()
    if not args.check:
        from aplicar_parche_p2pnet import aplicar
        aplicar()
    weights=ROOT/'external'/'P2PNet'/'weights'/'SHTechA.pth'
    if not weights.is_file():
        raise SystemExit('Faltan los pesos oficiales. Inicializa el submódulo P2PNet según la guía.')
    import torch
    from detection import DetectorP2PNet
    torch.set_num_threads(2)
    model=DetectorP2PNet(str(weights),device='cpu')
    import numpy as np
    model.detectar(np.zeros((128,128,3),dtype=np.uint8))
    print('P2PNet preparado: código, checkpoint e inferencia CPU verificados.')


if __name__=='__main__': main()
