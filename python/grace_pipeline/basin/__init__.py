"""
Basin analysis module.
"""

from grace_pipeline.basin.boundary import BasinBoundary, read_boundary
from grace_pipeline.basin.mask import make_mask
from grace_pipeline.basin.timeseries import extract_basin_ts, compute_weighted_mean
from grace_pipeline.basin.fitting import fit_seasonal_trend

__all__ = [
    "BasinBoundary",
    "read_boundary",
    "make_mask",
    "extract_basin_ts",
    "compute_weighted_mean",
    "fit_seasonal_trend",
]
