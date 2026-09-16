@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0preparar_sistema.ps1"
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" (
  echo.
  echo La preparacion no termino. Lee el ultimo mensaje de error.
  pause
)
exit /b %RESULT%
