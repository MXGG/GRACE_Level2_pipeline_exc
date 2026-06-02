# Repository Structure

## Top-level
- `python/`: Python project (GUI + pipeline runtime)
- `matlab/`: MATLAB project (HPC/SLURM workflows)
- `data/`: shared input/reference data
- `output/`: runtime outputs (`local/`, `remote/<jobid>/`)
- `docs/`: engineering and architecture docs
- `_archive/`: legacy/retired assets

## Python project (`python/`)
- `grace_pipeline/`: application package
- `grace_pipeline/ui/gui_app.py`: concrete GUI implementation
- `grace_pipeline/gui.py`: GUI public interface only (re-export)
- `grace_pipeline/services/`: service layers (`ui/`, `workflows/`, `adapters/`)
- `grace_pipeline/services/adapters/gui/`: non-UI GUI helper subpackage

## MATLAB project (`matlab/`)
- `cfg/`: JSON config templates and run configs
- `src/`: core MATLAB modules by domain
- `scripts/run/`: SLURM entry scripts
- `scripts/audit/`: structure/interface audit scripts

## Rules
- Keep GUI script (`grace_pipeline/gui.py`) as interface layer only.
- Keep implementation logic in service/adapters/workflows modules.
- Keep generated artifacts (`build/`, `dist/`, virtualenv, outputs, caches) out of source structure.

