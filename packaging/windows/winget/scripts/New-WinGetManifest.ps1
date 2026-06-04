param(
  [string]$PackageIdentifier = "MXGG.GRACELevel2Pipeline",
  [string]$PackageName = "GRACE Level-2 Pipeline",
  [string]$Publisher = "MXGG",
  [Parameter(Mandatory = $true)]
  [string]$PackageVersion,
  [Parameter(Mandatory = $true)]
  [string]$InstallerUrl,
  [Parameter(Mandatory = $true)]
  [string]$InstallerSha256,
  [string]$OutputRoot = "packaging/windows/winget/manifests"
)

$ErrorActionPreference = "Stop"

$manifestDir = Join-Path $OutputRoot (Join-Path $PackageIdentifier $PackageVersion)
New-Item -ItemType Directory -Force -Path $manifestDir | Out-Null

$versionFile = Join-Path $manifestDir "$PackageIdentifier.yaml"
$installerFile = Join-Path $manifestDir "$PackageIdentifier.installer.yaml"
$localeFile = Join-Path $manifestDir "$PackageIdentifier.locale.en-US.yaml"
$installerSha = $InstallerSha256.Trim().ToUpperInvariant()
$today = Get-Date -Format yyyy-MM-dd

$versionYaml = @"
PackageIdentifier: $PackageIdentifier
PackageVersion: $PackageVersion
DefaultLocale: en-US
ManifestType: version
ManifestVersion: 1.6.0
"@

$installerYaml = @"
PackageIdentifier: $PackageIdentifier
PackageVersion: $PackageVersion
InstallerType: inno
Scope: machine
InstallModes:
  - interactive
  - silent
  - silentWithProgress
InstallerSwitches:
  Silent: /VERYSILENT /NORESTART
  SilentWithProgress: /SILENT /NORESTART
UpgradeBehavior: install
ReleaseDate: $today
Installers:
  - Architecture: x64
    InstallerUrl: $InstallerUrl
    InstallerSha256: $installerSha
ManifestType: installer
ManifestVersion: 1.6.0
"@

$localeYaml = @"
PackageIdentifier: $PackageIdentifier
PackageVersion: $PackageVersion
PackageLocale: en-US
Publisher: $Publisher
PublisherUrl: https://github.com/MXGG
PublisherSupportUrl: https://github.com/MXGG/GRACE_Level2_pipeline_exc/issues
PackageName: $PackageName
PackageUrl: https://github.com/MXGG/GRACE_Level2_pipeline_exc
License: MIT
LicenseUrl: https://github.com/MXGG/GRACE_Level2_pipeline_exc/blob/main/LICENSE
ShortDescription: GRACE/GRACE-FO Level-2 spherical harmonic processing pipeline.
Description: A MATLAB and Python processing workspace for GRACE and GRACE-FO Level-2 spherical harmonic products.
Moniker: grace-l2-pipeline
Tags:
  - grace
  - grace-fo
  - geodesy
  - gravity
  - satellite
  - hydrology
  - spherical-harmonics
ManifestType: defaultLocale
ManifestVersion: 1.6.0
"@

Set-Content -Path $versionFile -Value $versionYaml -Encoding UTF8
Set-Content -Path $installerFile -Value $installerYaml -Encoding UTF8
Set-Content -Path $localeFile -Value $localeYaml -Encoding UTF8

Write-Host "Created WinGet manifest files under: $manifestDir"
Write-Host "Validate with: winget validate $manifestDir"
Write-Host "Test local install with: winget install --manifest $manifestDir"
