"""Local automation preferences. Missing configuration disables every task."""
import copy
import json
import re

from projects import atomic_write


DEFAULTS = {
    "timezone": "America/Lima",
    "reports": {"enabled": False, "time": "18:00"},
    "backups": {"enabled": False, "time": "02:00", "retention": 7},
    "escalation": {"enabled": False, "delay_minutes": 15, "recipients": []},
    "cleanup": {"enabled": False, "retention_days": 30},
}


def validate(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULTS):
        raise ValueError("Invalid automation settings")
    result = copy.deepcopy(DEFAULTS)
    if value.get("timezone", "America/Lima") != "America/Lima":
        raise ValueError("Only America/Lima is supported")
    for task in ("reports", "backups", "escalation", "cleanup"):
        options = value.get(task, {})
        if not isinstance(options, dict) or set(options) - set(result[task]):
            raise ValueError("Invalid task settings")
        result[task].update(options)
        if not isinstance(result[task]["enabled"], bool):
            raise ValueError("enabled must be boolean")
    for task in ("reports", "backups"):
        hour = result[task]["time"]
        if not isinstance(hour, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", hour):
            raise ValueError("Invalid daily time")
    for task, key in (("backups", "retention"), ("escalation", "delay_minutes"),
                      ("cleanup", "retention_days")):
        number = result[task][key]
        if type(number) is not int or not 1 <= number <= 3650:
            raise ValueError("Invalid positive retention/delay")
    recipients = result["escalation"]["recipients"]
    if (not isinstance(recipients, list) or len(recipients) > 20 or
            any(not isinstance(r, str) or "@" not in r or len(r) > 200 for r in recipients)):
        raise ValueError("Invalid escalation recipients")
    if result["escalation"]["enabled"] and not recipients:
        raise ValueError("Escalation needs recipients")
    return result


def load(root):
    path = root / "automation.local.json"
    return validate(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else validate({})


def save(root, value):
    result = validate(value)
    atomic_write(root / "automation.local.json", json.dumps(result, indent=2))
    return result
