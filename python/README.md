# Python Guide

## Purpose

`python/` contains the current Python backend, command-line interface, GUI entrypoint, packaging scripts, and tests. The Python backend should use the same shared configuration files under `configs/` as the MATLAB backend.

## Core CLI install

The core CLI install is suitable for Windows, Linux, macOS, and HPC/headless environments. It intentionally avoids GUI-only dependencies such as PySide6.

Windows PowerShell:

```powershell
cd python
python -m pip install --upgrade pip
python -m pip install -e .
```

Linux/macOS:

```bash
cd python
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

## Runtime checks

Run the doctor command before a full processing run:

```powershell
grace-pipeline doctor -c ..\configs\user.json -d ..\configs\default.json
```

The standalone console script is equivalent:

```powershell
grace-pipeline-doctor -c ..\configs\user.json -d ..\configs\default.json
```

For GUI dependency checks, add `--gui` after installing the GUI extra.

## CLI run

```powershell
grace-pipeline info -c ..\configs\user.json -d ..\configs\default.json
grace-pipeline run  -c ..\configs\user.json -d ..\configs\default.json
```

Useful `run` options:

- `-c, --config PATH`
- `-d, --default-config PATH`
- `-o, --output PATH`
- `--start YYYY-MM`
- `--end YYYY-MM`
- `-j, --jobs N`
- `--no-parallel`
- `-v, --verbose`

## GUI source debugging

Install the GUI extra before starting the GUI from source:

```powershell
cd python
python -m pip install -e ".[gui]"
python -m grace_pipeline.gui_entry
```

or via the installed CLI:

```powershell
grace-pipeline gui
```

Linux users need a graphical session or suitable Qt backend. Headless Linux/HPC users should keep to the core CLI install.

## Build

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

Packaged executables are written to `../dist/`.

## Package layout

| Path | Purpose |
| --- | --- |
| `grace_pipeline/app` | Workflow orchestration and top-level runtime logic. |
| `grace_pipeline/domain` | Domain-facing import surface. |
| `grace_pipeline/infra` | Config, runtime, doctor checks, datasets, stack, and I/O infrastructure. |
| `grace_pipeline/ui` | GUI shell, controllers, and plotting. |
| `grace_pipeline/core` | Legacy implementation still used by some wrappers. |
| `grace_pipeline/compat` | Temporary compatibility shims. |
| `grace_pipeline/services` | Temporary migration surface for old imports. |

## Related documents

- `../README.md`
- `../configs/README.md`
- `../packaging/hpc/README.md`
- `grace_pipeline/compat/README.md`
- `grace_pipeline/services/README.md`
