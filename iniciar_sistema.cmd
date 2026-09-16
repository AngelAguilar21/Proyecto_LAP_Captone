@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0iniciar_sistema.ps1"
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" (
  echo.
  echo El servidor se detuvo por un error. Lee el ultimo mensaje de error.
  pause
)
exit /b %RESULT%
