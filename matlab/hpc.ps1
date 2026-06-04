param(
  [ValidateSet("matlab", "python")]
  [string]$Runtime = "matlab",
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
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$canonical = Join-Path $repoRoot "packaging\hpc\hpc.ps1"
if (-not (Test-Path $canonical)) {
  throw "Missing canonical HPC wrapper: $canonical"
}

Write-Warning "matlab/hpc.ps1 is a compatibility wrapper. Prefer .\packaging\hpc\hpc.ps1 from the repository root."

& $canonical `
  -Runtime $Runtime `
  -RemoteRoot $RemoteRoot `
  -SlurmScript $SlurmScript `
  -ConfigPath $ConfigPath `
  -DefaultConfigPath $DefaultConfigPath `
  -Remote $Remote `
  -RemotePort $RemotePort `
  -SyncMode $SyncMode `
  -PythonBin $PythonBin `
  -MatlabBin $MatlabBin

exit $LASTEXITCODE
