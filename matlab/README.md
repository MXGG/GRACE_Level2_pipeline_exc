# MATLAB Guide

## Purpose

`matlab/` contains the production-oriented MATLAB backend, the shared configuration bridge, source modules under `src/`, and compatibility wrappers for older MATLAB-side run scripts.

## Layout

| Path | Purpose |
| --- | --- |
| `cfg/` | Legacy JSON configs and config helpers retained for compatibility. |
| `src/` | MATLAB source modules grouped by responsibility. |
| `scripts/` | Run, audit, analysis, plot, and performance scripts. |
| `hpc.ps1` | Compatibility wrapper that delegates to `packaging/hpc/hpc.ps1`. |
| `_legacy/` | Historical code kept only for reference. |

## Local run

Standard one-click entry from the repository root:

```matlab
run('matlab/src/main/run_oneclick.m')
```

Explicit shared configuration:

```matlab
addpath(genpath('matlab/src'));
OUT = run_oneclick_cfg('configs/user.json');
```

Manual setup for debugging:

```matlab
addpath(genpath('matlab/src'));
addpath('matlab/cfg');
cfg = cfg_load('configs/user.json', 'configs/default.json');
setup_env(cfg);
OUT = run_pipeline(cfg);
```

The MATLAB entries prefer `configs/user.json` and `configs/default.json`. `matlab/cfg/` remains a fallback during the staged migration.

## HPC usage

Use the canonical wrapper from the repository root:

```powershell
.\packaging\hpc\hpc.ps1 -Runtime matlab -Remote user@host -RemoteRoot /remote/path/GRACE_Level2_pipeline
```

The legacy `matlab/hpc.ps1` remains as a compatibility wrapper only.

Portable SLURM entry:

```text
packaging/hpc/slurm/run_matlab.slurm
```

Adjust SLURM partition, QoS, CPU count, wall time, and MATLAB module settings for the target cluster before production use.

## Module map

| Module | Purpose |
| --- | --- |
| `src/main/` | Pipeline orchestration and entrypoints. |
| `src/core/` | Runtime helpers, planning, indexing, checkpoints. |
| `src/inversion/` | GFC reading, low-degree replacement, EWH synthesis, GIA. |
| `src/filters/` | GAUSS, FAN, P4M6, DDK, and HSAF filters. |
| `src/io/` | Outputs, stacks, metadata, and logs. |
| `src/metrics/` | Reference comparison and evaluation. |
| `src/basin/` | Basin analysis and time-series extraction. |
| `src/leakage/` | Leakage correction workflows. |
| `src/plot/` | Figures and diagnostics. |
| `src/tools/` | Project helpers and vendored third-party tools. |

## Related documents

- `../README.md`
- `../configs/README.md`
- `../packaging/hpc/README.md`
- `matlab/cfg/README.md`
- `matlab/scripts/README.md`
- `matlab/src/main/README.md`
