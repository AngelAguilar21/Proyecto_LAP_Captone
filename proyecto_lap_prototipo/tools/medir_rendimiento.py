"""Mide cuánto tarda un paso de análisis con un proyecto real, etapa por etapa.

Arranca una sesión con el mismo flujo del servidor (YOLO, ByteTrack, OSNet, motor de identidad) sobre una copia temporal
del proyecto, deja correr unos pasos y resume los milisegundos. No guarda grabaciones en `data/`.

Uso (desde proyecto_lap_prototipo):
    python tools/medir_rendimiento.py p-859ce3f0 --camaras 7 --performance auto --pasos 12
    python tools/medir_rendimiento.py p-859ce3f0 --camaras 2 --performance precise
"""
import argparse
import copy
import importlib
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", help="id del proyecto o ruta de un .json")
    ap.add_argument("--camaras", type=int, default=0, help="usa solo las primeras N cámaras (0: todas)")
    ap.add_argument("--performance", default="auto", help="auto, precise, balanced o fast")
    ap.add_argument("--pasos", type=int, default=12, help="pasos de análisis a medir (se descartan los 2 primeros)")
    ap.add_argument("--servidor", default="live_server", help="módulo del servidor (para comparar versiones)")
    ap.add_argument("--limite-s", type=float, default=300, help="tiempo máximo de espera")
    args = ap.parse_args()

    ruta = Path(args.project) if Path(args.project).suffix == ".json" else ROOT / "config" / "projects" / f"{args.project}.json"
    guardado = json.loads(ruta.read_text(encoding="utf-8"))
    config = copy.deepcopy(guardado.get("config", guardado))
    config["cameras"] = [c for c in config["cameras"] if c.get("active", True)]
    if args.camaras:
        config["cameras"] = config["cameras"][:args.camaras]
        ids = {c["id"] for c in config["cameras"]}
        # Lo que se apoya en cámaras que se quitaron no se puede validar.
        config["personPairs"] = [p for p in config.get("personPairs", []) if {p["a"]["camera"], p["b"]["camera"]} <= ids]
        for c in config["cameras"]:
            c["links"] = [x for x in c.get("links", []) if x in ids]
    servidor = importlib.import_module(args.servidor)
    with tempfile.TemporaryDirectory() as carpeta:
        motor = servidor.Engine(Path(carpeta) / "live.json")
        motor.configure(config)
        pedido = {"detector": "yolo"}
        if args.servidor == "live_server":
            pedido["performance"] = args.performance
        motor.start(pedido)
        medidas, vistos, inicio = [], set(), time.time()
        while len(medidas) < args.pasos and time.time() - inicio < args.limite_s:
            with motor.lock:
                estado = {k: motor.state.get(k) for k in ("t", "processingMs", "performance", "status", "error")}
            if estado.get("status") == "error":
                print("error de la sesión:", estado.get("error"))
                break
            if estado.get("processingMs") is not None and estado["t"] not in vistos:
                vistos.add(estado["t"])
                medidas.append(estado)
            time.sleep(0.05)
        motor.stop()
        if motor.worker:
            motor.worker.join(timeout=30)
    utiles = medidas[2:] or medidas
    if not utiles:
        sys.exit("No se midió ningún paso.")
    ms = [m["processingMs"] for m in utiles]
    rend = utiles[-1].get("performance") or {}
    paso = rend.get("stepSeconds", 0.2)
    print(f"{len(config['cameras'])} cámara(s), servidor {args.servidor}, performance={rend.get('preset', 'n/a')} "
          f"(paso {paso:g} s, detector {rend.get('detectorSize', 'n/a')} px)")
    print(f"  un paso tarda en promedio {statistics.mean(ms):.0f} ms (mediana {statistics.median(ms):.0f}, mínimo {min(ms)}, máximo {max(ms)}) para {paso:g} s de video")
    print(f"  velocidad: {statistics.mean(ms) / 1000 / paso:.1f} veces más lento que el video" if statistics.mean(ms) / 1000 > paso
          else f"  velocidad: alcanza el tiempo real ({statistics.mean(ms) / 1000 / paso:.2f} del tiempo disponible)")
    por_etapa = {}
    for m in utiles:
        for clave, valor in ((m.get("performance") or {}).get("msPorEtapa") or {}).items():
            por_etapa.setdefault(clave, []).append(valor)
    if por_etapa:
        print("  promedio por etapa (ms):", {k: round(statistics.mean(v)) for k, v in por_etapa.items()})


if __name__ == "__main__":
    main()
