# WinGet Packaging

This directory contains the Windows Package Manager (`winget`) packaging method for GRACE Level-2 Pipeline.

The project is not automatically available through `winget install` until a valid manifest is submitted to and accepted by the Windows Package Manager Community Repository (`microsoft/winget-pkgs`). A GitHub Release installer alone is not sufficient.

## Recommended workflow

1. Build the Windows installer.
2. Upload the installer to a GitHub Release.
3. Calculate the SHA256 digest of the installer.
4. Generate WinGet manifest files from the release URL and SHA256.
5. Validate the manifest locally.
6. Test local installation using `winget install --manifest`.
7. Submit the manifest to `microsoft/winget-pkgs`.

## Generate installer SHA256

```powershell
.\packaging\windows\winget\scripts\Get-InstallerSha256.ps1 `
  -InstallerPath .\dist\grace-l2-pipeline-v0.1.0-win-x64-setup.exe
```

or manually:

```powershell
Get-FileHash .\dist\grace-l2-pipeline-v0.1.0-win-x64-setup.exe -Algorithm SHA256
```

## Generate a manifest set

```powershell
.\packaging\windows\winget\scripts\New-WinGetManifest.ps1 `
  -PackageVersion 0.1.0 `
  -InstallerUrl "https://github.com/MXGG/GRACE_Level2_pipeline_exc/releases/download/v0.1.0/grace-l2-pipeline-v0.1.0-win-x64-setup.exe" `
  -InstallerSha256 "<SHA256>"
```

By default, the script writes to:

```text
packaging/windows/winget/manifests/MXGG.GRACELevel2Pipeline/<version>/
```

## Validate the manifest

```powershell
winget validate .\packaging\windows\winget\manifests\MXGG.GRACELevel2Pipeline\0.1.0
```

## Test local installation

```powershell
winget install --manifest .\packaging\windows\winget\manifests\MXGG.GRACELevel2Pipeline\0.1.0
```

## Public installation after acceptance

After the manifest is accepted by the official WinGet community repository, users should be able to install with:

```powershell
winget search grace
winget install --id MXGG.GRACELevel2Pipeline -e
```

## Notes

- `PackageIdentifier` is currently set to `MXGG.GRACELevel2Pipeline`.
- `InstallerType` is set to `inno`, assuming the Windows installer is built with Inno Setup.
- The installer must support silent installation before a public WinGet submission.
- Update the package version and SHA256 for every release.
- Do not commit generated manifests for unreleased or invalid installer URLs.
