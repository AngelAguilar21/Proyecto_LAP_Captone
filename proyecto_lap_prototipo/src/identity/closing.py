"""Cierre de sesión: reescribe la grabación (replay) con los IDs finales reagrupados, de 1 a N por orden de aparición.

En vivo una persona puede tener un ID provisional ("T00007") y cambiar al confirmarse o al unirse con otro tramo.
Al cerrar, `MotorIdentidadV2.cierre()` decide la identidad definitiva de cada tracklet y aquí se aplica a cada muestra
guardada: las personas contadas pasan a "P00001".. y las pasadas breves quedan con su ID provisional y `confirmed: false`.
Solo cambia el campo `id`; no se guardan vectores ni imágenes.
"""
import json
from pathlib import Path


def reescribir_replay(directorio, cierre):
    """Aplica los IDs finales a samples.jsonl de una sesión cerrada y anota el resumen en manifest.json.

    Las muestras sin el campo `local` (grabaciones anteriores) se dejan igual. Devuelve cuántas personas se renumeraron.
    """
    directorio = Path(directorio)
    muestras = directorio / "samples.jsonl"
    temporal = directorio / "samples.jsonl.tmp"
    cambiadas = 0
    with muestras.open(encoding="utf-8") as origen, temporal.open("w", encoding="utf-8") as destino:
        for linea in origen:
            try:
                muestra = json.loads(linea)
            except ValueError:
                destino.write(linea)
                continue
            for camara in muestra.get("cameras", []):
                for persona in camara.get("people", []):
                    if "local" not in persona or persona.get('association') == 'manual' or persona.get('id', '').startswith(('M', 'U')):
                        continue
                    final = cierre.id_final(camara["id"], persona["local"], muestra["t"])
                    if final is not None:
                        persona["id"], persona["confirmed"] = f"P{final:05d}", True
                        cambiadas += 1
                    else:
                        persona["confirmed"] = False
            destino.write(json.dumps(muestra, ensure_ascii=False, allow_nan=False) + "\n")
    temporal.replace(muestras)
    manifiesto = directorio / "manifest.json"
    meta = json.loads(manifiesto.read_text(encoding="utf-8"))
    meta["identity"] = {"engine": "reid_v2", "finalizada": True, **cierre.resumen()}
    temporal_meta = manifiesto.with_suffix(".tmp")
    temporal_meta.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    temporal_meta.replace(manifiesto)
    return cambiadas
