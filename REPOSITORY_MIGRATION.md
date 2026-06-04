# Repository Layout Migration Plan

This document defines the staged repository reorganization for the GRACE Level-2 Pipeline.

The migration is intentionally non-destructive. Existing source directories such as `python/`, `matlab/`, `installer/`, `output/`, and root-level helper scripts are not deleted in this phase. New standardized directories are introduced first, then runtime paths and documentation can be switched gradually.

## Target layout

```text
GRACE_Level2_pipeline_exc/
├─ configs/                 # shared JSON configuration for Python and MATLAB
├─ src/
│  ├─ python/               # future canonical Python backend location
│  └─ matlab/               # future canonical MATLAB backend location
├─ packaging/
│  ├─ windows/              # Windows Python/MATLAB packaging and installer files
│  ├─ linux/                # Linux Python/MATLAB packaging and batch helpers
│  └─ hpc/                  # Windows-to-HPC and SLURM helpers
├─ data/                    # input data workspace; large data are not tracked
├─ outputs/                 # runtime outputs; large generated files are not tracked
├─ docs/                    # user, developer, data, runtime, release, and algorithm docs
├─ examples/                # small reproducible examples
└─ archive/                 # deprecated or historical materials
```

## Migration policy

1. Do not delete existing source files in the first migration phase.
2. Copy source directories into the new layout only after the migration scripts have been reviewed.
3. Keep root-level wrappers temporarily so existing user commands remain valid.
4. Move shared configuration out of `matlab/cfg/` conceptually and use `configs/` as the canonical configuration root.
5. Treat `src/python/` and `src/matlab/` as the future canonical source roots.
6. Treat `packaging/` as the only place for build, installer, release, and HPC deployment scripts.

## Phase 1: safe scaffolding

- Create `configs/`, `src/`, `packaging/`, `outputs/`, `examples/`, and additional documentation directories.
- Add non-destructive staging scripts under `scripts/dev/`.
- Add shared configuration templates under `configs/`.
- Add wrapper scripts under `packaging/` that detect both new and legacy paths.

## Phase 2: copy source trees

Run one of the following from the repository root:

```powershell
.\scripts\dev\stage_repository_layout.ps1
```

or

```bash
bash scripts/dev/stage_repository_layout.sh
```

These scripts copy existing source trees into the new layout without deleting the original paths.

## Phase 3: path switch

After the copied layout is verified:

- update README commands to use `src/python`, `src/matlab`, `configs`, and `outputs`;
- update Python build scripts to use `src/python` as the package root;
- update MATLAB entry scripts to read `configs/default.json` and `configs/user.json`;
- update HPC scripts to sync `configs`, `src/python`, `src/matlab`, and `docs`.

## Phase 4: cleanup

Only after validation and one release cycle should legacy root paths be considered for removal. This step is intentionally outside the current migration phase.
