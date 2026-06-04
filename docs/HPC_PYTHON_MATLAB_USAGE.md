# HPC Python/MATLAB Usage

## Goal

Provide a portable local entrypoint for submitting either the Python or MATLAB backend to a SLURM cluster.

Canonical entry from the repository root:

```powershell
.\packaging\hpc\hpc.ps1
```

The compatibility wrapper `hpc.ps1` is kept at the repository root, but new documentation should prefer `packaging/hpc/hpc.ps1`.

## Supported backends

- `matlab`: submits `packaging/hpc/slurm/run_matlab.slurm`
- `python`: submits `packaging/hpc/slurm/run_python.slurm`

If `-SlurmScript` is omitted, `hpc.ps1` selects the correct default script from `-Runtime`.

## Common usage

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

Python backend with explicit SSH port and scp sync:

```powershell
.\packaging\hpc\hpc.ps1 `
  -Runtime python `
  -Remote user@host `
  -RemotePort 22 `
  -RemoteRoot /remote/path/GRACE_Level2_pipeline `
  -SyncMode scp
```

## What the wrapper does

1. Synchronizes source files through git or scp.
2. Checks the remote worktree, config files, and SLURM script.
3. Submits the selected backend with `sbatch`.
4. Optionally polls `squeue` until the job ends.
5. Optionally pulls outputs and logs back to `outputs/remote/<jobid>/`.

When no local git remote is configured, `SyncMode=auto` falls back to `scp`.

## Remote runtime details

### MATLAB

The MATLAB SLURM script reads:

- `GRACE_REMOTE_ROOT`
- `GRACE_USER_CONFIG`
- `GRACE_DEFAULT_CONFIG`
- `GRACE_OUTPUT_ROOT`
- `GRACE_MATLAB_BIN`
- `GRACE_MATLAB_MODULE` when a cluster module is needed

### Python

The Python SLURM script reads:

- `GRACE_REMOTE_ROOT`
- `GRACE_USER_CONFIG`
- `GRACE_DEFAULT_CONFIG`
- `GRACE_OUTPUT_ROOT`
- `GRACE_PYTHON_BIN`

It prefers these interpreters in order:

1. `python/.venv-hpc/bin/python`
2. `python/.venv/bin/python`
3. `-PythonBin` value, default `python3`

The Python job runs a preflight check before the full pipeline:

```bash
python -m grace_pipeline.infra.doctor -c configs/user.json -d configs/default.json
```

## Output layout

- remote runs: `outputs/remote/<jobid>/...`
- logs: `outputs/logs/grace_<jobid>.out` and `.err`
- local pull-back target: `outputs/remote/<jobid>/`

## Notes

- No GUI-side HPC button is required; the cluster is headless.
- Edit SLURM partition, QoS, wall time, CPU count, and module loading for each cluster.
- Python and MATLAB jobs inherit the same shared config files under `configs/`.
