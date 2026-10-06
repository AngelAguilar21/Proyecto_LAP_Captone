"""Prepara el etiquetado a mano de identidades entre cámaras.

A partir de observaciones capturadas (tools/capturar_observaciones.py) genera, en
data/anotacion/<nombre>/:
  etiquetas.csv       una fila por track local con id_real VACÍO para que lo rellenes
  hoja_<cam>_<n>.jpg  hojas con recortes de cada track a lo largo del tiempo

Cómo etiquetar: mira las hojas y escribe en id_real la misma etiqueta (P1, P2...) para los
tracks que son la misma persona, también entre cámaras. Si un track mezcla a dos personas,
duplica la fila y ajusta t_ini y t_fin. Deja vacío lo que no sea una persona (reflejos, objetos).

Privacidad: las hojas contienen recortes de personas reales y solo existen en tu disco
(data/anotacion/ está fuera de git). Bórralas al terminar de etiquetar.

Uso (desde proyecto_lap_prototipo):
    python tools/preparar_anotacion.py data/anotacion/obs_camera_AB.pkl
"""
import argparse
import csv
import pickle
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CROPS_POR_TRACK, TRACKS_POR_HOJA, ALTO = 4, 7, 190


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pkl")
    ap.add_argument("--min-muestras", type=int, default=3, help="ignora tracks más cortos")
    args = ap.parse_args()

    datos = pickle.loads(Path(args.pkl).read_bytes())
    if "sources" not in datos:
        sys.exit("El archivo no trae las rutas de video: vuelve a capturarlo con tools/capturar_observaciones.py.")
    tracks = defaultdict(list)
    for t, filas in datos["obs"]:
        for r in filas:
            if r["box"]:
                tracks[(r["camera"], r["local"])].append((t, r["box"]))
    salida = Path(args.pkl).parent / Path(args.pkl).stem.replace("obs_", "")
    salida.mkdir(parents=True, exist_ok=True)

    with open(salida / "etiquetas.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["camara", "local_id", "t_ini", "t_fin", "muestras", "id_real"])
        for (cam, local), seq in sorted(tracks.items(), key=lambda kv: (kv[0][0], kv[1][0][0])):
            if len(seq) >= args.min_muestras:
                w.writerow([cam, local, round(seq[0][0], 2), round(seq[-1][0], 2), len(seq), ""])

    for cam in sorted({c for c, _ in tracks}):
        origen = datos["sources"][cam]
        if isinstance(origen, str) and "://" not in origen and not Path(origen).is_absolute():
            origen = str(ROOT / origen)
        cap = cv2.VideoCapture(origen)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.
        ancho, alto = datos["sizes"][cam]
        lista = sorted(((k, v) for k, v in tracks.items() if k[0] == cam and len(v) >= args.min_muestras), key=lambda kv: kv[1][0][0])
        for pagina in range(0, len(lista), TRACKS_POR_HOJA):
            filas = []
            for (_, local), seq in lista[pagina:pagina + TRACKS_POR_HOJA]:
                idx = np.linspace(0, len(seq) - 1, CROPS_POR_TRACK).round().astype(int)
                tira = []
                for i in idx:
                    t, (x1, y1, x2, y2) = seq[i]
                    cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
                    ok, frame = cap.read()
                    if ok and frame.shape[1] != ancho:
                        frame = cv2.resize(frame, (ancho, alto))
                    x1, y1, x2, y2 = max(0, int(x1)), max(0, int(y1)), int(x2), int(y2)
                    recorte = frame[y1:y2, x1:x2] if ok and x2 > x1 and y2 > y1 else np.zeros((ALTO, 80, 3), np.uint8)
                    escala = ALTO / max(recorte.shape[0], 1)
                    recorte = cv2.resize(recorte, (max(20, int(recorte.shape[1] * escala)), ALTO))
                    cv2.putText(recorte, f"{t:.1f}s", (3, 14), cv2.FONT_HERSHEY_SIMPLEX, .45, (0, 255, 255), 1)
                    tira.append(cv2.copyMakeBorder(recorte, 0, 0, 0, 4, cv2.BORDER_CONSTANT))
                fila = np.hstack(tira)
                etiqueta = np.zeros((ALTO, 170, 3), np.uint8)
                cv2.putText(etiqueta, f"{cam}{local}", (8, 40), cv2.FONT_HERSHEY_SIMPLEX, 1., (255, 255, 255), 2)
                cv2.putText(etiqueta, f"{seq[0][0]:.1f} - {seq[-1][0]:.1f} s", (8, 70), cv2.FONT_HERSHEY_SIMPLEX, .5, (200, 200, 200), 1)
                cv2.putText(etiqueta, f"{len(seq)} muestras", (8, 92), cv2.FONT_HERSHEY_SIMPLEX, .5, (200, 200, 200), 1)
                filas.append(np.hstack([etiqueta, fila]))
            ancho_max = max(f.shape[1] for f in filas)
            filas = [cv2.copyMakeBorder(f, 0, 6, 0, ancho_max - f.shape[1], cv2.BORDER_CONSTANT) for f in filas]
            cv2.imwrite(str(salida / f"hoja_{cam}_{pagina // TRACKS_POR_HOJA + 1}.jpg"), np.vstack(filas))
    print("Plantilla:", salida / "etiquetas.csv")
    print("Hojas:", sorted(p.name for p in salida.glob("hoja_*.jpg")))


if __name__ == "__main__":
    main()
