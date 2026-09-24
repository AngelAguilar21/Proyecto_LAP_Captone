"""Aviso por correo al personal de seguridad cuando salta una alerta.

La contraseña vive en config/correo.local.json, fuera del archivo del proyecto y
fuera del control de versiones: los proyectos se copian y se comparten, las
credenciales no. La API nunca devuelve la contraseña, solo si está configurada.

Gmail no acepta la contraseña normal de la cuenta: hay que generar una
«contraseña de aplicación» con la verificación en dos pasos activada.
"""
import json
import os
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage
from pathlib import Path

FILE = "correo.local.json"
COOLDOWN = 120.0  # segundos mínimos entre correos de la misma zona


def path_for(settings_root):
    return Path(settings_root) / FILE


def load(settings_root):
    try:
        data = json.loads(path_for(settings_root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def public(settings_root):
    """Lo que se puede mostrar en la interfaz: todo menos la contraseña."""
    data = load(settings_root)
    return {
        "enabled": bool(data.get("enabled")),
        "host": data.get("host", "smtp.gmail.com"),
        "port": int(data.get("port", 465)),
        "user": data.get("user", ""),
        "recipients": data.get("recipients", []),
        "configured": bool(data.get("password")),
    }


def save(settings_root, changes):
    data = load(settings_root)
    if "password" in changes:
        password = changes.pop("password")
        if password:  # una cadena vacía significa «no la cambies»
            data["password"] = password
    for key in ("enabled", "host", "user"):
        if key in changes:
            data[key] = changes[key]
    if "port" in changes:
        port = changes["port"]
        if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
            raise ValueError("Puerto de correo inválido.")
        data["port"] = port
    if "recipients" in changes:
        people = changes["recipients"]
        if not isinstance(people, list) or len(people) > 20:
            raise ValueError("Indica hasta 20 correos de destino.")
        for address in people:
            if not isinstance(address, str) or "@" not in address or len(address) > 200:
                raise ValueError(f"Correo de destino inválido: {address}")
        data["recipients"] = people
    if data.get("enabled") and not data.get("password"):
        raise ValueError("Falta la contraseña de aplicación del correo remitente.")
    if data.get("enabled") and not data.get("recipients"):
        raise ValueError("Añade al menos un correo de destino.")
    target = path_for(settings_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, target)
    return public(settings_root)


def _send(data, subject, body):
    message = EmailMessage()
    message["From"] = data.get("user", "")
    message["To"] = ", ".join(data.get("recipients", []))
    message["Subject"] = subject
    message.set_content(body)
    port = int(data.get("port", 465))
    host = data.get("host", "smtp.gmail.com")
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=20, context=context) as server:
            server.login(data["user"], data["password"])
            server.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.starttls(context=context)
            server.login(data["user"], data["password"])
            server.send_message(message)


class Mailer:
    """Envía en segundo plano y no repite el mismo aviso una y otra vez."""

    def __init__(self, settings_root):
        self.settings_root = settings_root
        self.last = {}
        self.error = None
        self.sent = 0

    def ready(self):
        data = load(self.settings_root)
        return bool(data.get("enabled") and data.get("password") and data.get("recipients"))

    def send(self, subject, body, key=None, blocking=False):
        """key agrupa avisos parecidos para no repetirlos dentro del enfriamiento."""
        data = load(self.settings_root)
        if not (data.get("enabled") and data.get("password") and data.get("recipients")):
            return False
        now = time.time()
        if key and now - self.last.get(key, 0) < COOLDOWN:
            return False
        if key:
            self.last[key] = now

        def run():
            try:
                _send(data, subject, body)
                self.sent += 1
                self.error = None
            except Exception as exc:  # el correo nunca debe tumbar la sesión
                self.error = str(exc)

        if blocking:
            run()
            if self.error:
                raise ValueError(self.error)
            return True
        threading.Thread(target=run, daemon=True).start()
        return True
