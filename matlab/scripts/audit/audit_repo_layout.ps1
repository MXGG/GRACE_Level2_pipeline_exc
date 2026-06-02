param(
    [string]$Root = "."
)

$ErrorActionPreference = "Stop"
Set-Location $Root

Write-Host "== Repository Layout Audit =="

$dirs = @("python", "matlab/src", "matlab/scripts", "data", "docs", "dist", "dist_tmp", "output", "_archive", "_scratch")
$sizeRows = @()
foreach ($d in $dirs) {
    if (-not (Test-Path $d)) { continue }
    $files = Get-ChildItem $d -Recurse -File -ErrorAction SilentlyContinue
    $sum = ($files | Measure-Object Length -Sum).Sum
    $sizeRows += [pscustomobject]@{
        Dir = $d
        Files = $files.Count
        GB = [math]::Round(($sum / 1GB), 3)
    }
}

Write-Host ""
Write-Host "-- Directory Size Overview --"
$sizeRows | Sort-Object GB -Descending | Format-Table -AutoSize

Write-Host ""
Write-Host "-- Duplicate Scripts By Content Hash (scripts/) --"
$scriptFiles = Get-ChildItem matlab/scripts -Recurse -File -ErrorAction SilentlyContinue
if ($scriptFiles.Count -eq 0) {
    Write-Host "No files in scripts/."
} else {
    $rows = foreach ($f in $scriptFiles) {
        [pscustomobject]@{
            Name = $f.Name
            Length = $f.Length
            Hash = (Get-FileHash $f.FullName -Algorithm SHA256).Hash
        }
    }
    $dups = $rows | Group-Object Hash | Where-Object { $_.Count -gt 1 }
    if ($dups.Count -eq 0) {
        Write-Host "No duplicate scripts found."
    } else {
        foreach ($g in $dups) {
            $g.Group | Select-Object Name, Length, Hash | Format-Table -AutoSize
        }
    }
}

Write-Host ""
Write-Host "-- Build Entrypoints (python/) --"
$buildFiles = @("build.ps1", "build.bat", "build.sh", "fast_build.bat", "fast_build_py312.bat")
foreach ($bf in $buildFiles) {
    $p = Join-Path "python" $bf
    if (Test-Path $p) {
        $len = (Get-Item $p).Length
        Write-Host ("{0} ({1} bytes)" -f $p, $len)
    }
}

Write-Host ""
Write-Host "-- Cleanup Candidates (manual review) --"
@(
    "_scratch/",
    "_archive/",
    "dist_tmp/",
    "python/build_tmp/",
    "python/venv312/",
    "output/"
) | ForEach-Object { Write-Host $_ }

Write-Host ""
Write-Host "Audit completed."

