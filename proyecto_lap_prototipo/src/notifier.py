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


class DeliveryError(ValueError):
    """Safe delivery outcome: uncertain errors must never be auto-retried."""

    def __init__(self, reason, uncertain=True):
        super().__init__(reason)
        self.uncertain = uncertain


def delivery_error(exc):
    if isinstance(exc, DeliveryError):
        return exc
    refused = isinstance(exc, (smtplib.SMTPAuthenticationError,
                              smtplib.SMTPSenderRefused,
                              smtplib.SMTPRecipientsRefused,
                              smtplib.SMTPDataError))
    # Do not persist server messages: they may contain addresses or credentials.
    return DeliveryError(type(exc).__name__, uncertain=not refused)


def _send(data, subject, body):
    message = EmailMessage()
    message["From"] = data.get("user", "")
    message["To"] = ", ".join(data.get("recipients", []))
    message["Subject"] = subject
    message.set_content(body)
    port = int(data.get("port", 465))
    host = data.get("host", "smtp.gmail.com")
    context = ssl.create_default_context()
    attempted = confirmed = False
    try:
        connection = (smtplib.SMTP_SSL(host, port, timeout=20, context=context)
                      if port == 465 else smtplib.SMTP(host, port, timeout=20))
        with connection as server:
            if port != 465:
                server.starttls(context=context)
            server.login(data["user"], data["password"])
            attempted = True
            refused = server.send_message(message)
            if refused:
                # Some recipients may already have accepted the message.
                raise DeliveryError("partial_recipient_refusal", uncertain=True)
            confirmed = True
    except Exception as exc:
        if confirmed:
            return  # A QUIT failure cannot undo confirmed DATA acceptance.
        error = delivery_error(exc)
        if not attempted:
            error = DeliveryError(type(exc).__name__, uncertain=False)
        raise error from exc


class Mailer:
    """Envía en segundo plano y no repite el mismo aviso una y otra vez."""

    def __init__(self, settings_root):
        self.settings_root = settings_root
        self.last = {}
        self.error = None
        self.sent = 0
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.workers = set()

    def _configuration(self, recipients):
        data = load(self.settings_root)
        if recipients is not None:
            if (not isinstance(recipients, list) or not 1 <= len(recipients) <= 20 or
                    any(not isinstance(r, str) or "@" not in r or len(r) > 200 for r in recipients)):
                raise ValueError("Destinatarios alternativos inválidos.")
            data["recipients"] = list(recipients)
        return data

    def ready(self, recipients=None):
        data = self._configuration(recipients)
        return bool(data.get("enabled") and data.get("password") and data.get("recipients"))

    def send(self, subject, body, key=None, blocking=False, recipients=None):
        """key agrupa avisos parecidos para no repetirlos dentro del enfriamiento."""
        data = self._configuration(recipients)
        if not (data.get("enabled") and data.get("password") and data.get("recipients")):
            return False
        with self.lock:
            if self.stop_event.is_set():
                return False
            now = time.time()
            if key and key in self.last and now - self.last[key] < COOLDOWN:
                return False
            if key:
                self.last[key] = now

        def run():
            try:
                _send(data, subject, body)
                with self.lock:
                    self.sent += 1
                    self.error = None
                return None
            except Exception as exc:  # el correo nunca debe tumbar la sesión
                error = delivery_error(exc)
                with self.lock:
                    self.error = str(error)
                return error
            finally:
                with self.lock:
                    self.workers.discard(threading.current_thread())

        if blocking:
            with self.lock:
                if self.stop_event.is_set():
                    return False
                self.workers.add(threading.current_thread())
            error = run()
            if error is not None:
                raise error
            return True
        with self.lock:
            if self.stop_event.is_set():
                return False
            worker = threading.Thread(target=run, name="mailer", daemon=True)
            self.workers.add(worker)
            try:
                worker.start()
            except Exception:
                self.workers.discard(worker)
                raise
        return True

    def has_writers(self):
        return bool(self.workers)
