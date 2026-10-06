"""Evalúa la identidad entre cámaras contra anotaciones hechas a mano.

Mide: IDF1 (global, entre cámaras), cambios de ID por cámara, IDs por persona real (1 es lo ideal),
fragmentación, personas únicas
contadas frente a reales y pureza de los IDs. No necesita paquetes nuevos: usa scipy
(ya instalado) para la asignación húngara.

Formatos (CSV con encabezado, cajas normalizadas 0..1 respecto al ancho y alto del frame):
  anotacion.csv   camara,t,x1,y1,x2,y2,id_real
  salida.csv      camara,t,x1,y1,x2,y2,id_sistema
  etiquetas.csv   camara,local_id,t_ini,t_fin,id_real   (por track; se expande a cajas)

Uso:
  python tools/evaluar_identidad.py --anotacion A.csv --salida S.csv
  python tools/evaluar_identidad.py --etiquetas E.csv --salida-pkl data/salida_reid/obs_x.pkl
  python tools/evaluar_identidad.py --anotacion A.csv --salida-replay <sesion>
Opciones: --iou 0.5 --tol 0.11 --min-frames 3 --json resultado.json
"""
import argparse
import csv
import json
import pickle
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def iou(a, b):
    ix = max(0., min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0., min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.


def leer_csv(path, campo_id):
    filas = []
    with open(path, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if not str(r.get(campo_id, "")).strip():
                continue  # fila sin etiquetar
            filas.append({"camara": r["camara"], "t": float(r["t"]),
                          "caja": tuple(float(r[k]) for k in ("x1", "y1", "x2", "y2")), "id": str(r[campo_id]).strip()})
    return filas


def emparejar_cuadros(gt, sistema, umbral_iou=.5, tol=.11):
    """Empareja cajas anotadas con cajas del sistema por cámara y tiempo (húngaro por cuadro).

    Devuelve lista de (indice_gt, indice_sistema).
    """
    por_cam = defaultdict(list)
    for j, s in enumerate(sistema):
        por_cam[s["camara"]].append((s["t"], j))
    for cam in por_cam:
        por_cam[cam].sort()
    gt_por_cuadro = defaultdict(list)
    for i, g in enumerate(gt):
        gt_por_cuadro[(g["camara"], g["t"])].append(i)
    pares = []
    for (cam, t), indices in gt_por_cuadro.items():
        candidatos = [j for ts, j in por_cam.get(cam, []) if abs(ts - t) <= tol]
        if not candidatos:
            continue
        # De los cuadros del sistema cercanos en el tiempo, se usa el más cercano.
        mejor_t = min({sistema[j]["t"] for j in candidatos}, key=lambda x: abs(x - t))
        candidatos = [j for j in candidatos if sistema[j]["t"] == mejor_t]
        costo = np.array([[1. - iou(gt[i]["caja"], sistema[j]["caja"]) for j in candidatos] for i in indices])
        filas, cols = linear_sum_assignment(costo)
        pares += [(indices[r], candidatos[c]) for r, c in zip(filas, cols) if 1. - costo[r, c] >= umbral_iou]
    return pares


def metricas(gt, sistema, umbral_iou=.5, tol=.11, min_frames=3):
    pares = emparejar_cuadros(gt, sistema, umbral_iou, tol)
    gt_ids = sorted({g["id"] for g in gt})
    sys_ids = sorted({s["id"] for s in sistema})
    gi, si = {k: n for n, k in enumerate(gt_ids)}, {k: n for n, k in enumerate(sys_ids)}
    coincide = np.zeros((len(gt_ids), len(sys_ids)))
    for i, j in pares:
        coincide[gi[gt[i]["id"]], si[sistema[j]["id"]]] += 1
    # IDF1: la asignación de identidades que maximiza las detecciones bien identificadas.
    idtp = 0
    if coincide.size:
        filas, cols = linear_sum_assignment(-coincide)
        idtp = int(coincide[filas, cols].sum())
    idfn, idfp = len(gt) - idtp, len(sistema) - idtp
    idf1 = 2 * idtp / (2 * idtp + idfp + idfn) if (2 * idtp + idfp + idfn) else 0.

    # Cambios de ID y fragmentación por persona real.
    emparejado = {i: j for i, j in pares}
    secuencias = defaultdict(list)
    for i, g in enumerate(gt):
        secuencias[(g["id"], g["camara"])].append((g["t"], i))
    cambios = fragmentos = 0
    ids_por_real = defaultdict(set)
    for (real, _cam), seq in secuencias.items():
        seq.sort()
        estado_prev = None
        vistos = []
        for _t, i in seq:
            seguido = i in emparejado
            if estado_prev is False and seguido:
                fragmentos += 1
            estado_prev = seguido
            if seguido:
                vistos.append(sistema[emparejado[i]]["id"])
                ids_por_real[real].add(sistema[emparejado[i]]["id"])
        # Cambios de ID dentro de una cámara; la inconsistencia entre cámaras se mide con ids_por_persona.
        cambios += sum(1 for a, b in zip(vistos, vistos[1:]) if a != b)
    ids_por_persona = (sum(len(v) for v in ids_por_real.values()) / len(ids_por_real)) if ids_por_real else None

    # Personas contadas: IDs del sistema que siguieron a alguien real al menos min_frames cuadros.
    cuadros_por_sys = Counter(sistema[j]["id"] for _, j in pares)
    contadas = sum(1 for n in cuadros_por_sys.values() if n >= min_frames)
    # Pureza: cuánto de cada ID del sistema pertenece a su persona real dominante.
    pureza = []
    for k, n_sys in enumerate(sys_ids):
        total = coincide[:, k].sum()
        if total >= min_frames:
            pureza.append(coincide[:, k].max() / total)
    return {
        "personas_reales": len(gt_ids), "ids_sistema_total": len(sys_ids), "ids_sistema_que_siguen_a_alguien": contadas,
        "exceso_de_ids": contadas - len(gt_ids), "IDF1": round(idf1, 4), "cambios_de_id": cambios,
        "ids_por_persona": round(ids_por_persona, 2) if ids_por_persona else None, "fragmentos": fragmentos, "detecciones_anotadas": len(gt), "detecciones_sistema": len(sistema),
        "recall_deteccion": round(len(pares) / len(gt), 4) if gt else 0.,
        "precision_deteccion": round(len(pares) / len(sistema), 4) if sistema else 0.,
        "pureza_media": round(float(np.mean(pureza)), 4) if pureza else None,
    }


def expandir_etiquetas(etiquetas_csv, obs_filas):
    """Convierte etiquetas por track (cámara, local_id, t_ini, t_fin, id_real) en cajas anotadas.

    obs_filas: filas {camara, local, t, caja} del sistema (cajas normalizadas).
    """
    segmentos = []
    with open(etiquetas_csv, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if str(r.get("id_real", "")).strip():
                segmentos.append((r["camara"], str(r["local_id"]), float(r["t_ini"]), float(r["t_fin"]), r["id_real"].strip()))
    gt = []
    for o in obs_filas:
        for cam, local, t0, t1, real in segmentos:
            if o["camara"] == cam and str(o["local"]) == local and t0 - 1e-6 <= o["t"] <= t1 + 1e-6:
                gt.append({"camara": cam, "t": o["t"], "caja": o["caja"], "id": real})
                break
    return gt


def salida_desde_replay(sesion):
    ruta = ROOT / "data" / "replays" / sesion / "samples.jsonl"
    filas = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        r = json.loads(linea)
        for cam in r.get("cameras", []):
            for p in cam.get("people", []):
                if p.get("box"):
                    filas.append({"camara": cam["id"], "t": float(r["t"]), "caja": tuple(p["box"]), "id": p["id"], "local": p["id"]})
    return filas


def politica_en_vivo(tienda, indice, observaciones, estado, ticks, info, t=None):
    """Lo que hace live_server con el motor v2: recalcula el vector cada `ticks` muestras (o si el track es nuevo o de baja
    confianza) y, además, en cada muestra mientras el motor pide más vistas de ese track (sin ID público o con pocas vistas).
    Los vectores no recalculados se repiten como `embedding` viejo (`embeddingFresh` False)."""
    for o in observaciones:
        clave = (o["camera"], o["local"])
        vector = o.get("embedding")
        previo = estado.get(clave)
        debido = previo is None or indice - previo[0] >= ticks or (o.get("score") if o.get("score") is not None else 1.) < .5
        if vector is not None and (debido or tienda.necesita_vista(o["camera"], o["local"], t)):
            estado[clave] = (indice, vector)
            o["embeddingFresh"] = True
            info["embeddings"] = info.get("embeddings", 0) + 1
        else:
            o["embedding"], o["embeddingFresh"] = (previo[1] if previo else None), False


def salida_desde_pkl(ruta, ticks=2, ajustes=None, sin_geometria=False, solo_confirmados=False,
                     extra_config=None, desplazar=None, cierre=False, info=None, politica="vivo"):
    """Reproduce las observaciones capturadas con el motor de identidad. Devuelve filas con id global y track local.

    ajustes: sobrescribe umbrales del asociador. sin_geometria: quita los puntos del suelo (el motor cae a visual_temporal).
    politica: "vivo" reproduce lo que hace el servidor (vector cada `ticks` muestras y, además, mientras el track no tiene ID
    público); "todos" entrega un vector fresco en cada muestra. info: diccionario donde se anotan embeddings calculados,
    muestras y milisegundos del motor.
    """
    import copy
    from identity.engine import MotorIdentidadV2
    datos = pickle.loads(Path(ruta).read_bytes())
    tamanos = datos.get("sizes", {})
    cfg = copy.deepcopy(datos["config"])
    cfg["clocksVerified"] = True
    cfg.update(extra_config or {})
    cfg["cameras"] = copy.deepcopy(datos["cameras"])
    ids = {c["id"] for c in cfg["cameras"]}
    for c in cfg["cameras"]:
        c["links"] = [o for o in ids if o != c["id"]]
        if sin_geometria:
            c["pairs"] = []
    obs = copy.deepcopy(datos["obs"])
    for _, observaciones in obs:      # experimento de oráculo: calibraciones coherentes entre cámaras
        for o in observaciones:
            if o.get("point") is not None and o["camera"] in (desplazar or {}):
                dx, dy = desplazar[o["camera"]]
                o["point"] = (o["point"][0] + dx, o["point"][1] + dy)
    info = info if info is not None else {}
    tienda = MotorIdentidadV2(cfg, ajustes=ajustes)
    filas, motor_s, estado = [], 0.0, {}
    for indice, (t, observaciones) in enumerate(obs):
        if politica == "vivo":
            politica_en_vivo(tienda, indice, observaciones, estado, ticks, info, t)
        inicio_motor = time.perf_counter()
        resultado = tienda.update(observaciones, t, tamanos=tamanos)
        motor_s += time.perf_counter() - inicio_motor
        for p in resultado:
            ancho, alto = tamanos.get(p["camera"], (1., 1.))
            x1, y1, x2, y2 = p["box"] if p.get("box") else (None,) * 4
            if x1 is None or (solo_confirmados and not p.get("confirmed", True)):
                continue
            filas.append({"camara": p["camera"], "t": float(t), "caja": (x1 / ancho, y1 / alto, x2 / ancho, y2 / alto),
                          "id": p["id"], "local": p["local"], "confirmado": p.get("confirmed", True), "duplicado": bool(p.get("duplicate", False))})
    if cierre:
        # Reagrupación al cerrar la sesión: IDs finales 1..N; las pasadas breves quedan como no confirmadas.
        finales = tienda.cierre()
        salida = []
        for f in filas:
            n = finales.id_final(f["camara"], f["local"], f["t"])
            if n is None and solo_confirmados:
                continue
            salida.append({**f, "id": f"F{n}" if n is not None else f["id"], "confirmado": n is not None})
        filas = salida
        info["cierre"] = finales.resumen()
    info.update(muestras=len(obs), motor_ms_por_muestra=round(1000 * motor_s / max(len(obs), 1), 2))
    if politica == "todos":
        info["embeddings"] = sum(1 for _, os_ in obs for o in os_ if o.get("embedding") is not None)
    return filas


def _leer_desfases(texto):
    """'B:2.39,0.09;C:0,1' -> {'B': (2.39, 0.09), 'C': (0.0, 1.0)}."""
    if not texto:
        return None
    salida = {}
    for parte in texto.split(";"):
        cam, valores = parte.split(":")
        dx, dy = (float(v) for v in valores.split(","))
        salida[cam] = (dx, dy)
    return salida


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--anotacion")
    ap.add_argument("--etiquetas")
    ap.add_argument("--salida")
    ap.add_argument("--salida-pkl")
    ap.add_argument("--salida-replay")
    ap.add_argument("--iou", type=float, default=.5)
    ap.add_argument("--tol", type=float, default=.11)
    ap.add_argument("--min-frames", type=int, default=3)
    ap.add_argument("--json")
    ap.add_argument("--ticks", type=int, default=2, help="cadencia del vector OSNet, en muestras")
    ap.add_argument("--ajustes", help="JSON con umbrales del asociador v2, por ejemplo {\"threshold\": 0.5}")
    ap.add_argument("--sin-geometria", action="store_true", help="sin homografías (visual_temporal)")
    ap.add_argument("--desplazar", help="experimento de oráculo: suma un desfase a los puntos del plano de una cámara, p. ej. B:2.39,0.09")
    ap.add_argument("--cierre", action="store_true", help="con la reagrupación final de la sesión")
    ap.add_argument("--solo-confirmados", action="store_true", help="descarta las filas con ID provisional")
    args = ap.parse_args()

    if args.salida:
        sistema = leer_csv(args.salida, "id_sistema")
        obs = [{**s, "camara": s["camara"], "local": s["id"]} for s in sistema]
    elif args.salida_pkl:
        info = {}
        obs = salida_desde_pkl(args.salida_pkl, args.ticks, json.loads(args.ajustes) if args.ajustes else None,
                               args.sin_geometria, args.solo_confirmados,
                               desplazar=_leer_desfases(args.desplazar), cierre=args.cierre, info=info)
        print("motor:", info, file=sys.stderr)
        sistema = obs
    elif args.salida_replay:
        obs = salida_desde_replay(args.salida_replay)
        sistema = obs
    else:
        sys.exit("Indica --salida, --salida-pkl o --salida-replay.")
    if args.anotacion:
        gt = leer_csv(args.anotacion, "id_real")
    elif args.etiquetas:
        gt = expandir_etiquetas(args.etiquetas, obs)
    else:
        sys.exit("Indica --anotacion o --etiquetas.")
    if not gt:
        sys.exit("No hay detecciones anotadas: revisa que el archivo tenga id_real rellenado.")
    resultado = metricas(gt, sistema, args.iou, args.tol, args.min_frames)
    for k, v in resultado.items():
        print(f"  {k}: {v}")
    if args.json:
        Path(args.json).write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
