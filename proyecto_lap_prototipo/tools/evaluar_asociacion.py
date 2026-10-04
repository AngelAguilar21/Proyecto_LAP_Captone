"""Evalúa IdentityStore sobre observaciones capturadas (tools/capturar_observaciones.py).

Sin verdad de campo, mide señales objetivas de estabilidad:
- cambios de ID: veces que un track local (cámara, id local) cambia de ID global;
- tiempo hasta el ID definitivo: desde que un track aparece hasta que ya lleva el ID
  con el que termina (mide el retraso inicial de la asociación);
- fusiones dudosas: tracks de cámaras distintas unidos pese a estar lejos en el plano.

Uso: python tools/evaluar_asociacion.py data/salida_reid/obs_p-7fc87baa.pkl [--core ruta/live_core.py]
"""
import argparse
import copy
import importlib.util
import math
import pickle
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def load_core(path):
    spec = importlib.util.spec_from_file_location("live_core_eval", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluate(core, data, use_embeddings=True):
    cfg = copy.deepcopy(data["config"])
    cfg["clocksVerified"] = True
    cfg["cameras"] = copy.deepcopy(data["cameras"])
    ids = {c["id"] for c in cfg["cameras"]}
    for c in cfg["cameras"]:
        c["links"] = [o for o in ids if o != c["id"]]
    store = core.IdentityStore(cfg)
    gids = defaultdict(list)       # (cam, local) -> [(t, gid)]
    points = defaultdict(list)     # (cam, local) -> [(t, point)]
    states = Counter()
    for t, rows in data["obs"]:
        rows = [r if use_embeddings else {**r, "embedding": None} for r in rows]
        for p in store.update(copy.deepcopy(rows), t):
            key = (p["camera"], p["local"])
            gids[key].append((t, p["id"]))
            if p.get("point"):
                points[key].append((t, p["point"]))
            states[p["association"]] += 1
    switches = sum(sum(1 for a, b in zip(seq, seq[1:]) if a[1] != b[1]) for seq in gids.values())
    delays = []
    for seq in gids.values():
        final = seq[-1][1]
        stable_from = next(t for i, (t, _) in enumerate(seq) if all(g == final for _, g in seq[i:]))
        delays.append(stable_from - seq[0][0])
    by_gid = defaultdict(set)
    for key, seq in gids.items():
        for _, g in seq:
            by_gid[g].add(key)
    doubtful = 0
    for g, keys in by_gid.items():
        cams = defaultdict(list)
        for key in keys:
            cams[key[0]].append(key)
        if len(cams) < 2:
            continue
        first, second = sorted(cams)[:2]
        for a in cams[first]:
            for b in cams[second]:
                pa, pb = dict(points[a]), dict(points[b])
                common = [t for t in pa if t in pb]
                if common and sum(math.dist(pa[t], pb[t]) for t in common) / len(common) > 1.5 * cfg.get("matchDistance", 1):
                    doubtful += 1
    all_gids = {g for seq in gids.values() for _, g in seq}
    cross = sum(1 for g, keys in by_gid.items() if len({k[0] for k in keys}) > 1)
    return {"ids_globales": len(all_gids), "ids_en_ambas_camaras": cross, "tracks_locales": len(gids),
            "cambios_de_id": switches,
            "retraso_medio_s": round(sum(delays) / max(len(delays), 1), 2), "retraso_max_s": round(max(delays, default=0), 2),
            "fusiones_dudosas": doubtful, "estados": dict(states)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pkl")
    ap.add_argument("--core", default=str(ROOT / "src" / "live_core.py"))
    ap.add_argument("--no-embeddings", action="store_true")
    args = ap.parse_args()
    data = pickle.loads(Path(args.pkl).read_bytes())
    print(Path(args.core).name, "| embeddings:", not args.no_embeddings)
    for k, v in evaluate(load_core(args.core), data, not args.no_embeddings).items():
        print(f"  {k}: {v}")
