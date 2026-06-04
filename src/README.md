# Source Layout

`src/` is the future canonical source root.

This migration is staged and non-destructive. The legacy roots `python/` and `matlab/` remain available until the copied source layout is verified.

## Target structure

```text
src/
├─ python/   # Python package, CLI, GUI, tests, and Python project metadata
└─ matlab/   # MATLAB backend, scripts, tests, and future +grace package namespace
```

## Python backend

The Python package already follows a layered architecture:

```text
grace_pipeline/
├─ app/      # application orchestration and use-case workflows
├─ domain/   # scientific algorithms
├─ infra/    # configuration, datasets, runtime, path and file I/O
├─ ui/       # GUI shell, controllers, widgets, plotting
└─ compat/   # temporary compatibility shims
```

The future source path is:

```text
src/python/grace_pipeline/
```

During migration, the legacy path remains:

```text
python/grace_pipeline/
```

## MATLAB backend

The current MATLAB backend is organized by responsibility:

```text
main/
core/
inversion/
filters/
io/
metrics/
basin/
leakage/
plot/
tools/
```

The future target is a MATLAB package namespace:

```text
src/matlab/+grace/+filters/
src/matlab/+grace/+inversion/
src/matlab/+grace/+basin/
```

Do not convert existing MATLAB functions to `+grace` namespace until the copied layout is validated.
