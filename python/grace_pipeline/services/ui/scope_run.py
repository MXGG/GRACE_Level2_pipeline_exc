"""Compatibility shim for canonical ui.controllers.scope_runs."""

from grace_pipeline.ui.controllers.scope_runs import on_run_basin, on_run_leakage

__all__ = ["on_run_basin", "on_run_leakage"]
