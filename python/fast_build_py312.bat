@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "PY312=%LocalAppData%\Programs\Python\Python312\python.exe"
echo Fast build (Python 3.12 preferred): reusing .venv-build and skipping dependency refresh.
if exist "%PY312%" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%build.ps1" -Python "%PY312%" -Fast %*
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%build.ps1" -Fast %*
)
exit /b %errorlevel%
