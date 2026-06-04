param(
  [switch]$Force
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

function New-DirIfMissing {
  param([string]$Path)
  if (-not (Test-Path $Path)) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
  }
}

function Copy-TreeSafe {
  param(
    [string]$Source,
    [string]$Destination
  )

  if (-not (Test-Path $Source)) {
    Write-Warning "Skip missing source: $Source"
    return
  }

  if ((Test-Path $Destination) -and -not $Force) {
    Write-Host "Skip existing destination: $Destination  (use -Force to overwrite files)" -ForegroundColor Yellow
    return
  }

  New-DirIfMissing (Split-Path -Parent $Destination)
  Write-Host "Copy $Source -> $Destination" -ForegroundColor Cyan
  Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force:$Force
}

# Canonical directories
$dirs = @(
  "configs\schema",
  "src",
  "src\python",
  "src\matlab",
  "packaging\windows\python\pyinstaller",
  "packaging\windows\matlab",
  "packaging\windows\installer",
  "packaging\linux\python",
  "packaging\linux\matlab",
  "packaging\hpc",
  "outputs\local",
  "outputs\remote",
  "outputs\figures",
  "outputs\logs",
  "examples\quickstart-python",
  "examples\quickstart-matlab",
  "examples\caspian-leakage",
  "examples\basin-timeseries",
  "archive\legacy",
  "archive\deprecated",
  "docs\runtime",
  "docs\data",
  "docs\release",
  "docs\algorithms"
)

foreach ($dir in $dirs) {
  New-DirIfMissing (Join-Path $RepoRoot $dir)
}

# Non-destructive source staging.
Copy-TreeSafe -Source (Join-Path $RepoRoot "python") -Destination (Join-Path $RepoRoot "src\python")
Copy-TreeSafe -Source (Join-Path $RepoRoot "matlab") -Destination (Join-Path $RepoRoot "src\matlab")
Copy-TreeSafe -Source (Join-Path $RepoRoot "installer") -Destination (Join-Path $RepoRoot "packaging\windows\installer\legacy-installer")
Copy-TreeSafe -Source (Join-Path $RepoRoot "output") -Destination (Join-Path $RepoRoot "outputs\legacy-output")

# Copy root helper files into packaging locations when present.
$rootIss = Join-Path $RepoRoot "grace-l2.iss"
if (Test-Path $rootIss) {
  Copy-Item $rootIss (Join-Path $RepoRoot "packaging\windows\installer\grace-l2.iss") -Force:$Force
}

$rootHpc = Join-Path $RepoRoot "hpc.ps1"
if (Test-Path $rootHpc) {
  Copy-Item $rootHpc (Join-Path $RepoRoot "packaging\hpc\hpc-root-wrapper.legacy.ps1") -Force:$Force
}

Write-Host "Staged repository layout without deleting legacy paths." -ForegroundColor Green
Write-Host "Next: update commands to use configs/, src/python/, src/matlab/, packaging/, and outputs/." -ForegroundColor Green
