param([int]$Port = 8765)
# Usa el entorno del proyecto (.venv), sin depender del Python global.
$ErrorActionPreference = 'Stop'
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    throw 'Falta .venv. Ejecuta primero preparar_sistema (ver INSTALACION.md).'
}

# Si AeroTrack ya está levantado, no intentes abrir un segundo servidor en el
# mismo puerto. Esto evita el error de Windows "solo se permite un uso de cada
# dirección de socket" al volver a ejecutar el lanzador.
$healthUrl = "http://127.0.0.1:$Port/api/state"
try {
    $health = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
    if ($health.StatusCode -eq 200) {
        Write-Host "AeroTrack ya está levantado en http://127.0.0.1:$Port"
        exit 0
    }
} catch {
    $ocupado = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($ocupado) {
        throw "El puerto $Port está ocupado por otra aplicación. Cierra esa aplicación o inicia AeroTrack con -Port otro_puerto."
    }
}

if (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'proyecto_lap_prototipo\config\storage.local.json')) {
    Write-Host 'Comprobando PostgreSQL/PostGIS. Docker Desktop debe estar abierto.'
    & $projectPython (Join-Path $PSScriptRoot 'proyecto_lap_prototipo\tools\preparar_base.py')
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo iniciar la base. Abre Docker Desktop y vuelve a ejecutar iniciar_sistema.cmd.' }
}
Write-Host "AeroTrack (seguimiento y reidentificación): http://127.0.0.1:$Port/?view=overview"
& $projectPython (Join-Path $PSScriptRoot 'proyecto_lap_prototipo\live_server.py') --port $Port
