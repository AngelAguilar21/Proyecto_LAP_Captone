"""Usuarios y sesiones: operador y administrador.

Dos roles con una diferencia concreta:
  - operador: configura el sistema (plano, cámaras, calibración, proyectos).
  - administrador: ve todo lo demás y ajusta los umbrales de alerta, pero no
    entra a la configuración para no tocar por error una calibración.

Las contraseñas nunca se guardan en claro ni se devuelven por la API: se
guarda un hash PBKDF2 con sal propia por usuario. El archivo vive en
config/usuarios.local.json, fuera del control de versiones, porque los
proyectos se copian y se comparten y las credenciales no.
"""
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

FILE = "usuarios.local.json"
ROLES = ("operador", "administrador")
ITERACIONES = 240_000
DURACION_SESION = 12 * 3600


def path_for(settings_root):
    return Path(settings_root) / FILE


def _read(settings_root):
    try:
        data = json.loads(path_for(settings_root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"usuarios": []}
    return data if isinstance(data.get("usuarios"), list) else {"usuarios": []}


def _write(settings_root, data):
    path = path_for(settings_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _hash(clave, sal):
    return hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), bytes.fromhex(sal), ITERACIONES).hex()


def hay_usuarios(settings_root):
    return bool(_read(settings_root)["usuarios"])


def listar(settings_root):
    """Nunca devuelve hash ni sal: solo lo que la interfaz necesita mostrar."""
    return [{"usuario": u["usuario"], "rol": u["rol"], "creado": u.get("creado")}
            for u in _read(settings_root)["usuarios"]]


def crear(settings_root, usuario, clave, rol):
    if not isinstance(usuario, str) or not usuario.strip():
        raise ValueError("Escribe un nombre de usuario.")
    if rol not in ROLES:
        raise ValueError("Rol inválido.")
    if not isinstance(clave, str) or len(clave) < 6:
        raise ValueError("La contraseña debe tener al menos 6 caracteres.")
    usuario = usuario.strip().lower()
    data = _read(settings_root)
    if any(u["usuario"] == usuario for u in data["usuarios"]):
        raise ValueError("Ya existe un usuario con ese nombre.")
    sal = secrets.token_hex(16)
    data["usuarios"].append({"usuario": usuario, "rol": rol, "sal": sal,
                             "hash": _hash(clave, sal), "creado": time.time()})
    _write(settings_root, data)
    return listar(settings_root)


def eliminar(settings_root, usuario):
    data = _read(settings_root)
    restantes = [u for u in data["usuarios"] if u["usuario"] != usuario]
    if len(restantes) == len(data["usuarios"]):
        raise ValueError("El usuario no existe.")
    if not any(u["rol"] == "operador" for u in restantes):
        raise ValueError("Debe quedar al menos un operador que pueda configurar el sistema.")
    data["usuarios"] = restantes
    _write(settings_root, data)
    return listar(settings_root)


def cambiar_clave(settings_root, usuario, clave):
    if not isinstance(clave, str) or len(clave) < 6:
        raise ValueError("La contraseña debe tener al menos 6 caracteres.")
    data = _read(settings_root)
    for registro in data["usuarios"]:
        if registro["usuario"] == usuario:
            registro["sal"] = secrets.token_hex(16)
            registro["hash"] = _hash(clave, registro["sal"])
            _write(settings_root, data)
            return True
    raise ValueError("El usuario no existe.")


def verificar(settings_root, usuario, clave):
    """Devuelve el rol si las credenciales son correctas, o None."""
    if not isinstance(usuario, str) or not isinstance(clave, str):
        return None
    for registro in _read(settings_root)["usuarios"]:
        if registro["usuario"] == usuario.strip().lower():
            # compare_digest evita filtrar por tiempo de respuesta si el hash
            # coincide parcialmente.
            if hmac.compare_digest(_hash(clave, registro["sal"]), registro["hash"]):
                return registro["rol"]
            return None
    return None


class Sesiones:
    """Sesiones activas. Con `archivo` sobreviven a un reinicio del servidor; se guarda el resumen SHA-256 del
    token, nunca el token, así que el archivo no sirve para entrar."""

    def __init__(self, archivo=None):
        self.archivo = Path(archivo) if archivo else None
        self.activas = {}
        if self.archivo:
            try:
                guardadas = json.loads(self.archivo.read_text(encoding="utf-8"))
                ahora = time.time()
                self.activas = {k: v for k, v in guardadas.items() if isinstance(v, dict) and v.get("expira", 0) > ahora}
            except (OSError, ValueError, AttributeError):
                self.activas = {}

    @staticmethod
    def _clave(token):
        return hashlib.sha256((token or "").encode("utf-8")).hexdigest()

    def _guardar(self):
        if not self.archivo:
            return
        try:
            self.archivo.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.archivo.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.activas), encoding="utf-8")
            os.replace(tmp, self.archivo)
        except OSError:
            pass  # sin disco la sesión sigue valiendo mientras el servidor no se reinicie

    def abrir(self, usuario, rol):
        token = secrets.token_urlsafe(32)
        self.activas[self._clave(token)] = {"usuario": usuario, "rol": rol, "expira": time.time() + DURACION_SESION}
        self._guardar()
        return token

    def leer(self, token):
        clave = self._clave(token)
        sesion = self.activas.get(clave)
        if not sesion:
            return None
        if sesion["expira"] < time.time():
            self.activas.pop(clave, None)
            self._guardar()
            return None
        return sesion

    def cerrar(self, token):
        self.activas.pop(self._clave(token), None)
        self._guardar()

    def cerrar_usuario(self, usuario):
        for clave in [k for k, s in self.activas.items() if s["usuario"] == usuario]:
            self.activas.pop(clave, None)
        self._guardar()
