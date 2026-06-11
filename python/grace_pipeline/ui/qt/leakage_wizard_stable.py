"""Stable entry point for the simplified leakage wizard."""

from __future__ import annotations

from grace_pipeline.ui.qt import leakage_wizard as base

EXTRA_REUSED_WIDGET_ATTRS = (
    "edit_coastal_buffer_cells",
    "edit_coastal_attenuation_gain",
    "edit_regularized_lambda",
    "edit_regularized_step_size",
    "edit_regularized_sigma",
    "edit_regularized_iter",
    "edit_lrc_edge_buffer",
    "edit_lrc_sf_fan_r1",
    "edit_lrc_sf_fan_r2",
    "edit_lrc_sf_hsa_ts",
    "edit_lrc_sf_p4_deg",
    "edit_lrc_sf_p4_m",
    "edit_lrc_sf_grid",
    "edit_lrc_sf_hsa_window",
    "edit_lrc_sf_hsa_p",
    "edit_lrc_sf_hsa_order",
    "edit_lrc_sf_hsa_buffer",
    "edit_lrc_toolbox",
    "edit_lrc_aux_global",
    "edit_lrc_aux_region",
    "edit_lrc_matlab",
)


def install_leakage_wizard(window) -> None:
    existing = tuple(getattr(base, "_REUSED_WIDGET_ATTRS", ()))
    base._REUSED_WIDGET_ATTRS = tuple(dict.fromkeys(existing + EXTRA_REUSED_WIDGET_ATTRS))
    base.install_leakage_wizard(window)
