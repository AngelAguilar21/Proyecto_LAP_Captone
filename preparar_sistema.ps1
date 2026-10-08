param()
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
function Run-Step([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Falló: $Program $($Arguments -join ' ')" }
}
# Node solo hace falta para compilar la interfaz; si el paquete ya trae dashboard/dist se puede usar sin Node.
$hayNode = [bool](Get-Command npm.cmd -ErrorAction SilentlyContinue)
$hayDist = Test-Path -LiteralPath (Join-Path $PSScriptRoot 'proyecto_lap_prototipo/dashboard/dist/index.html')
if (-not $hayNode -and -not $hayDist) { throw 'Instala Node.js 22 LTS (npm) antes de continuar. Consulta INSTALACION.md.' }
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'

# Las dependencias están fijadas para Python 3.12 (numpy, scipy y otras no tienen instalador para 3.13 en Windows).
# Si hay varios Pythons instalados, se usa el 3.12 aunque el predeterminado sea otro.
function Find-Python312 {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.12 -c "import sys" 2>$null
        if ($LASTEXITCODE -eq 0) { return @('py', '-3.12') }
    }
    foreach ($name in @('python3.12', 'python')) {
        if (Get-Command $name -ErrorAction SilentlyContinue) {
            $version = & $name -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($version -eq '3.12') { return @($name) }
        }
    }
    return    # nada: no hay Python 3.12
}

# Un .venv creado antes con otra versión de Python no sirve: se rehace.
if (Test-Path -LiteralPath $python) {
    $actual = & $python -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
    if ($actual -ne '3.12') {
        Write-Host "El entorno .venv usa Python $actual y se necesita 3.12: se vuelve a crear."
        Remove-Item -LiteralPath (Join-Path $PSScriptRoot '.venv') -Recurse -Force
    }
}
if (-not (Test-Path -LiteralPath $python)) {
    $py312 = @(Find-Python312)     # @() evita que un solo elemento se convierta en texto
    if ($py312.Count -eq 0) {
        throw 'Hace falta Python 3.12 (64 bits) y no se encontró. Instálalo desde python.org: puede convivir con otras versiones (por ejemplo 3.13) y este instalador lo usará solo. Consulta INSTALACION.md.'
    }
    Run-Step $py312[0] (@($py312 | Select-Object -Skip 1) + @('-m', 'venv', '.venv'))
}
Run-Step $python @('-m','pip','install','--no-compile','-r','requirements.txt')
Run-Step $python @('-m','pip','check')
Run-Step $python @('proyecto_lap_prototipo/setup_objects.py','--download')
Run-Step $python @('proyecto_lap_prototipo/setup_workspace.py')
if ($hayNode) {
    Push-Location 'proyecto_lap_prototipo/dashboard'
    try {
        Run-Step 'npm.cmd' @('ci')
        Run-Step 'npm.cmd' @('run','build')
    } finally { Pop-Location }
} else {
    Write-Host 'Node.js no está instalado: se usa la interfaz ya compilada (dashboard/dist).'
}
Write-Host 'Preparación completada. Ejecuta .\iniciar_sistema.ps1 y abre http://127.0.0.1:8765'

