# HPC Python/Matlab Usage

## Goal

Keep the local entrypoint unchanged while allowing either MATLAB or Python to run on the cluster.

The user-facing entry remains:

```powershell
.\hpc.ps1
```

The only new switch is `-Runtime`.

## Supported backends

- `matlab`: submits `matlab/scripts/run/run.slurm`
- `python`: submits `matlab/scripts/run/run_python.slurm`

If `-SlurmScript` is omitted, `hpc.ps1` selects the correct default script from `-Runtime`.

The helper also supports:

- `-Remote`: explicit SSH target such as `um202370130@202.114.0.141`
- `-RemotePort`: explicit SSH port such as `21150`
- `-SyncMode auto|git|scp`: choose how code is synchronized before submission

## Common usage

MATLAB backend:

```powershell
.\hpc.ps1 -Runtime matlab
```

Python backend:

```powershell
.\hpc.ps1 -Runtime python
```

Python backend with an explicit config:

```powershell
.\hpc.ps1 -Runtime python -ConfigPath "matlab/cfg/user.json" -DefaultConfigPath "matlab/cfg/default.json"
```

Python backend with a custom interpreter name:

```powershell
.\hpc.ps1 -Runtime python -PythonBin "python3"
```

Python backend with explicit host, port, and file sync:

```powershell
.\hpc.ps1 -Runtime python -Remote "um202370130@202.114.0.141" -RemotePort 21150 -SyncMode scp
```

## What `hpc.ps1` now does

1. synchronize code via `git push` or `scp`
2. check the remote worktree, config files, and SLURM script
3. submit the selected backend with `sbatch`
4. poll `squeue` until the job ends
5. pull results and logs back into `output/remote/<jobid>/`

This keeps the interface close to the current desktop workflow: configure locally, submit once, and inspect pulled-back results locally.

When no local `git remote` is configured, `SyncMode=auto` falls back to `scp` automatically.

## Remote runtime details

### MATLAB

- still uses `matlab/scripts/run/run.slurm`
- `run_oneclick.m` now accepts:
  - `GRACE_USER_CONFIG`
  - `GRACE_DEFAULT_CONFIG`

### Python

- uses `matlab/scripts/run/run_python.slurm`
- runs:

```bash
python -m grace_pipeline.cli run -c <user-config> -d <default-config> -j 52 -v
```

- prefers these interpreters in order:
  1. `python/.venv-hpc/bin/python`
  2. `python/.venv/bin/python`
  3. `-PythonBin` value, default `python3`

- on the current HPC setup, the recommended runtime is the standalone environment at:
  - `/home/um202370130/GRACE_Level2_pipeline/python/.venv-hpc`

## Output layout

- remote runs: `output/remote/<jobid>/...`
- logs: `output/logs/grace_<jobid>.out` and `.err`
- local pull-back target: `output/remote/<jobid>/`

## Notes

- No GUI-side HPC button is needed; the cluster is headless.
- The design goal is a single easy local command with a backend switch, not a separate workflow.
- Python jobs inherit the same config files as MATLAB jobs, so the operational surface stays small.
