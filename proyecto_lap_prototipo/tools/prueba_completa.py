"""Prueba de punta a punta en cualquier equipo: servidor, YOLO, ByteTrack, OSNet y asociacion A-B.

Levanta su propio servidor en otro puerto con una configuracion aislada (no toca tus
proyectos), carga config/ejemplos/demo_camaras_A_B.json (videos data/camera_A.mp4 y
data/camera_B.mp4), inicia una sesion unificada y comprueba que:
  1. el servidor responde y la sesion arranca,
  2. se detectan personas en ambas camaras,
  3. OSNet esta activo (si no, avisa: se usa la firma de color),
  4. al menos una persona se asocia entre camaras.

Uso (desde proyecto_lap_prototipo, con el entorno del proyecto):
    python tools/prueba_completa.py [--seconds 90] [--port 8799]
Termina con codigo 0 si todo paso, 1 si algo fallo.
"""
import argparse
import json
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "config" / "ejemplos" / "demo_camaras_A_B.json"


def call(port, path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-LAP-Token"] = token
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, headers=headers,
                                     method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"{path} respondio {exc.code}: {exc.read().decode(errors='replace')[:300]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=90., help="tiempo maximo de espera de la sesion")
    ap.add_argument("--port", type=int, default=8799)
    args = ap.parse_args()

    for video in ("camera_A.mp4", "camera_B.mp4"):
        if not (ROOT / "data" / video).is_file():
            sys.exit(f"Falta data/{video}.")
    if not (ROOT / "models" / "yolo11n.pt").is_file():
        sys.exit("Falta models/yolo11n.pt: ejecuta setup_objects.py --download o tools/preparar_hardware.py --download.")

    tmp = Path(tempfile.mkdtemp(prefix="aerotrack_prueba_"))
    server = subprocess.Popen([sys.executable, "-u", str(ROOT / "live_server.py"), "--port", str(args.port),
                               "--config-path", str(tmp / "live.json")], cwd=ROOT,
                              stdout=(tmp / "server.log").open("w"), stderr=subprocess.STDOUT)
    failures = []
    try:
        for _ in range(60):
            try:
                token = call(args.port, "/api/config")["token"]
                break
            except (OSError, SystemExit):
                if server.poll() is not None:
                    sys.exit(f"El servidor no arranco. Revisa {tmp / 'server.log'}")
                time.sleep(1)
        else:
            sys.exit("El servidor no respondio en 60 s.")
        print("1. Servidor activo.")

        call(args.port, "/api/config", json.loads(DEMO.read_text(encoding="utf-8")), token)
        call(args.port, "/api/start", {"detector": "hybrid", "combined": True, "requireUnified": True,
                                       "inferenceSize": 640, "cameraIds": ["A", "B"]}, token)
        print("   Sesion unificada A+B iniciada; procesando...")

        seen, states, cams_of = Counter(), Counter(), defaultdict(set)
        status, reid, hardware, last_t = None, set(), None, -1.
        deadline = time.time() + args.seconds
        while time.time() < deadline:
            state = call(args.port, "/api/state")
            status = state.get("status")
            if status not in ("starting", "running"):
                break
            for cam in state.get("cameras", []):
                if cam.get("reid"):
                    reid.add(cam["reid"])
                hardware = cam.get("hardware") or hardware
            if state.get("t", -1) != last_t:
                last_t = state.get("t", -1)
                for p in state.get("people", []):
                    seen[p["id"]] += 1
                    states[p["association"]] += 1
                    cams_of[p["id"]].add(p["camera"])
            time.sleep(.5)
        error = call(args.port, "/api/state").get("error")
        try:
            call(args.port, "/api/stop", {}, token)
        except SystemExit:
            pass

        both = [pid for pid, cams in cams_of.items() if len(cams) > 1]
        print(f"2. Estado final: {status} (error: {error}); tiempo de fuente procesado: {last_t:.1f} s")
        print(f"   Hardware: {hardware}")
        print(f"   Personas (IDs): {len(seen)}; vistas en A y B: {len(both)}; estados: {dict(states)}")
        if status == "error" or error:
            failures.append(f"la sesion fallo: {error}")
        if not seen:
            failures.append("no se detecto ninguna persona")
        if "osnet" not in reid:
            print("   AVISO: OSNet no esta activo (modelo o onnxruntime ausentes); se uso la firma de color.")
            failures.append("OSNet inactivo")
        if not both:
            failures.append("ninguna persona se asocio entre A y B (puede requerir mas --seconds)")
    finally:
        server.terminate()
        try:
            server.wait(10)
        except subprocess.TimeoutExpired:
            server.kill()
    if failures:
        print("\nFALLO:", "; ".join(failures))
        sys.exit(1)
    print("\nPRUEBA COMPLETA OK: servidor, deteccion, OSNet y asociacion entre camaras funcionan.")


if __name__ == "__main__":
    main()
