param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    throw 'Falta .venv. Sigue proyecto_lap_prototipo/docs/GUIA_CONTEO.md para preparar el entorno.'
}
Write-Host "AeroTrack (conteo y seguimiento): http://127.0.0.1:$Port/?view=overview"
& $projectPython (Join-Path $PSScriptRoot 'proyecto_lap_prototipo\live_server.py') --port $Port
