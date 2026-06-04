# HPC Packaging and Submission Helpers

This directory is the canonical location for Windows-to-HPC and SLURM submission helpers.

The current migration is non-destructive. Existing root-level and MATLAB-side HPC scripts are kept in place. During the staged migration, use the compatibility wrappers here or run the legacy scripts directly.

## Recommended future command

```powershell
.\packaging\hpc\hpc.ps1 -Runtime python -ConfigPath configs\user.json -DefaultConfigPath configs\default.json
.\packaging\hpc\hpc.ps1 -Runtime matlab -ConfigPath configs\user.json -DefaultConfigPath configs\default.json
```

## Migration note

The legacy default configuration paths were:

```text
matlab/cfg/user.json
matlab/cfg/default.json
```

The canonical paths are now:

```text
configs/user.json
configs/default.json
```

Full HPC sync logic should eventually sync:

```text
configs/
src/python/
src/matlab/
docs/
```

and pull back outputs from:

```text
outputs/remote/<jobid>/
outputs/logs/
```
