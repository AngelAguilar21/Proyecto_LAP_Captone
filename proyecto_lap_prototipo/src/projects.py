"""Proyectos guardados: cada uno es un archivo de configuración independiente.

Un proyecto tiene exactamente la forma del config de siempre (plano, cámaras,
zonas, reglas), así que el resto del sistema no distingue entre trabajar con
proyectos o con un archivo suelto. El índice solo guarda cuál está activo y los
datos mínimos para listarlos sin abrir cada archivo.
"""
import json
import os
import secrets
import time
from pathlib import Path


def directory(root):
    return root / "config" / "projects"


def index_path(root):
    return directory(root) / "index.json"


def project_path(root, pid):
    if not isinstance(pid, str) or not pid or any(c in pid for c in "/\\.:"):
        raise ValueError("Identificador de proyecto inválido.")
    return directory(root) / f"{pid}.json"


def atomic_write(path, text, attempts=6):
    """Escribe y reemplaza reintentando: en carpetas sincronizadas (OneDrive,
    Drive) el proceso de sincronización sostiene el archivo unos milisegundos y
    os.replace falla con «acceso denegado» sin que nada esté mal."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    last = None
    for attempt in range(attempts):
        try:
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, path)
            return
        except PermissionError as exc:
            last = exc
            time.sleep(0.12 * (attempt + 1))
    raise OSError(f"No se pudo guardar {path.name}. Ciérralo en otras aplicaciones e inténtalo de nuevo. ({last})")


def read_index(root):
    path = index_path(root)
    if not path.exists():
        return None
    try:
        index = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return index if isinstance(index.get("projects"), list) and index["projects"] else None


def write_index(root, index):
    atomic_write(index_path(root), json.dumps(index, ensure_ascii=False, indent=2))


def ensure_index(root, legacy_path, name="Proyecto principal"):
    """Devuelve el índice, creándolo la primera vez.

    Si existe una configuración suelta anterior (live.local.json) se convierte en
    el primer proyecto, para no perder planos ni cámaras ya configurados.
    """
    index = read_index(root)
    if index:
        return index
    pid = "p-" + secrets.token_hex(4)
    directory(root).mkdir(parents=True, exist_ok=True)
    target = project_path(root, pid)
    if Path(legacy_path).exists():
        target.write_text(Path(legacy_path).read_text(encoding="utf-8"), encoding="utf-8")
    now = time.time()
    index = {"active": pid, "projects": [{"id": pid, "name": name, "created": now, "updated": now}]}
    write_index(root, index)
    return index


def entry(index, pid):
    return next((p for p in index["projects"] if p["id"] == pid), None)


def check_name(index, name, ignore=None):
    """Cada proyecto es un espacio distinto, así que dos no pueden llamarse igual.

    Con nombres repetidos la lista deja de servir para elegir: no hay forma de
    saber cuál plano y cuáles cámaras hay detrás de cada uno. Se compara sin
    distinguir mayúsculas ni espacios de sobra, que es como los lee una persona.
    """
    clean = " ".join(name.split())
    if not clean:
        raise ValueError("Escribe un nombre para el proyecto.")
    if len(clean) > 80:
        raise ValueError("El nombre no puede pasar de 80 caracteres.")
    taken = next((p for p in index["projects"]
                  if p["id"] != ignore and " ".join(str(p.get("name", "")).split()).casefold() == clean.casefold()), None)
    if taken:
        raise ValueError(f"Ya existe un proyecto llamado «{taken['name']}». Usa otro nombre para distinguirlos.")
    return clean


def create(root, name, config):
    index = read_index(root) or {"active": None, "projects": []}
    name = check_name(index, name)
    pid = "p-" + secrets.token_hex(4)
    atomic_write(project_path(root, pid), json.dumps(config, ensure_ascii=False, indent=2))
    now = time.time()
    index["projects"].append({"id": pid, "name": name, "created": now, "updated": now})
    index["active"] = pid
    write_index(root, index)
    return pid


def rename(root, pid, name):
    index = read_index(root)
    if not index or not entry(index, pid):
        raise ValueError("El proyecto no existe.")
    entry(index, pid)["name"] = check_name(index, name, ignore=pid)
    entry(index, pid)["updated"] = time.time()
    write_index(root, index)


def activate(root, pid):
    index = read_index(root)
    if not index or not entry(index, pid):
        raise ValueError("El proyecto no existe.")
    if index["active"] != pid:
        index["active"] = pid
        write_index(root, index)
    return project_path(root, pid)


def remove(root, pid):
    """Borra un proyecto y devuelve el que queda activo."""
    index = read_index(root)
    if not index or not entry(index, pid):
        raise ValueError("El proyecto no existe.")
    if len(index["projects"]) == 1:
        raise ValueError("No puedes borrar el único proyecto. Crea otro antes.")
    index["projects"] = [p for p in index["projects"] if p["id"] != pid]
    if index["active"] == pid:
        index["active"] = index["projects"][0]["id"]
    write_index(root, index)
    path = project_path(root, pid)
    if path.exists():
        path.unlink()
    return index["active"]


def touch(root, pid):
    """Marca el proyecto como editado recientemente."""
    index = read_index(root)
    if not index or not entry(index, pid):
        return
    entry(index, pid)["updated"] = time.time()
    write_index(root, index)


def summary(root, config):
    """Datos que se muestran en la lista de proyectos sin abrir el editor."""
    cameras = config.get("cameras", [])
    plans = config.get("plans") or {}
    return {
        "airport": config.get("airport", ""),
        "floor": config.get("floor", ""),
        "cameras": len(cameras),
        "plans": max(1, len(plans)),
        "setupComplete": bool(config.get("setupComplete")),
    }


def listing(root, active_config=None, active_id=None):
    index = read_index(root)
    if not index:
        return {"active": None, "projects": []}
    items = []
    for item in index["projects"]:
        config = active_config if item["id"] == active_id else None
        if config is None:
            try:
                config = json.loads(project_path(root, item["id"]).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                config = {}
        items.append({**item, **summary(root, config)})
    return {"active": index["active"], "projects": items}
