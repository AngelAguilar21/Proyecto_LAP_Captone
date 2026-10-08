"""Tabla «antes y después» y ablaciones del motor de identidad contra etiquetas a mano.

Corre sobre las observaciones capturadas (tools/capturar_observaciones.py) y las etiquetas por track (tools/preparar_anotacion.py):
  - el motor por defecto (umbrales de OSNet, con reagrupación al cerrar),
  - la misma configuración quitando una pieza cada vez: compuerta física, coincidencia mutua, reagrupación,
    vistas confiables y corte de tracklet,
  - opcionalmente, un «oráculo» con calibraciones coherentes entre cámaras (techo, no se puede desplegar).
El vector se calcula como en el servidor (cada N muestras y, además, mientras el track no tiene ID público), y se informa
cuántos vectores OSNet exige cada configuración y cuánto cuesta el motor por muestra.

Uso (desde proyecto_lap_prototipo):
    python tools/ablaciones.py data/anotacion/obs_camera_AB_v2.pkl data/anotacion/camera_AB/etiquetas_provisional.csv \
        --oraculo B:2.39,0.09 --md data/anotacion/ablaciones.md --json data/anotacion/ablaciones.json
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
import evaluar_identidad as ev  # noqa: E402


def medir(pkl, etiquetas, **opciones):
    info = {}
    filas = ev.salida_desde_pkl(pkl, info=info, **opciones)
    m = ev.metricas(ev.expandir_etiquetas(etiquetas, filas), filas)
    return {**m, "embeddings": info.get("embeddings"), "motor_ms": info.get("motor_ms_por_muestra"), "muestras": info.get("muestras"),
            "cierre": info.get("cierre")}


def configuraciones(oraculo):
    base = {"solo_confirmados": True, "cierre": True}
    filas = [
        ("por defecto (umbrales de OSNet, con cierre)", base),
        ("  umbrales de AeroVision sin recalibrar", {**base, "ajustes": {
            "threshold": 0.60, "average_threshold": 0.55, "same_camera_threshold": 0.70, "split_threshold": 0.40}}),
        ("  sin compuerta física (visual y temporal)", {**base, "sin_geometria": True}),
        ("  sin coincidencia mutua", {**base, "ajustes": {"mutual_best": False}}),
        ("  sin reagrupación al cerrar", {**base, "cierre": False}),
        ("  sin vistas confiables (usa cualquier recuadro)", {**base, "ajustes": {"min_conf": 0.0, "min_height": 1, "max_occlusion": 1.0, "edge_margin": -1000}}),
        ("  sin corte de tracklet", {**base, "ajustes": {"split_threshold": -1.0}}),
    ]
    if oraculo:
        filas.append(("ORÁCULO: calibraciones coherentes + cierre", {**base, "desplazar": oraculo}))
    return filas


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pkl")
    ap.add_argument("etiquetas")
    ap.add_argument("--oraculo", help="desfase que vuelve coherentes las calibraciones, p. ej. B:2.39,0.09")
    ap.add_argument("--md")
    ap.add_argument("--json")
    args = ap.parse_args()
    oraculo = ev._leer_desfases(args.oraculo)

    resultados, lineas = [], ["| Configuración | IDs contados | IDF1 | Cambios de ID | IDs por persona | Pureza | Vectores OSNet | Motor (ms/muestra) |", "|---|---|---|---|---|---|---|---|"]
    for nombre, opciones in configuraciones(oraculo):
        m = medir(args.pkl, args.etiquetas, **opciones)
        resultados.append({"configuracion": nombre, **m})
        lineas.append(f"| {nombre} | {m['ids_sistema_que_siguen_a_alguien']} de {m['personas_reales']} | {m['IDF1']:.3f} | {m['cambios_de_id']} | "
                      f"{m['ids_por_persona']} | {m['pureza_media']} | {m['embeddings']} | {m['motor_ms']} |")
        print(lineas[-1], flush=True)
    if args.md:
        Path(args.md).write_text("\n".join(lineas) + "\n", encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps(resultados, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
