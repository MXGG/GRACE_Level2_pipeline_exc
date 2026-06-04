param(
  [Parameter(Mandatory = $true)]
  [string]$InstallerPath
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $InstallerPath)) {
  throw "Installer not found: $InstallerPath"
}

$hash = Get-FileHash -LiteralPath $InstallerPath -Algorithm SHA256
$hash.Hash.ToUpperInvariant()
