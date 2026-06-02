Param(
    [string]$Root = ".",
    [string]$InnerDir = "python"
)

$ErrorActionPreference = "Stop"

$rootPath = (Resolve-Path $Root).Path
$innerPath = (Resolve-Path (Join-Path $rootPath $InnerDir)).Path
$exts = @(".py", ".ps1", ".bat", ".sh", ".slurm", ".m", ".cmd")

Write-Output "== Cross-Tree Script Audit =="
Write-Output ("Root:     {0}" -f $rootPath)
Write-Output ("InnerDir: {0}" -f $innerPath)
Write-Output ""

$files = Get-ChildItem -Path $rootPath -Recurse -File | Where-Object { $exts -contains $_.Extension.ToLower() }
$items = foreach ($f in $files) {
    $hash = (Get-FileHash -Algorithm SHA256 -Path $f.FullName).Hash
    [PSCustomObject]@{
        FullName = $f.FullName
        RelPath = $f.FullName.Replace($rootPath + "\", "")
        Name = $f.Name.ToLower()
        Hash = $hash
        InInner = $f.FullName.StartsWith($innerPath)
    }
}

Write-Output "-- Exact-content duplicate groups crossing boundary --"
$dupHashGroups = $items | Group-Object Hash | Where-Object {
    ($_.Group.InInner -contains $true) -and ($_.Group.InInner -contains $false)
}
if (-not $dupHashGroups) {
    Write-Output "No exact-content cross-boundary duplicates found."
} else {
    $i = 0
    foreach ($g in $dupHashGroups) {
        $i++
        Write-Output ("[{0}] {1} (n={2})" -f $i, $g.Name.Substring(0, 10), $g.Count)
        foreach ($r in ($g.Group | Sort-Object RelPath)) {
            Write-Output ("  {0}" -f $r.RelPath)
        }
    }
}

Write-Output ""
Write-Output "-- Same-name script files crossing boundary --"
$sameNameGroups = $items | Group-Object Name | Where-Object {
    ($_.Group.InInner -contains $true) -and ($_.Group.InInner -contains $false)
}
if (-not $sameNameGroups) {
    Write-Output "No same-name cross-boundary script files found."
} else {
    $j = 0
    foreach ($g in ($sameNameGroups | Sort-Object Name)) {
        $j++
        Write-Output ("[{0}] {1}" -f $j, $g.Name)
        foreach ($r in ($g.Group | Sort-Object RelPath)) {
            $tag = if ($r.InInner) { "IN " } else { "OUT" }
            Write-Output ("  {0} {1}" -f $tag, $r.RelPath)
        }
    }
}

Write-Output ""
Write-Output "Audit completed."

