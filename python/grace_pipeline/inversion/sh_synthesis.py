"""
Spherical harmonic synthesis for regular lon/lat grids.

This module follows the fully-normalized real spherical harmonic convention
used by the MATLAB pipeline. Equivalent water height (EWH) synthesis applies
the Wahr et al. / ICGEM-style load Love number scaling before the spatial
transform.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Optional, Tuple

import numpy as np
from scipy.special import sph_harm_y


_EARTH_RADIUS_M = 6.378136460e6
_RHO_EARTH = 5517.0
_RHO_WATER = 1000.0
_LOVE_N = np.array(
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20, 30, 40, 50, 70, 100, 150, 200],
    dtype=np.float64,
)
_LOVE_K = np.array(
    [0, 0.027, -0.303, -0.194, -0.132, -0.104, -0.089, -0.081, -0.076, -0.072, -0.069,
     -0.064, -0.058, -0.051, -0.040, -0.033, -0.027, -0.020, -0.014, -0.010, -0.007],
    dtype=np.float64,
)


def _grid_key(values: np.ndarray) -> Tuple[float, ...]:
    return tuple(np.asarray(values, dtype=np.float64).ravel().tolist())


@lru_cache(maxsize=16)
def _load_love_numbers(Lmax: int) -> np.ndarray:
    n = np.arange(Lmax + 1, dtype=np.float64)
    love_k = np.interp(n, _LOVE_N, _LOVE_K)
    return (2.0 * n + 1.0) / (1.0 + love_k)


def _unit_factor(unit: str) -> float:
    key = str(unit or "mmEWH").strip().lower()
    if key in {"mmeqh", "mmewh", "mm"}:
        return 1000.0
    if key in {"cmeqh", "cmewh", "cm"}:
        return 100.0
    if key in {"m", "meqh", "mewh"}:
        return 1.0
    return 1000.0


def compute_legendre(l: int, m: int, cos_theta: np.ndarray) -> np.ndarray:
    """
    Compute fully-normalized associated Legendre functions in the real form.

    This mirrors MATLAB `legendre(..., 'norm')` with an additional `sqrt(2)`
    factor for non-zonal terms to match the real C/S synthesis used by the
    pipeline.
    """
    x = np.asarray(cos_theta, dtype=np.float64)
    theta = np.arccos(np.clip(x, -1.0, 1.0))
    y_lm = np.real(sph_harm_y(int(l), int(m), theta, 0.0))
    if m == 0:
        return math.sqrt(2.0 * math.pi) * y_lm
    return ((-1.0) ** m) * math.sqrt(4.0 * math.pi) * y_lm


@lru_cache(maxsize=8)
def _precompute_basis(
    Lmax: int,
    lon_key: Tuple[float, ...],
    lat_key: Tuple[float, ...],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    lon_vec = np.asarray(lon_key, dtype=np.float64)
    lat_vec = np.asarray(lat_key, dtype=np.float64)

    lon_rad = np.deg2rad(lon_vec)
    cos_theta = np.sin(np.deg2rad(lat_vec))

    degrees = np.arange(Lmax + 1, dtype=np.float64)
    cos_m = np.cos(np.outer(degrees, lon_rad))
    sin_m = np.sin(np.outer(degrees, lon_rad))

    pnm = np.zeros((Lmax + 1, Lmax + 1, lat_vec.size), dtype=np.float64)
    for l in range(Lmax + 1):
        for m in range(l + 1):
            pnm[l, m, :] = compute_legendre(l, m, cos_theta)

    return pnm, cos_m, sin_m


def precompute_legendre_matrix(Lmax: int, nlat: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compatibility helper used by a few auxiliary scripts.

    Returns a flattened [nLat, nCoeff] matrix and latitude radians.
    """
    lat = np.linspace(-90.0, 90.0, int(nlat), dtype=np.float64)
    lat_rad = np.deg2rad(lat)
    cos_theta = np.sin(lat_rad)
    n_coeffs = (Lmax + 1) * (Lmax + 2) // 2
    plm = np.zeros((lat.size, n_coeffs), dtype=np.float64)

    idx = 0
    for l in range(Lmax + 1):
        for m in range(l + 1):
            plm[:, idx] = compute_legendre(l, m, cos_theta)
            idx += 1

    return plm, lat_rad


def sh_synthesis(
    C: np.ndarray,
    S: np.ndarray,
    Lmax: int,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    degree_weights: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Synthesize a spatial grid from fully-normalized Stokes coefficients.

    Returns a grid with shape [nLon, nLat].
    """
    lon_arr = np.asarray(lon_vec, dtype=np.float64).ravel()
    lat_arr = np.asarray(lat_vec, dtype=np.float64).ravel()
    l1 = int(Lmax) + 1

    c = np.asarray(C, dtype=np.float64)[:l1, :l1]
    s = np.asarray(S, dtype=np.float64)[:l1, :l1]

    if degree_weights is None:
        weights = np.ones(l1, dtype=np.float64)
    else:
        weights = np.asarray(degree_weights, dtype=np.float64).ravel()[:l1]

    pnm, cos_m, sin_m = _precompute_basis(Lmax, _grid_key(lon_arr), _grid_key(lat_arr))
    weighted_c = c * weights[:, None]
    weighted_s = s * weights[:, None]

    grid_lat_lon = (
        np.einsum("lmk,mn->kn", pnm * weighted_c[:, :, None], cos_m, optimize=True)
        + np.einsum("lmk,mn->kn", pnm * weighted_s[:, :, None], sin_m, optimize=True)
    )
    return np.ascontiguousarray(grid_lat_lon.T)


def plm2xyz(
    C: np.ndarray,
    S: np.ndarray,
    Lmax: int,
    lon_vec: Optional[np.ndarray] = None,
    lat_vec: Optional[np.ndarray] = None,
    degres: float = 1.0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compatibility wrapper matching the MATLAB-oriented API.
    """
    if lon_vec is None:
        lon_vec = np.arange(-179.5, 180.0, float(degres), dtype=np.float64)
    if lat_vec is None:
        lat_vec = np.arange(-89.5, 90.0, float(degres), dtype=np.float64)

    grid = sh_synthesis(C, S, Lmax, lon_vec, lat_vec)
    return grid, np.asarray(lon_vec), np.asarray(lat_vec)


def sh_synthesis_fast(
    C: np.ndarray,
    S: np.ndarray,
    Lmax: int,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
) -> np.ndarray:
    """
    Deterministic fast path used by the pipeline.

    The cached basis + vectorized einsum implementation is both faster than
    the old pure-Python loops and numerically aligned with the MATLAB code.
    """
    return sh_synthesis(C, S, Lmax, lon_vec, lat_vec)


def ewh_synthesis(
    C: np.ndarray,
    S: np.ndarray,
    Lmax: int,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    love_numbers: Optional[np.ndarray] = None,
    unit: str = "mmEWH",
) -> np.ndarray:
    """
    Synthesize Equivalent Water Height (EWH) from Stokes coefficients.

    The scaling follows Wahr et al. (1998) using interpolated load Love
    numbers and the same constants/table as the MATLAB pipeline.
    """
    if love_numbers is None:
        love_n = _load_love_numbers(Lmax)
    else:
        love_n = np.asarray(love_numbers, dtype=np.float64).ravel()[: Lmax + 1]

    base_scale = _EARTH_RADIUS_M * _RHO_EARTH / (3.0 * _RHO_WATER)
    degree_weights = base_scale * _unit_factor(unit) * love_n
    return sh_synthesis(C, S, Lmax, lon_vec, lat_vec, degree_weights=degree_weights)


def sh_analysis(
    grid: np.ndarray,
    Lmax: int,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    degree_weights: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Estimate fully-normalized real Stokes coefficients from a lon/lat grid.

    The inverse uses the same basis as :func:`sh_synthesis`: regular-longitude
    Fourier projection followed by latitude weighted least squares for each
    order. It returns coefficient matrices shaped [Lmax+1, Lmax+1].
    """
    lon_arr = np.asarray(lon_vec, dtype=np.float64).ravel()
    lat_arr = np.asarray(lat_vec, dtype=np.float64).ravel()
    grid_arr = np.asarray(grid, dtype=np.float64)
    if grid_arr.shape == (lat_arr.size, lon_arr.size):
        grid_arr = grid_arr.T
    if grid_arr.shape != (lon_arr.size, lat_arr.size):
        raise ValueError("SH analysis grid must be shaped [nLon x nLat].")
    if lon_arr.size < (2 * int(Lmax) + 1):
        raise ValueError("Longitude grid is too coarse for the requested SH degree.")
    if lat_arr.size < int(Lmax) + 1:
        raise ValueError("Latitude grid is too coarse for the requested SH degree.")

    l1 = int(Lmax) + 1
    if degree_weights is None:
        weights = np.ones(l1, dtype=np.float64)
    else:
        weights = np.asarray(degree_weights, dtype=np.float64).ravel()[:l1]
    weights = np.where(np.abs(weights) > np.finfo(np.float64).eps, weights, np.nan)

    g = np.where(np.isfinite(grid_arr), grid_arr, 0.0)
    pnm, cos_m, sin_m = _precompute_basis(int(Lmax), _grid_key(lon_arr), _grid_key(lat_arr))

    lon_alpha = np.full(l1, 2.0 / max(1, lon_arr.size), dtype=np.float64)
    lon_alpha[0] = 1.0 / max(1, lon_arr.size)
    a_m = (cos_m @ g) * lon_alpha[:, None]
    b_m = (sin_m @ g) * lon_alpha[:, None]

    lat_w = np.cos(np.deg2rad(lat_arr))
    lat_w = np.where(np.isfinite(lat_w), np.maximum(lat_w, 1.0e-12), 1.0e-12)
    lat_w_sqrt = np.sqrt(lat_w)

    C = np.zeros((l1, l1), dtype=np.float64)
    S = np.zeros((l1, l1), dtype=np.float64)
    for m in range(l1):
        design = pnm[m:, m, :].T * lat_w_sqrt[:, None]
        y_c = a_m[m, :] * lat_w_sqrt
        y_s = b_m[m, :] * lat_w_sqrt
        q_c, *_ = np.linalg.lstsq(design, y_c, rcond=None)
        q_s, *_ = np.linalg.lstsq(design, y_s, rcond=None)
        C[m:, m] = q_c / weights[m:]
        if m > 0:
            S[m:, m] = q_s / weights[m:]
    C[~np.isfinite(C)] = 0.0
    S[~np.isfinite(S)] = 0.0
    return C, S


def ewh_analysis(
    grid: np.ndarray,
    Lmax: int,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    love_numbers: Optional[np.ndarray] = None,
    unit: str = "mmEWH",
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Estimate Stokes coefficients from an EWH grid using synthesis parity.
    """
    if love_numbers is None:
        love_n = _load_love_numbers(Lmax)
    else:
        love_n = np.asarray(love_numbers, dtype=np.float64).ravel()[: Lmax + 1]
    base_scale = _EARTH_RADIUS_M * _RHO_EARTH / (3.0 * _RHO_WATER)
    degree_weights = base_scale * _unit_factor(unit) * love_n
    return sh_analysis(grid, Lmax, lon_vec, lat_vec, degree_weights=degree_weights)
