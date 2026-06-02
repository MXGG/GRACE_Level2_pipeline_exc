param(
    [string]$Root = "python/grace_pipeline",
    [int]$Top = 25
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyScript = Join-Path $scriptDir "audit_python_functions.py"

if (-not (Test-Path $pyScript)) {
    throw "Missing script: $pyScript"
}

$py312 = Join-Path $env:LocalAppData "Programs\Python\Python312\python.exe"
if (Test-Path $py312) {
    & $py312 $pyScript --root $Root --top $Top
    exit $LASTEXITCODE
}
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.12 $pyScript --root $Root --top $Top
    exit $LASTEXITCODE
}
if (Get-Command python -ErrorAction SilentlyContinue) {
    & python $pyScript --root $Root --top $Top
    exit $LASTEXITCODE
}
throw "No usable Python interpreter was found for audit_python_functions.py."

