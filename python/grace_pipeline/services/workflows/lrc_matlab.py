"""Compatibility shim for canonical app.lrc_matlab."""

from grace_pipeline.app.lrc_matlab import compute_sf_via_matlab, ensure_sf_wrapper, run_fm_correction

__all__ = ["ensure_sf_wrapper", "compute_sf_via_matlab", "run_fm_correction"]
