param(
  [Parameter(Mandatory=$true)]
  [string]$LogPath
)

if (-not (Test-Path -Path $LogPath)) {
  throw "Log file not found: $LogPath"
}

$regex = '^\[PERF\]\s+(.+?):\s+([0-9.]+)s'
$stats = @{}

Get-Content -Path $LogPath | ForEach-Object {
  if ($_ -match $regex) {
    $label = $Matches[1]
    $seconds = [double]$Matches[2]
    if (-not $stats.ContainsKey($label)) {
      $stats[$label] = [pscustomobject]@{
        Label = $label
        Count = 0
        Total = 0.0
        Max = 0.0
      }
    }
    $row = $stats[$label]
    $row.Count++
    $row.Total += $seconds
    if ($seconds -gt $row.Max) { $row.Max = $seconds }
  }
}

$stats.Values |
  ForEach-Object {
    [pscustomobject]@{
      Label = $_.Label
      Count = $_.Count
      Total_s = [math]::Round($_.Total, 3)
      Mean_s = if ($_.Count -gt 0) { [math]::Round($_.Total / $_.Count, 3) } else { 0 }
      Max_s = [math]::Round($_.Max, 3)
    }
  } |
  Sort-Object -Property Total_s -Descending |
  Format-Table -AutoSize
