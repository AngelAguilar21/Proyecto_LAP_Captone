param([int]$Port = 8765)
# Usa el entorno del proyecto (.venv), sin depender del Python global.
$ErrorActionPreference = 'Stop'
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    throw 'Falta .venv. Ejecuta primero preparar_sistema (ver INSTALACION.md).'
}
Write-Host "AeroTrack (seguimiento y reidentificación): http://127.0.0.1:$Port/?view=overview"
& $projectPython (Join-Path $PSScriptRoot 'proyecto_lap_prototipo\live_server.py') --port $Port
