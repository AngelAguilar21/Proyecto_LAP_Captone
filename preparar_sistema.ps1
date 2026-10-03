param()
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
function Run-Step([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Falló: $Program $($Arguments -join ' ')" }
}
foreach ($command in @('git', 'npm.cmd')) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) { throw "Instala $command antes de continuar. Consulta INSTALACION.md." }
}
Run-Step 'git' @('submodule','update','--init','--recursive')
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    # Lanzador py si existe; si no, un Python 3.12 del PATH (python3.12 o python).
    if (Get-Command py -ErrorAction SilentlyContinue) { Run-Step 'py' @('-3.12','-m','venv','.venv') }
    else {
        $found = @('python3.12','python') | Where-Object { Get-Command $_ -ErrorAction SilentlyContinue } | Select-Object -First 1
        if (-not $found) { throw 'Instala Python 3.12 (64 bits) antes de continuar. Consulta INSTALACION.md.' }
        Run-Step $found @('-m','venv','.venv')
    }
}
Run-Step $python @('-c','import sys; assert sys.version_info[:2] == (3,12), "Se requiere Python 3.12"')
Run-Step $python @('-m','pip','install','--no-compile','-r','requirements.txt')
Run-Step $python @('-m','pip','check')
Run-Step $python @('proyecto_lap_prototipo/setup_counting.py')
Run-Step $python @('proyecto_lap_prototipo/setup_objects.py','--download')
Run-Step $python @('proyecto_lap_prototipo/setup_workspace.py')
Push-Location 'proyecto_lap_prototipo/dashboard'
try {
    Run-Step 'npm.cmd' @('ci')
    Run-Step 'npm.cmd' @('run','build')
} finally { Pop-Location }
Write-Host 'Preparación completada. Ejecuta .\iniciar_sistema.ps1 y abre http://127.0.0.1:8765'

