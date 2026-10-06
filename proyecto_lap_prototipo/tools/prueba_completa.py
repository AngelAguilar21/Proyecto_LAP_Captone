"""Prueba de punta a punta en cualquier equipo: servidor, YOLO, ByteTrack, OSNet y asociacion A-B.

Levanta su propio servidor en otro puerto con una configuracion aislada (no toca tus
proyectos), carga config/ejemplos/demo_camaras_A_B.json (videos data/camera_A.mp4 y
data/camera_B.mp4), inicia una sesion unificada y comprueba que:
  1. el servidor responde y la sesion arranca,
  2. se detectan personas en ambas camaras,
  3. OSNet esta activo,
  4. al menos una persona se asocia entre camaras,
  5. la grabacion queda con los IDs finales (reagrupacion al cerrar) y se calculan los insights.

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
    ap.add_argument("--config", type=Path, default=DEMO, help="configuracion a probar (por defecto, la demo A y B)")
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

        config = json.loads(args.config.read_text(encoding="utf-8"))
        call(args.port, "/api/config", config, token)
        call(args.port, "/api/start", {"detector": "yolo", "combined": True, "requireUnified": True,
                                       "inferenceSize": 640, "cameraIds": ["A", "B"]}, token)
        print("   Sesion unificada A+B iniciada; procesando...")

        seen, states, cams_of = Counter(), Counter(), defaultdict(set)
        status, reid, hardware, last_t, identity, session = None, set(), None, -1., None, None
        procesamiento, inferencia = [], []   # ms por muestra del servidor (todo el ciclo) y de la inferencia del detector
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
            identity = state.get("identity") or identity
            session = state.get("session") or session
            if state.get("t", -1) != last_t:
                last_t = state.get("t", -1)
                if state.get("processingMs"):
                    procesamiento.append(state["processingMs"])
                inferencia += [c["inferenceMs"] for c in state.get("cameras", []) if c.get("inferenceMs")]
                for p in state.get("people", []):
                    if not p.get("confirmed", True):
                        continue   # los IDs provisionales no cuentan como personas
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
        if procesamiento:
            import statistics
            ordenado = sorted(procesamiento)
            print(f"   Rendimiento (CPU): ciclo por muestra mediana {statistics.median(procesamiento):.0f} ms, p95 {ordenado[int(.95 * (len(ordenado) - 1))]:.0f} ms "
                  f"({len(procesamiento)} muestras observadas); deteccion por camara mediana {statistics.median(inferencia) if inferencia else float('nan'):.0f} ms")
        print(f"   Personas (IDs): {len(seen)}; vistas en A y B: {len(both)}; estados: {dict(states)}")
        if status == "error" or error:
            failures.append(f"la sesion fallo: {error}")
        if not seen:
            failures.append("no se detecto ninguna persona")
        if "osnet" not in reid:
            failures.append("OSNet inactivo")
        if not both:
            failures.append("ninguna persona se asocio entre A y B (puede requerir mas --seconds)")
        if not identity:
            failures.append("el estado no informa el motor de identidad")
        else:
            print(f"   Identidad: modo {identity.get('mode')}, identidades {identity.get('identidades_globales')}, "
                  f"multicamara {identity.get('identidades_multicamara')}")
        # El cierre termina la ultima muestra y reescribe la grabacion con los IDs finales: se espera a que acabe.
        meta, limite = {}, time.time() + 60
        while time.time() < limite:
            manifiesto = next(iter(sorted((tmp / "data" / "replays").glob("*/manifest.json"), key=lambda q: q.stat().st_mtime)), None)
            try:
                meta = json.loads(manifiesto.read_text(encoding="utf-8")) if manifiesto else {}
            except (OSError, ValueError):
                meta = {}
            if meta.get("identity", {}).get("finalizada"):
                break
            time.sleep(1)
        if not meta.get("identity", {}).get("finalizada"):
            failures.append("la grabacion no quedo con los IDs finales (reagrupacion al cerrar)")
        else:
            print(f"   Cierre: {meta['identity']}")
        # Insights espaciales (exposición, captación, rutas) calculados al cerrar la sesión.
        time.sleep(1)
        archivo = next(iter(sorted((tmp / "data" / "replays").glob("*/insights.json"), key=lambda q: q.stat().st_mtime)), None)
        if archivo is None:
            failures.append("no se calcularon los insights de la sesion (data/replays/<sesion>/insights.json)")
        else:
            insights = json.loads(archivo.read_text(encoding="utf-8"))
            locales = ", ".join(f"{l['nombre']}: exposicion {l['exposicion']}, visitas {l['visitas']}, captacion {l['tasa_captacion']}" for l in insights["locales"])
            print(f"3. Insights: {insights['resumen']['personas']} personas con trayectoria; eventos {insights['resumen']['eventos']}; {locales or 'sin locales'}")
            print(f"   Rutas frecuentes: {len(insights['rutas'])}; flujos origen-destino: {len(insights['origen_destino'])}; congestion: {len(insights['congestion'])}")
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
