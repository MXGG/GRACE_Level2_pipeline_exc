param(
  [ValidateSet("matlab", "python")]
  [string]$Runtime = "python",
  [string]$RemoteRoot = "~/GRACE_Level2_pipeline",
  [string]$SlurmScript = "",
  [string]$ConfigPath = "configs/user.json",
  [string]$DefaultConfigPath = "configs/default.json",
  [string]$Remote = "",
  [int]$RemotePort = 22,
  [ValidateSet("auto", "git", "scp")]
  [string]$SyncMode = "auto",
  [string]$PythonBin = "python3",
  [string]$MatlabBin = "matlab"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $scriptDir "packaging\hpc\hpc.ps1"
if (-not (Test-Path $target)) {
  throw "Missing canonical HPC wrapper: $target"
}

$params = @{
  Runtime = $Runtime
  RemoteRoot = $RemoteRoot
  SlurmScript = $SlurmScript
  ConfigPath = $ConfigPath
  DefaultConfigPath = $DefaultConfigPath
  Remote = $Remote
  RemotePort = $RemotePort
  SyncMode = $SyncMode
  PythonBin = $PythonBin
  MatlabBin = $MatlabBin
}

& $target @params
exit $LASTEXITCODE
