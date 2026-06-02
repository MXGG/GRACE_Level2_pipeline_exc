"""Canonical basin-analysis exports."""

from grace_pipeline.basin import (
    BasinBoundary,
    compute_weighted_mean,
    extract_basin_ts,
    fit_seasonal_trend,
    make_mask,
    read_boundary,
)

__all__ = [
    "BasinBoundary",
    "read_boundary",
    "make_mask",
    "extract_basin_ts",
    "compute_weighted_mean",
    "fit_seasonal_trend",
]
