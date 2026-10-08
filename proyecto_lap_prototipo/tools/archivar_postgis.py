"""Importa una sesión ya cerrada. La conexión se recibe solo por entorno."""
import argparse
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from storage.postgis import import_session
from storage.environment import load_environment

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sesion', type=Path, help='Carpeta que contiene manifest.json y samples.jsonl')
    args = parser.parse_args()
    load_environment(Path(__file__).resolve().parents[2])
    if not os.environ.get('AEROTRACK_DATABASE_URL'):
        parser.error('Define AEROTRACK_DATABASE_URL; no pongas contraseñas en argumentos.')
    print(import_session(args.sesion))
