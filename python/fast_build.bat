@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
echo Fast build: reusing .venv-build and skipping dependency refresh.
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%build.ps1" -Fast %*
exit /b %errorlevel%
