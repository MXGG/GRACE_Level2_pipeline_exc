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

function Convert-ToPosixPath {
  param([string]$PathText)
  return ($PathText -replace '\\', '/')
}

function Get-EffectiveSyncMode {
  param(
    [string]$RequestedMode,
    [string]$RepoRoot
  )
  if ($RequestedMode -ne "auto") {
    return $RequestedMode
  }
  try {
    $remotes = git -C $RepoRoot remote 2>$null
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace(($remotes | Out-String))) {
      return "git"
    }
  }
  catch {
  }
  return "scp"
}

function Sync-ProjectViaScp {
  param(
    [string]$RepoRoot,
    [string]$Remote,
    [int]$RemotePort,
    [string]$RemoteRoot
  )

  $sshExe = "C:\Windows\System32\OpenSSH\ssh.exe"
  $scpExe = "C:\Windows\System32\OpenSSH\scp.exe"
  $remoteMatlab = "${Remote}:$RemoteRoot/matlab/"
  $remotePython = "${Remote}:$RemoteRoot/python/"
  $remoteDocs = "${Remote}:$RemoteRoot/docs/"

  Write-Host "1) Sync project to HPC via scp ..." -ForegroundColor Cyan
  & $sshExe -p $RemotePort $Remote "mkdir -p '$RemoteRoot/matlab' '$RemoteRoot/python' '$RemoteRoot/docs'"
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to prepare remote directories under $RemoteRoot."
  }

  & $scpExe -P $RemotePort -r `
    (Join-Path $RepoRoot "matlab\cfg") `
    (Join-Path $RepoRoot "matlab\scripts") `
    (Join-Path $RepoRoot "matlab\src") `
    $remoteMatlab
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to upload matlab project directories."
  }

  & $scpExe -P $RemotePort -r `
    (Join-Path $RepoRoot "python\grace_pipeline") `
    $remotePython
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to upload python/grace_pipeline."
  }

  & $scpExe -P $RemotePort `
    (Join-Path $RepoRoot "python\pyproject.toml") `
    (Join-Path $RepoRoot "python\requirements.txt") `
    $remotePython
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to upload python metadata files."
  }

  $docPath = Join-Path $RepoRoot "docs\HPC_PYTHON_MATLAB_USAGE.md"
  if (Test-Path $docPath) {
    & $scpExe -P $RemotePort $docPath $remoteDocs
    if ($LASTEXITCODE -ne 0) {
      Write-Warning "Failed to upload docs/HPC_PYTHON_MATLAB_USAGE.md"
    }
  }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$effectiveSyncMode = Get-EffectiveSyncMode -RequestedMode $SyncMode -RepoRoot $repoRoot

$resolvedSlurmScript = if ([string]::IsNullOrWhiteSpace($SlurmScript)) {
  if ($Runtime -eq "python") { "matlab/scripts/run/run_python.slurm" } else { "matlab/scripts/run/run.slurm" }
} else {
  $SlurmScript
}
$resolvedSlurmScript = Convert-ToPosixPath $resolvedSlurmScript
$resolvedConfigPath = Convert-ToPosixPath $ConfigPath
$resolvedDefaultConfigPath = Convert-ToPosixPath $DefaultConfigPath
$resolvedRemoteRoot = Convert-ToPosixPath $RemoteRoot

$sshArgs = @("-p", "$RemotePort", $Remote)
$checkCommand = "cd '$resolvedRemoteRoot' && pwd && ls -l '$resolvedSlurmScript' '$resolvedConfigPath' '$resolvedDefaultConfigPath'"
$submitCommand = "cd '$resolvedRemoteRoot' && GRACE_RUNTIME='$Runtime' GRACE_USER_CONFIG='$resolvedConfigPath' GRACE_DEFAULT_CONFIG='$resolvedDefaultConfigPath' GRACE_PYTHON_BIN='$PythonBin' sbatch '$resolvedSlurmScript'"

Push-Location $repoRoot
try {
  if ($effectiveSyncMode -eq "git") {
    Write-Host "1) Git push to HPC ..." -ForegroundColor Cyan
    git push | Out-Host
  } else {
    Sync-ProjectViaScp -RepoRoot $repoRoot -Remote $Remote -RemotePort $RemotePort -RemoteRoot $resolvedRemoteRoot
  }

  Write-Host "2) Check remote worktree, config, and slurm script ..." -ForegroundColor Cyan
  $check = & C:\Windows\System32\OpenSSH\ssh.exe @sshArgs $checkCommand 2>&1
  $check | Out-Host
  if ($LASTEXITCODE -ne 0) {
    throw "Remote check failed. Ensure the sync succeeded and $resolvedRemoteRoot contains the requested files."
  }

  Write-Host "3) Submit $Runtime job via sbatch ..." -ForegroundColor Cyan
  $sb = & C:\Windows\System32\OpenSSH\ssh.exe @sshArgs $submitCommand 2>&1
  $sb | Out-Host

  $jobid = ""
  if ($sb -match "Submitted batch job\s+(\d+)") { $jobid = $Matches[1] }
  if ([string]::IsNullOrWhiteSpace($jobid)) {
    throw "Failed to get JobID from sbatch output. See output above."
  }
  Write-Host "JobID = $jobid" -ForegroundColor Green

  Write-Host "4) Wait job to finish ..." -ForegroundColor Cyan
  while ($true) {
    $q = & C:\Windows\System32\OpenSSH\ssh.exe @sshArgs "squeue -j $jobid -h -o %T" 2>$null
    if ([string]::IsNullOrWhiteSpace($q)) { break }
    Write-Host "  status: $q"
    Start-Sleep -Seconds 10
  }
  Write-Host "Job finished." -ForegroundColor Green

  $localRunDir = Join-Path -Path $repoRoot -ChildPath "output\remote\$jobid"
  New-Item -ItemType Directory -Force -Path $localRunDir | Out-Null

  Write-Host "5) Pull outputs back to $localRunDir ..." -ForegroundColor Cyan
  $remoteRunDir = "${Remote}:$resolvedRemoteRoot/output/remote/$jobid/."
  $remoteOutLog = "${Remote}:$resolvedRemoteRoot/output/logs/grace_$jobid.out"
  $remoteErrLog = "${Remote}:$resolvedRemoteRoot/output/logs/grace_$jobid.err"

  & C:\Windows\System32\OpenSSH\scp.exe -P $RemotePort -r $remoteRunDir $localRunDir 2>$null
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "Failed to pull remote run directory: $remoteRunDir"
  }
  & C:\Windows\System32\OpenSSH\scp.exe -P $RemotePort $remoteOutLog $localRunDir 2>$null
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "Failed to pull stdout log: $remoteOutLog"
  }
  & C:\Windows\System32\OpenSSH\scp.exe -P $RemotePort $remoteErrLog $localRunDir 2>$null
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "Failed to pull stderr log: $remoteErrLog"
  }

  Write-Host "DONE." -ForegroundColor Green
}
finally {
  Pop-Location
}
