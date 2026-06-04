# GRACE Level-2 Pipeline

[中文说明](README.zh-CN.md)

A MATLAB/Python processing workspace for GRACE/GRACE-FO Level-2 spherical harmonic products. The project supports spherical harmonic inversion, low-degree replacement, GIA correction, Gaussian/Fan/decorrelation/DDK/HSAF filtering, basin-scale TWSA extraction, leakage correction, diagnostics, Windows desktop usage, Linux batch execution, and HPC submission.

This repository is currently in a staged layout migration. The legacy `python/`, `matlab/`, `installer/`, and `output/` paths are kept for compatibility. New commands and documentation should prefer `configs/`, `src/`, `packaging/`, and `outputs/`.

## Repository layout

| Path | Purpose |
| --- | --- |
| `configs/` | Shared JSON configurations for Python and MATLAB. |
| `src/python/` | Future canonical Python backend location. |
| `src/matlab/` | Future canonical MATLAB backend location. |
| `python/` | Legacy Python backend, kept during migration. |
| `matlab/` | Legacy MATLAB backend, kept during migration. |
| `data/` | Local input data workspace. Large data are not tracked. |
| `outputs/` | Canonical runtime outputs. Generated outputs are not tracked. |
| `packaging/` | Windows, Linux, installer, release, and HPC packaging helpers. |
| `docs/` | User, developer, runtime, data, release, and algorithm notes. |
| `examples/` | Small reproducible examples. |
| `archive/` | Historical or deprecated materials. |

## Configuration

Use `configs/` as the shared configuration root.

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

Typical layout:

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

## Python: install and run

Legacy path, currently safest:

```powershell
cd python
python -m pip install -e .
grace-pipeline info -c ..\configs\user.json -d ..\configs\default.json
grace-pipeline run  -c ..\configs\user.json -d ..\configs\default.json
```

Future staged path after copying the source layout locally:

```powershell
.\scripts\dev\stage_repository_layout.ps1
cd src\python
python -m pip install -e .
grace-pipeline info -c ..\..\configs\user.json -d ..\..\configs\default.json
grace-pipeline run  -c ..\..\configs\user.json -d ..\..\configs\default.json
```

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

## Python GUI debugging

Legacy path:

```powershell
cd python
python -m grace_pipeline.gui_entry
```

Future staged path:

```powershell
cd src\python
python -m grace_pipeline.gui_entry
```

## MATLAB local run

Legacy path, currently safest:

```matlab
run('matlab/src/main/run_oneclick.m')
```

Explicit configuration entry, if available in your local checkout:

```matlab
addpath(genpath('matlab/src'));
OUT = run_oneclick_cfg('configs/user.json');
```

Future staged path after copying:

```matlab
addpath(genpath('src/matlab/src'));
OUT = run_oneclick_cfg('configs/user.json');
```

## Linux batch usage

Python CLI:

```bash
cd python
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
grace-pipeline run -c ../configs/user.json -d ../configs/default.json
```

MATLAB batch:

```bash
matlab -batch "run('matlab/src/main/run_oneclick.m')"
```

## HPC submission

Canonical wrapper:

```powershell
.\packaging\hpc\hpc.ps1 -Runtime python -ConfigPath configs\user.json -DefaultConfigPath configs\default.json
.\packaging\hpc\hpc.ps1 -Runtime matlab -ConfigPath configs\user.json -DefaultConfigPath configs\default.json
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
```

## Build and packaging

Current legacy Python build scripts remain under `python/`.

```powershell
cd python
.\build.ps1
```

Linux:

```bash
cd python
bash build.sh
```

The canonical packaging area is `packaging/`. Build scripts will be migrated there in a later cleanup pass.

## Layout staging

To copy legacy source trees into the staged layout without deleting the original files:

Windows:

```powershell
.\scripts\dev\stage_repository_layout.ps1
```

Linux/macOS:

```bash
bash scripts/dev/stage_repository_layout.sh
```

This copies:

```text
python/      -> src/python/
matlab/      -> src/matlab/
installer/   -> packaging/windows/installer/legacy-installer/
output/      -> outputs/legacy-output/
```

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
| `outputs/README.md` | Output workspace convention. |
| `docs/runtime/` | Runtime notes. |
| `docs/data/` | Data and metadata notes. |
| `docs/release/` | Release policy notes. |
| `docs/algorithms/` | Algorithm notes. |

## Notes

- Do not commit large GRACE, GLDAS, Mascon, Hydroweb, boundary, intermediate, or generated output files.
- Keep Python and MATLAB aligned in inversion, low-degree replacement, filtering, basin statistics, leakage correction, and output metadata.
- Prefer `configs/` for all new commands. Legacy `matlab/cfg/` is retained only for compatibility during migration.
