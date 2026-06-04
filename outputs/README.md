# Outputs Workspace

`outputs/` is the canonical runtime output directory for local, remote, figure, and log products.

Generated outputs should not be committed.

## Layout

```text
outputs/
├─ local/       # local runs
├─ remote/      # HPC runs pulled back by job id
├─ figures/     # exported figures and diagnostics
└─ logs/        # runtime logs
```

## Recommended run layout

```text
outputs/local/<run_id>/
├─ grids/
├─ basin/
├─ leakage/
├─ figures/
├─ logs/
└─ metadata.json
```

`metadata.json` should record software version, Git commit, backend, platform, configuration hash, input manifest, and output convention.
