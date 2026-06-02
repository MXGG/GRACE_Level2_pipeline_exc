"""Validation runner for literature-aligned leakage correction paths."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import scipy.io as sio


ROOT = Path(__file__).resolve().parents[3]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from grace_pipeline.app.leakage_helpers import (
    build_global_land_mask,
    build_leakage_filter_options,
    save_leakage_bundle,
)
from grace_pipeline.basin import read_boundary, make_mask
from grace_pipeline.domain.leakage import (
    apply_gridded_gain_factors_stack,
    apply_scale_factors_stack,
    classify_leakage_scene,
    compute_basin_scale_factor_from_reference,
    compute_gridded_gain_factors,
    compute_masked_series,
    infer_operator_spec,
    recommend_correction_method,
)
from grace_pipeline.infra.stack.loader import load_stack_any


def _write_polygon(path: Path, coords: list[tuple[float, float]]):
    path.write_text("\n".join(f"{lon} {lat}" for lon, lat in coords), encoding="utf-8")


def _save_stack(path: Path, stack: np.ndarray, lon_vec: np.ndarray, lat_vec: np.ndarray, labels: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    sio.savemat(path, {"ewh": stack, "lon": lon_vec, "lat": lat_vec, "t": np.asarray(labels, dtype=object)})


def _load_stack(path: Path):
    ewh, lon, lat, t, meta = load_stack_any(str(path))
    labels = [str(x) for x in np.asarray(t).reshape(-1)]
    return np.asarray(ewh, dtype=float), np.asarray(lon, dtype=float), np.asarray(lat, dtype=float), labels, meta


def _rmse(a: np.ndarray, b: np.ndarray) -> float:
    aa = np.asarray(a, dtype=float).reshape(-1)
    bb = np.asarray(b, dtype=float).reshape(-1)
    return float(np.sqrt(np.nanmean((aa - bb) ** 2)))


def _prepare_masks(boundary_path: Path, lon_vec: np.ndarray, lat_vec: np.ndarray, *, coastal_land_only: bool):
    region_mask = make_mask(read_boundary(str(boundary_path))[0], lon_vec, lat_vec)
    land_mask, _ = build_global_land_mask(lon_vec, lat_vec, root_dir=str(ROOT))
    target_mask = region_mask & land_mask if coastal_land_only else region_mask
    if not np.any(target_mask):
        raise ValueError(f"Target mask is empty for boundary: {boundary_path}")
    return region_mask, target_mask, land_mask


def _run_basin_sf_case(
    *,
    case_dir: Path,
    case_name: str,
    filtered_stack_path: Path,
    reference_stack_path: Path,
    boundary_path: Path,
):
    reference, lon, lat, labels, _ = _load_stack(reference_stack_path)
    filtered, lon_f, lat_f, labels_f, meta = _load_stack(filtered_stack_path)
    if reference.shape != filtered.shape:
        raise ValueError(f"Reference/filtered stack shape mismatch: {reference.shape} vs {filtered.shape}")
    if not (np.allclose(lon, lon_f) and np.allclose(lat, lat_f)):
        raise ValueError("Reference and filtered stacks use different grids.")

    region_mask, target_mask, land_mask = _prepare_masks(boundary_path, lon, lat, coastal_land_only=False)
    opts = build_leakage_filter_options(raw_method="AUTO", in_path=str(filtered_stack_path), data_meta=meta)
    operator = infer_operator_spec(str(filtered_stack_path), opts, data_meta=meta, source="validation")
    scene = classify_leakage_scene(region_mask, lon, lat, global_land_mask=land_mask)
    method = recommend_correction_method("basin_scale_factor", scene, operator, has_reference_model=True)
    if method not in ("BASIN_SCALE_FACTOR", "SCALE_FACTOR"):
        method = "BASIN_SCALE_FACTOR"

    factor, info = compute_basin_scale_factor_from_reference(reference, target_mask, lon, lat, opts)
    corrected = apply_scale_factors_stack(filtered, target_mask, np.asarray([factor], dtype=float))

    raw_series = compute_masked_series(reference, target_mask, lat)
    filtered_series = compute_masked_series(filtered, target_mask, lat)
    corrected_series = compute_masked_series(corrected, target_mask, lat)
    filtered_rmse = _rmse(filtered_series, raw_series)
    corrected_rmse = _rmse(corrected_series, raw_series)

    out_file = case_dir / f"{case_name}.mat"
    _save_stack(out_file, corrected, lon, lat, labels_f)
    bundle = save_leakage_bundle(
        output_file=str(out_file),
        raw_stack=filtered,
        corrected_stack=corrected,
        lon_vec=lon,
        lat_vec=lat,
        labels=labels_f,
        mask=target_mask,
        method="BASIN_SCALE_FACTOR",
        scene_info=scene.__dict__,
        operator_info=operator.__dict__,
        validation={
            "regional_series_reference": raw_series,
            "residual_metric_by_month": np.abs(corrected_series - raw_series),
            "representative_index": int(np.nanargmax(np.abs(corrected_series - filtered_series))),
        },
        extra_meta={
            "reference_stack": str(reference_stack_path),
            "filtered_stack": str(filtered_stack_path),
            "basin_scale_factor": float(factor),
            "filtered_rmse_to_reference": filtered_rmse,
            "corrected_rmse_to_reference": corrected_rmse,
            "rmse_improvement_pct": (100.0 * (filtered_rmse - corrected_rmse) / filtered_rmse) if filtered_rmse > 0 else None,
            "filtered_series_mean": float(np.nanmean(info["filtered_series"])),
            "reference_series_mean": float(np.nanmean(info["reference_series"])),
        },
    )
    return {
        "case": case_name,
        "method": "BASIN_SCALE_FACTOR",
        "stack": str(filtered_stack_path),
        "reference": str(reference_stack_path),
        "bundle": bundle,
        "filtered_rmse_to_reference": filtered_rmse,
        "corrected_rmse_to_reference": corrected_rmse,
        "rmse_improvement_pct": (100.0 * (filtered_rmse - corrected_rmse) / filtered_rmse) if filtered_rmse > 0 else None,
    }


def _run_gridded_gain_case(
    *,
    case_dir: Path,
    case_name: str,
    filtered_stack_path: Path,
    reference_stack_path: Path,
    boundary_path: Path,
):
    reference, lon, lat, labels, _ = _load_stack(reference_stack_path)
    filtered, lon_f, lat_f, labels_f, meta = _load_stack(filtered_stack_path)
    if reference.shape != filtered.shape:
        raise ValueError(f"Reference/filtered stack shape mismatch: {reference.shape} vs {filtered.shape}")
    if not (np.allclose(lon, lon_f) and np.allclose(lat, lat_f)):
        raise ValueError("Reference and filtered stacks use different grids.")

    region_mask, target_mask, land_mask = _prepare_masks(boundary_path, lon, lat, coastal_land_only=True)
    opts = build_leakage_filter_options(raw_method="AUTO", in_path=str(filtered_stack_path), data_meta=meta)
    operator = infer_operator_spec(str(filtered_stack_path), opts, data_meta=meta, source="validation")
    scene = classify_leakage_scene(region_mask, lon, lat, global_land_mask=land_mask)
    method = recommend_correction_method("gridded_gain_factor", scene, operator, has_reference_model=True)
    if method != "GRIDDED_GAIN_FACTOR":
        method = "GRIDDED_GAIN_FACTOR"

    gains, _ = compute_gridded_gain_factors(reference, lon, lat, opts, target_mask=target_mask)
    corrected = apply_gridded_gain_factors_stack(filtered, gains, target_mask=target_mask)

    raw_series = compute_masked_series(reference, target_mask, lat)
    filtered_series = compute_masked_series(filtered, target_mask, lat)
    corrected_series = compute_masked_series(corrected, target_mask, lat)
    filtered_rmse = _rmse(filtered_series, raw_series)
    corrected_rmse = _rmse(corrected_series, raw_series)

    out_file = case_dir / f"{case_name}.mat"
    _save_stack(out_file, corrected, lon, lat, labels_f)
    bundle = save_leakage_bundle(
        output_file=str(out_file),
        raw_stack=filtered,
        corrected_stack=corrected,
        lon_vec=lon,
        lat_vec=lat,
        labels=labels_f,
        mask=target_mask,
        method="GRIDDED_GAIN_FACTOR",
        scene_info=scene.__dict__,
        operator_info=operator.__dict__,
        validation={
            "regional_series_reference": raw_series,
            "residual_metric_by_month": np.abs(corrected_series - raw_series),
            "representative_index": int(np.nanargmax(np.abs(corrected_series - filtered_series))),
        },
        extra_meta={
            "reference_stack": str(reference_stack_path),
            "filtered_stack": str(filtered_stack_path),
            "gain_grid_min": float(np.nanmin(gains[target_mask])),
            "gain_grid_median": float(np.nanmedian(gains[target_mask])),
            "gain_grid_max": float(np.nanmax(gains[target_mask])),
            "filtered_rmse_to_reference": filtered_rmse,
            "corrected_rmse_to_reference": corrected_rmse,
            "rmse_improvement_pct": (100.0 * (filtered_rmse - corrected_rmse) / filtered_rmse) if filtered_rmse > 0 else None,
            "reference_note": "RAW_stack is used here only as a pseudo-reference for workflow regression checks.",
        },
    )
    return {
        "case": case_name,
        "method": "GRIDDED_GAIN_FACTOR",
        "stack": str(filtered_stack_path),
        "reference": str(reference_stack_path),
        "bundle": bundle,
        "filtered_rmse_to_reference": filtered_rmse,
        "corrected_rmse_to_reference": corrected_rmse,
        "rmse_improvement_pct": (100.0 * (filtered_rmse - corrected_rmse) / filtered_rmse) if filtered_rmse > 0 else None,
    }


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_root = ROOT / "output" / "local" / "leakage_validation" / timestamp
    out_root.mkdir(parents=True, exist_ok=True)

    inland_boundary = out_root / "amazon_box.txt"
    coastal_boundary = out_root / "china_coast_box.txt"
    _write_polygon(inland_boundary, [(-75, -15), (-50, -15), (-50, 5), (-75, 5), (-75, -15)])
    _write_polygon(coastal_boundary, [(110, 18), (125, 18), (125, 32), (110, 32), (110, 18)])

    stacks_root = ROOT / "output" / "20260210" / "local" / "stacks"
    raw_stack = stacks_root / "RAW_stack.mat"
    results = [
        _run_basin_sf_case(
            case_dir=out_root / "case_inland_gauss_p4m6_basin_sf",
            case_name="gauss_p4m6_inland_basin_sf",
            filtered_stack_path=stacks_root / "GAUSS+P4M6_stack.mat",
            reference_stack_path=raw_stack,
            boundary_path=inland_boundary,
        ),
        _run_gridded_gain_case(
            case_dir=out_root / "case_coastal_ddk4_gridgain",
            case_name="ddk4_coastal_gridgain",
            filtered_stack_path=stacks_root / "DDK4_stack.mat",
            reference_stack_path=raw_stack,
            boundary_path=coastal_boundary,
        ),
        _run_basin_sf_case(
            case_dir=out_root / "case_inland_fan_basin_sf",
            case_name="fan_inland_basin_sf",
            filtered_stack_path=stacks_root / "FAN_stack.mat",
            reference_stack_path=raw_stack,
            boundary_path=inland_boundary,
        ),
    ]

    summary = {
        "output_root": str(out_root),
        "reference_stack": str(raw_stack),
        "cases": results,
    }
    (out_root / "validation_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
