param(
    [string]$Python = "",
    [string]$PipIndexUrl = "",
    [switch]$Fast
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$VenvDir = Join-Path $ScriptDir ".venv-build"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$DistDir = Join-Path $RepoRoot "dist"
$WorkDir = Join-Path $ScriptDir "build"

function Test-PythonCandidate {
    param(
        [string]$Command,
        [string[]]$Args = @()
    )

    try {
        $json = & $Command @Args -c "import json,sys; print(json.dumps({'exe': sys.executable, 'major': sys.version_info[0], 'minor': sys.version_info[1]}))" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $json) {
            return $null
        }
        $info = $json | Select-Object -Last 1 | ConvertFrom-Json
        if ($info.major -lt 3 -or ($info.major -eq 3 -and $info.minor -lt 9)) {
            return $null
        }
        return @{
            Command = $Command
            Args = $Args
            Executable = [string]$info.exe
            Version = "$($info.major).$($info.minor)"
        }
    } catch {
        return $null
    }
}

function Resolve-Python {
    param([string]$Requested)

    $candidates = New-Object System.Collections.Generic.List[hashtable]
    if ($Requested) {
        $candidates.Add(@{ Command = $Requested; Args = @() })
    }

    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($ver in @("3.12", "3.11", "3.10", "3.9")) {
            $candidates.Add(@{ Command = "py"; Args = @("-$ver") })
        }
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        $candidates.Add(@{ Command = "python"; Args = @() })
    }

    foreach ($common in @(
        (Join-Path $env:LocalAppData "Programs\Python\Python312\python.exe"),
        (Join-Path $env:LocalAppData "Programs\Python\Python311\python.exe"),
        (Join-Path $env:LocalAppData "Programs\Python\Python310\python.exe"),
        (Join-Path $env:LocalAppData "Programs\Python\Python39\python.exe")
    )) {
        if ($common -and (Test-Path $common)) {
            $candidates.Add(@{ Command = $common; Args = @() })
        }
    }

    foreach ($candidate in $candidates) {
        $resolved = Test-PythonCandidate -Command $candidate.Command -Args $candidate.Args
        if ($resolved) {
            return $resolved
        }
    }

    throw "No usable Python >= 3.9 was found. Install Python 3.12 and enable the py launcher, or pass -Python <path-to-python.exe>."
}

Write-Host "========================================"
Write-Host "GRACE Pipeline Build Script"
Write-Host "========================================"
Write-Host ""

Set-Location $ScriptDir

$pythonInfo = Resolve-Python -Requested $Python
Write-Host ("Using Python {0} -> {1}" -f $pythonInfo.Version, $pythonInfo.Executable)

if ($PipIndexUrl) {
    $env:PIP_INDEX_URL = $PipIndexUrl
    Write-Host ("Using pip mirror: {0}" -f $PipIndexUrl)
}

if (Test-Path $VenvPython) {
    try {
        & $VenvPython -c "import sys; print(sys.executable)" > $null
        if ($LASTEXITCODE -ne 0) {
            throw "Broken venv"
        }
    } catch {
        Write-Host "Removing broken build environment..."
        Remove-Item -LiteralPath $VenvDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

if ((Test-Path $VenvDir) -and -not (Test-Path $VenvPython)) {
    Write-Host "Removing incomplete build environment..."
    Remove-Item -LiteralPath $VenvDir -Recurse -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating build virtual environment..."
    $pythonArgs = @($pythonInfo.Args)
    & $pythonInfo.Command @pythonArgs -m venv $VenvDir
}

if ($Fast) {
    Write-Host "Fast mode: reusing existing build environment and skipping dependency refresh."
} else {
    Write-Host "Installing build dependencies..."
    & $VenvPython -m pip install --upgrade pip setuptools wheel
    & $VenvPython -m pip install -e ".[build]"
}

Write-Host ""
Write-Host "Building executable..."
$pyinstallerArgs = @(
    "-m", "PyInstaller", "grace_pipeline.spec",
    "--noconfirm",
    "--distpath", $DistDir,
    "--workpath", $WorkDir
)
if (-not $Fast) {
    $pyinstallerArgs += "--clean"
}
& $VenvPython @pyinstallerArgs

$guiExe = Join-Path $DistDir "grace-pipeline-gui.exe"
$cliExe = Join-Path $DistDir "grace-pipeline.exe"
if (-not (Test-Path $guiExe) -and -not (Test-Path $cliExe)) {
    throw "Build finished without expected executables in $DistDir"
}

Write-Host ""
Write-Host "========================================"
Write-Host "Build successful!"
if (Test-Path $guiExe) {
    Write-Host "GUI executable: $guiExe"
}
if (Test-Path $cliExe) {
    Write-Host "CLI executable: $cliExe"
}
Write-Host "Build venv: $VenvDir"
Write-Host "========================================"
