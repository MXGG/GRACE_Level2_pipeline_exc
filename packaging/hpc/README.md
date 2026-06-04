# HPC Submission

This directory contains the canonical HPC submission workflow for the GRACE Level-2 Pipeline.

The workflow is intentionally environment-agnostic. Cluster-specific details such as partition, QoS, CPU count, wall time, MATLAB module names, and Python environment paths must be adjusted before production use.

## Entry point

Run from the repository root on the local workstation:

```powershell
.\packaging\hpc\hpc.ps1 `
  -Runtime python `
  -Remote user@host `
  -RemoteRoot /remote/path/GRACE_Level2_pipeline `
  -ConfigPath configs/user.json `
  -DefaultConfigPath configs/default.json
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

## Portable SLURM scripts

| Script | Runtime |
| --- | --- |
| `packaging/hpc/slurm/run_python.slurm` | Python CLI backend |
| `packaging/hpc/slurm/run_matlab.slurm` | MATLAB backend |

These scripts read runtime paths from environment variables set by `hpc.ps1`:

| Variable | Purpose |
| --- | --- |
| `GRACE_REMOTE_ROOT` | Remote project root. |
| `GRACE_USER_CONFIG` | User config path relative to remote root, or absolute remote path. |
| `GRACE_DEFAULT_CONFIG` | Default config path relative to remote root, or absolute remote path. |
| `GRACE_OUTPUT_ROOT` | Output root. Defaults to `<remote-root>/outputs`. |
| `GRACE_PYTHON_BIN` | Python executable for Python runtime. |
| `GRACE_MATLAB_BIN` | MATLAB executable for MATLAB runtime. |
| `GRACE_MATLAB_MODULE` | Optional environment module name for MATLAB. |

## Sync mode

`-SyncMode auto` uses git when a git remote exists, otherwise falls back to scp. For isolated clusters or early testing, use:

```powershell
.\packaging\hpc\hpc.ps1 -Runtime python -Remote user@host -SyncMode scp
```

The scp mode uploads the runtime directories required for submission, including `configs/`, `python/`, `matlab/`, `packaging/`, and selected documentation files.

## Before production use

Review and update the SLURM headers for the target cluster:

```bash
#SBATCH --partition=<partition>
#SBATCH --qos=<qos>
#SBATCH --cpus-per-task=<n>
#SBATCH --time=<hh:mm:ss>
```

For MATLAB clusters that use modules, set the module at submission time:

```powershell
$env:GRACE_MATLAB_MODULE = "app/matlab/2023a"
```

or edit the remote SLURM script to load the proper module.

## Validation

Python runtime performs a preflight check before running the pipeline:

```bash
python3 -m grace_pipeline.infra.doctor -c configs/user.json -d configs/default.json
```

A failed required check stops the SLURM job before long-running processing begins.
