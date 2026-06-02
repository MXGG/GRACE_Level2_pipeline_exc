"""
Fan (anisotropic) filter for spherical harmonic coefficients.

This follows the separable implementation used by the MATLAB pipeline:
Gaussian smoothing along degree, then recursive order smoothing.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, Tuple

import numpy as np

from grace_pipeline.filters.gaussian import filter_sh_gaussian


_EARTH_RADIUS_M = 6.378136460e6


@lru_cache(maxsize=32)
def _order_weights(radius_km: float, Lmax: int) -> np.ndarray:
    radius_km = float(radius_km)
    Lmax = int(Lmax)
    if radius_km <= 0:
        return np.ones(Lmax + 1, dtype=np.float64)

    radius_m = radius_km * 1000.0
    b = np.log(2.0) / (1.0 - np.cos(radius_m / _EARTH_RADIUS_M))

    weights = np.zeros(Lmax + 1, dtype=np.float64)
    weights[0] = 1.0
    if Lmax >= 1:
        weights[1] = (1.0 + np.exp(-2.0 * b)) / (1.0 - np.exp(-2.0 * b)) - (1.0 / b)
    for l in range(1, Lmax):
        weights[l + 1] = -((2.0 * l) + 1.0) / b * weights[l] + weights[l - 1]
    return weights


def filter_sh_fan(
    C: np.ndarray,
    S: np.ndarray,
    Lmax: int,
    radius1_km: float = 300.0,
    radius2_km: float = 300.0,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Apply fan filtering: degree Gaussian + order smoothing.
    """
    c_deg, s_deg, _ = filter_sh_gaussian(C, S, Lmax, radius1_km)
    w_order = _order_weights(radius2_km, Lmax)

    if np.ndim(c_deg) == 2:
        c_f = np.asarray(c_deg) * w_order[None, :]
        s_f = np.asarray(s_deg) * w_order[None, :]
    else:
        c_f = np.asarray(c_deg) * w_order[None, :, None]
        s_f = np.asarray(s_deg) * w_order[None, :, None]

    meta = {
        "type": "Fan",
        "radius1_km": float(radius1_km),
        "radius2_km": float(radius2_km),
        "w_order": w_order,
    }
    return c_f, s_f, meta
