"""ICGEM-style C/S coefficient export helpers."""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from grace_pipeline.core.config import CoefficientExportConfig
from grace_pipeline.inversion.sh_synthesis import ewh_analysis, ewh_synthesis


@dataclass
class FilteredMonthlyProduct:
    year_month: str
    center: str
    release: str
    method: str
    source_domain: str
    cs_available: bool
    clm: Optional[np.ndarray]
    slm: Optional[np.ndarray]
    grid_available: bool
    grid: Optional[np.ndarray]
    grid_unit: Optional[str]
    lon: Optional[np.ndarray]
    lat: Optional[np.ndarray]
    max_degree: int
    metadata: Dict[str, Any] = field(default_factory=dict)


def _safe_token(value: Any, fallback: str = "UNKNOWN") -> str:
    text = str(value or fallback).strip()
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^0-9A-Za-z_.+-]+", "_", text)
    return text.strip("_") or fallback


def method_output_dir(method: str) -> str:
    token = _safe_token(method, "method")
    if token.startswith("GAUSS_P4M6") or token == "GAUSS_P4M6":
        return "Gaussian_PnMl"
    if token.startswith("GAUSS+P4M6") or token == "GAUSS+P4M6":
        return "Gaussian_PnMl"
    if token.startswith("FAN_P4M6") or token == "FAN_P4M6":
        return "FAN_PnMl"
    if token.startswith("FAN+P4M6") or token == "FAN+P4M6":
        return "FAN_PnMl"
    if token.startswith("P4M6"):
        return "PnMl"
    if token.startswith("GAUSS"):
        return "Gaussian"
    if token.startswith("DDK"):
        return "DDK"
    return token


def method_file_token(method: str) -> str:
    token = _safe_token(method, "method")
    return (
        token.replace("GAUSS+P4M6", "Gaussian_PnMl")
        .replace("GAUSS_P4M6", "Gaussian_PnMl")
        .replace("FAN+P4M6", "FAN_PnMl")
        .replace("FAN_P4M6", "FAN_PnMl")
        .replace("P4M6", "PnMl")
        .replace("GAUSS", "Gaussian")
    )


def validate_global_regular_grid(lon: np.ndarray, lat: np.ndarray, grid: np.ndarray) -> None:
    lon_arr = np.asarray(lon, dtype=float).ravel()
    lat_arr = np.asarray(lat, dtype=float).ravel()
    grid_arr = np.asarray(grid, dtype=float)
    if lon_arr.size < 4 or lat_arr.size < 4:
        raise ValueError("C/S export requires a global regular grid with at least 4 lon/lat samples.")
    if grid_arr.shape[:2] != (lon_arr.size, lat_arr.size):
        raise ValueError(f"C/S export grid shape mismatch: expected {(lon_arr.size, lat_arr.size)}, got {grid_arr.shape}.")
    if not np.isfinite(grid_arr).all():
        raise ValueError("C/S export from grid requires finite values; NaN or Inf was found.")

    lon_step = np.diff(lon_arr)
    lat_step = np.diff(lat_arr)
    if not np.allclose(lon_step, lon_step[0], rtol=1e-5, atol=1e-8):
        raise ValueError("C/S export requires regularly spaced longitudes.")
    if not np.allclose(lat_step, lat_step[0], rtol=1e-5, atol=1e-8):
        raise ValueError("C/S export requires regularly spaced latitudes.")
    lon_coverage = abs(lon_arr[-1] - lon_arr[0]) + abs(lon_step[0])
    lat_coverage = abs(lat_arr[-1] - lat_arr[0]) + abs(lat_step[0])
    if lon_coverage < 359.5 or lat_coverage < 179.0:
        raise ValueError(
            "C/S export from regional grid is not allowed. Please use global regular grid or provide a global background."
        )


def truncate_cs(clm: np.ndarray, slm: np.ndarray, lmax: int) -> tuple[np.ndarray, np.ndarray]:
    c = np.asarray(clm, dtype=np.float64)[: lmax + 1, : lmax + 1].copy()
    s = np.asarray(slm, dtype=np.float64)[: lmax + 1, : lmax + 1].copy()
    c[~np.isfinite(c)] = 0.0
    s[~np.isfinite(s)] = 0.0
    for degree in range(lmax + 1):
        if degree + 1 < c.shape[1]:
            c[degree, degree + 1 :] = 0.0
            s[degree, degree + 1 :] = 0.0
    s[:, 0] = 0.0
    return c, s


def _roundtrip_check(
    clm: np.ndarray,
    slm: np.ndarray,
    original_grid: np.ndarray,
    lon: np.ndarray,
    lat: np.ndarray,
    unit: str,
) -> Dict[str, float]:
    reconstructed = ewh_synthesis(clm, slm, int(clm.shape[0] - 1), lon, lat, unit=unit)
    original = np.asarray(original_grid, dtype=np.float64)
    diff = reconstructed - original
    finite = np.isfinite(diff) & np.isfinite(original) & np.isfinite(reconstructed)
    if not finite.any():
        return {
            "roundtrip_rmse": math.nan,
            "roundtrip_max_abs_error": math.nan,
            "roundtrip_mean_bias": math.nan,
            "roundtrip_corr": math.nan,
        }
    x = original[finite].ravel()
    y = reconstructed[finite].ravel()
    corr = float(np.corrcoef(x, y)[0, 1]) if x.size > 1 and np.std(x) > 0 and np.std(y) > 0 else math.nan
    return {
        "roundtrip_rmse": float(np.sqrt(np.mean(diff[finite] ** 2))),
        "roundtrip_max_abs_error": float(np.max(np.abs(diff[finite]))),
        "roundtrip_mean_bias": float(np.mean(diff[finite])),
        "roundtrip_corr": corr,
    }


def _build_output_path(product: FilteredMonthlyProduct, config: CoefficientExportConfig, output_root: Path, lmax: int) -> Path:
    content = _safe_token(config.coefficient_content, "anomaly")
    method_token = method_file_token(product.method)
    filename = config.filename_template.format(
        center=_safe_token(product.center, "CSR"),
        year_month=_safe_token(product.year_month, "YYYY-MM"),
        method=method_token,
        max_degree=int(lmax),
        content=content,
    )
    return output_root / method_output_dir(product.method) / filename


def write_icgem_gfc(
    output_path: Path,
    clm: np.ndarray,
    slm: np.ndarray,
    config: CoefficientExportConfig,
    product: FilteredMonthlyProduct,
    source_domain: str,
    grid_to_cs: bool,
    diagnostics: Optional[Dict[str, float]] = None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    modelname = output_path.stem
    comments = {
        "coefficient_content": config.coefficient_content,
        "source_product": f"{product.center}_{product.release}",
        "year_month": product.year_month,
        "filter_method": product.method,
        "source_domain": source_domain,
        "grid_to_cs": str(bool(grid_to_cs)).lower(),
        "baseline": product.metadata.get("baseline", ""),
        "low_degree_replacement": product.metadata.get("low_degree_replacement", ""),
        "gia_model": product.metadata.get("gia_model", ""),
        "max_degree": str(clm.shape[0] - 1),
        "grid_unit_for_inverse": product.grid_unit or config.unit_for_grid_inverse,
    }
    for key, value in product.metadata.items():
        if key not in comments and value not in (None, ""):
            comments[key] = value
    if diagnostics:
        for key, value in diagnostics.items():
            comments[key] = value

    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        f.write("# GRACE-L2 Pipeline generated coefficient product\n")
        for key, value in comments.items():
            if value not in (None, ""):
                f.write(f"# {key} {value}\n")
        f.write("\nbegin_of_head\n")
        f.write("product_type gravity_field\n")
        f.write(f"modelname {modelname}\n")
        f.write(f"earth_gravity_constant {config.earth_gravity_constant:.10E}\n")
        f.write(f"radius {config.radius:.10E}\n")
        f.write(f"max_degree {clm.shape[0] - 1}\n")
        f.write(f"errors {config.errors}\n")
        f.write(f"norm {config.norm}\n")
        f.write(f"tide_system {config.tide_system}\n")
        f.write("end_of_head\n\n")
        lmax = clm.shape[0] - 1
        for degree in range(lmax + 1):
            for order in range(degree + 1):
                sval = 0.0 if order == 0 else float(slm[degree, order])
                f.write(f"gfc {degree:5d} {order:5d} {float(clm[degree, order]):+.16e} {sval:+.16e}\n")
    tmp.replace(output_path)


def export_monthly_coefficients(
    product: FilteredMonthlyProduct,
    config: CoefficientExportConfig,
    output_root: Path,
    *,
    reference_clm: Optional[np.ndarray] = None,
    reference_slm: Optional[np.ndarray] = None,
) -> Optional[Dict[str, Any]]:
    if not config.enabled:
        return None
    content = str(config.coefficient_content or "anomaly").strip().lower()
    if content not in {"anomaly", "full"}:
        raise ValueError(f"Unknown coefficient_content: {config.coefficient_content}")

    lmax = int(config.max_degree or product.max_degree)
    if lmax > int(product.max_degree):
        raise ValueError(f"C/S export max_degree {lmax} exceeds product max_degree {product.max_degree}.")

    diagnostics: Optional[Dict[str, float]] = None
    if product.cs_available and product.clm is not None and product.slm is not None:
        clm, slm = truncate_cs(product.clm, product.slm, lmax)
        source_domain = "spherical_harmonic"
        grid_to_cs = False
    elif product.grid_available and config.allow_grid_to_cs and product.grid is not None and product.lon is not None and product.lat is not None:
        if config.require_global_grid:
            validate_global_regular_grid(product.lon, product.lat, product.grid)
        unit = product.grid_unit or config.unit_for_grid_inverse or "mmEWH"
        clm, slm = ewh_analysis(product.grid, lmax, product.lon, product.lat, unit=unit)
        clm, slm = truncate_cs(clm, slm, lmax)
        source_domain = "grid"
        grid_to_cs = True
        if config.roundtrip_check:
            diagnostics = _roundtrip_check(clm, slm, product.grid, product.lon, product.lat, unit)
    else:
        raise ValueError("No available C/S or global grid product for coefficient export.")

    if content == "full":
        if reference_clm is None or reference_slm is None:
            raise ValueError("Full coefficient export requires reference coefficients.")
        ref_c, ref_s = truncate_cs(reference_clm, reference_slm, lmax)
        clm = ref_c + clm
        slm = ref_s + slm
    else:
        clm[0, 0] = 0.0
        slm[0, 0] = 0.0

    output_path = _build_output_path(product, config, output_root, lmax)
    write_icgem_gfc(output_path, clm, slm, config, product, source_domain, grid_to_cs, diagnostics)
    manifest: Dict[str, Any] = {
        "year_month": product.year_month,
        "method": product.method,
        "gfc_file": str(output_path),
        "source_domain": source_domain,
        "grid_to_cs": grid_to_cs,
        "coefficient_content": content,
        "max_degree": lmax,
    }
    if diagnostics:
        manifest.update(diagnostics)
    return manifest


def update_coefficient_summary(summary: Dict[str, Any], manifest: Dict[str, Any]) -> None:
    method = str(manifest.get("method") or "UNKNOWN")
    methods = summary.setdefault("methods", {})
    method_summary = methods.setdefault(
        method,
        {
            "source_domain": manifest.get("source_domain"),
            "grid_to_cs": bool(manifest.get("grid_to_cs", False)),
            "file_count": 0,
        },
    )
    method_summary["file_count"] = int(method_summary.get("file_count", 0)) + 1
    if manifest.get("grid_to_cs"):
        method_summary["roundtrip_check"] = True
        for key in ("roundtrip_rmse", "roundtrip_max_abs_error", "roundtrip_mean_bias", "roundtrip_corr"):
            if key in manifest and np.isfinite(manifest[key]):
                values_key = f"_{key}_values"
                method_summary.setdefault(values_key, []).append(float(manifest[key]))


def finalize_coefficient_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    clean = json.loads(json.dumps(summary, default=str))
    for method_summary in clean.get("methods", {}).values():
        for key in list(method_summary.keys()):
            if key.startswith("_") and key.endswith("_values"):
                public_key = key[1:-7] + "_mean"
                values = [float(v) for v in method_summary.pop(key) if np.isfinite(float(v))]
                method_summary[public_key] = float(np.mean(values)) if values else math.nan
    return clean


def write_summary_json(summary_dir: Path, coefficient_summary: Dict[str, Any]) -> Path:
    summary_dir.mkdir(parents=True, exist_ok=True)
    payload = {"coefficient_export": finalize_coefficient_summary(coefficient_summary)}
    path = summary_dir / "summary.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return path


def coefficient_config_to_summary(config: CoefficientExportConfig, output_dir: Path, max_degree: int) -> Dict[str, Any]:
    payload = asdict(config)
    payload.update(
        {
            "enabled": bool(config.enabled),
            "format": config.format,
            "coefficient_content": config.coefficient_content,
            "max_degree": int(config.max_degree or max_degree),
            "output_dir": str(output_dir),
            "methods": {},
        }
    )
    return payload
