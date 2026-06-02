# Python Architecture

Canonical package layout under `python/grace_pipeline/`:

- `app/`: application orchestration and use-case workflows
- `domain/`: scientific/domain algorithms
- `infra/`: configuration, runtime, datasets, stack loading, file I/O
- `ui/`: Tk GUI shell, controllers, widgets, plotting, tab adapters
- `compat/`: temporary compatibility shims only

Import rules:

- `app/` may depend on `domain/` and `infra/`.
- `domain/` must stay free of GUI and compat imports.
- `infra/` must not depend on `ui/` or `compat/`.
- `ui/` may depend on `app/`, `infra/`, and `domain/` only through canonical modules.
- New canonical code must not import from root `services/*.py`, `main/`, or `ui/gui_app.py`.

Compatibility policy:

- `grace_pipeline.main.pipeline` remains as a shim to `grace_pipeline.app.pipeline`.
- `grace_pipeline.ui.gui_app` remains as a shim to `grace_pipeline.ui.app`.
- Legacy root wrappers are retained for one migration cycle and must not gain new business logic.
