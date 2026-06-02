param(
  [ValidateSet("matlab", "python")]
  [string]$Runtime = "matlab",
  [string]$RemoteRoot = "/home/um202370130/GRACE_Level2_pipeline",
  [string]$SlurmScript = "",
  [string]$ConfigPath = "matlab/cfg/user.json",
  [string]$DefaultConfigPath = "matlab/cfg/default.json",
  [string]$Remote = "hust-hpc",
  [int]$RemotePort = 22,
  [ValidateSet("auto", "git", "scp")]
  [string]$SyncMode = "auto",
  [string]$PythonBin = "python3"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $scriptDir "matlab\hpc.ps1"
if (-not (Test-Path $target)) {
  throw "Missing target script: $target"
}

& $target `
  -Runtime $Runtime `
  -RemoteRoot $RemoteRoot `
  -SlurmScript $SlurmScript `
  -ConfigPath $ConfigPath `
  -DefaultConfigPath $DefaultConfigPath `
  -Remote $Remote `
  -RemotePort $RemotePort `
  -SyncMode $SyncMode `
  -PythonBin $PythonBin
exit $LASTEXITCODE
