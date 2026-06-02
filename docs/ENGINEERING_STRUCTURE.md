# Engineering Structure Baseline

This repository is split into two language projects with shared data/output.

## Top-Level Layout

- `matlab/`: MATLAB project (`cfg/`, `src/`, `scripts/`, `hpc.ps1`)
- `python/`: Python project (`grace_pipeline/`, build scripts)
- `data/`: shared input datasets
- `output/`: shared runtime outputs (`local/` and `remote/<jobid>/`)
- `docs/`: design notes and reports
- `dist/`: built executables

## MATLAB Responsibilities

- `matlab/src/main`: orchestration only
- `matlab/src/io`: persistence only
- `matlab/src/inversion|filters|basin|leakage|metrics|plot`: domain modules
- `matlab/src/core`: shared utilities
- `matlab/src/tools`: third-party and low-level helpers
- `matlab/scripts/run|analysis|plot|audit|perf`: operational scripts by purpose

## Python Responsibilities

- `python/grace_pipeline/main`: orchestration only
- `python/grace_pipeline/services`: GUI/application service layer
- `python/grace_pipeline/core`: config/runtime/shared primitives
- `python/grace_pipeline/inversion|filters|io|metrics|basin|leakage|plot`: domain modules

## Interface Rules

- MATLAB file name must match primary function name.
- Avoid high-arity function signatures; prefer grouped config/state structs.
- Keep optional behavior controlled by config, not hidden side effects.
- Keep data stack shape consistent as `[nLon x nLat x Nt]`.

## Fast Audits

- `powershell -NoProfile -ExecutionPolicy Bypass -File matlab/scripts/audit/audit_repo_layout.ps1`
- `powershell -NoProfile -ExecutionPolicy Bypass -File matlab/scripts/audit/audit_cross_tree_scripts.ps1`
- `powershell -NoProfile -ExecutionPolicy Bypass -File matlab/scripts/audit/audit_python_functions.ps1`
- `powershell -NoProfile -ExecutionPolicy Bypass -File matlab/scripts/audit/audit_matlab_interfaces.ps1`

Report output:
- `docs/reports/matlab_interface_audit.txt`
