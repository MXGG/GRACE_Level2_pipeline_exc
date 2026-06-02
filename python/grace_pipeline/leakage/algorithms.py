"""
Built-in leakage correction algorithms (SF/FM).

The FM/SF forward operator follows the same core chain used in the
reference MATLAB scripts:
grid -> SH analysis (truncate Lmax) -> same filter -> synthesis.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from scipy.ndimage import binary_dilation, gaussian_filter
from scipy.special import gammaln, lpmv

from grace_pipeline.core.config import get_data_dir, get_root_dir
from grace_pipeline.core.grid import ensure_latlon_order
from grace_pipeline.filters.ddk import filter_sh_ddk
from grace_pipeline.filters.fan import filter_sh_fan
from grace_pipeline.filters.gaussian import filter_sh_gaussian
from grace_pipeline.filters.hsaf import filter_grid_hsaf_matlab
from grace_pipeline.filters.p4m6 import filter_sh_p4m6


@dataclass
class LeakageFilterOptions:
    method: str = "GAUSSIAN"
    gaussian_km: float = 300.0
    fan_r1_km: float = 300.0
    fan_r2_km: float = 300.0
    ddk_type: str = "DDK4"
    ddk_data_dir: str = ""
    hsaf_params: Optional[Dict] = None
    hsaf_ts: float = 1.0
    hsaf_input: str = "P4M6"
    p4m6_poly_deg: int = 4
    p4m6_m_start: int = 6
    lmax: int = 60


@dataclass
class LeakageOperatorSpec:
    product_type: str = "grid_stack"
    method: str = "GAUSSIAN"
    ddk_type: str = "DDK4"
    filter_family: str = "gaussian"
    is_gaussian_equivalent: bool = True
    native_gain_applied: bool = False
    product_native_correction: str = "none"
    source: str = "user"
    notes: List[str] = field(default_factory=list)


@dataclass
class LeakageScene:
    scene: str = "inland_basin"
    recommended_method: str = "FORWARD_MODELING"
    mask_fraction: float = 0.0
    land_fraction: float = 1.0
    coastal_fraction: float = 0.0
    high_lat_fraction: float = 0.0
    bbox: Dict[str, float] = field(default_factory=dict)
    reasoning: List[str] = field(default_factory=list)


@dataclass
class LeakageValidationReport:
    regional_series_raw: Optional[np.ndarray] = None
    regional_series_corrected: Optional[np.ndarray] = None
    regional_series_reference: Optional[np.ndarray] = None
    representative_index: int = 0
    residual_metric_by_month: Optional[np.ndarray] = None
    convergence_by_month: Optional[np.ndarray] = None
    flags: List[str] = field(default_factory=list)


@dataclass
class LeakageResult:
    method: str = "FORWARD_MODELING"
    corrected_stack: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    validation: LeakageValidationReport = field(default_factory=LeakageValidationReport)
    default_preview_asset: str = ""
    preview_collection: Dict[str, Any] = field(default_factory=dict)
    result_dimensions: Dict[str, Any] = field(default_factory=dict)


@dataclass
class _SHBasis:
    Lmax: int
    lon_vec: np.ndarray
    lat_vec: np.ndarray
    cos_m_lon: np.ndarray
    sin_m_lon: np.ndarray
    lon_alpha: np.ndarray
    lat_w_sqrt: np.ndarray
    pnm_by_m: List[np.ndarray]
    pinv_by_m: List[np.ndarray]


def _normalize_method(method: str) -> str:
    m = str(method or "").strip().upper().replace(" ", "_")
    if not m:
        return "GAUSSIAN"
    aliases = {
        "SF": "GAUSSIAN",
        "HANKEL": "HSAF",
        "PNMM": "P4M6",
        "P4M6_DECORRELATION": "P4M6",
        "DECORRELATION": "P4M6",
    }
    return aliases.get(m, m)


def normalize_correction_method(method: str) -> str:
    m = str(method or "").strip().upper().replace(" ", "_")
    aliases = {
        "ITERATIVE": "ITERATIVE",
        "ITERATIVE_WAHR": "ITERATIVE",
        "WAHR_1998": "ITERATIVE",
        "WAHR_ITERATIVE": "ITERATIVE",
        "FM": "FORWARD_MODELING",
        "FORWARD": "FORWARD_MODELING",
        "FORWARD_MODEL": "FORWARD_MODELING",
        "CHEN_2015": "FORWARD_MODELING",
        "FORWARD_MODELING_BY_CHEN_2015": "FORWARD_MODELING",
        "MULTIPLICATIVE": "MULTIPLICATIVE",
        "LONGUEVERGNE_2007": "MULTIPLICATIVE",
        "SF": "SCALE_FACTOR",
        "SCALE": "SCALE_FACTOR",
        "SCALING": "SCALING",
        "LANDERER_2012": "SCALING",
        "LANDERER_AND_SWENSON_2012": "SCALING",
        "SCALE_FACTORS": "SCALE_FACTOR",
        "GAIN_FACTOR": "SCALE_FACTOR",
        "BASIN_SF": "BASIN_SCALE_FACTOR",
        "BASIN_SCALE": "BASIN_SCALE_FACTOR",
        "BASIN_SCALE_FACTOR": "BASIN_SCALE_FACTOR",
        "GRIDDED_GAIN": "GRIDDED_GAIN_FACTOR",
        "GRID_GAIN": "GRIDDED_GAIN_FACTOR",
        "GRID_SCALE": "GRIDDED_GAIN_FACTOR",
        "GRIDDED_GAIN_FACTOR": "GRIDDED_GAIN_FACTOR",
        "OFFICIAL_GAIN": "OFFICIAL_SCALING",
        "OFFICIAL_SCALE": "OFFICIAL_SCALING",
        "OFFICIAL_SCALING": "OFFICIAL_SCALING",
        "OFFICIAL_LAND_SCALING": "OFFICIAL_LAND_SCALING",
        "OFFICIAL_OCEAN_NATIVE": "OFFICIAL_OCEAN_NATIVE",
        "OFFICIAL_MASCON_NATIVE": "OFFICIAL_MASCON_NATIVE",
        "GLOBAL_COASTAL": "GLOBAL_COASTAL_GAUSSIAN",
        "GLOBAL_COASTAL_GAUSSIAN": "GLOBAL_COASTAL_GAUSSIAN",
        "COASTAL_GAUSSIAN": "GLOBAL_COASTAL_GAUSSIAN",
        "GLOBAL_REGULARIZED": "GLOBAL_REGULARIZED",
        "GLOBAL_REGULARIZED_TIKHONOV": "GLOBAL_REGULARIZED",
        "REGULARIZED": "GLOBAL_REGULARIZED",
        "TIKHONOV": "GLOBAL_REGULARIZED",
        "REGIONAL_FM": "FORWARD_MODELING",
        "REGIONAL_BASIN_SCALE_FACTOR": "BASIN_SCALE_FACTOR",
        "MODEL": "MODEL_BASED_ADDITIVE",
        "MODEL_BASED": "MODEL_BASED_ADDITIVE",
        "ADDITIVE": "MODEL_BASED_ADDITIVE",
        "MBA": "MODEL_BASED_ADDITIVE",
        "KLEES_2007": "MODEL_BASED_ADDITIVE",
        "DATA_DRIVEN": "DATA_DRIVEN",
        "DATA-DRIVEN": "DATA_DRIVEN",
        "DDC": "DATA_DRIVEN",
        "VISHWAKARMA_2017": "DATA_DRIVEN",
        "BUFFER": "BUFFER_ZONE",
        "BUFFER_ZONE": "BUFFER_ZONE",
        "CHEN_2019": "BUFFER_ZONE",
    }
    if m in ("", "AUTO"):
        return "AUTO"
    return aliases.get(m, m)


def infer_leakage_product_type(in_path: str, data_meta: Optional[Dict[str, Any]] = None) -> str:
    tokens: List[str] = []
    if isinstance(data_meta, dict):
        for key in ("tag", "source_tag", "filter_tag", "product_tag", "active_var", "title", "long_name", "source"):
            value = data_meta.get(key)
            if value is not None:
                tokens.append(str(value).upper())
    path_text = str(in_path or "").upper()
    if path_text:
        tokens.append(path_text)
    text = " | ".join(tokens)
    if "SCALE_FACTOR" in text or "SCALING_COEFFICIENT" in text or "GAIN_FACTOR" in text:
        return "official_scaling_grid"
    if "GRCTELLUS" in text or ("MONTHLY MASS GRIDS" in text and "LAND" in text):
        return "official_land_grid"
    if "MASCON" in text or "RL06M" in text or "CSR_GRACE_GRACE-FO_RL06_MASCONS" in text or "JPL_MASCON" in text:
        return "mascon_native"
    return "grid_stack"


def infer_operator_spec(
    in_path: str,
    options: LeakageFilterOptions,
    data_meta: Optional[Dict[str, Any]] = None,
    *,
    source: str = "user",
) -> LeakageOperatorSpec:
    method = _normalize_method(getattr(options, "method", "GAUSSIAN"))
    product_type = infer_leakage_product_type(in_path, data_meta=data_meta)
    notes: List[str] = []
    token_text = str(in_path or "").upper()
    if isinstance(data_meta, dict):
        token_text = " | ".join(
            [token_text]
            + [str(data_meta.get(k, "")).upper() for k in ("tag", "source_tag", "filter_tag", "product_tag", "active_var", "title")]
        )
    # Guardrail: if UI/config keeps a stale generic operator, infer from input tokens.
    # This avoids mis-routing DDK/FAN/P4M6 stacks into Gaussian-only strategies.
    if method in ("GAUSSIAN", "NONE", "AUTO"):
        if "HSAF" in token_text or "HANKEL" in token_text:
            method = "HSAF"
            notes.append("Operator inferred from input tokens: HSAF/HANKEL.")
        elif "FAN" in token_text and ("P4M6" in token_text or "PNMM" in token_text or "DECOR" in token_text):
            method = "FAN_DECORRELATION"
            notes.append("Operator inferred from input tokens: FAN + decorrelation.")
        elif "FAN" in token_text:
            method = "FAN"
            notes.append("Operator inferred from input tokens: FAN.")
        elif "P4M6" in token_text or "PNMM" in token_text:
            method = "P4M6"
            notes.append("Operator inferred from input tokens: P4M6.")
        else:
            m_ddk = re.search(r"DDK\s*[_-]?([1-8])", token_text)
            if m_ddk:
                method = "DDK4"
                notes.append(f"Operator inferred from input tokens: DDK{m_ddk.group(1)}.")
    native_gain = False
    product_native_correction = "none"
    filter_family = "gaussian"
    is_gaussian_equivalent = method in ("GAUSSIAN", "NONE")
    if method in ("DDK4",):
        filter_family = "ddk"
    elif method == "FAN":
        filter_family = "fan"
    elif method == "P4M6":
        filter_family = "decorrelation"
    elif method == "HSAF":
        filter_family = "hsaf"
    if product_type == "mascon_native":
        native_gain = True
        product_native_correction = "mascon_native"
        notes.append("Mascon/native-gain product detected.")
    elif product_type == "official_land_grid":
        product_native_correction = "official_land_scaling"
    elif product_type == "official_scaling_grid":
        product_native_correction = "official_scaling_grid"
    ddk_type = str(getattr(options, "ddk_type", "DDK4") or "DDK4").upper()
    return LeakageOperatorSpec(
        product_type=product_type,
        method=method,
        ddk_type=ddk_type,
        filter_family=filter_family,
        is_gaussian_equivalent=is_gaussian_equivalent,
        native_gain_applied=native_gain,
        product_native_correction=product_native_correction,
        source=str(source or "user"),
        notes=notes,
    )


def _lat_area_weights(lat_vec: np.ndarray, nlon: int) -> np.ndarray:
    lat = np.asarray(lat_vec, dtype=float).ravel()
    if lat.ndim != 1:
        raise ValueError("lat_vec must be 1D.")
    w_lat = np.cos(np.deg2rad(lat))
    w = np.broadcast_to(w_lat.reshape(1, -1), (int(nlon), lat.size)).astype(float)
    w[~np.isfinite(w)] = 0.0
    return w


def _weighted_mask_mean(grid: np.ndarray, mask: np.ndarray, lat_vec: np.ndarray) -> float:
    g = np.asarray(grid, dtype=float)
    m = np.asarray(mask, dtype=bool)
    if g.shape != m.shape:
        raise ValueError("grid and mask shape mismatch.")
    if not np.any(m):
        return float(np.nan)
    w = _lat_area_weights(lat_vec, g.shape[0])
    ww = w * m
    den = float(np.nansum(ww))
    if den <= 0:
        return float(np.nan)
    num = float(np.nansum(np.where(np.isfinite(g), g, 0.0) * ww))
    return num / den


def compute_masked_series(grid3d: np.ndarray, mask: np.ndarray, lat_vec: np.ndarray) -> np.ndarray:
    g3 = np.asarray(grid3d, dtype=float)
    if g3.ndim == 2:
        g3 = g3[:, :, None]
    if g3.ndim != 3:
        raise ValueError("grid3d must be 2D or 3D.")
    out = np.full(g3.shape[2], np.nan, dtype=float)
    for k in range(g3.shape[2]):
        out[k] = _weighted_mask_mean(g3[:, :, k], mask, lat_vec)
    return out


def classify_leakage_scene(
    mask: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    global_land_mask: Optional[np.ndarray] = None,
) -> LeakageScene:
    m = np.asarray(mask, dtype=bool)
    if m.ndim != 2 or not np.any(m):
        raise ValueError("Mask must be a non-empty 2D array.")
    lon = np.asarray(lon_vec, dtype=float).ravel()
    lat = np.asarray(lat_vec, dtype=float).ravel()
    total_cells = float(m.size)
    mask_fraction = float(np.count_nonzero(m) / max(1.0, total_cells))
    lon_idx, lat_idx = np.where(m)
    bbox = {
        "lon_min": float(np.nanmin(lon[lon_idx])),
        "lon_max": float(np.nanmax(lon[lon_idx])),
        "lat_min": float(np.nanmin(lat[lat_idx])),
        "lat_max": float(np.nanmax(lat[lat_idx])),
    }
    reasoning: List[str] = []
    high_lat_fraction = float(np.mean(np.abs(lat[lat_idx]) >= 60.0))
    land_fraction = 1.0
    coastal_fraction = 0.0
    if global_land_mask is not None and np.asarray(global_land_mask).shape == m.shape:
        land = np.asarray(global_land_mask, dtype=bool)
        land_fraction = float(np.mean(land[m]))
        coastal_ring = binary_dilation(m, iterations=1) & (~m)
        if np.any(coastal_ring):
            coastal_fraction = float(np.mean(land[coastal_ring] != bool(np.round(land_fraction))))
        mixed_land = float(min(land_fraction, 1.0 - land_fraction))
        if mixed_land > 0.12:
            coastal_fraction = max(coastal_fraction, mixed_land * 2.0)
    scene = "inland_basin"
    recommended = "FORWARD_MODELING"
    if high_lat_fraction >= 0.6:
        scene = "cryosphere"
        recommended = "FORWARD_MODELING"
        reasoning.append("Most selected cells lie in high latitudes.")
    elif coastal_fraction >= 0.2 or (0.15 <= land_fraction <= 0.85):
        scene = "coastal"
        recommended = "GLOBAL_COASTAL_GAUSSIAN"
        reasoning.append("Mask intersects mixed land/ocean support; prioritize coastline leakage correction.")
    elif mask_fraction <= 0.002:
        scene = "lake_reservoir"
        recommended = "FORWARD_MODELING"
        reasoning.append("Mask footprint is compact relative to the global grid.")
    else:
        scene = "inland_basin"
        recommended = "FORWARD_MODELING"
        reasoning.append("Mask is dominantly inland with contiguous support.")
    return LeakageScene(
        scene=scene,
        recommended_method=recommended,
        mask_fraction=mask_fraction,
        land_fraction=land_fraction,
        coastal_fraction=float(coastal_fraction),
        high_lat_fraction=high_lat_fraction,
        bbox=bbox,
        reasoning=reasoning,
    )


def recommend_correction_method(
    requested_method: str,
    scene: LeakageScene,
    operator_spec: LeakageOperatorSpec,
    *,
    has_reference_model: bool = False,
) -> str:
    requested = normalize_correction_method(requested_method)
    if requested != "AUTO":
        return requested
    if operator_spec.product_type == "mascon_native":
        return "OFFICIAL_MASCON_NATIVE"
    if operator_spec.product_type in ("official_land_grid", "official_scaling_grid"):
        return "OFFICIAL_LAND_SCALING"
    if scene.scene == "coastal":
        if bool(getattr(operator_spec, "is_gaussian_equivalent", False)):
            return "GLOBAL_COASTAL_GAUSSIAN"
        return "GLOBAL_REGULARIZED"
    if scene.scene == "inland_basin" and has_reference_model and scene.mask_fraction >= 0.02:
        return "BASIN_SCALE_FACTOR"
    if requested == "SCALE_FACTOR":
        return "BASIN_SCALE_FACTOR"
    return scene.recommended_method or "FORWARD_MODELING"


def resolve_strategy_request(
    strategy_family: str,
    requested_method: str,
    operator_spec: LeakageOperatorSpec,
    *,
    official_mode: str = "auto",
) -> str:
    family = str(strategy_family or "regional").strip().lower()
    requested = normalize_correction_method(requested_method)
    official = str(official_mode or "auto").strip().lower()
    if requested != "AUTO":
        return requested
    if family == "official":
        if official == "land_scaling":
            return "OFFICIAL_LAND_SCALING"
        if official == "ocean_native":
            return "OFFICIAL_OCEAN_NATIVE"
        if official == "mascon_native":
            return "OFFICIAL_MASCON_NATIVE"
        if operator_spec.product_type == "mascon_native":
            return "OFFICIAL_MASCON_NATIVE"
        if operator_spec.product_type in ("official_land_grid", "official_scaling_grid"):
            return "OFFICIAL_LAND_SCALING"
        return "OFFICIAL_SCALING"
    if family == "global_coastal":
        return "GLOBAL_COASTAL_GAUSSIAN" if bool(getattr(operator_spec, "is_gaussian_equivalent", False)) else "GLOBAL_REGULARIZED"
    if family == "global_regularized":
        return "GLOBAL_REGULARIZED"
    return "AUTO"


def strategy_family_for_method(method: str) -> str:
    normalized = normalize_correction_method(method)
    if normalized in ("BASIN_SCALE_FACTOR", "FORWARD_MODELING", "ITERATIVE", "MULTIPLICATIVE", "SCALING", "DATA_DRIVEN", "MODEL_BASED_ADDITIVE", "GRIDDED_GAIN_FACTOR"):
        return "regional"
    if normalized in ("GLOBAL_COASTAL_GAUSSIAN", "BUFFER_ZONE"):
        return "global_coastal"
    if normalized == "GLOBAL_REGULARIZED":
        return "global_regularized"
    if normalized in ("OFFICIAL_SCALING", "OFFICIAL_LAND_SCALING", "OFFICIAL_OCEAN_NATIVE", "OFFICIAL_MASCON_NATIVE"):
        return "official"
    return "regional"


def strategy_variant_for_method(method: str, operator_spec: Optional[LeakageOperatorSpec] = None) -> str:
    normalized = normalize_correction_method(method)
    if normalized == "OFFICIAL_SCALING":
        if operator_spec is not None and operator_spec.product_type == "mascon_native":
            return "mascon_native"
        return "land_scaling"
    mapping = {
        "BASIN_SCALE_FACTOR": "basin_scale_factor",
        "FORWARD_MODELING": "forward_modeling",
        "ITERATIVE": "iterative",
        "MULTIPLICATIVE": "multiplicative",
        "SCALING": "scaling",
        "DATA_DRIVEN": "data_driven",
        "BUFFER_ZONE": "buffer_zone",
        "GRIDDED_GAIN_FACTOR": "gridded_gain_factor",
        "MODEL_BASED_ADDITIVE": "additive",
        "GLOBAL_COASTAL_GAUSSIAN": "gaussian",
        "GLOBAL_REGULARIZED": "tikhonov",
        "OFFICIAL_LAND_SCALING": "land_scaling",
        "OFFICIAL_OCEAN_NATIVE": "ocean_native",
        "OFFICIAL_MASCON_NATIVE": "mascon_native",
    }
    return mapping.get(normalized, normalized.lower())


def _is_regular_axis(vec: np.ndarray, tol: float = 1.0e-8) -> Tuple[bool, float, float]:
    v = np.asarray(vec, dtype=float).ravel()
    if v.size < 2:
        return True, float(v[0] if v.size else 0.0), 1.0
    dv = np.diff(v)
    step = float(np.nanmedian(dv))
    ok = bool(np.all(np.isfinite(dv)) and np.nanmax(np.abs(dv - step)) <= tol)
    return ok, float(v[0]), step


def _effective_lmax(lon_vec: np.ndarray, lat_vec: np.ndarray, requested: int) -> int:
    nlon = int(np.asarray(lon_vec).size)
    nlat = int(np.asarray(lat_vec).size)
    hard = max(2, min(nlat - 1, nlon // 2))
    return int(max(2, min(int(requested), hard)))


def _schmidt_plm(l: int, m: int, x: np.ndarray) -> np.ndarray:
    p = lpmv(m, l, x)
    if m == 0:
        return np.asarray(p, dtype=float)
    sign = -1.0 if (m % 2) else 1.0
    norm = sign * np.sqrt(2.0 * np.exp(gammaln(l - m + 1.0) - gammaln(l + m + 1.0)))
    return np.asarray(p * norm, dtype=float)


def _build_sh_basis(lon_vec: np.ndarray, lat_vec: np.ndarray, Lmax: int) -> _SHBasis:
    lon = np.asarray(lon_vec, dtype=float).ravel()
    lat = np.asarray(lat_vec, dtype=float).ravel()
    if lon.ndim != 1 or lat.ndim != 1:
        raise ValueError("lon/lat vectors must be 1D.")
    if lon.size < 4 or lat.size < 4:
        raise ValueError("Grid is too small for SH operator.")

    lon_rad = np.deg2rad(lon)
    mvals = np.arange(Lmax + 1, dtype=float).reshape(-1, 1)
    cos_m_lon = np.cos(mvals * lon_rad.reshape(1, -1))
    sin_m_lon = np.sin(mvals * lon_rad.reshape(1, -1))

    lon_alpha = np.full(Lmax + 1, 2.0 / max(1, lon.size), dtype=float)
    lon_alpha[0] = 1.0 / max(1, lon.size)

    lat_w = np.cos(np.deg2rad(lat))
    lat_w = np.where(np.isfinite(lat_w), np.maximum(lat_w, 1.0e-12), 1.0e-12)
    lat_w_sqrt = np.sqrt(lat_w)

    x = np.sin(np.deg2rad(lat))
    pnm = np.zeros((Lmax + 1, Lmax + 1, lat.size), dtype=float)
    for l in range(Lmax + 1):
        for m in range(l + 1):
            pnm[l, m, :] = _schmidt_plm(l, m, x)

    pnm_by_m: List[np.ndarray] = []
    pinv_by_m: List[np.ndarray] = []
    for m in range(Lmax + 1):
        pm = np.column_stack([pnm[l, m, :] for l in range(m, Lmax + 1)])
        xw = pm * lat_w_sqrt[:, None]
        pnm_by_m.append(pm)
        pinv_by_m.append(np.linalg.pinv(xw, rcond=1.0e-10))

    return _SHBasis(
        Lmax=Lmax,
        lon_vec=lon,
        lat_vec=lat,
        cos_m_lon=cos_m_lon,
        sin_m_lon=sin_m_lon,
        lon_alpha=lon_alpha,
        lat_w_sqrt=lat_w_sqrt,
        pnm_by_m=pnm_by_m,
        pinv_by_m=pinv_by_m,
    )


@lru_cache(maxsize=12)
def _build_sh_basis_cached_regular(
    Lmax: int,
    nlon: int,
    nlat: int,
    lon0: float,
    dlon: float,
    lat0: float,
    dlat: float,
) -> _SHBasis:
    lon = lon0 + np.arange(int(nlon), dtype=float) * dlon
    lat = lat0 + np.arange(int(nlat), dtype=float) * dlat
    return _build_sh_basis(lon, lat, int(Lmax))


def _get_sh_basis(lon_vec: np.ndarray, lat_vec: np.ndarray, Lmax: int) -> _SHBasis:
    lon = np.asarray(lon_vec, dtype=float).ravel()
    lat = np.asarray(lat_vec, dtype=float).ravel()
    ok_lon, lon0, dlon = _is_regular_axis(lon)
    ok_lat, lat0, dlat = _is_regular_axis(lat)
    if ok_lon and ok_lat:
        return _build_sh_basis_cached_regular(
            int(Lmax),
            int(lon.size),
            int(lat.size),
            float(lon0),
            float(dlon),
            float(lat0),
            float(dlat),
        )
    return _build_sh_basis(lon, lat, int(Lmax))


def _grid_to_sh(grid: np.ndarray, basis: _SHBasis) -> Tuple[np.ndarray, np.ndarray]:
    g = np.asarray(grid, dtype=float)
    if g.ndim != 2:
        raise ValueError("SH analysis expects a 2D grid.")
    if g.shape != (basis.lon_vec.size, basis.lat_vec.size):
        raise ValueError("Grid shape mismatch for SH analysis.")
    if not np.isfinite(g).all():
        g = np.where(np.isfinite(g), g, 0.0)

    a_m = (basis.cos_m_lon @ g) * basis.lon_alpha[:, None]
    b_m = (basis.sin_m_lon @ g) * basis.lon_alpha[:, None]

    Lmax = basis.Lmax
    C = np.zeros((Lmax + 1, Lmax + 1), dtype=float)
    S = np.zeros((Lmax + 1, Lmax + 1), dtype=float)
    y_scale = basis.lat_w_sqrt

    for m in range(Lmax + 1):
        yc = a_m[m, :] * y_scale
        ys = b_m[m, :] * y_scale
        c_coef = basis.pinv_by_m[m] @ yc
        s_coef = basis.pinv_by_m[m] @ ys
        C[m : Lmax + 1, m] = c_coef
        S[m : Lmax + 1, m] = s_coef
    return C, S


def _sh_to_grid(C: np.ndarray, S: np.ndarray, basis: _SHBasis) -> np.ndarray:
    C = np.asarray(C, dtype=float)
    S = np.asarray(S, dtype=float)
    Lmax = basis.Lmax
    if C.shape[0] < Lmax + 1 or S.shape[0] < Lmax + 1:
        raise ValueError("SH coefficient matrix too small for synthesis.")

    out = np.zeros((basis.lon_vec.size, basis.lat_vec.size), dtype=float)
    for m in range(Lmax + 1):
        pm = basis.pnm_by_m[m]
        cc = C[m : Lmax + 1, m]
        ss = S[m : Lmax + 1, m]
        lat_c = pm @ cc
        lat_s = pm @ ss
        out += np.outer(basis.cos_m_lon[m, :], lat_c)
        out += np.outer(basis.sin_m_lon[m, :], lat_s)
    return out


def _resolve_ddk_data_dir(options: LeakageFilterOptions) -> str:
    d = str(getattr(options, "ddk_data_dir", "") or "").strip()
    if d and os.path.isdir(d):
        return d
    try:
        root = get_root_dir()
        data_dir = get_data_dir(root)
    except Exception:
        root = ""
        data_dir = ""
    candidates = [
        os.path.join(str(data_dir), "Aux", "DDK") if data_dir else "",
        os.path.join(str(data_dir), "DDK") if data_dir else "",
        str(root),
    ]
    for c in candidates:
        if c and os.path.isdir(c):
            return c
    return d


def _apply_filter_in_sh(
    C: np.ndarray,
    S: np.ndarray,
    Lmax: int,
    options: LeakageFilterOptions,
    method: str,
) -> Tuple[np.ndarray, np.ndarray]:
    m = _normalize_method(method)

    if m == "GAUSSIAN":
        Cf, Sf, _ = filter_sh_gaussian(C, S, Lmax, float(options.gaussian_km))
        return np.asarray(Cf, dtype=float), np.asarray(Sf, dtype=float)

    if m == "FAN":
        Cf, Sf, _ = filter_sh_fan(C, S, Lmax, float(options.fan_r1_km), float(options.fan_r2_km))
        return np.asarray(Cf, dtype=float), np.asarray(Sf, dtype=float)

    if m == "GAUSSIAN_DECORRELATION":
        C1, S1, _ = filter_sh_p4m6(C, S, Lmax, int(options.p4m6_poly_deg), int(options.p4m6_m_start))
        Cf, Sf, _ = filter_sh_gaussian(C1, S1, Lmax, float(options.gaussian_km))
        return np.asarray(Cf, dtype=float), np.asarray(Sf, dtype=float)

    if m == "FAN_DECORRELATION":
        C1, S1, _ = filter_sh_p4m6(C, S, Lmax, int(options.p4m6_poly_deg), int(options.p4m6_m_start))
        Cf, Sf, _ = filter_sh_fan(C1, S1, Lmax, float(options.fan_r1_km), float(options.fan_r2_km))
        return np.asarray(Cf, dtype=float), np.asarray(Sf, dtype=float)

    if m.startswith("DDK"):
        ddk_type = str(options.ddk_type or m).upper()
        ddk_dir = _resolve_ddk_data_dir(options)
        Cf, Sf, _ = filter_sh_ddk(C, S, Lmax, ddk_type=ddk_type, data_dir=ddk_dir)
        return np.asarray(Cf, dtype=float), np.asarray(Sf, dtype=float)

    if m == "P4M6":
        Cf, Sf, _ = filter_sh_p4m6(C, S, Lmax, int(options.p4m6_poly_deg), int(options.p4m6_m_start))
        return np.asarray(Cf, dtype=float), np.asarray(Sf, dtype=float)

    # No filtering.
    return np.asarray(C, dtype=float), np.asarray(S, dtype=float)


def apply_forward_operator(
    gtrue: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    options: LeakageFilterOptions,
) -> np.ndarray:
    """
    Apply the leakage FM/SF forward operator:
    SH analysis (truncate) + same filter + synthesis.
    """
    g = ensure_latlon_order(np.asarray(gtrue, dtype=float), lon_vec, lat_vec, target_order="lon_lat")
    if g.ndim != 2:
        raise ValueError("Forward operator expects 2D grid [nLon x nLat].")

    lon = np.asarray(lon_vec, dtype=float).ravel()
    lat = np.asarray(lat_vec, dtype=float).ravel()
    Lmax = _effective_lmax(lon, lat, int(getattr(options, "lmax", 60)))
    basis = _get_sh_basis(lon, lat, Lmax)

    C, S = _grid_to_sh(g, basis)
    method = _normalize_method(options.method)

    if method in ("HSAF", "HANKEL"):
        # Follow the selected HSAF input route (RAW or P4M6) to keep FM operator
        # consistent with the product generation chain.
        pre_input = str(getattr(options, "hsaf_input", "P4M6") or "P4M6").strip().upper()
        if pre_input in ("P4M6", "PNMM", "DECORRELATION", "P4M6_DECORRELATION"):
            C1, S1, _ = filter_sh_p4m6(C, S, Lmax, int(options.p4m6_poly_deg), int(options.p4m6_m_start))
            g_in = _sh_to_grid(C1, S1, basis)
        else:
            g_in = _sh_to_grid(C, S, basis)
        cfg = {"params": options.hsaf_params or {"N": 60, "P": 20, "K": 6, "J": 10, "workers": 1, "iterations": 1}}
        gf, _ = filter_grid_hsaf_matlab(g_in, lon, lat, cfg, Ts=float(options.hsaf_ts))
        return np.asarray(gf, dtype=float)

    Cf, Sf = _apply_filter_in_sh(C, S, Lmax, options, method)
    return _sh_to_grid(Cf, Sf, basis)


def compute_scale_factor(
    mask: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    options: LeakageFilterOptions,
    unit_mm: float = 1.0,
) -> Tuple[float, Dict[str, float]]:
    """
    Compute SF from a synthetic unit field using the same forward operator as FM.
    """
    m = np.asarray(mask, dtype=bool)
    if m.ndim != 2:
        raise ValueError("Mask must be 2D.")
    if not np.any(m):
        raise ValueError("Mask is empty.")

    g_unit = np.zeros(m.shape, dtype=float)
    g_unit[m] = float(unit_mm)
    g_f = apply_forward_operator(g_unit, lon_vec, lat_vec, options)

    mu = _weighted_mask_mean(g_f, m, lat_vec)
    if not np.isfinite(mu) or np.isclose(mu, 0.0):
        raise ValueError("Filtered mean is invalid/zero for SF computation.")
    sf = float(unit_mm) / mu
    return sf, {"filtered_mean": mu}


def compute_basin_scale_factor_from_reference(
    reference_stack: np.ndarray,
    mask: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    options: LeakageFilterOptions,
    *,
    clip_min: float = 0.25,
    clip_max: float = 4.0,
) -> Tuple[float, Dict[str, np.ndarray]]:
    ref = np.asarray(reference_stack, dtype=float)
    if ref.ndim == 2:
        ref = ref[:, :, None]
    if ref.ndim != 3:
        raise ValueError("reference_stack must be 2D or 3D.")
    m = np.asarray(mask, dtype=bool)
    if m.shape != ref.shape[:2]:
        raise ValueError("mask shape mismatch for basin scale factor.")

    filtered_stack = np.empty_like(ref, dtype=float)
    for k in range(ref.shape[2]):
        filtered_stack[:, :, k] = apply_forward_operator(ref[:, :, k], lon_vec, lat_vec, options)
    reference_series = compute_masked_series(ref, m, lat_vec)
    filtered_series = compute_masked_series(filtered_stack, m, lat_vec)
    denom = float(np.nansum(filtered_series ** 2))
    if not np.isfinite(denom) or np.isclose(denom, 0.0):
        raise ValueError("Filtered reference series is invalid for basin scale-factor estimation.")
    numer = float(np.nansum(reference_series * filtered_series))
    factor = numer / denom
    if not np.isfinite(factor):
        raise ValueError("Basin scale factor is invalid.")
    factor = float(np.clip(factor, clip_min, clip_max))
    return factor, {
        "reference_series": reference_series,
        "filtered_series": filtered_series,
        "filtered_reference_stack": filtered_stack,
    }


def compute_gridded_gain_factors(
    reference_stack: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    options: LeakageFilterOptions,
    *,
    target_mask: Optional[np.ndarray] = None,
    clip_min: float = 0.25,
    clip_max: float = 4.0,
    min_denominator: float = 1.0e-8,
) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    ref = np.asarray(reference_stack, dtype=float)
    if ref.ndim == 2:
        ref = ref[:, :, None]
    if ref.ndim != 3:
        raise ValueError("reference_stack must be 2D or 3D.")

    filtered_stack = np.empty_like(ref, dtype=float)
    for k in range(ref.shape[2]):
        filtered_stack[:, :, k] = apply_forward_operator(ref[:, :, k], lon_vec, lat_vec, options)

    numerator = np.nansum(ref * filtered_stack, axis=2)
    denominator = np.nansum(filtered_stack * filtered_stack, axis=2)
    gains = np.divide(
        numerator,
        denominator,
        out=np.ones(ref.shape[:2], dtype=float),
        where=np.abs(denominator) > float(min_denominator),
    )
    gains = np.clip(gains, clip_min, clip_max)
    if target_mask is not None:
        tmask = np.asarray(target_mask, dtype=bool)
        if tmask.shape != gains.shape:
            raise ValueError("target_mask shape mismatch for gridded gain factors.")
        gains = np.where(tmask, gains, 1.0)
    return gains, {
        "filtered_reference_stack": filtered_stack,
        "numerator": numerator,
        "denominator": denominator,
    }


def compute_scale_factor_series(
    reference_stack: np.ndarray,
    mask: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    options: LeakageFilterOptions,
    *,
    mode: str = "per_month_mean_ratio",
    clip_min: float = 0.25,
    clip_max: float = 4.0,
) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    ref = np.asarray(reference_stack, dtype=float)
    if ref.ndim == 2:
        ref = ref[:, :, None]
    if ref.ndim != 3:
        raise ValueError("reference_stack must be 2D or 3D.")
    m = np.asarray(mask, dtype=bool)
    if m.shape != ref.shape[:2]:
        raise ValueError("mask shape mismatch for scale-factor series.")

    mode_n = str(mode or "per_month_mean_ratio").strip().lower()
    filtered_series = np.full(ref.shape[2], np.nan, dtype=float)
    reference_series = np.full(ref.shape[2], np.nan, dtype=float)
    factors = np.full(ref.shape[2], np.nan, dtype=float)
    for k in range(ref.shape[2]):
        model_k = ref[:, :, k]
        filtered_k = apply_forward_operator(model_k, lon_vec, lat_vec, options)
        reference_series[k] = _weighted_mask_mean(model_k, m, lat_vec)
        filtered_series[k] = _weighted_mask_mean(filtered_k, m, lat_vec)
        denom = filtered_series[k]
        numer = reference_series[k]
        if np.isfinite(numer) and np.isfinite(denom) and not np.isclose(denom, 0.0):
            factors[k] = numer / denom
    valid = np.isfinite(factors)
    if not np.any(valid):
        raise ValueError("No valid scale factors could be estimated from the reference stack.")
    if mode_n in ("constant", "global", "median"):
        value = float(np.nanmedian(factors[valid]))
        factors[:] = value
    factors = np.clip(np.where(np.isfinite(factors), factors, np.nanmedian(factors[valid])), clip_min, clip_max)
    return factors, {
        "reference_series": reference_series,
        "filtered_series": filtered_series,
        "valid_mask": valid.astype(int),
    }


def apply_scale_factors_stack(grid3d: np.ndarray, mask: np.ndarray, factors: np.ndarray) -> np.ndarray:
    g3 = np.asarray(grid3d, dtype=float)
    if g3.ndim == 2:
        g3 = g3[:, :, None]
    if g3.ndim != 3:
        raise ValueError("grid3d must be 2D or 3D.")
    m = np.asarray(mask, dtype=bool)
    f = np.asarray(factors, dtype=float).reshape(-1)
    if f.size not in (1, g3.shape[2]):
        raise ValueError("factors must be scalar or length Nt.")
    if f.size == 1:
        f = np.repeat(f, g3.shape[2])
    out = g3.copy()
    for k in range(g3.shape[2]):
        out[:, :, k] = np.where(m, out[:, :, k] * f[k], out[:, :, k])
    return out


def apply_gridded_gain_factors_stack(
    grid3d: np.ndarray,
    gains: np.ndarray,
    *,
    target_mask: Optional[np.ndarray] = None,
) -> np.ndarray:
    g3 = np.asarray(grid3d, dtype=float)
    if g3.ndim == 2:
        g3 = g3[:, :, None]
    if g3.ndim != 3:
        raise ValueError("grid3d must be 2D or 3D.")
    gain_grid = np.asarray(gains, dtype=float)
    if gain_grid.shape != g3.shape[:2]:
        raise ValueError("gain grid shape mismatch.")
    out = g3.copy()
    if target_mask is not None:
        tmask = np.asarray(target_mask, dtype=bool)
        if tmask.shape != gain_grid.shape:
            raise ValueError("target_mask shape mismatch for gridded gain application.")
        gain_grid = np.where(tmask, gain_grid, 1.0)
    out *= gain_grid[:, :, None]
    return out


def estimate_rate_map(
    grid3d: np.ndarray,
    t_axis: Optional[np.ndarray] = None,
    min_valid: int = 6,
) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """
    Estimate linear rate map from a stack [nLon x nLat x Nt].
    """
    g3 = np.asarray(grid3d, dtype=float)
    if g3.ndim == 2:
        g3 = g3[:, :, np.newaxis]
    if g3.ndim != 3:
        raise ValueError("grid3d must be 2D/3D.")

    _, _, nt = g3.shape
    if nt < 2:
        return g3[:, :, 0].copy(), {
            "valid_count": np.sum(np.isfinite(g3), axis=2).astype(int),
            "time_axis": np.array([0.0], dtype=float),
        }

    t = None
    if t_axis is not None:
        try:
            t = np.asarray(t_axis, dtype=float).reshape(-1)
        except Exception:
            t = None
    if t is None or t.size != nt or (not np.all(np.isfinite(t))):
        t = np.arange(nt, dtype=float)
    t = t - float(np.nanmean(t))
    if not np.any(np.isfinite(t)):
        t = np.arange(nt, dtype=float)
        t = t - np.mean(t)

    y = np.where(np.isfinite(g3), g3, 0.0)
    w = np.isfinite(g3).astype(float)
    t3 = t.reshape(1, 1, nt)
    n_valid = np.sum(w, axis=2)
    n_req = int(max(2, min(min_valid, nt)))

    with np.errstate(invalid="ignore", divide="ignore"):
        t_mean = np.sum(w * t3, axis=2) / np.maximum(n_valid, 1.0)
        y_mean = np.sum(y, axis=2) / np.maximum(n_valid, 1.0)
        tc = t3 - t_mean[:, :, None]
        yc = y - y_mean[:, :, None]
        den = np.sum(w * tc * tc, axis=2)
        num = np.sum(w * tc * yc, axis=2)
        rate = num / den

    rate[(n_valid < n_req) | (~np.isfinite(rate)) | (den <= 0)] = np.nan
    return rate, {"valid_count": n_valid.astype(int), "time_axis": t}


def build_reference_field(
    grid3d: np.ndarray,
    mask: np.ndarray,
    *,
    mode: str = "trend",
    reference_stack: Optional[np.ndarray] = None,
    time_axis: Optional[np.ndarray] = None,
) -> np.ndarray:
    m = np.asarray(mask, dtype=bool)
    source = np.asarray(reference_stack, dtype=float) if reference_stack is not None else np.asarray(grid3d, dtype=float)
    if source.ndim == 2:
        source = source[:, :, None]
    if source.ndim != 3:
        raise ValueError("reference source must be 2D or 3D.")
    mode_n = str(mode or "trend").strip().lower()
    if mode_n in ("mean", "climatology", "stack_mean"):
        ref = np.nanmean(source, axis=2)
    elif mode_n in ("first", "initial"):
        ref = source[:, :, 0]
    elif mode_n in ("median",):
        ref = np.nanmedian(source, axis=2)
    else:
        ref, _ = estimate_rate_map(source, t_axis=time_axis)
    ref = np.asarray(ref, dtype=float)
    if ref.shape != m.shape:
        raise ValueError("reference field shape mismatch.")
    if np.count_nonzero(np.isfinite(ref[m])) < 3:
        raise ValueError("reference field has insufficient finite support inside mask.")
    return ref


def model_based_additive_correct_month(
    gobs: np.ndarray,
    reference_field: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    options: LeakageFilterOptions,
    *,
    mask: Optional[np.ndarray] = None,
    restrict_to_mask: bool = True,
) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    g = ensure_latlon_order(np.asarray(gobs, dtype=float), lon_vec, lat_vec, target_order="lon_lat")
    ref = ensure_latlon_order(np.asarray(reference_field, dtype=float), lon_vec, lat_vec, target_order="lon_lat")
    if g.shape != ref.shape:
        raise ValueError("Observed field and reference field must have the same shape.")
    filtered_ref = apply_forward_operator(ref, lon_vec, lat_vec, options)
    leakage_term = ref - filtered_ref
    corrected = g + leakage_term
    if restrict_to_mask and mask is not None:
        m = np.asarray(mask, dtype=bool)
        corrected = np.where(m, corrected, g)
    return corrected, {
        "reference_field": np.asarray(ref, dtype=float),
        "filtered_reference": np.asarray(filtered_ref, dtype=float),
        "leakage_term": np.asarray(leakage_term, dtype=float),
    }


def model_based_additive_correct_stack(
    grid3d: np.ndarray,
    reference_field: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    options: LeakageFilterOptions,
    *,
    mask: Optional[np.ndarray] = None,
    restrict_to_mask: bool = True,
) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    g3 = np.asarray(grid3d, dtype=float)
    if g3.ndim == 2:
        g3 = g3[:, :, None]
    if g3.ndim != 3:
        raise ValueError("grid3d must be 2D or 3D.")
    ref_input_ndim = np.asarray(reference_field).ndim
    ref = np.asarray(reference_field, dtype=float)
    if ref.ndim == 2:
        ref = ref[:, :, None]
    if ref.ndim != 3:
        raise ValueError("reference_field must be 2D or 3D.")
    if ref.shape[:2] != g3.shape[:2]:
        raise ValueError("reference_field spatial shape mismatch.")
    if ref.shape[2] == 1 and g3.shape[2] > 1:
        ref = np.repeat(ref, g3.shape[2], axis=2)
    if ref.shape[2] != g3.shape[2]:
        raise ValueError("reference_field time dimension mismatch.")

    out = np.full_like(g3, np.nan, dtype=float)
    filtered_ref = np.empty_like(ref, dtype=float)
    leakage_term = np.empty_like(ref, dtype=float)
    for k in range(g3.shape[2]):
        filtered_ref[:, :, k] = apply_forward_operator(ref[:, :, k], lon_vec, lat_vec, options)
        leakage_term[:, :, k] = ref[:, :, k] - filtered_ref[:, :, k]
        corrected = g3[:, :, k] + leakage_term[:, :, k]
        if restrict_to_mask and mask is not None:
            m = np.asarray(mask, dtype=bool)
            corrected = np.where(m, corrected, g3[:, :, k])
        out[:, :, k] = corrected
    info = {
        "leakage_term": np.asarray(leakage_term, dtype=float),
        "filtered_reference": np.asarray(filtered_ref, dtype=float),
        "reference_stack": np.asarray(ref, dtype=float),
    }
    # Backward compatibility: if caller provided a static 2D reference field,
    # keep diagnostics in 2D even when internally broadcast across months.
    if ref_input_ndim == 2:
        info["leakage_term"] = info["leakage_term"][:, :, 0]
        info["filtered_reference"] = info["filtered_reference"][:, :, 0]
        info["reference_stack"] = info["reference_stack"][:, :, 0]
    if np.asarray(info["leakage_term"]).ndim == 3 and info["leakage_term"].shape[2] == 1:
        info["leakage_term"] = info["leakage_term"][:, :, 0]
        info["filtered_reference"] = info["filtered_reference"][:, :, 0]
        info["reference_stack"] = info["reference_stack"][:, :, 0]
    return out, info


def data_driven_correct_stack(
    grid3d: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    options: LeakageFilterOptions,
    *,
    mask: Optional[np.ndarray] = None,
    restrict_to_mask: bool = False,
) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """Data-driven leakage repair after Vishwakarma et al. (2017).

    The corrected field is obtained from the once-filtered input ``g`` and the
    twice-filtered field ``g2 = F(g)`` as ``g' = 2g - g2``. This preserves the
    original input/output contract of the module and provides a model-free
    correction path for basin-scale applications.
    """
    g3 = np.asarray(grid3d, dtype=float)
    if g3.ndim == 2:
        g3 = g3[:, :, None]
    if g3.ndim != 3:
        raise ValueError("grid3d must be 2D or 3D.")

    twice_filtered = np.empty_like(g3, dtype=float)
    corrected = np.empty_like(g3, dtype=float)
    for k in range(g3.shape[2]):
        gk = np.asarray(g3[:, :, k], dtype=float)
        g2 = apply_forward_operator(gk, lon_vec, lat_vec, options)
        twice_filtered[:, :, k] = g2
        ck = 2.0 * gk - g2
        if restrict_to_mask and mask is not None:
            m = np.asarray(mask, dtype=bool)
            ck = np.where(m, ck, gk)
        corrected[:, :, k] = ck
    return corrected, {
        "twice_filtered_stack": twice_filtered,
        "deviation_stack": g3 - twice_filtered,
        "residual_metric_by_month": np.nanmean(np.abs(corrected - g3), axis=(0, 1)),
    }


def _apply_mass_conservation(
    field: np.ndarray,
    mask: np.ndarray,
    lat_vec: np.ndarray,
    mode: str,
    lat_weights: Optional[np.ndarray] = None,
    balance_mask: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, float]:
    m = np.asarray(mask, dtype=bool)
    f = np.asarray(field, dtype=float).copy()
    mode_l = str(mode or "ocean_uniform_land_balance").lower()
    if not np.any(m):
        return f, 0.0

    if balance_mask is not None:
        bmask = np.asarray(balance_mask, dtype=bool)
        if bmask.shape != f.shape:
            raise ValueError("balance_mask shape mismatch in mass conservation.")
        bmask = bmask & (~m)
        fixed_outside = (~m) & (~bmask)
    else:
        bmask = ~m
        fixed_outside = np.zeros_like(m, dtype=bool)

    if lat_weights is None:
        w = _lat_area_weights(lat_vec, f.shape[0])
    else:
        w = np.asarray(lat_weights, dtype=float)
    ocean_val = 0.0

    if mode_l in ("none", "off"):
        return f, ocean_val

    if mode_l in ("global_zero_mean", "zero_mean"):
        mean_all = float(np.nanmean(f)) if np.any(np.isfinite(f)) else 0.0
        f = f - mean_all
        if np.any(fixed_outside):
            f[fixed_outside] = 0.0
        return f, float(-mean_all)

    if mode_l in ("legacy_land_mean_fill", "legacy", "script_land_mean"):
        # Match MATLAB main1/FM_HPC behavior:
        # land_ewh = M .* landMask
        # mean_land = mean(land_ewh over all cells) = mean(M_land) * nLand / nAll
        # ocean_ewh = mean_land * (landMask - 1) => ocean = -mean_land
        n_all = float(f.size)
        n_land = float(np.count_nonzero(m))
        if n_all <= 0 or n_land <= 0:
            return f, 0.0
        mean_land_only = float(np.nanmean(f[m])) if np.any(np.isfinite(f[m])) else 0.0
        mean_land_global = mean_land_only * (n_land / n_all)
        ocean_val = -mean_land_global
        f[bmask] = ocean_val
        if np.any(fixed_outside):
            f[fixed_outside] = 0.0
        return f, float(ocean_val)

    # Chen-style mass conservation:
    # keep in-mask signal; set outside-mask to one uniform layer balancing mass.
    in_mass = float(np.nansum(np.where(np.isfinite(f), f, 0.0)[m] * w[m]))
    out_w = float(np.nansum(w[bmask]))
    if out_w > 0:
        ocean_val = -in_mass / out_w
        f[bmask] = ocean_val
    else:
        f[bmask] = 0.0
    if np.any(fixed_outside):
        f[fixed_outside] = 0.0
    return f, float(ocean_val)


def _nan_smooth_2d(grid: np.ndarray, sigma) -> np.ndarray:
    g = np.asarray(grid, dtype=float)
    if isinstance(sigma, (tuple, list, np.ndarray)):
        if len(sigma) >= 2:
            s0 = float(sigma[0])
            s1 = float(sigma[1])
        else:
            s0 = s1 = float(sigma[0]) if len(sigma) else 0.0
        if s0 <= 0 and s1 <= 0:
            return g.copy()
        sigma_use = (max(0.0, s0), max(0.0, s1))
    else:
        s = float(sigma)
        if s <= 0:
            return g.copy()
        sigma_use = (s, s)

    if sigma_use[0] <= 0 and sigma_use[1] <= 0:
        return g.copy()
    nan_mask = ~np.isfinite(g)
    if np.all(nan_mask):
        return g.copy()
    x = np.where(nan_mask, 0.0, g)
    w = np.where(nan_mask, 0.0, 1.0)
    xf = gaussian_filter(x, sigma=sigma_use, mode="reflect")
    wf = gaussian_filter(w, sigma=sigma_use, mode="reflect")
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(wf > 0, xf / wf, np.nan)
    return out


def fm_correct_month(
    gobs: np.ndarray,
    mask: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    options: LeakageFilterOptions,
    n_iter: int = 30,
    tol_rmse_mm: float = 0.1,
    update_mode: str = "global",
    init_mode: str = "obs",
    mass_conservation: str = "ocean_uniform_land_balance",
    update_operator: str = "identity",
    convergence_metric: str = "land_weighted_mean",
    accel: float = 1.2,
    prefilter_obs: bool = False,
    min_iter: int = 3,
    stagnation_patience: int = 8,
    min_improve: float = 1.0e-4,
    output_mode: str = "preserve_observed_outside_mask",
    balance_mask: Optional[np.ndarray] = None,
    iter_cb: Optional[Callable[[int, int, float], None]] = None,
    should_continue: Optional[Callable[[], bool]] = None,
) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """
    Chen-style forward modeling for one map.

    Default steps follow the literature flow:
    1) initialize M_tru = M_obs
    2) apply land/ocean mass-balance model
    3) forward filter operator -> M_pre
    4) delta = M_obs - M_pre
    5) M_tru = M_tru + k * delta
    """
    gobs = ensure_latlon_order(np.asarray(gobs, dtype=float), lon_vec, lat_vec, target_order="lon_lat")
    m = np.asarray(mask, dtype=bool)
    if gobs.ndim != 2 or m.shape != gobs.shape:
        raise ValueError("FM expects 2D gobs with same-shape mask.")
    if not np.any(m):
        raise ValueError("Mask is empty for FM.")
    bmask = None
    if balance_mask is not None:
        bmask = np.asarray(balance_mask, dtype=bool)
        if bmask.shape != gobs.shape:
            raise ValueError("balance_mask shape mismatch for FM.")
    gobs_ref = gobs
    if bool(prefilter_obs):
        # Keep FM consistent with its selected forward operator by first
        # moving observations into the same filtered domain.
        gobs_ref = apply_forward_operator(gobs, lon_vec, lat_vec, options)
        if gobs_ref.shape != gobs.shape:
            gobs_ref = gobs_ref.reshape(gobs.shape)
        if not np.all(np.isfinite(gobs_ref)):
            gobs_ref = np.where(np.isfinite(gobs_ref), gobs_ref, gobs)

    n_iter = max(1, int(n_iter))
    tol = float(max(0.0, tol_rmse_mm))
    min_iter = int(max(1, min_iter))
    stagnation_patience = int(max(0, stagnation_patience))
    min_improve = float(max(0.0, min_improve))
    k = float(accel)
    update_mode = str(update_mode or "global").lower()
    init_mode = str(init_mode or "obs").lower()
    update_operator = str(update_operator or "identity").lower()
    conv_metric = str(convergence_metric or "land_weighted_mean").lower()
    output_mode = str(output_mode or "preserve_observed_outside_mask").lower()

    if init_mode == "zeros":
        gtrue = np.zeros_like(gobs_ref)
    elif init_mode in ("mask", "obs_mask"):
        gtrue = np.zeros_like(gobs_ref)
        gtrue[m] = gobs_ref[m]
    else:
        gtrue = gobs_ref.copy()

    hist = []
    last_pre = np.full_like(gobs_ref, np.nan)
    last_ocean = 0.0
    w_lat = _lat_area_weights(lat_vec, gobs.shape[0])
    best_err = np.inf
    no_improve = 0

    for it in range(1, n_iter + 1):
        if should_continue is not None and not should_continue():
            break

        g_iter, ocean_val = _apply_mass_conservation(
            gtrue,
            m,
            lat_vec,
            mass_conservation,
            lat_weights=w_lat,
            balance_mask=bmask,
        )
        gpre = apply_forward_operator(g_iter, lon_vec, lat_vec, options)
        delta = gobs_ref - gpre

        if update_operator in ("forward", "a", "operator"):
            delta_upd = apply_forward_operator(delta, lon_vec, lat_vec, options)
        else:
            delta_upd = delta
        delta_upd = np.where(np.isfinite(delta_upd), delta_upd, 0.0)

        # Script-style residual metric on current delta.
        if conv_metric in ("rmse", "land_rmse"):
            err = float(np.sqrt(np.nanmean((delta[m]) ** 2)))
        elif conv_metric in ("mean_abs", "land_mean_abs"):
            err = float(np.nanmean(np.abs(delta[m])))
        elif conv_metric in ("masked_abs_integral", "modeled_area_abs_integral", "weighted_abs_integral"):
            err = float(np.nansum(np.abs(np.where(np.isfinite(delta), delta, 0.0)[m]) * w_lat[m]))
        else:
            # MATLAB script convergence metric: |mean delta over land|.
            err = float(np.abs(np.nanmean(delta[m])))

        # Script-style update: fixed acceleration k, no extra damping/smoothing.
        if update_mode == "mask":
            gtrue[m] = gtrue[m] + k * delta_upd[m]
        else:
            gtrue = gtrue + k * delta_upd

        last_pre = gpre
        last_ocean = ocean_val
        hist.append(err)
        if np.isfinite(err):
            if err < (best_err - min_improve):
                best_err = err
                no_improve = 0
            else:
                no_improve += 1
        if iter_cb is not None:
            iter_cb(it, n_iter, err)
        if it >= min_iter and tol > 0 and np.isfinite(err) and err < tol:
            break
        if it >= min_iter and stagnation_patience > 0 and no_improve >= stagnation_patience:
            break

    gcorr_balanced, ocean_final = _apply_mass_conservation(
        gtrue,
        m,
        lat_vec,
        mass_conservation,
        lat_weights=w_lat,
        balance_mask=bmask,
    )
    gcorr = np.asarray(gcorr_balanced, dtype=float)
    if output_mode in (
        "preserve_observed_outside_mask",
        "restore_input_outside_mask",
        "blend_observed",
    ):
        gcorr = np.where(m, gcorr, gobs)
    elif output_mode in ("nan_outside_mask", "mask_nan"):
        gcorr = np.where(m, gcorr, np.nan)
    return gcorr, {
        "nIter": np.array([len(hist)], dtype=int),
        "rmse_hist": np.asarray(hist, dtype=float),
        "final_rmse": np.asarray([hist[-1] if hist else np.nan], dtype=float),
        "ocean_value_last": np.asarray([last_ocean], dtype=float),
        "ocean_value_final": np.asarray([ocean_final], dtype=float),
        "obs_prefiltered": np.asarray([1 if prefilter_obs else 0], dtype=int),
        "pre_last": np.asarray(last_pre, dtype=float),
        "final_balanced": np.asarray(gcorr_balanced, dtype=float),
    }


def fm_correct_stack(
    grid3d: np.ndarray,
    mask: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    options: LeakageFilterOptions,
    n_iter: int = 30,
    tol_rmse_mm: float = 0.1,
    update_mode: str = "global",
    init_mode: str = "obs",
    mass_conservation: str = "ocean_uniform_land_balance",
    update_operator: str = "identity",
    convergence_metric: str = "land_weighted_mean",
    accel: float = 1.2,
    output_mode: str = "preserve_observed_outside_mask",
    balance_mask: Optional[np.ndarray] = None,
    month_cb: Optional[Callable[[int, int], None]] = None,
    iter_cb: Optional[Callable[[int, int, int, float], None]] = None,
    should_continue: Optional[Callable[[], bool]] = None,
) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """FM correction for stack [nLon x nLat x Nt]."""
    g3 = np.asarray(grid3d, dtype=float)
    if g3.ndim == 2:
        g3 = g3[:, :, np.newaxis]
    if g3.ndim != 3:
        raise ValueError("FM stack must be 2D/3D array.")

    nt = g3.shape[2]
    out = np.full_like(g3, np.nan, dtype=float)
    err_all = []
    it_all = []

    for k in range(nt):
        if should_continue is not None and not should_continue():
            break
        if month_cb is not None:
            month_cb(k + 1, nt)

        def _iter_cb(it: int, nmax: int, err: float):
            if iter_cb is not None:
                iter_cb(k + 1, nt, it, err)

        corr, info = fm_correct_month(
            g3[:, :, k],
            mask,
            lon_vec,
            lat_vec,
            options,
            n_iter=n_iter,
            tol_rmse_mm=tol_rmse_mm,
            update_mode=update_mode,
            init_mode=init_mode,
            mass_conservation=mass_conservation,
            update_operator=update_operator,
            convergence_metric=convergence_metric,
            accel=accel,
            output_mode=output_mode,
            balance_mask=balance_mask,
            iter_cb=_iter_cb,
            should_continue=should_continue,
        )
        out[:, :, k] = corr
        err_all.append(float(np.asarray(info.get("final_rmse", [np.nan])).reshape(-1)[0]))
        it_all.append(int(np.asarray(info.get("nIter", [0])).reshape(-1)[0]))

    return out, {
        "rmse_final_by_month": np.asarray(err_all, dtype=float),
        "n_iter_by_month": np.asarray(it_all, dtype=int),
    }


def fm_estimate_scale_factor_from_rate(
    obs_rate: np.ndarray,
    mask: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    options: LeakageFilterOptions,
    n_iter: int = 30,
    tol_rmse_mm_per_yr: float = 0.03,
    accel: float = 1.2,
    balance_mask: Optional[np.ndarray] = None,
    convergence_metric: str = "modeled_area_abs_integral",
    iter_cb: Optional[Callable[[int, int, float], None]] = None,
    should_continue: Optional[Callable[[], bool]] = None,
) -> Tuple[float, Dict[str, np.ndarray]]:
    """
    FM-based scale factor estimation on a rate map.
    """
    r_obs = ensure_latlon_order(np.asarray(obs_rate, dtype=float), lon_vec, lat_vec, target_order="lon_lat")
    m = np.asarray(mask, dtype=bool)
    if r_obs.ndim != 2 or m.shape != r_obs.shape:
        raise ValueError("obs_rate and mask must be same-shape 2D grids.")
    if not np.any(m):
        raise ValueError("Mask is empty for FM scale-factor estimation.")
    if int(np.count_nonzero(np.isfinite(r_obs[m]))) < 3:
        raise ValueError("Observed rate has too few finite values inside mask.")

    r_rec, info = fm_correct_month(
        r_obs,
        m,
        lon_vec,
        lat_vec,
        options,
        n_iter=n_iter,
        tol_rmse_mm=tol_rmse_mm_per_yr,
        update_mode="mask",
        init_mode="mask",
        mass_conservation=("ocean_uniform_land_balance" if balance_mask is not None else "none"),
        convergence_metric=convergence_metric,
        accel=accel,
        output_mode="preserve_observed_outside_mask",
        balance_mask=balance_mask,
        iter_cb=iter_cb,
        should_continue=should_continue,
    )

    mu_obs = _weighted_mask_mean(r_obs, m, lat_vec)
    mu_rec = _weighted_mask_mean(r_rec, m, lat_vec)
    if (
        np.isfinite(mu_obs)
        and (not np.isclose(mu_obs, 0.0))
        and np.isfinite(mu_rec)
        and (np.sign(mu_obs) == np.sign(mu_rec))
    ):
        sf = float(mu_rec / mu_obs)
        sf_metric = "mean_ratio"
    else:
        rms_obs = float(np.sqrt(np.nanmean((r_obs[m]) ** 2)))
        rms_rec = float(np.sqrt(np.nanmean((r_rec[m]) ** 2)))
        if (not np.isfinite(rms_obs)) or np.isclose(rms_obs, 0.0):
            raise ValueError("Observed mean/rms in mask is invalid/zero for FM factor.")
        sf = float(rms_rec / rms_obs)
        sf_metric = "rms_ratio"
    sf = float(np.clip(abs(sf), 0.25, 8.0))

    r_pre = np.asarray(info.get("pre_last", np.full_like(r_obs, np.nan)), dtype=float)
    return sf, {
        "nIter": np.asarray(info.get("nIter", [0]), dtype=int),
        "rmse_hist": np.asarray(info.get("rmse_hist", []), dtype=float),
        "final_rmse": np.asarray(info.get("final_rmse", [np.nan]), dtype=float),
        "rate_obs": r_obs,
        "rate_rec": r_rec,
        "rate_pre": r_pre,
        "mean_obs": np.asarray([mu_obs], dtype=float),
        "mean_rec": np.asarray([mu_rec], dtype=float),
        "sf_metric": np.asarray([sf_metric], dtype=object),
    }


def compute_global_coastal_gaussian_stack(
    grid3d: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    options: LeakageFilterOptions,
    *,
    land_mask: np.ndarray,
    reference_stack: Optional[np.ndarray] = None,
    coastal_buffer_cells: int = 3,
    attenuation_gain: float = 1.0,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Literature-inspired global coastal correction for Gaussian-smoothed SH grids.

    The implementation separates land/ocean supports and estimates leakage terms
    from land->ocean and ocean->land using the same forward operator. It is
    intentionally restricted to Gaussian-equivalent operators.
    """
    method = _normalize_method(getattr(options, "method", "GAUSSIAN"))
    if method not in ("GAUSSIAN", "NONE"):
        raise ValueError("Global coastal Gaussian correction is only defined for Gaussian-equivalent filters.")

    g3 = np.asarray(grid3d, dtype=float)
    if g3.ndim == 2:
        g3 = g3[:, :, None]
    land = np.asarray(land_mask, dtype=bool)
    if g3.ndim != 3 or land.shape != g3.shape[:2]:
        raise ValueError("grid3d and land_mask shape mismatch.")

    ocean = ~land
    coastal_buffer_cells = max(1, int(coastal_buffer_cells))
    coastal_land = binary_dilation(ocean, iterations=coastal_buffer_cells) & land
    coastal_ocean = binary_dilation(land, iterations=coastal_buffer_cells) & ocean
    if not np.any(coastal_land) and not np.any(coastal_ocean):
        raise ValueError("Coastal buffer is empty on current grid.")

    if reference_stack is None:
        reference_stack = g3
    ref3 = np.asarray(reference_stack, dtype=float)
    if ref3.ndim == 2:
        ref3 = ref3[:, :, None]
    if ref3.shape[:2] != g3.shape[:2]:
        raise ValueError("reference_stack shape mismatch.")
    if ref3.shape[2] == 1 and g3.shape[2] > 1:
        ref3 = np.repeat(ref3, g3.shape[2], axis=2)
    if ref3.shape[2] != g3.shape[2]:
        raise ValueError("reference_stack length mismatch.")

    out = g3.copy()
    land_leak_metric = np.full(g3.shape[2], np.nan, dtype=float)
    ocean_leak_metric = np.full(g3.shape[2], np.nan, dtype=float)
    residual_metric = np.full(g3.shape[2], np.nan, dtype=float)
    last_terms: Dict[str, np.ndarray] = {}

    for k in range(g3.shape[2]):
        ref = ref3[:, :, k]
        land_ref = np.where(land, ref, 0.0)
        ocean_ref = np.where(ocean, ref, 0.0)
        land_forward = apply_forward_operator(land_ref, lon_vec, lat_vec, options)
        ocean_forward = apply_forward_operator(ocean_ref, lon_vec, lat_vec, options)
        land_to_ocean = np.where(coastal_ocean, land_forward, 0.0)
        ocean_to_land = np.where(coastal_land, ocean_forward, 0.0)
        attenuation = np.where(coastal_land, (land_ref - land_forward) * float(attenuation_gain), 0.0)

        corrected = np.asarray(g3[:, :, k], dtype=float).copy()
        corrected[coastal_ocean] = corrected[coastal_ocean] - land_to_ocean[coastal_ocean]
        corrected[coastal_land] = corrected[coastal_land] - ocean_to_land[coastal_land] + attenuation[coastal_land]
        out[:, :, k] = corrected

        land_leak_metric[k] = float(np.nanmean(np.abs(land_to_ocean[coastal_ocean]))) if np.any(coastal_ocean) else 0.0
        ocean_leak_metric[k] = float(np.nanmean(np.abs(ocean_to_land[coastal_land]))) if np.any(coastal_land) else 0.0
        residual_metric[k] = float(np.nanmean(np.abs(corrected - g3[:, :, k])))
        last_terms = {
            "land_to_ocean": land_to_ocean,
            "ocean_to_land": ocean_to_land,
            "attenuation": attenuation,
        }

    return out, {
        "coastal_land_mask": coastal_land,
        "coastal_ocean_mask": coastal_ocean,
        "land_to_ocean_metric": land_leak_metric,
        "ocean_to_land_metric": ocean_leak_metric,
        "residual_metric_by_month": residual_metric,
        **last_terms,
    }


def regularized_restore_stack(
    grid3d: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    options: LeakageFilterOptions,
    *,
    reg_lambda: float = 0.18,
    step_size: float = 0.9,
    smooth_sigma: float = 1.2,
    n_iter: int = 10,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Lightweight global regularized restoration.

    This is a pragmatic Tikhonov-like solver for v1: iterate on the residual
    under the matched forward operator while damping high-frequency growth with
    an isotropic smoothness prior.
    """
    g3 = np.asarray(grid3d, dtype=float)
    if g3.ndim == 2:
        g3 = g3[:, :, None]
    if g3.ndim != 3:
        raise ValueError("grid3d must be 2D or 3D.")

    lam = float(max(0.0, reg_lambda))
    alpha = float(step_size)
    sigma = float(max(0.25, smooth_sigma))
    nit = max(1, int(n_iter))

    out = np.asarray(g3, dtype=float).copy()
    month_err = np.full(g3.shape[2], np.nan, dtype=float)
    residual_history = []

    for k in range(g3.shape[2]):
        y = np.asarray(g3[:, :, k], dtype=float)
        x = y.copy()
        hist = []
        for _ in range(nit):
            hx = apply_forward_operator(x, lon_vec, lat_vec, options)
            residual = np.where(np.isfinite(y - hx), y - hx, 0.0)
            smooth_x = gaussian_filter(x, sigma=sigma, mode="nearest")
            x = x + alpha * residual - lam * (x - smooth_x)
            err = float(np.sqrt(np.nanmean(residual**2)))
            hist.append(err)
        out[:, :, k] = x
        month_err[k] = hist[-1] if hist else np.nan
        residual_history.append(hist)

    return out, {
        "residual_metric_by_month": month_err,
        "residual_history": np.asarray(residual_history, dtype=float),
        "regularization": {
            "lambda": lam,
            "step_size": alpha,
            "smooth_sigma": sigma,
            "n_iter": nit,
        },
    }
