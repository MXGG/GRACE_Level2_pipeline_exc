# GRACE Level-2 Pipeline

[中文说明](README.zh-CN.md)

A MATLAB/Python processing workspace for GRACE/GRACE-FO Level-2 spherical harmonic products. The project supports spherical harmonic inversion, low-degree replacement, GIA correction, Gaussian/Fan/decorrelation/DDK/HSAF filtering, basin-scale TWSA extraction, leakage correction, diagnostics, Windows desktop usage, Linux batch execution, and HPC submission.

This repository is in a staged layout migration. Legacy `python/`, `matlab/`, `installer/`, and `output/` paths are kept for compatibility. New runtime commands should prefer `configs/`, `packaging/`, and `outputs/`.

## Repository layout

| Path | Purpose |
| --- | --- |
| `configs/` | Shared JSON configurations for Python and MATLAB. |
| `python/` | Current Python backend and build scripts. |
| `matlab/` | Current MATLAB backend and compatibility scripts. |
| `data/` | Local input data workspace. Large data are not tracked. |
| `outputs/` | Canonical runtime outputs. Generated outputs are not tracked. |
| `packaging/` | Windows, Linux, installer, release, and HPC helpers. |
| `docs/` | User, developer, runtime, data, release, and algorithm notes. |
| `examples/` | Small reproducible examples. |
| `archive/` | Historical or deprecated materials. |

## Configuration

Use `configs/` as the shared configuration root.

Windows:

```powershell
Copy-Item configs\user.example.json configs\user.json
```

Linux/macOS:

```bash
cp configs/user.example.json configs/user.json
```

Then edit `configs/user.json` for local data paths, time range, filters, and worker count.

Common files:

| File | Purpose |
| --- | --- |
| `configs/default.json` | Version-controlled default configuration. |
| `configs/user.example.json` | Local user template. Copy to `configs/user.json`. |
| `configs/hpc.example.json` | HPC-oriented template. |
| `configs/schema/grace_l2_config.schema.json` | Initial schema placeholder. |

## Data layout

Large input datasets are not included. Put local data under `data/`.

```text
data/
├─ GRACE/GSM/
├─ GRACE/LowDegree/
├─ GRACE/GIA/
├─ DDK/
├─ Boundary/
├─ Reference/Mascon/
└─ Hydro/GLDAS/
```

See `data/INPUT_FILES.md` and `docs/data/` for data notes.

## Windows desktop installer

Download the latest `grace-l2-pipeline-vX.Y.Z-win-x64-setup.exe` from GitHub Releases and run the setup wizard.

Installed layout:

```text
<install-root>/
├─ dist/grace-pipeline-gui.exe
├─ dist/grace-pipeline.exe
├─ configs/
├─ data/
└─ outputs/
```

Example launch path:

```powershell
"C:\Program Files\GRACE_L2\dist\grace-pipeline-gui.exe"
```

The exact root depends on the installer path selected by the user.

### WinGet

After the package is accepted by the official Windows Package Manager community repository:

```powershell
winget install --id MXGG.GRACELevel2Pipeline -e
```

Before acceptance, install the Windows desktop edition from GitHub Releases.

## Python source install and run

Core CLI install. This does not install GUI-only dependencies such as PySide6.

Windows PowerShell:

```powershell
cd python
python -m pip install --upgrade pip
python -m pip install -e .
grace-pipeline doctor -c ..\configs\user.json -d ..\configs\default.json
grace-pipeline info   -c ..\configs\user.json -d ..\configs\default.json
grace-pipeline run    -c ..\configs\user.json -d ..\configs\default.json
```

Linux/macOS:

```bash
cd python
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
grace-pipeline doctor -c ../configs/user.json -d ../configs/default.json
grace-pipeline info   -c ../configs/user.json -d ../configs/default.json
grace-pipeline run    -c ../configs/user.json -d ../configs/default.json
```

GUI source debugging requires the optional GUI extra:

```powershell
cd python
python -m pip install -e ".[gui]"
python -m grace_pipeline.gui_entry
```

Linux GUI users should ensure a graphical session or suitable Qt backend is available. Headless Linux/HPC users should keep to the core CLI install.

Common CLI options:

```text
-c, --config PATH
-d, --default-config PATH
-o, --output PATH
--start YYYY-MM
--end YYYY-MM
-j, --jobs N
--no-parallel
-v, --verbose
```

## MATLAB local run

Standard local entry:

```matlab
run('matlab/src/main/run_oneclick.m')
```

Explicit shared configuration:

```matlab
addpath(genpath('matlab/src'));
OUT = run_oneclick_cfg('configs/user.json');
```

The MATLAB entries now prefer `configs/user.json` and `configs/default.json`, with `matlab/cfg/` retained only as a fallback.

Linux MATLAB batch:

```bash
matlab -batch "run('matlab/src/main/run_oneclick.m')"
```

## HPC submission

The canonical wrapper is `packaging/hpc/hpc.ps1`. It submits either the Python or MATLAB backend and passes remote paths through environment variables rather than hard-coded user paths.

Python backend:

```powershell
.\packaging\hpc\hpc.ps1 `
  -Runtime python `
  -Remote user@host `
  -RemoteRoot /remote/path/GRACE_Level2_pipeline `
  -ConfigPath configs/user.json `
  -DefaultConfigPath configs/default.json `
  -PythonBin python3
```

MATLAB backend:

```powershell
.\packaging\hpc\hpc.ps1 `
  -Runtime matlab `
  -Remote user@host `
  -RemoteRoot /remote/path/GRACE_Level2_pipeline `
  -ConfigPath configs/user.json `
  -DefaultConfigPath configs/default.json `
  -MatlabBin matlab
```

Useful options:

```text
-Runtime matlab|python
-Remote user@host
-RemotePort 22
-RemoteRoot /remote/path
-ConfigPath configs/user.json
-DefaultConfigPath configs/default.json
-SyncMode auto|git|scp
-PythonBin python3
-MatlabBin matlab
-NoWait
-NoPull
```

The portable SLURM entries are:

```text
packaging/hpc/slurm/run_python.slurm
packaging/hpc/slurm/run_matlab.slurm
```

Edit partition, QoS, wall time, CPU count, and optional module loading for the target cluster before production use.

## Build and packaging

Windows executable build:

```powershell
cd python
.\build.ps1
```

Linux executable build:

```bash
cd python
bash build.sh
```

The build extra installs GUI and PyInstaller dependencies; normal Linux CLI users do not need these packages.

## Outputs

Canonical output root:

```text
outputs/
├─ local/
├─ remote/
├─ figures/
└─ logs/
```

Recommended run layout:

```text
outputs/local/<run_id>/
├─ grids/
├─ basin/
├─ leakage/
├─ figures/
├─ logs/
└─ metadata.json
```

## Documentation

| Document | Purpose |
| --- | --- |
| `REPOSITORY_MIGRATION.md` | Staged repository layout migration plan. |
| `configs/README.md` | Configuration layout and usage. |
| `src/README.md` | Source layout guide. |
| `packaging/README.md` | Packaging and deployment layout. |
| `packaging/hpc/README.md` | Portable HPC submission workflow. |
| `outputs/README.md` | Output workspace convention. |
| `docs/runtime/` | Runtime notes. |
| `docs/data/` | Data and metadata notes. |
| `docs/release/` | Release policy notes. |
| `docs/algorithms/` | Algorithm notes. |

## Notes

- Do not commit large GRACE, GLDAS, Mascon, Hydroweb, boundary, intermediate, or generated output files.
- Keep Python and MATLAB aligned in inversion, low-degree replacement, filtering, basin statistics, leakage correction, and output metadata.
- Prefer `configs/` and `outputs/` for new workflows. Legacy `matlab/cfg/` and `output/` are compatibility paths only.
