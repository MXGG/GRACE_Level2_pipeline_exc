param(
    [string]$Root = "matlab/src",
    [int]$MaxLines = 300,
    [int]$MaxArgs = 8,
    [string]$Report = "docs/reports/matlab_interface_audit.txt"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyScript = Join-Path $scriptDir "audit_matlab_interfaces.py"

if (-not (Test-Path $pyScript)) {
    throw "Missing script: $pyScript"
}

$py312 = Join-Path $env:LocalAppData "Programs\Python\Python312\python.exe"
if (Test-Path $py312) {
    & $py312 $pyScript --root $Root --max-lines $MaxLines --max-args $MaxArgs --report $Report
    exit $LASTEXITCODE
}
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.12 $pyScript --root $Root --max-lines $MaxLines --max-args $MaxArgs --report $Report
    exit $LASTEXITCODE
}
if (Get-Command python -ErrorAction SilentlyContinue) {
    & python $pyScript --root $Root --max-lines $MaxLines --max-args $MaxArgs --report $Report
    exit $LASTEXITCODE
}
throw "No usable Python interpreter was found for audit_matlab_interfaces.py."

