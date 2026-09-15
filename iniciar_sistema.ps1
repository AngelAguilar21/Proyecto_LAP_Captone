param([int]$Port = 8765)
# Usa el entorno compartido de conteo y seguimiento, sin depender del Python global.
& (Join-Path $PSScriptRoot 'iniciar_conteo.ps1') -Port $Port
