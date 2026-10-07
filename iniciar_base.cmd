@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe proyecto_lap_prototipo\tools\preparar_base.py
if errorlevel 1 exit /b 1
echo Base de datos lista. Ahora ejecuta iniciar_sistema.cmd.
