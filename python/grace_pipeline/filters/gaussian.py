"""
Gaussian smoothing for spherical harmonic coefficients.

The implementation follows the recursive degree-weight construction used by
the MATLAB pipeline and common GRACE processing toolchains.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, Tuple

import numpy as np


_EARTH_RADIUS_M = 6.378136460e6


@lru_cache(maxsize=32)
def gaussian_weights(radius_km: float, Lmax: int) -> np.ndarray:
    """
    Compute degree-only Gaussian weights for degrees 0..Lmax.
    """
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


def filter_sh_gaussian(
    C: np.ndarray,
    S: np.ndarray,
    Lmax: int,
    radius_km: float,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Apply degree-only Gaussian smoothing.
    """
    weights = gaussian_weights(radius_km, Lmax)

    if np.ndim(C) == 2:
        c_f = np.asarray(C) * weights[:, None]
        s_f = np.asarray(S) * weights[:, None]
    else:
        c_f = np.asarray(C) * weights[:, None, None]
        s_f = np.asarray(S) * weights[:, None, None]

    meta = {
        "type": "Gaussian",
        "radius_km": float(radius_km),
        "w_degree": weights,
    }
    return c_f, s_f, meta


def apply_gaussian_filter(
    radius_km: float,
    Lmax: int,
    C: np.ndarray,
    S: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compatibility wrapper.
    """
    c_f, s_f, meta = filter_sh_gaussian(C, S, Lmax, radius_km)
    return c_f, s_f, meta["w_degree"]
