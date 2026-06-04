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
  [string]$MatlabBin = "matlab",
  [switch]$NoWait,
  [switch]$NoPull
)

$ErrorActionPreference = "Stop"

function Convert-ToPosixPath {
  param([string]$PathText)
  return ($PathText -replace '\\', '/')
}

function Get-CommandPath {
  param([string]$Name)
  $cmd = Get-Command $Name -ErrorAction SilentlyContinue
  if (-not $cmd) { throw "Required command not found on local machine: $Name" }
  return $cmd.Source
}

function Get-EffectiveSyncMode {
  param([string]$RequestedMode, [string]$RepoRoot)
  if ($RequestedMode -ne "auto") { return $RequestedMode }
  try {
    $remotes = git -C $RepoRoot remote 2>$null
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace(($remotes | Out-String))) { return "git" }
  } catch {}
  return "scp"
}

function Sync-ProjectViaScp {
  param(
    [string]$RepoRoot,
    [string]$Remote,
    [int]$RemotePort,
    [string]$RemoteRoot,
    [string]$SshExe,
    [string]$ScpExe
  )

  Write-Host "1) Sync project to HPC via scp ..." -ForegroundColor Cyan
  & $SshExe -p $RemotePort $Remote "mkdir -p '$RemoteRoot' '$RemoteRoot/output/logs' '$RemoteRoot/outputs/logs'"
  if ($LASTEXITCODE -ne 0) { throw "Failed to prepare remote root: $RemoteRoot" }

  $items = @("configs", "python", "matlab", "packaging", "docs", "data/INPUT_FILES.md", "README.md", "README.zh-CN.md", "LICENSE")
  foreach ($item in $items) {
    $src = Join-Path $RepoRoot $item
    if (-not (Test-Path $src)) { continue }
    & $ScpExe -P $RemotePort -r $src "${Remote}:$RemoteRoot/"
    if ($LASTEXITCODE -ne 0) { throw "Failed to upload: $item" }
  }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")

if ([string]::IsNullOrWhiteSpace($Remote)) {
  throw "Missing -Remote. Example: .\packaging\hpc\hpc.ps1 -Remote user@host -RemoteRoot /path/to/workdir"
}

$sshExe = Get-CommandPath "ssh"
$scpExe = Get-CommandPath "scp"
$effectiveSyncMode = Get-EffectiveSyncMode -RequestedMode $SyncMode -RepoRoot $repoRoot

$defaultSlurm = if ($Runtime -eq "python") { "packaging/hpc/slurm/run_python.slurm" } else { "packaging/hpc/slurm/run_matlab.slurm" }
$resolvedSlurmScript = if ([string]::IsNullOrWhiteSpace($SlurmScript)) { $defaultSlurm } else { $SlurmScript }

$resolvedSlurmScript = Convert-ToPosixPath $resolvedSlurmScript
$resolvedConfigPath = Convert-ToPosixPath $ConfigPath
$resolvedDefaultConfigPath = Convert-ToPosixPath $DefaultConfigPath
$resolvedRemoteRoot = Convert-ToPosixPath $RemoteRoot
$resolvedOutputRoot = "$resolvedRemoteRoot/outputs"
$sshArgs = @("-p", "$RemotePort", $Remote)

Push-Location $repoRoot
try {
  if ($effectiveSyncMode -eq "git") {
    Write-Host "1) Git push for HPC sync ..." -ForegroundColor Cyan
    git push | Out-Host
  } else {
    Sync-ProjectViaScp -RepoRoot $repoRoot -Remote $Remote -RemotePort $RemotePort -RemoteRoot $resolvedRemoteRoot -SshExe $sshExe -ScpExe $scpExe
  }

  Write-Host "2) Check remote worktree, config, and SLURM script ..." -ForegroundColor Cyan
  $checkCommand = "cd '$resolvedRemoteRoot' && pwd && ls -l '$resolvedSlurmScript' '$resolvedConfigPath' '$resolvedDefaultConfigPath'"
  $check = & $sshExe @sshArgs $checkCommand 2>&1
  $check | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "Remote check failed. Ensure sync succeeded and required files exist." }

  Write-Host "3) Submit $Runtime job via sbatch ..." -ForegroundColor Cyan
  $submitCommand = "cd '$resolvedRemoteRoot' && GRACE_RUNTIME='$Runtime' GRACE_REMOTE_ROOT='$resolvedRemoteRoot' GRACE_USER_CONFIG='$resolvedConfigPath' GRACE_DEFAULT_CONFIG='$resolvedDefaultConfigPath' GRACE_OUTPUT_ROOT='$resolvedOutputRoot' GRACE_PYTHON_BIN='$PythonBin' GRACE_MATLAB_BIN='$MatlabBin' sbatch '$resolvedSlurmScript'"
  $sb = & $sshExe @sshArgs $submitCommand 2>&1
  $sb | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "sbatch submission failed." }

  $jobid = ""
  if ($sb -match "Submitted batch job\s+(\d+)") { $jobid = $Matches[1] }
  if ([string]::IsNullOrWhiteSpace($jobid)) { throw "Failed to parse JobID from sbatch output." }
  Write-Host "JobID = $jobid" -ForegroundColor Green

  if ($NoWait) { return }

  Write-Host "4) Wait job to finish ..." -ForegroundColor Cyan
  while ($true) {
    $q = & $sshExe @sshArgs "squeue -j $jobid -h -o %T" 2>$null
    if ([string]::IsNullOrWhiteSpace($q)) { break }
    Write-Host "  status: $q"
    Start-Sleep -Seconds 10
  }
  Write-Host "Job finished." -ForegroundColor Green

  if ($NoPull) { return }

  $localRunDir = Join-Path -Path $repoRoot -ChildPath "outputs\remote\$jobid"
  New-Item -ItemType Directory -Force -Path $localRunDir | Out-Null

  Write-Host "5) Pull outputs back to $localRunDir ..." -ForegroundColor Cyan
  $remoteRunDir = "${Remote}:$resolvedOutputRoot/remote/$jobid/."
  $remoteOutLog = "${Remote}:$resolvedOutputRoot/logs/grace_$jobid.out"
  $remoteErrLog = "${Remote}:$resolvedOutputRoot/logs/grace_$jobid.err"

  & $scpExe -P $RemotePort -r $remoteRunDir $localRunDir 2>$null
  if ($LASTEXITCODE -ne 0) { Write-Warning "Failed to pull remote run directory: $remoteRunDir" }
  & $scpExe -P $RemotePort $remoteOutLog $localRunDir 2>$null
  if ($LASTEXITCODE -ne 0) { Write-Warning "Failed to pull stdout log: $remoteOutLog" }
  & $scpExe -P $RemotePort $remoteErrLog $localRunDir 2>$null
  if ($LASTEXITCODE -ne 0) { Write-Warning "Failed to pull stderr log: $remoteErrLog" }

  Write-Host "DONE." -ForegroundColor Green
}
finally {
  Pop-Location
}
