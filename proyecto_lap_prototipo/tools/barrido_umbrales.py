"""Barrido de umbrales del motor de identidad contra etiquetas a mano, para elegir valores robustos.

Recorre una rejilla de `threshold` (unión entre cámaras) y `split_threshold` (corte de tracklet), mide IDF1 y
conteos con tools/evaluar_identidad.py y elige el centro de la meseta: la mediana de las combinaciones cuyo IDF1
queda a menos de `--meseta` del máximo. Elegir el máximo exacto sobrecalibra a unas pocas personas; el centro de
la meseta es más estable. Con pocas personas sigue siendo una estimación optimista (se calibra y se mide sobre los
mismos datos): repetir con un conjunto más grande antes de fiarse.

Uso (desde proyecto_lap_prototipo):
    python tools/barrido_umbrales.py data/anotacion/obs_camera_AB_v2.pkl data/anotacion/camera_AB/etiquetas_provisional.csv \
        --salida data/anotacion/umbrales_osnet_barrido.json
"""
import argparse
import itertools
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
import evaluar_identidad as ev  # noqa: E402


def medir(pkl, etiquetas, ajustes, **opciones):
    filas = ev.salida_desde_pkl(pkl, ajustes=ajustes, solo_confirmados=True, **opciones)
    return ev.metricas(ev.expandir_etiquetas(etiquetas, filas), filas)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pkl")
    ap.add_argument("etiquetas")
    ap.add_argument("--thresholds", type=float, nargs="+", default=[0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85])
    ap.add_argument("--splits", type=float, nargs="+", default=[0.30, 0.40, 0.50, 0.55, 0.60, 0.65, 0.70])
    ap.add_argument("--margen-misma-camara", type=float, default=0.04, help="same_camera_threshold = threshold + margen")
    ap.add_argument("--meseta", type=float, default=0.02, help="IDF1 mínimo = máximo - meseta")
    ap.add_argument("--sin-geometria", action="store_true")
    ap.add_argument("--salida")
    args = ap.parse_args()

    resultados = []
    print("threshold  split   IDF1   ids  cambios  ids/persona")
    for thr, split in itertools.product(args.thresholds, args.splits):
        ajustes = {"threshold": thr, "average_threshold": round(max(thr - 0.2, 0.3), 3),
                   "same_camera_threshold": round(min(thr + args.margen_misma_camara, 0.99), 3), "split_threshold": split}
        m = medir(args.pkl, args.etiquetas, ajustes, sin_geometria=args.sin_geometria)
        resultados.append((m["IDF1"], thr, split, ajustes, m))
        print(f"{thr:8.2f}  {split:5.2f}  {m['IDF1']:.3f}  {m['ids_sistema_que_siguen_a_alguien']:3d}  {m['cambios_de_id']:5d}  {m['ids_por_persona']}")
    mejor = max(r[0] for r in resultados)
    meseta = [r for r in resultados if r[0] >= mejor - args.meseta]
    thr = statistics.median(r[1] for r in meseta)
    split = statistics.median(r[2] for r in meseta)
    elegido = {"threshold": round(thr, 3), "average_threshold": round(max(thr - 0.2, 0.3), 3),
               "same_camera_threshold": round(min(thr + args.margen_misma_camara, 0.99), 3), "split_threshold": round(split, 3)}
    final = medir(args.pkl, args.etiquetas, elegido, sin_geometria=args.sin_geometria)
    print(f"\nMáximo IDF1 {mejor:.3f}; meseta de {len(meseta)} de {len(resultados)} combinaciones (>= {mejor - args.meseta:.3f})")
    print("Elegido (centro de la meseta):", elegido)
    print(f"  IDF1 {final['IDF1']}, IDs {final['ids_sistema_que_siguen_a_alguien']} para {final['personas_reales']} personas, "
          f"cambios {final['cambios_de_id']}, IDs por persona {final['ids_por_persona']}")
    if args.salida:
        Path(args.salida).write_text(json.dumps(elegido, indent=2), encoding="utf-8")
        print("Escrito:", args.salida)


if __name__ == "__main__":
    main()
