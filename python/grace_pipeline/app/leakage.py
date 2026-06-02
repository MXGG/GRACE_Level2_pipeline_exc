"""Leakage service extracted from GUI layer."""

import os
import numpy as np
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from datetime import datetime

from grace_pipeline.app.leakage_workers import leakage_fm_month_worker as _leakage_fm_month_worker
from grace_pipeline.app.leakage_helpers import save_leakage_bundle
from grace_pipeline.infra.datasets.grid_ops import regrid_regular
from grace_pipeline.domain.leakage import (
    LeakageFilterOptions,
    apply_gridded_gain_factors_stack,
    apply_scale_factors_stack,
    build_reference_field,
    classify_leakage_scene,
    compute_basin_scale_factor_from_reference,
    compute_global_coastal_gaussian_stack,
    compute_gridded_gain_factors,
    compute_masked_series,
    compute_scale_factor,
    compute_scale_factor_series,
    data_driven_correct_stack,
    estimate_rate_map,
    fm_correct_month,
    infer_operator_spec,
    model_based_additive_correct_stack,
    normalize_correction_method,
    regularized_restore_stack,
    recommend_correction_method,
    resolve_strategy_request,
    strategy_family_for_method,
    strategy_variant_for_method,
)


def _parse_ym_label(label: str):
    text = str(label or "").strip()
    for fmt, width in (("%Y-%m", 7), ("%Y/%m", 7), ("%Y%m", 6), ("%Y-%m-%d", 10), ("%Y/%m/%d", 10)):
        try:
            dt = datetime.strptime(text[:width], fmt)
            return dt.year, dt.month
        except Exception:
            continue
    parts = text.replace("/", "-").split("-")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        return int(parts[0]), int(parts[1])
    return None


def _month_distance(a: str, b: str):
    pa = _parse_ym_label(a)
    pb = _parse_ym_label(b)
    if pa is None or pb is None:
        return None
    return abs((pa[0] - pb[0]) * 12 + (pa[1] - pb[1]))


def _regrid_stack_to_target(grid_in, lon_in, lat_in, lon_out, lat_out):
    arr = np.asarray(grid_in, dtype=float)
    if arr.ndim == 2:
        return regrid_regular(lon_in, lat_in, arr, lon_out, lat_out)
    if arr.ndim != 3:
        raise ValueError("Reference grid must be 2D or 3D.")
    out = np.full((len(lon_out), len(lat_out), arr.shape[2]), np.nan, dtype=float)
    for k in range(arr.shape[2]):
        out[:, :, k] = regrid_regular(lon_in, lat_in, arr[:, :, k], lon_out, lat_out)
    return out


def _align_reference_stack_to_target(ref_grid, ref_labels, target_labels):
    ref_arr = np.asarray(ref_grid, dtype=float)
    if ref_arr.ndim == 2:
        return ref_arr
    if ref_arr.ndim != 3:
        raise ValueError("Reference stack must be 2D or 3D.")
    if ref_arr.shape[2] == len(target_labels):
        return ref_arr
    ref_labels = list(ref_labels or [])
    target_labels = list(target_labels or [])
    if not ref_labels:
        raise ValueError(f"Reference stack length mismatch: input Nt={len(target_labels)}, reference Nt={ref_arr.shape[2]}")
    aligned = np.full((ref_arr.shape[0], ref_arr.shape[1], len(target_labels)), np.nan, dtype=float)
    used = []
    for i, label in enumerate(target_labels):
        if label in ref_labels:
            idx = ref_labels.index(label)
        else:
            distances = [_month_distance(label, rl) for rl in ref_labels]
            finite = [d if d is not None else 999999 for d in distances]
            idx = int(np.argmin(finite)) if finite else -1
            if idx < 0 or finite[idx] > 1:
                raise ValueError(
                    f"Reference stack time mismatch at {label}: no exact/nearest month within tolerance."
                )
        aligned[:, :, i] = ref_arr[:, :, idx]
        used.append(ref_labels[idx])
    return aligned

def run_leakage_correction(self):
    if not bool(self.var_lrc_enable.get()):
        self._msg_warn("Leakage", "Leakage Reduction/Correction is disabled.")
        return
    raw_method = str(self.var_lrc_method.get()).upper()
    scope = str(self.var_lrc_scope.get()).lower()
    in_path = self.var_lrc_input.get().strip()
    if not in_path:
        self._msg_warn("Leakage", "Please select an input data file.")
        return
    out_path = self.var_lrc_output.get().strip()
    try:
        data = self._get_leakage_data()
        grid3d = np.asarray(data["ewh"], dtype=float)
        lon_vec = np.asarray(data["lon"], dtype=float).squeeze()
        lat_vec = np.asarray(data["lat"], dtype=float).squeeze()
        t_arr = data.get("t", None)
        data_meta = data.get("meta", {}) if isinstance(data, dict) else {}
        if grid3d.ndim == 2:
            grid3d = grid3d[:, :, None]
        nt = int(grid3d.shape[2])
        labels = self._infer_time_labels(t_arr, nt)
    except Exception as e:
        self._msg_error("Leakage", f"Failed to load input: {e}")
        return

    try:
        mask = self._build_leakage_mask(scope, lon_vec, lat_vec)
    except Exception as e:
        self._msg_error("Leakage", f"Failed to build leakage mask: {e}")
        return
    opts = self._build_leakage_filter_options(in_path=in_path, data_meta=data_meta)
    operator_spec = infer_operator_spec(in_path, opts, data_meta=data_meta, source="config")
    global_land_mask = None
    try:
        global_land_mask = self._build_global_land_mask(lon_vec, lat_vec)
    except Exception:
        global_land_mask = None
    scene = classify_leakage_scene(mask, lon_vec, lat_vec, global_land_mask=global_land_mask)
    leak_cfg = self.cfg.leakage if isinstance(getattr(self.cfg, "leakage", None), dict) else {}
    scene_override = str(leak_cfg.get("scene_override", "") or "").strip().lower()
    if scene_override:
        scene.scene = scene_override
    reference_mode = str(leak_cfg.get("reference_mode", "trend") or "trend").strip().lower()
    has_reference_model = False
    reference_field = None
    reference_stack = None
    external_reference_stack = None
    reference_scaling_grid = None
    try:
        if leak_cfg.get("reference_input"):
            ref_path = str(leak_cfg.get("reference_input", "")).strip()
            if ref_path:
                ref_data = self._load_stack_any(ref_path)
                ref_grid = np.asarray(ref_data[0], dtype=float)
                ref_lon = np.asarray(ref_data[1], dtype=float).squeeze() if ref_data[1] is not None else None
                ref_lat = np.asarray(ref_data[2], dtype=float).squeeze() if ref_data[2] is not None else None
                ref_labels = self._infer_time_labels(ref_data[3], ref_grid.shape[2]) if ref_grid.ndim == 3 else []
                if ref_lon is not None and ref_lat is not None:
                    same_grid = (
                        ref_lon.ndim == 1
                        and ref_lat.ndim == 1
                        and ref_lon.size == lon_vec.size
                        and ref_lat.size == lat_vec.size
                        and np.allclose(ref_lon, lon_vec)
                        and np.allclose(ref_lat, lat_vec)
                    )
                    if not same_grid:
                        self._append_log(
                            f"[LEAKAGE] Regridding reference data from {ref_lon.size}x{ref_lat.size} to {lon_vec.size}x{lat_vec.size}."
                        )
                        ref_grid = _regrid_stack_to_target(ref_grid, ref_lon, ref_lat, lon_vec, lat_vec)
                if ref_grid.ndim == 2:
                    reference_scaling_grid = ref_grid
                else:
                    ref_grid = _align_reference_stack_to_target(ref_grid, ref_labels, self._infer_time_labels(t_arr, nt))
                    reference_stack = ref_grid
                    external_reference_stack = ref_grid
                    reference_field = build_reference_field(
                        grid3d,
                        mask,
                        mode=reference_mode,
                        reference_stack=ref_grid,
                        time_axis=self._resolve_time(ref_data[3], ref_grid.shape[2])[0] if ref_data[3] is not None else None,
                    )
                    has_reference_model = True
    except Exception as exc:
        self._append_log(f"[LEAKAGE][WARN] External reference model ignored: {exc}", tag="stderr")
        reference_field = None
    if reference_field is None and str(leak_cfg.get("allow_observed_reference", True)).lower() not in ("false", "0", "no"):
        try:
            years, _ = self._resolve_time(t_arr, int(grid3d.shape[2]), data_meta)
            reference_field = build_reference_field(grid3d, mask, mode=reference_mode, time_axis=years)
            has_reference_model = True
        except Exception as exc:
            self._append_log(f"[LEAKAGE][WARN] Failed to derive internal reference field: {exc}", tag="stderr")
            reference_field = None
            has_reference_model = False
    requested_strategy = str(leak_cfg.get("correction_strategy", raw_method) or raw_method)
    requested_family = str(leak_cfg.get("strategy_family", "regional") or "regional").strip().lower()
    requested_official_mode = str(leak_cfg.get("official_mode", "auto") or "auto").strip().lower()
    resolved_request = resolve_strategy_request(
        requested_family,
        requested_strategy,
        operator_spec,
        official_mode=requested_official_mode,
    )
    method = recommend_correction_method(resolved_request, scene, operator_spec, has_reference_model=has_reference_model)
    requested_algorithm_name = method
    if method == "SCALE_FACTOR":
        method = "BASIN_SCALE_FACTOR"
    elif method == "ITERATIVE":
        # Wahr-style iterative correction shares the same forward-model core here.
        method = "FORWARD_MODELING"
    elif method == "MULTIPLICATIVE":
        # Map the classical basin-factor implementation to the existing scalar path.
        method = "BASIN_SCALE_FACTOR"
    elif method == "SCALING":
        # Prefer literature-style distributed scaling when a 3-D reference stack is available.
        method = "GRIDDED_GAIN_FACTOR" if external_reference_stack is not None else "BASIN_SCALE_FACTOR"
    elif method == "BUFFER_ZONE":
        method = "GLOBAL_COASTAL_GAUSSIAN" if bool(getattr(operator_spec, "is_gaussian_equivalent", False)) else "GLOBAL_REGULARIZED"
    strategy_family = strategy_family_for_method(method)
    strategy_variant = strategy_variant_for_method(method, operator_spec)
    if method == "GLOBAL_COASTAL_GAUSSIAN" and not operator_spec.is_gaussian_equivalent:
        self._append_log(
            "[LEAKAGE][WARN] Global coastal Gaussian is only supported for Gaussian-equivalent SH inputs; "
            "falling back to global regularized restoration.",
            tag="stderr",
        )
        method = "GLOBAL_REGULARIZED"
        strategy_family = strategy_family_for_method(method)
        strategy_variant = strategy_variant_for_method(method, operator_spec)
    if method in ("GRIDDED_GAIN_FACTOR", "MODEL_BASED_ADDITIVE"):
        self._append_log(
            f"[LEAKAGE][WARN] {method} is kept only as an advanced compatibility path. "
            "Default recommendations now prefer basin scale factor, regional forward modeling, "
            "global coastal Gaussian, global regularized restoration, or official/native routes.",
            tag="stderr",
        )
    n_mask = int(np.count_nonzero(mask))
    self._append_log(
        f"[LEAKAGE] Scope={scope}, mask cells={n_mask}, product={operator_spec.product_type}, "
        f"operator={operator_spec.method}, scene={scene.scene}, strategy={method} "
        f"({strategy_family}.{strategy_variant})"
    )

    self._set_scope_progress_pct("leakage", 0.0, "0%")

    sig_payload = {
        "algo_version": "builtin_leakage_20260411_operator_matched_fm_v2_masked_output",
        "input": self._file_fingerprint(in_path),
        "boundary": self._file_fingerprint(self.var_lrc_boundary.get().strip() if hasattr(self, "var_lrc_boundary") else ""),
        "scope": scope,
        "method": method,
        "requested_method": requested_strategy,
        "resolved_request": resolved_request,
        "product_type": operator_spec.product_type,
        "scene": scene.scene,
        "strategy_family": strategy_family,
        "strategy_variant": strategy_variant,
        "format": str(self.var_lrc_fmt.get()).lower() if hasattr(self, "var_lrc_fmt") else "mat",
        "options": opts.__dict__,
        "fm_ctrl": {
            "max_iter": (leak_cfg.get("fm_max_iter", 40) if isinstance(getattr(self.cfg, "leakage", None), dict) else 40),
            "tol": (leak_cfg.get("fm_tol", 0.01) if isinstance(getattr(self.cfg, "leakage", None), dict) else 0.01),
            "accel": (leak_cfg.get("fm_accel", 1.1) if isinstance(getattr(self.cfg, "leakage", None), dict) else 1.1),
            "metric": (leak_cfg.get("fm_metric", "land_weighted_mean") if isinstance(getattr(self.cfg, "leakage", None), dict) else "land_weighted_mean"),
            "update_mode": (leak_cfg.get("fm_update_mode", "mask") if isinstance(getattr(self.cfg, "leakage", None), dict) else "mask"),
            "output_mode": (leak_cfg.get("fm_output_mode", "preserve_observed_outside_mask") if isinstance(getattr(self.cfg, "leakage", None), dict) else "preserve_observed_outside_mask"),
            "run_mode": (leak_cfg.get("fm_run_mode", "rate_map" if scope == "regional" else "monthly_experimental") if isinstance(getattr(self.cfg, "leakage", None), dict) else ("rate_map" if scope == "regional" else "monthly_experimental")),
        },
        "nt": nt,
    }
    sig = self._build_scope_signature("leakage", sig_payload)

    validation = {"regional_series_reference": None}
    if external_reference_stack is not None:
        try:
            validation["regional_series_reference"] = compute_masked_series(external_reference_stack, mask, lat_vec)
        except Exception:
            validation["regional_series_reference"] = None
    elif reference_field is not None:
        validation["regional_series_reference"] = compute_masked_series(reference_field[:, :, None], mask, lat_vec)

    if method in ("OFFICIAL_SCALING", "OFFICIAL_LAND_SCALING", "OFFICIAL_OCEAN_NATIVE", "OFFICIAL_MASCON_NATIVE"):
        if method == "OFFICIAL_MASCON_NATIVE" or (operator_spec.product_type == "mascon_native" and reference_scaling_grid is None):
            grid_out = grid3d.copy()
            self._append_log("[LEAKAGE] Official/native gain path: mascon-native product detected, no extra scaling applied.")
        elif method == "OFFICIAL_OCEAN_NATIVE":
            grid_out = grid3d.copy()
            self._append_log("[LEAKAGE] Official ocean-native product detected, no extra SH leakage correction applied.")
        else:
            if reference_scaling_grid is None:
                self._msg_error(
                    "Leakage",
                    "Official scaling requires a 2-D scaling/gain grid as reference input.",
                )
                return
            if reference_scaling_grid.shape != grid3d.shape[:2]:
                self._msg_error(
                    "Leakage",
                    f"Scaling grid shape mismatch: expected {grid3d.shape[:2]}, got {reference_scaling_grid.shape}",
                )
                return
            target_mask = mask if scope == "regional" else np.isfinite(reference_scaling_grid)
            gains = np.where(target_mask, reference_scaling_grid, 1.0)
            grid_out = apply_gridded_gain_factors_stack(grid3d, gains, target_mask=target_mask)
            self._append_log(
                f"[LEAKAGE] Official scaling applied: min={np.nanmin(gains[target_mask]):.6f}, "
                f"median={np.nanmedian(gains[target_mask]):.6f}, max={np.nanmax(gains[target_mask]):.6f}"
            )
        validation["residual_metric_by_month"] = np.nanmean(np.abs(grid_out - grid3d), axis=(0, 1))
        validation["representative_index"] = int(np.nanargmax(validation["residual_metric_by_month"])) if np.any(np.isfinite(validation["residual_metric_by_month"])) else 0
        out_file = self._save_leakage_output(grid_out, lon_vec, lat_vec, t_arr, labels, in_path, out_path, "official")
        bundle = save_leakage_bundle(
            output_file=out_file,
            raw_stack=grid3d,
            corrected_stack=grid_out,
            lon_vec=lon_vec,
            lat_vec=lat_vec,
            labels=labels,
            mask=mask,
            method=method,
            scene_info=scene.__dict__,
            operator_info=operator_spec.__dict__,
            validation=validation,
            extra_meta={
                "scope": scope,
                "requested_strategy": requested_strategy,
                "resolved_request": resolved_request,
                "strategy_family": strategy_family,
                "strategy_variant": strategy_variant,
                "options": opts.__dict__,
                "input_path": in_path,
            },
        )
        self._clear_scope_progress("leakage")
        self._set_scope_progress_pct("leakage", 100.0, "100%")
        self._last_leakage_bundle = bundle
        self._append_log(f"[LEAKAGE] Official scaling completed. Output: {out_file}")
        self._append_log(f"[LEAKAGE] Diagnostics bundle: {bundle.get('bundle_dir', '')}")
        self._msg_info("Leakage", f"Official scaling completed.\n{out_file}\n\nDiagnostics:\n{bundle.get('bundle_dir', '')}")
        return

    if method == "GLOBAL_COASTAL_GAUSSIAN":
        if not operator_spec.is_gaussian_equivalent:
            self._msg_error("Leakage", "Global coastal Gaussian correction only supports Gaussian-equivalent SH inputs.")
            return
        land_mask = global_land_mask
        if land_mask is None:
            self._msg_error("Leakage", "Global coastal Gaussian correction requires a valid global land mask.")
            return
        ref_stack = np.asarray(external_reference_stack if external_reference_stack is not None else grid3d, dtype=float)
        coastal_buffer_cells = max(1, int(round(float(leak_cfg.get("coastal_buffer_cells", 3)))))
        attenuation_gain = float(leak_cfg.get("coastal_attenuation_gain", 1.0) or 1.0)
        self._append_log(
            f"[LEAKAGE] Running global coastal Gaussian correction: buffer={coastal_buffer_cells}, "
            f"attenuation_gain={attenuation_gain:.3f}, reference={'external' if external_reference_stack is not None else 'observed'}"
        )
        try:
            grid_out, coastal_info = compute_global_coastal_gaussian_stack(
                grid3d,
                lon_vec,
                lat_vec,
                opts,
                land_mask=land_mask,
                reference_stack=ref_stack,
                coastal_buffer_cells=coastal_buffer_cells,
                attenuation_gain=attenuation_gain,
            )
        except Exception as e:
            self._msg_error("Leakage", f"Global coastal Gaussian correction failed: {e}")
            return
        validation.update({k: v for k, v in coastal_info.items() if k not in ("coastal_land_mask", "coastal_ocean_mask")})
        validation["representative_index"] = int(np.nanargmax(coastal_info.get("residual_metric_by_month", np.array([0.0]))))
        out_file = self._save_leakage_output(grid_out, lon_vec, lat_vec, t_arr, labels, in_path, out_path, "coastal")
        bundle = save_leakage_bundle(
            output_file=out_file,
            raw_stack=grid3d,
            corrected_stack=grid_out,
            lon_vec=lon_vec,
            lat_vec=lat_vec,
            labels=labels,
            mask=(coastal_info.get("coastal_land_mask", np.zeros_like(mask, dtype=bool)) | coastal_info.get("coastal_ocean_mask", np.zeros_like(mask, dtype=bool))),
            method=method,
            scene_info=scene.__dict__,
            operator_info=operator_spec.__dict__,
            validation=validation,
            extra_meta={
                "scope": "global",
                "requested_strategy": requested_strategy,
                "resolved_request": resolved_request,
                "strategy_family": strategy_family,
                "strategy_variant": strategy_variant,
                "options": opts.__dict__,
                "input_path": in_path,
                "region_names": ["全球海岸带"],
            },
        )
        self._clear_scope_progress("leakage")
        self._set_scope_progress_pct("leakage", 100.0, "100%")
        self._last_leakage_bundle = bundle
        self._append_log(f"[LEAKAGE] Global coastal Gaussian completed. Output: {out_file}")
        self._append_log(f"[LEAKAGE] Diagnostics bundle: {bundle.get('bundle_dir', '')}")
        self._msg_info("Leakage", f"Global coastal Gaussian correction completed.\n{out_file}\n\nDiagnostics:\n{bundle.get('bundle_dir', '')}")
        return

    if method == "GLOBAL_REGULARIZED":
        reg_lambda = float(leak_cfg.get("regularized_lambda", 0.18) or 0.18)
        reg_step = float(leak_cfg.get("regularized_step_size", 0.9) or 0.9)
        reg_sigma = float(leak_cfg.get("regularized_sigma", 1.2) or 1.2)
        reg_iter = max(1, int(round(float(leak_cfg.get("regularized_iter", 10) or 10))))
        self._append_log(
            f"[LEAKAGE] Running global regularized restoration: lambda={reg_lambda:.3f}, "
            f"step={reg_step:.3f}, sigma={reg_sigma:.3f}, iter={reg_iter}"
        )
        try:
            grid_out, reg_info = regularized_restore_stack(
                grid3d,
                lon_vec,
                lat_vec,
                opts,
                reg_lambda=reg_lambda,
                step_size=reg_step,
                smooth_sigma=reg_sigma,
                n_iter=reg_iter,
            )
        except Exception as e:
            self._msg_error("Leakage", f"Global regularized restoration failed: {e}")
            return
        validation["residual_metric_by_month"] = np.asarray(reg_info.get("residual_metric_by_month"), dtype=float)
        validation["convergence_by_month"] = np.asarray(reg_info.get("residual_metric_by_month"), dtype=float)
        validation["representative_index"] = int(np.nanargmax(validation["residual_metric_by_month"])) if np.any(np.isfinite(validation["residual_metric_by_month"])) else 0
        validation["regularized_residual_history"] = np.asarray(reg_info.get("residual_history"), dtype=float)
        out_file = self._save_leakage_output(grid_out, lon_vec, lat_vec, t_arr, labels, in_path, out_path, "regularized")
        bundle = save_leakage_bundle(
            output_file=out_file,
            raw_stack=grid3d,
            corrected_stack=grid_out,
            lon_vec=lon_vec,
            lat_vec=lat_vec,
            labels=labels,
            mask=mask if scope == "regional" else np.isfinite(grid3d[:, :, 0]),
            method=method,
            scene_info=scene.__dict__,
            operator_info=operator_spec.__dict__,
            validation=validation,
            extra_meta={
                "scope": scope,
                "requested_strategy": requested_strategy,
                "resolved_request": resolved_request,
                "strategy_family": strategy_family,
                "strategy_variant": strategy_variant,
                "options": opts.__dict__,
                "input_path": in_path,
                "region_names": ["全球恢复"],
            },
        )
        self._clear_scope_progress("leakage")
        self._set_scope_progress_pct("leakage", 100.0, "100%")
        self._last_leakage_bundle = bundle
        self._append_log(f"[LEAKAGE] Global regularized restoration completed. Output: {out_file}")
        self._append_log(f"[LEAKAGE] Diagnostics bundle: {bundle.get('bundle_dir', '')}")
        self._msg_info("Leakage", f"Global regularized restoration completed.\n{out_file}\n\nDiagnostics:\n{bundle.get('bundle_dir', '')}")
        return

    if method == "DATA_DRIVEN":
        self._append_log("[LEAKAGE] Running data-driven deviation correction...")
        try:
            grid_out, ddc_info = data_driven_correct_stack(
                grid3d,
                lon_vec,
                lat_vec,
                opts,
                mask=mask,
                restrict_to_mask=bool(leak_cfg.get("restrict_ddc_to_mask", False)),
            )
        except Exception as e:
            self._msg_error("Leakage", f"Data-driven correction failed: {e}")
            return
        validation["residual_metric_by_month"] = np.asarray(ddc_info.get("residual_metric_by_month"), dtype=float)
        validation["representative_index"] = int(np.nanargmax(validation["residual_metric_by_month"])) if np.any(np.isfinite(validation["residual_metric_by_month"])) else 0
        out_file = self._save_leakage_output(grid_out, lon_vec, lat_vec, t_arr, labels, in_path, out_path, "ddc")
        bundle = save_leakage_bundle(
            output_file=out_file,
            raw_stack=grid3d,
            corrected_stack=grid_out,
            lon_vec=lon_vec,
            lat_vec=lat_vec,
            labels=labels,
            mask=mask,
            method=method,
            scene_info=scene.__dict__,
            operator_info=operator_spec.__dict__,
            validation={**validation, **ddc_info},
            extra_meta={
                "scope": scope,
                "requested_strategy": requested_strategy,
                "requested_algorithm_name": requested_algorithm_name,
                "resolved_request": resolved_request,
                "strategy_family": strategy_family,
                "strategy_variant": strategy_variant,
                "options": opts.__dict__,
                "input_path": in_path,
            },
        )
        self._clear_scope_progress("leakage")
        self._set_scope_progress_pct("leakage", 100.0, "100%")
        self._last_leakage_bundle = bundle
        self._append_log(f"[LEAKAGE] Data-driven correction completed. Output: {out_file}")
        self._append_log(f"[LEAKAGE] Diagnostics bundle: {bundle.get('bundle_dir', '')}")
        self._msg_info("Leakage", f"Data-driven correction completed.\n{out_file}\n\nDiagnostics:\n{bundle.get('bundle_dir', '')}")
        return

    if method == "GRIDDED_GAIN_FACTOR":
        if external_reference_stack is None:
            self._msg_error("Leakage", "Gridded gain factors require an external 3-D reference stack.")
            return
        ref_stack = np.asarray(external_reference_stack, dtype=float)
        if ref_stack.ndim == 2:
            ref_stack = ref_stack[:, :, None]
        if ref_stack.shape[:2] != grid3d.shape[:2]:
            self._msg_error(
                "Leakage",
                f"Reference stack shape mismatch: expected {grid3d.shape[:2]}, got {ref_stack.shape[:2]}",
            )
            return
        if ref_stack.shape[2] == 1 and nt > 1:
            ref_stack = np.repeat(ref_stack, nt, axis=2)
        if ref_stack.shape[2] != nt:
            self._msg_error(
                "Leakage",
                f"Reference stack length mismatch: input Nt={nt}, reference Nt={ref_stack.shape[2]}",
            )
            return
        self._append_log("[LEAKAGE] Computing literature-style gridded gain factors from external reference stack...")
        try:
            gains, gain_info = compute_gridded_gain_factors(ref_stack, lon_vec, lat_vec, opts, target_mask=mask if scope == "regional" else None)
            grid_out = apply_gridded_gain_factors_stack(grid3d, gains, target_mask=mask if scope == "regional" else None)
        except Exception as e:
            self._msg_error("Leakage", f"Gridded gain-factor estimation failed: {e}")
            return
        validation["regional_series_reference"] = compute_masked_series(ref_stack, mask, lat_vec)
        validation["residual_metric_by_month"] = np.nanmean(np.abs(grid_out - grid3d), axis=(0, 1))
        validation["representative_index"] = int(np.nanargmax(validation["residual_metric_by_month"])) if np.any(np.isfinite(validation["residual_metric_by_month"])) else 0
        out_file = self._save_leakage_output(grid_out, lon_vec, lat_vec, t_arr, labels, in_path, out_path, "gridgain")
        bundle = save_leakage_bundle(
            output_file=out_file,
            raw_stack=grid3d,
            corrected_stack=grid_out,
            lon_vec=lon_vec,
            lat_vec=lat_vec,
            labels=labels,
            mask=mask,
            method=method,
            scene_info=scene.__dict__,
            operator_info=operator_spec.__dict__,
            validation=validation,
            extra_meta={
                "scope": scope,
                "gain_grid_min": float(np.nanmin(gains)),
                "gain_grid_median": float(np.nanmedian(gains)),
                "gain_grid_max": float(np.nanmax(gains)),
                "requested_strategy": requested_strategy,
                "resolved_request": resolved_request,
                "strategy_family": strategy_family,
                "strategy_variant": strategy_variant,
                "options": opts.__dict__,
                "input_path": in_path,
            },
        )
        self._clear_scope_progress("leakage")
        self._set_scope_progress_pct("leakage", 100.0, "100%")
        self._last_leakage_bundle = bundle
        self._append_log(f"[LEAKAGE] Gridded gain-factor correction completed. Output: {out_file}")
        self._append_log(f"[LEAKAGE] Diagnostics bundle: {bundle.get('bundle_dir', '')}")
        self._msg_info("Leakage", f"Gridded gain-factor correction completed.\n{out_file}\n\nDiagnostics:\n{bundle.get('bundle_dir', '')}")
        return

    if method == "FORWARD_MODELING":
        # Literature-aligned FM defaults to constrained rate-map recovery for
        # regional studies. Monthly map FM is kept only as an experimental path.
        try:
            n_iter = max(1, int(leak_cfg.get("fm_max_iter", 40)))
        except Exception:
            n_iter = 40
        try:
            min_iter = max(1, int(leak_cfg.get("fm_min_iter", 3)))
        except Exception:
            min_iter = 3
        try:
            tol = max(0.0, float(leak_cfg.get("fm_tol", 0.01)))
        except Exception:
            tol = 0.01
        try:
            patience = max(0, int(leak_cfg.get("fm_patience", 8)))
        except Exception:
            patience = 8
        try:
            min_improve = max(0.0, float(leak_cfg.get("fm_min_improve", max(1.0e-4, tol * 0.02))))
        except Exception:
            min_improve = max(1.0e-4, tol * 0.02)
        try:
            accel = float(leak_cfg.get("fm_accel", 1.1))
            if not np.isfinite(accel) or abs(accel) < 1.0e-9:
                accel = 1.1
        except Exception:
            accel = 1.1
        conv_metric = str(leak_cfg.get("fm_metric", "land_weighted_mean"))
        fm_run_mode = str(
            leak_cfg.get(
                "fm_run_mode",
                "rate_map" if scope == "regional" else "monthly_experimental",
            )
            or ("rate_map" if scope == "regional" else "monthly_experimental")
        ).strip().lower()
        if fm_run_mode not in ("rate_map", "monthly_experimental"):
            fm_run_mode = "rate_map" if scope == "regional" else "monthly_experimental"
        fm_update_mode = str(leak_cfg.get("fm_update_mode", "mask") or "mask").strip().lower()
        if fm_update_mode not in ("mask", "global"):
            fm_update_mode = "mask"
        fm_output_mode = str(leak_cfg.get("fm_output_mode", "preserve_observed_outside_mask") or "preserve_observed_outside_mask").strip().lower()
        fm_opts = LeakageFilterOptions(**opts.__dict__)
        mass_mode = "legacy_land_mean_fill" if scope == "global" else "ocean_uniform_land_balance"
        # Keep FM operator as selected in leakage settings; no proxy rewrite.
        prefilter_obs = False
        fm_method_norm = str(getattr(fm_opts, "method", "") or "").strip().upper()
        try:
            requested_workers = max(1, int(getattr(self.cfg.parallel, "n_workers", 1)))
        except Exception:
            requested_workers = 1
        try:
            parallel_enable = bool(getattr(self.cfg.parallel, "enable", False))
        except Exception:
            parallel_enable = False
        if fm_method_norm in ("HSAF", "HANKEL"):
            try:
                auto_cap = bool(leak_cfg.get("fm_autocap_hsaf_iter", True))
            except Exception:
                auto_cap = True
            try:
                hsaf_iter_cap = max(1, int(leak_cfg.get("fm_hsaf_iter_cap", 40)))
            except Exception:
                hsaf_iter_cap = 40
            if auto_cap and n_iter > hsaf_iter_cap:
                self._append_log(
                    f"[LEAKAGE][INFO] FM+HSAF is expensive; capping max iterations {n_iter}->{hsaf_iter_cap}. "
                    "Set leakage.fm_autocap_hsaf_iter=false to disable.",
                )
                n_iter = hsaf_iter_cap
        if fm_method_norm in ("HSAF", "HANKEL"):
            hsaf_params = dict(getattr(fm_opts, "hsaf_params", {}) or {})
            old_workers = int(hsaf_params.get("workers", 1) or 1)
            try:
                cfg_inner = max(1, int(leak_cfg.get("fm_hsaf_inner_workers", 1)))
            except Exception:
                cfg_inner = 1
            # Prefer outer (monthly) parallelism for FM+HSAF; keep inner workers small
            # to avoid SVD/BLAS over-subscription.
            target_inner_workers = 1 if (parallel_enable and requested_workers > 1) else cfg_inner
            hsaf_params["workers"] = target_inner_workers
            fm_opts.hsaf_params = hsaf_params
            if old_workers != target_inner_workers:
                self._append_log(
                    f"[LEAKAGE][WARN] FM+HSAF inner workers {old_workers}->{target_inner_workers} "
                    "to avoid SVD oversubscription and improve throughput.",
                    tag="stderr",
                )
            try:
                hsaf_j = int(hsaf_params.get("J", 1))
                if hsaf_j <= 1:
                    self._append_log(
                        "[LEAKAGE][INFO] HSAF J=1 is computationally expensive; consider J=2~4 for faster FM iterations.",
                    )
            except Exception:
                pass
        self._append_log(
            f"[LEAKAGE] FM(monthly) config: iter={n_iter}, min_iter={min_iter}, k={accel}, tol={tol:g}, "
            f"patience={patience}, min_improve={min_improve:g}, "
            f"operator={fm_opts.method}, Lmax={fm_opts.lmax}, "
            f"hsaf_input={fm_opts.hsaf_input}, "
            f"prefilter_obs={'on' if prefilter_obs else 'off'}, mass={mass_mode}, "
            f"update={fm_update_mode}, output={fm_output_mode}, metric={conv_metric}, mode={fm_run_mode}"
        )

        if fm_run_mode == "rate_map":
            if scope != "regional":
                self._append_log(
                    "[LEAKAGE][WARN] Literature FM is intended for constrained regional recovery. "
                    "Global scope falls back to experimental monthly FM.",
                    tag="stderr",
                )
            else:
                try:
                    t_years, _ = self._resolve_time(t_arr, nt, data_meta)
                    rate_map, rate_aux = estimate_rate_map(grid3d, t_axis=t_years, min_valid=max(6, min(nt, 12)))
                except Exception as e:
                    self._msg_error("Leakage", f"Failed to build rate map for FM: {e}")
                    return

                modeled_mask = np.asarray(mask, dtype=bool)
                balance_mask = None
                if global_land_mask is not None:
                    balance_mask = ~np.asarray(global_land_mask, dtype=bool)
                rate_tol = 0.0
                try:
                    rate_tol = max(0.0, float(leak_cfg.get("fm_rate_tol", 0.0)))
                except Exception:
                    rate_tol = 0.0
                rate_metric = str(leak_cfg.get("fm_rate_metric", "modeled_area_abs_integral") or "modeled_area_abs_integral")
                rate_init_mode = str(leak_cfg.get("fm_rate_init_mode", "mask") or "mask").strip().lower()
                if rate_init_mode not in ("mask", "obs", "zeros"):
                    rate_init_mode = "mask"

                obs_mean = compute_masked_series(rate_map[:, :, None], modeled_mask, lat_vec)[0]
                self._append_log(
                    f"[LEAKAGE] FM(rate-map) start: observed regional rate={obs_mean:.6g}, "
                    f"metric={rate_metric}, iter={n_iter}, k={accel}"
                )

                try:
                    recovered_rate, rate_info = fm_correct_month(
                        rate_map,
                        modeled_mask,
                        lon_vec,
                        lat_vec,
                        fm_opts,
                        n_iter=n_iter,
                        tol_rmse_mm=rate_tol,
                        update_mode="mask",
                        init_mode=rate_init_mode,
                        mass_conservation="ocean_uniform_land_balance" if balance_mask is not None else "none",
                        convergence_metric=rate_metric,
                        accel=accel,
                        prefilter_obs=False,
                        min_iter=min_iter,
                        stagnation_patience=patience,
                        min_improve=min_improve,
                        output_mode="preserve_observed_outside_mask",
                        balance_mask=balance_mask,
                        iter_cb=None,
                        should_continue=self._check_pause_stop,
                    )
                except Exception as e:
                    self._msg_error("Leakage", f"FM rate-map recovery failed: {e}")
                    return

                predicted_rate = np.asarray(rate_info.get("pre_last", np.full_like(rate_map, np.nan)), dtype=float)
                residual_rate = np.asarray(rate_map - predicted_rate, dtype=float)
                recovered_mean = compute_masked_series(recovered_rate[:, :, None], modeled_mask, lat_vec)[0]
                if np.isfinite(obs_mean) and (not np.isclose(obs_mean, 0.0)):
                    fm_factor = float(recovered_mean / obs_mean)
                    factor_basis = "regional_mean_ratio"
                else:
                    obs_rms = float(np.sqrt(np.nanmean((rate_map[modeled_mask]) ** 2)))
                    rec_rms = float(np.sqrt(np.nanmean((recovered_rate[modeled_mask]) ** 2)))
                    if (not np.isfinite(obs_rms)) or np.isclose(obs_rms, 0.0):
                        self._msg_error("Leakage", "FM rate-map scale factor is invalid because the observed regional rate is zero.")
                        return
                    fm_factor = float(rec_rms / obs_rms)
                    factor_basis = "regional_rms_ratio"
                try:
                    fm_factor = float(np.clip(fm_factor, float(leak_cfg.get("fm_factor_clip_min", 0.25)), float(leak_cfg.get("fm_factor_clip_max", 8.0))))
                except Exception:
                    fm_factor = float(np.clip(fm_factor, 0.25, 8.0))

                out = apply_scale_factors_stack(grid3d, modeled_mask, np.asarray([fm_factor], dtype=float))
                validation["residual_metric_by_month"] = np.abs(
                    compute_masked_series(out, modeled_mask, lat_vec) - compute_masked_series(grid3d, modeled_mask, lat_vec)
                )
                validation["representative_index"] = int(np.nanargmax(validation["residual_metric_by_month"])) if np.any(np.isfinite(validation["residual_metric_by_month"])) else 0
                validation["fm_mode"] = "rate_map"
                validation["fm_rate_iterations"] = int(np.asarray(rate_info.get("nIter", [0])).reshape(-1)[0])
                validation["fm_rate_residual_history"] = np.asarray(rate_info.get("rmse_hist", []), dtype=float)
                validation["fm_rate_observed"] = np.asarray(rate_map, dtype=float)
                validation["fm_rate_recovered"] = np.asarray(recovered_rate, dtype=float)
                validation["fm_rate_predicted"] = predicted_rate
                validation["fm_rate_residual"] = residual_rate
                validation["fm_rate_factor"] = float(fm_factor)
                validation["fm_rate_factor_basis"] = factor_basis
                validation["fm_rate_observed_mean"] = float(obs_mean) if np.isfinite(obs_mean) else None
                validation["fm_rate_recovered_mean"] = float(recovered_mean) if np.isfinite(recovered_mean) else None
                if rate_aux:
                    validation["fm_rate_valid_count"] = np.asarray(rate_aux.get("valid_count", []), dtype=int)

                out_file = self._save_leakage_output(out, lon_vec, lat_vec, t_arr, labels, in_path, out_path, "fm")
                bundle = save_leakage_bundle(
                    output_file=out_file,
                    raw_stack=grid3d,
                    corrected_stack=out,
                    lon_vec=lon_vec,
                    lat_vec=lat_vec,
                    labels=labels,
                    mask=mask,
                    method=method,
                    scene_info=scene.__dict__,
                    operator_info=operator_spec.__dict__,
                    validation=validation,
                    extra_meta={
                        "scope": scope,
                        "requested_strategy": requested_strategy,
                "resolved_request": resolved_request,
                        "strategy_family": strategy_family,
                        "strategy_variant": strategy_variant,
                        "options": opts.__dict__,
                        "fm_run_mode": fm_run_mode,
                        "fm_factor": float(fm_factor),
                        "fm_factor_basis": factor_basis,
                        "input_path": in_path,
                    },
                )
                self._clear_scope_progress("leakage")
                self._set_scope_progress_pct("leakage", 100.0, "100%")
                self._last_leakage_bundle = bundle
                self._append_log(
                    f"[LEAKAGE] FM(rate-map) completed. factor={fm_factor:.6f} ({factor_basis}), "
                    f"iter={validation['fm_rate_iterations']}, output={out_file}"
                )
                self._append_log(f"[LEAKAGE] Diagnostics bundle: {bundle.get('bundle_dir', '')}")
                self._msg_info("Leakage", f"FM rate-map correction completed.\n{out_file}\n\nDiagnostics:\n{bundle.get('bundle_dir', '')}")
                return

        out = np.full_like(grid3d, np.nan, dtype=float)
        final_metric_by_month = np.full(nt, np.nan, dtype=float)
        iter_count_by_month = np.zeros(nt, dtype=int)
        partial_dir = self._scope_cache_dir() / "leakage_monthly"
        partial_dir.mkdir(parents=True, exist_ok=True)

        cache = self._load_scope_progress("leakage", sig)
        state = cache.get("state", {}) if cache else {}
        try:
            start_idx = int(state.get("next_month_idx", 1)) if state else 1
        except Exception:
            start_idx = 1
        start_idx = int(max(1, min(start_idx, nt + 1)))

        if start_idx > 1:
            for k in range(1, min(start_idx, nt + 1)):
                f = partial_dir / f"{sig}_{k:04d}.npy"
                if f.exists():
                    try:
                        out[:, :, k - 1] = np.load(str(f))
                    except Exception:
                        pass
            self._append_log(f"[LEAKAGE] Resuming FM from month {start_idx}/{nt}")

        start_pct = ((start_idx - 1) / max(1, nt)) * 100.0
        self._set_scope_progress_pct("leakage", start_pct, f"{start_pct:4.1f}%")

        try:
            use_par = bool(getattr(self.cfg.parallel, "enable", False))
            n_workers = int(getattr(self.cfg.parallel, "n_workers", 1))
        except Exception:
            use_par = False
            n_workers = 1
        try:
            allow_hsaf_parallel = bool(leak_cfg.get("fm_allow_hsaf_parallel", True))
        except Exception:
            allow_hsaf_parallel = True
        try:
            use_hsaf_process_pool = bool(leak_cfg.get("fm_hsaf_use_process_pool", True))
        except Exception:
            use_hsaf_process_pool = True
        if use_par and n_workers > 1 and fm_method_norm in ("HSAF", "HANKEL") and (not allow_hsaf_parallel):
            # Stability guard: FM+HSAF in multi-thread mode can stall on
            # Windows/BLAS runtime. Keep other FM operators parallel.
            self._append_log(
                "[LEAKAGE][WARN] FM+HSAF parallel may stall; forcing workers=1 for stability.",
                tag="stderr",
            )
            use_par = False
            n_workers = 1
        elif use_par and n_workers > 1 and fm_method_norm in ("HSAF", "HANKEL") and allow_hsaf_parallel:
            try:
                hsaf_outer_cap = max(1, int(leak_cfg.get("fm_hsaf_outer_workers_cap", 12)))
            except Exception:
                hsaf_outer_cap = 12
            if n_workers > hsaf_outer_cap:
                self._append_log(
                    f"[LEAKAGE][INFO] FM+HSAF monthly workers capped {n_workers}->{hsaf_outer_cap} for stability.",
                )
                n_workers = hsaf_outer_cap
            self._append_log(
                "[LEAKAGE][INFO] FM+HSAF monthly parallel enabled. If it stalls on your machine, set fm_allow_hsaf_parallel=false.",
            )

        months = list(range(start_idx, nt + 1))
        done_set = set(range(1, start_idx))

        def _next_idx_from_done():
            nxt = start_idx
            while nxt in done_set:
                nxt += 1
            return nxt

        def _run_month(k):
            gobs = np.asarray(grid3d[:, :, k - 1], dtype=float)
            self._append_log(f"[LEAKAGE] FM ({k}/{nt}) start...")

            def _iter_cb(it, nmax, errv):
                if it == 1 or it == nmax or (it % max(1, nmax // 6) == 0):
                    pct_iter = ((k - 1) + (it / max(1, nmax))) / max(1, nt) * 100.0
                    self._set_scope_progress_pct("leakage", pct_iter, f"{pct_iter:4.1f}%")
                    self._append_log(f"[LEAKAGE] FM ({k}/{nt}) iter {it}/{nmax}, metric={errv:.4f}")

            corr, info = fm_correct_month(
                gobs,
                mask,
                lon_vec,
                lat_vec,
                fm_opts,
                n_iter=n_iter,
                tol_rmse_mm=tol,
                update_mode=fm_update_mode,
                init_mode="obs",
                mass_conservation=mass_mode,
                convergence_metric=conv_metric,
                accel=accel,
                prefilter_obs=prefilter_obs,
                min_iter=min_iter,
                stagnation_patience=patience,
                min_improve=min_improve,
                output_mode=fm_output_mode,
                iter_cb=_iter_cb,
                should_continue=self._check_pause_stop,
            )
            n_used = int(np.asarray(info.get("nIter", [0])).reshape(-1)[0])
            final_err = float(np.asarray(info.get("final_rmse", [np.nan])).reshape(-1)[0])
            return k, corr, n_used, final_err

        use_proc_pool = bool(use_par and n_workers > 1 and len(months) > 1 and fm_method_norm in ("HSAF", "HANKEL") and use_hsaf_process_pool)

        if use_proc_pool:
            n_workers = max(1, min(n_workers, len(months)))
            self._append_log(f"[LEAKAGE] FM monthly process workers={n_workers}")
            self._set_scope_progress_indeterminate("leakage", text="...")
            env_backup = {}
            for _env_name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
                env_backup[_env_name] = os.environ.get(_env_name)
                os.environ[_env_name] = "1"
            try:
                with ProcessPoolExecutor(max_workers=n_workers) as ex:
                    futures = {}
                    for k in months:
                        job = {
                            "k": k,
                            "gobs": np.asarray(grid3d[:, :, k - 1], dtype=float),
                            "mask": np.asarray(mask, dtype=bool),
                            "lon_vec": np.asarray(lon_vec, dtype=float),
                            "lat_vec": np.asarray(lat_vec, dtype=float),
                            "options": dict(fm_opts.__dict__),
                            "n_iter": n_iter,
                            "tol": tol,
                            "update_mode": fm_update_mode,
                            "init_mode": "obs",
                            "mass_mode": mass_mode,
                            "conv_metric": conv_metric,
                            "accel": accel,
                            "prefilter_obs": prefilter_obs,
                            "min_iter": min_iter,
                            "patience": patience,
                            "min_improve": min_improve,
                            "output_mode": fm_output_mode,
                        }
                        futures[ex.submit(_leakage_fm_month_worker, job)] = k
                    for fut in as_completed(futures):
                        k = futures[fut]
                        if not self._check_pause_stop():
                            self._append_log("[LEAKAGE] Stop requested. Waiting for running worker processes to finish current month...", tag="stderr")
                            self._save_scope_progress_throttled(
                                "leakage",
                                sig,
                                {"next_month_idx": _next_idx_from_done(), "nt": nt},
                                force=True,
                            )
                            return
                        try:
                            k, gk, n_used, final_err = fut.result()
                        except Exception as e:
                            self._msg_error("Leakage", f"FM failed at month {k}/{nt}: {e}")
                            self._save_scope_progress_throttled(
                                "leakage",
                                sig,
                                {"next_month_idx": _next_idx_from_done(), "nt": nt},
                                force=True,
                            )
                            return

                        out[:, :, k - 1] = gk
                        final_metric_by_month[k - 1] = final_err
                        iter_count_by_month[k - 1] = n_used
                        try:
                            np.save(str(partial_dir / f"{sig}_{k:04d}.npy"), gk)
                        except Exception:
                            pass
                        done_set.add(k)
                        self._save_scope_progress_throttled(
                            "leakage",
                            sig,
                            {"next_month_idx": _next_idx_from_done(), "nt": nt},
                            min_interval_s=2.0,
                        )
                        done = len(done_set)
                        pct = (done / max(1, nt)) * 100.0
                        self._set_scope_progress_pct("leakage", pct, f"{pct:4.1f}%")
                        self._append_log(f"[LEAKAGE] FM ({k}/{nt}) done, iter={n_used}, final_metric={final_err:.4f}")
            finally:
                for _env_name, _env_val in env_backup.items():
                    if _env_val is None:
                        try:
                            os.environ.pop(_env_name, None)
                        except Exception:
                            pass
                    else:
                        os.environ[_env_name] = _env_val
        elif use_par and n_workers > 1 and len(months) > 1:
            n_workers = max(1, min(n_workers, len(months)))
            self._append_log(f"[LEAKAGE] FM monthly parallel workers={n_workers}")
            self._set_scope_progress_indeterminate("leakage", text="...")
            with ThreadPoolExecutor(max_workers=n_workers) as ex:
                futures = {ex.submit(_run_month, k): k for k in months}
                for fut in as_completed(futures):
                    if not self._check_pause_stop():
                        self._append_log("[LEAKAGE] Stopped by user.", tag="stderr")
                        try:
                            for ff in futures:
                                ff.cancel()
                        except Exception:
                            pass
                        self._save_scope_progress_throttled(
                            "leakage",
                            sig,
                            {"next_month_idx": _next_idx_from_done(), "nt": nt},
                            force=True,
                        )
                        return
                    k = futures[fut]
                    try:
                        k, gk, n_used, final_err = fut.result()
                    except Exception as e:
                        self._msg_error("Leakage", f"FM failed at month {k}/{nt}: {e}")
                        self._save_scope_progress_throttled(
                            "leakage",
                            sig,
                            {"next_month_idx": _next_idx_from_done(), "nt": nt},
                            force=True,
                        )
                        return

                    out[:, :, k - 1] = gk
                    final_metric_by_month[k - 1] = final_err
                    iter_count_by_month[k - 1] = n_used
                    try:
                        np.save(str(partial_dir / f"{sig}_{k:04d}.npy"), gk)
                    except Exception:
                        pass
                    done_set.add(k)
                    self._save_scope_progress_throttled(
                        "leakage",
                        sig,
                        {"next_month_idx": _next_idx_from_done(), "nt": nt},
                        min_interval_s=2.0,
                    )
                    done = len(done_set)
                    pct = (done / max(1, nt)) * 100.0
                    self._set_scope_progress_pct("leakage", pct, f"{pct:4.1f}%")
                    self._append_log(f"[LEAKAGE] FM ({k}/{nt}) done, iter={n_used}, final_metric={final_err:.4f}")
        else:
            for k in months:
                if not self._check_pause_stop():
                    self._append_log("[LEAKAGE] Stopped by user.", tag="stderr")
                    self._save_scope_progress_throttled(
                        "leakage",
                        sig,
                        {"next_month_idx": k, "nt": nt},
                        force=True,
                    )
                    return
                self._append_log(f"[LEAKAGE] FM ({k}/{nt}) running...")
                try:
                    k, gk, n_used, final_err = _run_month(k)
                except Exception as e:
                    self._msg_error("Leakage", f"FM failed at month {k}/{nt}: {e}")
                    self._save_scope_progress_throttled(
                        "leakage",
                        sig,
                        {"next_month_idx": k, "nt": nt},
                        force=True,
                    )
                    return
                out[:, :, k - 1] = gk
                final_metric_by_month[k - 1] = final_err
                iter_count_by_month[k - 1] = n_used
                try:
                    np.save(str(partial_dir / f"{sig}_{k:04d}.npy"), gk)
                except Exception:
                    pass
                done_set.add(k)
                self._save_scope_progress_throttled(
                    "leakage",
                    sig,
                    {"next_month_idx": k + 1, "nt": nt},
                    min_interval_s=2.0,
                )
                pct = (len(done_set) / max(1, nt)) * 100.0
                self._set_scope_progress_pct("leakage", pct, f"{pct:4.1f}%")
                self._append_log(f"[LEAKAGE] FM ({k}/{nt}) done, iter={n_used}, final_metric={final_err:.4f}")

        try:
            for k in range(1, nt + 1):
                f = partial_dir / f"{sig}_{k:04d}.npy"
                if f.exists():
                    f.unlink()
        except Exception:
            pass

        self._set_scope_progress_pct("leakage", 99.0, "99.0%")
        out_file = self._save_leakage_output(out, lon_vec, lat_vec, t_arr, labels, in_path, out_path, "fm")
        validation["residual_metric_by_month"] = final_metric_by_month
        validation["convergence_by_month"] = iter_count_by_month
        bundle = save_leakage_bundle(
            output_file=out_file,
            raw_stack=grid3d,
            corrected_stack=out,
            lon_vec=lon_vec,
            lat_vec=lat_vec,
            labels=labels,
            mask=mask,
            method=method,
            scene_info=scene.__dict__,
            operator_info=operator_spec.__dict__,
            validation=validation,
            extra_meta={
                "scope": scope,
                "requested_strategy": requested_strategy,
                "resolved_request": resolved_request,
                "strategy_family": strategy_family,
                "strategy_variant": strategy_variant,
                "options": opts.__dict__,
                "input_path": in_path,
            },
        )
        self._clear_scope_progress("leakage")
        self._set_scope_progress_pct("leakage", 100.0, "100%")
        self._last_leakage_bundle = bundle
        self._append_log(f"[LEAKAGE] FM completed. Output: {out_file}")
        self._append_log(f"[LEAKAGE] Diagnostics bundle: {bundle.get('bundle_dir', '')}")
        self._msg_info("Leakage", f"FM leakage correction completed.\n{out_file}\n\nDiagnostics:\n{bundle.get('bundle_dir', '')}")
        return

    if method == "MODEL_BASED_ADDITIVE":
        additive_reference = external_reference_stack if external_reference_stack is not None else reference_field
        if additive_reference is None:
            self._msg_error("Leakage", "Model-based additive correction requires a reference field.")
            return
        self._append_log(f"[LEAKAGE] Model-based additive correction using reference_mode={reference_mode}")
        try:
            out, info = model_based_additive_correct_stack(
                grid3d,
                additive_reference,
                lon_vec,
                lat_vec,
                opts,
                mask=mask,
                restrict_to_mask=bool(leak_cfg.get("restrict_additive_to_mask", True)),
            )
        except Exception as e:
            self._msg_error("Leakage", f"Model-based additive correction failed: {e}")
            return
        leakage_term = np.asarray(info.get("leakage_term", np.zeros_like(mask, dtype=float)), dtype=float)
        delta_metric = np.nanmean(np.abs(out - grid3d), axis=(0, 1))
        validation["residual_metric_by_month"] = np.asarray(delta_metric, dtype=float)
        validation["representative_index"] = int(np.nanargmax(delta_metric)) if np.any(np.isfinite(delta_metric)) else 0
        out_file = self._save_leakage_output(out, lon_vec, lat_vec, t_arr, labels, in_path, out_path, "mba")
        bundle = save_leakage_bundle(
            output_file=out_file,
            raw_stack=grid3d,
            corrected_stack=out,
            lon_vec=lon_vec,
            lat_vec=lat_vec,
            labels=labels,
            mask=mask,
            method=method,
            scene_info=scene.__dict__,
            operator_info=operator_spec.__dict__,
            validation={**validation, "leakage_term": leakage_term},
            extra_meta={
                "scope": scope,
                "reference_mode": reference_mode,
                "requested_algorithm_name": requested_algorithm_name,
                "requested_strategy": requested_strategy,
                "resolved_request": resolved_request,
                "strategy_family": strategy_family,
                "strategy_variant": strategy_variant,
                "options": opts.__dict__,
                "input_path": in_path,
            },
        )
        self._clear_scope_progress("leakage")
        self._set_scope_progress_pct("leakage", 100.0, "100%")
        self._last_leakage_bundle = bundle
        self._append_log(f"[LEAKAGE] Model-based additive completed. Output: {out_file}")
        self._append_log(f"[LEAKAGE] Diagnostics bundle: {bundle.get('bundle_dir', '')}")
        self._msg_info("Leakage", f"Model-based additive correction completed.\n{out_file}\n\nDiagnostics:\n{bundle.get('bundle_dir', '')}")
        return

    # BASIN_SCALE_FACTOR method
    try:
        sf = float(self.var_lrc_sf.get())
    except Exception:
        sf = 1.0
    if not np.isfinite(sf) or np.isclose(sf, 0.0):
        sf = 1.0

    if external_reference_stack is not None:
        ref_stack = np.asarray(external_reference_stack, dtype=float)
        if ref_stack.ndim == 2:
            ref_stack = ref_stack[:, :, None]
        if ref_stack.shape[:2] != grid3d.shape[:2]:
            self._msg_error(
                "Leakage",
                f"Reference stack shape mismatch: expected {grid3d.shape[:2]}, got {ref_stack.shape[:2]}",
            )
            return
        if ref_stack.shape[2] == 1 and nt > 1:
            ref_stack = np.repeat(ref_stack, nt, axis=2)
        if ref_stack.shape[2] != nt:
            self._msg_error(
                "Leakage",
                f"Reference stack length mismatch: input Nt={nt}, reference Nt={ref_stack.shape[2]}",
            )
            return
        self._append_log("[LEAKAGE] Computing literature-style basin scale factor from external reference stack...")
        try:
            sf, sf_info = compute_basin_scale_factor_from_reference(ref_stack, mask, lon_vec, lat_vec, opts)
        except Exception as e:
            self._msg_error("Leakage", f"Basin scale-factor estimation failed: {e}")
            return
        grid_out = apply_scale_factors_stack(grid3d, mask, np.asarray([sf], dtype=float))
        validation["regional_series_reference"] = compute_masked_series(ref_stack, mask, lat_vec)
        self._append_log(f"[LEAKAGE] Basin SF={sf:.6f}")
        try:
            self.var_lrc_sf.set(float(sf))
        except Exception:
            pass
        self._set_scope_progress_pct("leakage", 100.0, "100%")
    else:
        if bool(self.var_lrc_sf_auto.get()) if hasattr(self, "var_lrc_sf_auto") else False:
            self._append_log("[LEAKAGE] Auto-computing basin SF from synthetic unit field...")
            try:
                sf, info = compute_scale_factor(mask, lon_vec, lat_vec, opts, unit_mm=1.0)
                self._append_log(f"[LEAKAGE] SF={sf:.6f}, filtered_mean={info.get('filtered_mean', np.nan):.6f}")
            except Exception as e:
                self._msg_error("Leakage", f"Auto SF failed: {e}")
                return
            try:
                self.var_lrc_sf.set(sf)
            except Exception:
                pass

        grid_out = grid3d.copy()
        try:
            use_par = bool(getattr(self.cfg.parallel, "enable", False))
            n_workers = int(getattr(self.cfg.parallel, "n_workers", 1))
        except Exception:
            use_par = False
            n_workers = 1

        if use_par and n_workers > 1 and nt > 1:
            n_workers = max(1, min(n_workers, nt))
            self._append_log(f"[LEAKAGE] SF parallel workers={n_workers}")

            def _scale_month(k):
                g = grid3d[:, :, k]
                return k, np.where(mask, g * sf, g)

            with ThreadPoolExecutor(max_workers=n_workers) as ex:
                futures = {ex.submit(_scale_month, k): k for k in range(nt)}
                done = 0
                for fut in as_completed(futures):
                    if not self._check_pause_stop():
                        self._append_log("[LEAKAGE] Stopped by user.", tag="stderr")
                        try:
                            for ff in futures:
                                ff.cancel()
                        except Exception:
                            pass
                        return
                    try:
                        k, gk = fut.result()
                    except Exception:
                        continue
                    grid_out[:, :, k] = gk
                    done += 1
                    pct = (done / max(1, nt)) * 100.0
                    self._set_scope_progress_pct("leakage", pct, f"{pct:4.1f}%")
        else:
            for k in range(nt):
                if not self._check_pause_stop():
                    self._append_log("[LEAKAGE] Stopped by user.", tag="stderr")
                    return
                grid_out[:, :, k] = np.where(mask, grid_out[:, :, k] * sf, grid_out[:, :, k])
                pct = ((k + 1) / max(1, nt)) * 100.0
                self._set_scope_progress_pct("leakage", pct, f"{pct:4.1f}%")

    validation["residual_metric_by_month"] = np.nanmean(np.abs(grid_out - grid3d), axis=(0, 1))
    validation["representative_index"] = int(np.nanargmax(validation["residual_metric_by_month"])) if np.any(np.isfinite(validation["residual_metric_by_month"])) else 0
    out_file = self._save_leakage_output(grid_out, lon_vec, lat_vec, t_arr, labels, in_path, out_path, "lrc")
    bundle = save_leakage_bundle(
        output_file=out_file,
        raw_stack=grid3d,
        corrected_stack=grid_out,
        lon_vec=lon_vec,
        lat_vec=lat_vec,
        labels=labels,
        mask=mask,
        method=method,
        scene_info=scene.__dict__,
        operator_info=operator_spec.__dict__,
        validation=validation,
        extra_meta={
            "scope": scope,
            "scale_factor": sf,
            "requested_strategy": requested_strategy,
            "strategy_family": strategy_family,
            "strategy_variant": strategy_variant,
            "options": opts.__dict__,
            "input_path": in_path,
        },
    )
    self._clear_scope_progress("leakage")
    self._last_leakage_bundle = bundle
    self._append_log(f"[LEAKAGE] Basin SF completed. Output: {out_file}")
    self._append_log(f"[LEAKAGE] Diagnostics bundle: {bundle.get('bundle_dir', '')}")
    self._msg_info("Leakage", f"Basin scale-factor correction completed.\n{out_file}\n\nDiagnostics:\n{bundle.get('bundle_dir', '')}")




