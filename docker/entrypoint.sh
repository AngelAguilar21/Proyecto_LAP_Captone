#!/bin/sh
set -e
cd /app/proyecto_lap_prototipo

# Instalación nueva: mapas del LAP y configuración base. Si ya existe (volumen con datos), se conserva.
python setup_workspace.py

# Cuenta inicial sin pasar por la pantalla de primer ingreso (que cualquiera que llegue primero podría usar
# al exponer el servidor). Solo se crea si todavía no hay usuarios.
if [ -n "$AEROTRACK_ADMIN_USER" ] && [ -n "$AEROTRACK_ADMIN_PASSWORD" ]; then
python - <<'PY'
import os, sys
sys.path.insert(0, "src")
import auth
if not auth.hay_usuarios("config"):
    auth.crear("config", os.environ["AEROTRACK_ADMIN_USER"], os.environ["AEROTRACK_ADMIN_PASSWORD"], "operador")
    print("Usuario operador inicial creado.", flush=True)
PY
fi

# El propio servidor detecta la GPU y escribe en el registro qué perfil eligió.
exec python live_server.py --host "$AEROTRACK_HOST" --port "$AEROTRACK_PORT"
