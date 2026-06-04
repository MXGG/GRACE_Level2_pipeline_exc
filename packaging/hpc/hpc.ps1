param(
  [ValidateSet("matlab", "python")]
  [string]$Runtime = "matlab",
  [string]$RemoteRoot = "/home/um202370130/GRACE_Level2_pipeline",
  [string]$SlurmScript = "",
  [string]$ConfigPath = "configs/user.json",
  [string]$DefaultConfigPath = "configs/default.json",
  [string]$Remote = "hust-hpc",
  [int]$RemotePort = 22,
  [ValidateSet("auto", "git", "scp")]
  [string]$SyncMode = "auto",
  [string]$PythonBin = "python3"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")

# During the staged migration, use the legacy MATLAB-side HPC implementation when present.
# This wrapper only changes the public-facing canonical default paths.
$legacyTarget = Join-Path $repoRoot "matlab\hpc.ps1"
if (-not (Test-Path $legacyTarget)) {
  throw "Missing legacy HPC implementation: $legacyTarget. Run scripts/dev/stage_repository_layout.ps1 first or restore matlab/hpc.ps1."
}

& $legacyTarget `
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
