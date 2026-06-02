"""Leakage workflow helpers extracted from GUI (non-UI logic)."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
from scipy.io import savemat

from grace_pipeline.infra.config import get_data_dir
from grace_pipeline.leakage import LeakageFilterOptions, compute_masked_series, infer_leakage_product_type


def default_global_land_shp(root_dir: str) -> Path:
    root = Path(root_dir)
    data_dir = get_data_dir(root)
    candidates = [
        data_dir / "Boundary" / "ne_admin_0" / "ne_50m_admin_0_countries.shp",
        data_dir / "Boundary" / "boundary_cache" / "ne_50m_admin_0_countries.shp",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError("Global land boundary shapefile not found (ne_50m_admin_0_countries.shp).")


def build_global_land_mask(
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    *,
    root_dir: str,
    cache_key=None,
    cache_mask=None,
):
    lon = np.asarray(lon_vec, dtype=float).squeeze()
    lat = np.asarray(lat_vec, dtype=float).squeeze()
    if lon.ndim != 1 or lat.ndim != 1:
        raise ValueError("lon/lat vectors must be 1D for global land mask.")

    lon_wrapped = lon.copy()
    if np.nanmin(lon_wrapped) >= 0 and np.nanmax(lon_wrapped) > 180:
        lon_wrapped = ((lon_wrapped + 180.0) % 360.0) - 180.0

    shp = default_global_land_shp(root_dir)
    key = (
        int(lon_wrapped.size),
        int(lat.size),
        float(np.nanmin(lon_wrapped)),
        float(np.nanmax(lon_wrapped)),
        float(np.nanmin(lat)),
        float(np.nanmax(lat)),
        str(shp),
        int(shp.stat().st_mtime),
    )
    if cache_key == key and isinstance(cache_mask, np.ndarray) and cache_mask.shape == (lon.size, lat.size):
        return cache_mask.copy(), key

    from grace_pipeline.basin import read_boundary, make_mask

    basins = read_boundary(str(shp), name_field="NAME")
    if not basins:
        raise ValueError("No polygons found in global land boundary shapefile.")

    mask = np.zeros((lon.size, lat.size), dtype=bool)
    for b in basins:
        try:
            mask |= make_mask(b, lon_wrapped, lat)
        except Exception:
            continue
    if not np.any(mask):
        raise ValueError("Global land mask is empty.")
    return mask, key


def build_regional_leakage_mask(
    boundary_file: str,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    *,
    cache_key=None,
    cache_mask=None,
):
    bfile = (boundary_file or "").strip()
    if not bfile:
        raise ValueError("区域模式需要边界文件（shp/txt/bln）。")
    if not os.path.exists(bfile):
        raise FileNotFoundError(f"Boundary file not found: {bfile}")

    p = Path(bfile)
    key = (
        "regional",
        int(lon_vec.size),
        int(lat_vec.size),
        float(np.nanmin(lon_vec)),
        float(np.nanmax(lon_vec)),
        float(np.nanmin(lat_vec)),
        float(np.nanmax(lat_vec)),
        str(p.resolve()),
        int(p.stat().st_mtime),
    )
    if cache_key == key and isinstance(cache_mask, np.ndarray) and cache_mask.shape == (lon_vec.size, lat_vec.size):
        return cache_mask.copy(), key

    from grace_pipeline.basin import read_boundary, make_mask

    basins = read_boundary(bfile)
    if not basins:
        raise ValueError("No basins loaded from boundary file.")

    mask = np.zeros((lon_vec.size, lat_vec.size), dtype=bool)
    for b in basins:
        try:
            mask |= make_mask(b, lon_vec, lat_vec)
        except Exception:
            continue
    if not np.any(mask):
        raise ValueError("Regional mask is empty for leakage correction.")
    return mask, key


def infer_leakage_method_from_input(in_path: str, data_meta: Optional[Dict[str, Any]] = None):
    tokens = []
    if isinstance(data_meta, dict):
        for k in ("tag", "source_tag", "filter_tag", "product_tag", "active_var"):
            v = data_meta.get(k)
            if v is not None:
                tokens.append(str(v).upper())
    p = str(in_path or "").upper()
    if p:
        tokens.extend([p, Path(p).stem.upper(), Path(p).name.upper(), Path(p).parent.name.upper()])
    text = " | ".join(tokens)

    m_ddk = re.search(r"DDK\s*[_-]?([1-8])", text)
    if m_ddk:
        return "DDK4", f"DDK{m_ddk.group(1)}"
    if ("HSAF" in text) or ("HANKEL" in text):
        return "HSAF", None
    if ("FAN" in text) and ("P4" in text or "PNMM" in text or "DECOR" in text):
        return "FAN_DECORRELATION", None
    if "FAN" in text:
        return "FAN", None
    if ("P4M6" in text) or ("PNMM" in text):
        return "P4M6", None
    if ("GAUSS" in text or "GAUSSIAN" in text) and ("P4" in text or "PNMM" in text or "DECOR" in text):
        return "GAUSSIAN_DECORRELATION", None
    if "GAUSS" in text or "GAUSSIAN" in text:
        return "GAUSSIAN", None
    return None, None


def build_leakage_filter_options(
    *,
    raw_method: str,
    in_path: str = "",
    data_meta: Optional[Dict[str, Any]] = None,
    sf_ddk: str = "DDK4",
    parallel_enable: bool = False,
    parallel_n_workers: int = 1,
    frozen_allow_parallel: bool = False,
    frozen_max_workers: int = 0,
    hsaf_n: int = 60,
    hsaf_p: int = 20,
    hsaf_k: int = 6,
    hsaf_j: int = 10,
    hsaf_input: str = "P4M6",
    sf_gauss: float = 300.0,
    sf_fan_r1: float = 300.0,
    sf_fan_r2: float = 300.0,
    sf_hsa_ts: float = 1.0,
    sf_p4_deg: int = 4,
    sf_p4_m: int = 6,
    lmax: int = 60,
    ddk_data_dir: str = "",
    log_info_cb=None,
    log_warn_cb=None,
) -> LeakageFilterOptions:
    raw = str(raw_method or "AUTO").strip().upper().replace(" ", "_")
    if raw == "HANKEL":
        raw = "HSAF"

    inferred_method, inferred_ddk = infer_leakage_method_from_input(in_path, data_meta)
    inferred_product = infer_leakage_product_type(in_path, data_meta=data_meta)
    method = raw
    if raw in ("", "AUTO"):
        method = inferred_method or ("NONE" if inferred_product == "mascon_native" else "GAUSSIAN")
        if callable(log_info_cb):
            log_info_cb(f"[LEAKAGE] Forward operator auto-detected: {method}")
    elif inferred_method and raw != inferred_method:
        if callable(log_warn_cb):
            log_warn_cb(
                f"[LEAKAGE][WARN] Selected operator={raw}, input-detected={inferred_method}. "
                "If artifacts appear, switch to Auto."
            )

    if method.startswith("DDK"):
        ddk = inferred_ddk or method
        method = "DDK4"
    else:
        ddk = inferred_ddk or str(sf_ddk).upper()

    hsaf_workers = int(parallel_n_workers) if parallel_enable else 1
    if getattr(sys, "frozen", False):
        if not frozen_allow_parallel:
            hsaf_workers = 1
        elif int(frozen_max_workers) > 0:
            hsaf_workers = min(hsaf_workers, int(frozen_max_workers))
    hsaf_workers = max(1, min(hsaf_workers, 32))

    hsaf_input = str(hsaf_input or "P4M6").strip().upper()
    if hsaf_input not in ("RAW", "P4M6"):
        hsaf_input = "P4M6"

    hsaf_params = {
        "N": int(hsaf_n),
        "P": int(hsaf_p),
        "K": int(hsaf_k),
        "J": int(hsaf_j),
        "workers": hsaf_workers,
        "iterations": 1,
    }
    return LeakageFilterOptions(
        method=method,
        gaussian_km=float(sf_gauss),
        fan_r1_km=float(sf_fan_r1),
        fan_r2_km=float(sf_fan_r2),
        ddk_type=ddk,
        ddk_data_dir=str(ddk_data_dir or ""),
        hsaf_params=hsaf_params,
        hsaf_ts=float(sf_hsa_ts),
        hsaf_input=hsaf_input,
        p4m6_poly_deg=int(sf_p4_deg),
        p4m6_m_start=int(sf_p4_m),
        lmax=int(lmax),
    )


def save_leakage_output(
    *,
    fmt: str,
    grid_out,
    lon_vec,
    lat_vec,
    t_arr,
    labels,
    in_path,
    out_path,
    suffix,
    resolve_output_file_cb,
    save_grid_txt_cb,
    safe_savemat_cb,
):
    out_fmt = str(fmt or "mat").lower()
    if out_fmt == "txt":
        out_file, out_dir = resolve_output_file_cb(out_path, in_path, suffix, "txt")
        if grid_out.shape[2] == 1:
            save_grid_txt_cb(out_file, lon_vec, lat_vec, grid_out[:, :, 0])
        else:
            base = Path(out_file).stem
            out_dir = out_dir or str(Path(out_file).parent)
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            for k in range(grid_out.shape[2]):
                lbl = labels[k] if k < len(labels) else f"{k:03d}"
                save_grid_txt_cb(str(Path(out_dir) / f"{base}_{lbl}.txt"), lon_vec, lat_vec, grid_out[:, :, k])
        return out_file

    t_save = t_arr
    try:
        arr = np.asarray(t_arr)
        if arr.size == 0:
            t_save = np.asarray(labels, dtype=object)
        elif arr.dtype == object:
            flat = []
            for i, x in enumerate(arr.ravel()):
                if x is None:
                    flat.append(labels[i] if i < len(labels) else np.nan)
                else:
                    flat.append(x)
            t_save = np.asarray(flat, dtype=object).reshape(arr.shape)
    except Exception:
        if t_arr is None:
            t_save = np.asarray(labels, dtype=object)

    out_file, _ = resolve_output_file_cb(out_path, in_path, suffix, "mat")
    safe_savemat_cb(out_file, {"ewh": grid_out, "lon": lon_vec, "lat": lat_vec, "t": t_save})
    return out_file


def _safe_write_text(path: str | Path, text: str):
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, out)


def _safe_write_json(path: str | Path, payload: Dict[str, Any]):
    _safe_write_text(path, json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default))


def _safe_write_mat(path: str | Path, payload: Dict[str, Any]):
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    savemat(str(tmp), payload)
    os.replace(tmp, out)


def _json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    return str(value)


def save_leakage_bundle(
    *,
    output_file: str,
    raw_stack,
    corrected_stack,
    lon_vec,
    lat_vec,
    labels,
    mask,
    method: str,
    scene_info: Optional[Dict[str, Any]] = None,
    operator_info: Optional[Dict[str, Any]] = None,
    validation: Optional[Dict[str, Any]] = None,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = Path(output_file)
    bundle_dir = out.parent / f"{out.stem}_bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    raw_arr = np.asarray(raw_stack, dtype=float)
    corr_arr = np.asarray(corrected_stack, dtype=float)
    if raw_arr.ndim == 2:
        raw_arr = raw_arr[:, :, None]
    if corr_arr.ndim == 2:
        corr_arr = corr_arr[:, :, None]
    labels = list(labels or [f"{k + 1:03d}" for k in range(corr_arr.shape[2])])
    mask_arr = np.asarray(mask, dtype=bool)
    raw_series = compute_masked_series(raw_arr, mask_arr, lat_vec)
    corrected_series = compute_masked_series(corr_arr, mask_arr, lat_vec)
    reference_series = None
    if isinstance(validation, dict) and validation.get("regional_series_reference") is not None:
        reference_series = np.asarray(validation.get("regional_series_reference"), dtype=float).reshape(-1)

    if isinstance(validation, dict) and validation.get("representative_index") is not None:
        rep_idx = int(validation.get("representative_index"))
    else:
        delta_mag = np.nanmean(np.abs(corr_arr - raw_arr), axis=(0, 1))
        rep_idx = int(np.nanargmax(delta_mag)) if np.any(np.isfinite(delta_mag)) else 0
    rep_idx = max(0, min(rep_idx, corr_arr.shape[2] - 1))

    figure_paths: Dict[str, str] = {}

    fig, ax = plt.subplots(figsize=(10, 4.5), constrained_layout=True)
    x = np.arange(len(labels))
    ax.plot(x, raw_series, label="Raw", color="#6c757d", linewidth=1.5)
    ax.plot(x, corrected_series, label="Corrected", color="#005db5", linewidth=1.8)
    if reference_series is not None and reference_series.size == len(labels):
        ax.plot(x, reference_series, label="Reference", color="#2f7d32", linewidth=1.4, linestyle="--")
    tick_step = max(1, len(labels) // 12)
    ax.set_xticks(x[::tick_step], [labels[i] for i in x[::tick_step]], rotation=45, ha="right")
    ax.set_ylabel("Area-weighted mean")
    ax.set_title(f"Leakage correction series: {method}")
    ax.grid(True, alpha=0.25)
    ax.legend()
    series_path = bundle_dir / "regional_series.png"
    fig.savefig(series_path, dpi=180)
    plt.close(fig)
    figure_paths["regional_series"] = str(series_path)

    vmin = np.nanpercentile(np.concatenate([raw_arr[:, :, rep_idx].ravel(), corr_arr[:, :, rep_idx].ravel()]), 5)
    vmax = np.nanpercentile(np.concatenate([raw_arr[:, :, rep_idx].ravel(), corr_arr[:, :, rep_idx].ravel()]), 95)
    diff = corr_arr[:, :, rep_idx] - raw_arr[:, :, rep_idx]
    diff_abs = np.nanpercentile(np.abs(diff), 95)
    if not np.isfinite(diff_abs) or diff_abs <= 0:
        diff_abs = 1.0
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.2), constrained_layout=True)
    im0 = axes[0].imshow(raw_arr[:, :, rep_idx].T, origin="lower", cmap="RdBu_r", vmin=vmin, vmax=vmax)
    axes[0].set_title(f"Raw | {labels[rep_idx]}")
    im1 = axes[1].imshow(corr_arr[:, :, rep_idx].T, origin="lower", cmap="RdBu_r", vmin=vmin, vmax=vmax)
    axes[1].set_title("Corrected")
    im2 = axes[2].imshow(diff.T, origin="lower", cmap="coolwarm", vmin=-diff_abs, vmax=diff_abs)
    axes[2].set_title("Corrected - Raw")
    for ax in axes:
        ax.set_xlabel("Lon index")
        ax.set_ylabel("Lat index")
    fig.colorbar(im1, ax=axes[:2], shrink=0.8, location="bottom")
    fig.colorbar(im2, ax=axes[2], shrink=0.8, location="bottom")
    map_path = bundle_dir / "representative_map.png"
    fig.savefig(map_path, dpi=180)
    plt.close(fig)
    figure_paths["representative_map"] = str(map_path)

    roi_idx = np.argwhere(mask_arr)
    if roi_idx.size:
        x0, y0 = roi_idx.min(axis=0)
        x1, y1 = roi_idx.max(axis=0)
        pad_x = max(4, int(0.15 * max(1, x1 - x0 + 1)))
        pad_y = max(4, int(0.15 * max(1, y1 - y0 + 1)))
        xs = slice(max(0, x0 - pad_x), min(mask_arr.shape[0], x1 + pad_x + 1))
        ys = slice(max(0, y0 - pad_y), min(mask_arr.shape[1], y1 + pad_y + 1))
        raw_roi = raw_arr[xs, ys, rep_idx]
        corr_roi = corr_arr[xs, ys, rep_idx]
        diff_roi = diff[xs, ys]
        roi_stack = np.concatenate([raw_roi.ravel(), corr_roi.ravel()])
        roi_vmin = np.nanpercentile(roi_stack, 5)
        roi_vmax = np.nanpercentile(roi_stack, 95)
        roi_diff_abs = np.nanpercentile(np.abs(diff_roi), 98)
        if not np.isfinite(roi_diff_abs) or roi_diff_abs <= 0:
            roi_diff_abs = diff_abs
        fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.2), constrained_layout=True)
        im0 = axes[0].imshow(raw_roi.T, origin="lower", cmap="RdBu_r", vmin=roi_vmin, vmax=roi_vmax)
        axes[0].set_title(f"ROI Raw | {labels[rep_idx]}")
        im1 = axes[1].imshow(corr_roi.T, origin="lower", cmap="RdBu_r", vmin=roi_vmin, vmax=roi_vmax)
        axes[1].set_title("ROI Corrected")
        im2 = axes[2].imshow(diff_roi.T, origin="lower", cmap="coolwarm", vmin=-roi_diff_abs, vmax=roi_diff_abs)
        axes[2].set_title("ROI Corrected - Raw")
        for ax in axes:
            ax.set_xlabel("Lon index")
            ax.set_ylabel("Lat index")
        fig.colorbar(im1, ax=axes[:2], shrink=0.8, location="bottom")
        fig.colorbar(im2, ax=axes[2], shrink=0.8, location="bottom")
        roi_path = bundle_dir / "representative_map_roi.png"
        fig.savefig(roi_path, dpi=180)
        plt.close(fig)
        figure_paths["representative_map_roi"] = str(roi_path)

    fig, ax = plt.subplots(figsize=(5.4, 4.2), constrained_layout=True)
    ax.imshow(mask_arr.T, origin="lower", cmap="Greens")
    scene_text = "\n".join((scene_info or {}).get("reasoning", [])[:3]) if isinstance(scene_info, dict) else ""
    title = (scene_info or {}).get("scene", "mask") if isinstance(scene_info, dict) else "mask"
    ax.set_title(f"Mask preview | {title}")
    if scene_text:
        ax.text(1.02, 0.98, scene_text, transform=ax.transAxes, va="top", ha="left", fontsize=8)
    ax.set_xlabel("Lon index")
    ax.set_ylabel("Lat index")
    mask_path = bundle_dir / "mask_scene.png"
    fig.savefig(mask_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    figure_paths["mask_scene"] = str(mask_path)

    conv = None
    if isinstance(validation, dict):
        conv = validation.get("convergence_by_month")
        if conv is None:
            conv = validation.get("residual_metric_by_month")
    if conv is not None:
        conv = np.asarray(conv, dtype=float).reshape(-1)
        fig, ax = plt.subplots(figsize=(10, 4.0), constrained_layout=True)
        ax.plot(np.arange(conv.size), conv, color="#b35a00", linewidth=1.5)
        ax.set_title("Convergence / residual metric by month")
        ax.set_xlabel("Month index")
        ax.set_ylabel("Metric")
        ax.grid(True, alpha=0.25)
        conv_path = bundle_dir / "convergence.png"
        fig.savefig(conv_path, dpi=180)
        plt.close(fig)
        figure_paths["convergence"] = str(conv_path)

    if isinstance(validation, dict):
        fm_obs = validation.get("fm_rate_observed")
        fm_rec = validation.get("fm_rate_recovered")
        fm_pre = validation.get("fm_rate_predicted")
        fm_res = validation.get("fm_rate_residual")
        if all(v is not None for v in (fm_obs, fm_rec, fm_pre, fm_res)):
            fm_obs = np.asarray(fm_obs, dtype=float)
            fm_rec = np.asarray(fm_rec, dtype=float)
            fm_pre = np.asarray(fm_pre, dtype=float)
            fm_res = np.asarray(fm_res, dtype=float)
            rate_stack = np.concatenate([fm_obs.ravel(), fm_rec.ravel()])
            rvmin = np.nanpercentile(rate_stack, 5)
            rvmax = np.nanpercentile(rate_stack, 95)
            rdiff = np.nanpercentile(np.abs(fm_res), 98)
            if not np.isfinite(rdiff) or rdiff <= 0:
                rdiff = 1.0
            fig, axes = plt.subplots(2, 2, figsize=(11.5, 8.2), constrained_layout=True)
            im0 = axes[0, 0].imshow(fm_obs.T, origin="lower", cmap="RdBu_r", vmin=rvmin, vmax=rvmax)
            axes[0, 0].set_title("FM observed apparent rate")
            im1 = axes[0, 1].imshow(fm_rec.T, origin="lower", cmap="RdBu_r", vmin=rvmin, vmax=rvmax)
            axes[0, 1].set_title("FM recovered true rate")
            im2 = axes[1, 0].imshow(fm_pre.T, origin="lower", cmap="RdBu_r", vmin=rvmin, vmax=rvmax)
            axes[1, 0].set_title("FM predicted apparent rate")
            im3 = axes[1, 1].imshow(fm_res.T, origin="lower", cmap="coolwarm", vmin=-rdiff, vmax=rdiff)
            axes[1, 1].set_title("FM residual (obs - pred)")
            for ax in axes.ravel():
                ax.set_xlabel("Lon index")
                ax.set_ylabel("Lat index")
            fig.colorbar(im1, ax=[axes[0, 0], axes[0, 1], axes[1, 0]], shrink=0.78, location="bottom")
            fig.colorbar(im3, ax=axes[1, 1], shrink=0.78, location="bottom")
            fm_diag_path = bundle_dir / "fm_rate_diagnostics.png"
            fig.savefig(fm_diag_path, dpi=180)
            plt.close(fig)
            figure_paths["fm_rate_diagnostics"] = str(fm_diag_path)

        fm_hist = validation.get("fm_rate_residual_history")
        if fm_hist is not None:
            fm_hist = np.asarray(fm_hist, dtype=float).reshape(-1)
            if fm_hist.size:
                fig, ax = plt.subplots(figsize=(10, 4.0), constrained_layout=True)
                ax.plot(np.arange(1, fm_hist.size + 1), fm_hist, color="#8f2d56", linewidth=1.6)
                ax.set_title("FM rate-map residual history")
                ax.set_xlabel("Iteration")
                ax.set_ylabel("Residual metric")
                ax.grid(True, alpha=0.25)
                hist_path = bundle_dir / "fm_rate_history.png"
                fig.savefig(hist_path, dpi=180)
                plt.close(fig)
                figure_paths["fm_rate_history"] = str(hist_path)

    series_csv = bundle_dir / "regional_series.csv"
    lines = ["label,raw,corrected,reference"]
    for idx, label in enumerate(labels):
        ref_val = ""
        if reference_series is not None and idx < reference_series.size and np.isfinite(reference_series[idx]):
            ref_val = f"{float(reference_series[idx]):.9g}"
        lines.append(
            f"{label},{float(raw_series[idx]) if np.isfinite(raw_series[idx]) else ''},"
            f"{float(corrected_series[idx]) if np.isfinite(corrected_series[idx]) else ''},{ref_val}"
        )
    _safe_write_text(series_csv, "\n".join(lines))

    corrected_stack_file = bundle_dir / "corrected_stack.mat"
    difference_stack_file = bundle_dir / "difference_stack.mat"
    _safe_write_mat(corrected_stack_file, {"ewh": corr_arr, "lon": lon_vec, "lat": lat_vec, "t": np.asarray(labels, dtype=object)})
    _safe_write_mat(difference_stack_file, {"ewh": corr_arr - raw_arr, "lon": lon_vec, "lat": lat_vec, "t": np.asarray(labels, dtype=object)})

    input_path = ""
    if isinstance(extra_meta, dict):
        input_path = str(extra_meta.get("input_path", "") or "")
    preview_collection = {
        "layers": {
            "raw": input_path,
            "corrected": str(corrected_stack_file),
            "difference": str(difference_stack_file),
        },
        "figures": figure_paths,
        "default_layer": "corrected",
        "default_figure": (
            "fm_rate_diagnostics"
            if "fm_rate_diagnostics" in figure_paths
            else ("representative_map_roi" if "representative_map_roi" in figure_paths else "representative_map")
        ),
        "time_labels": labels,
        "regions": list((extra_meta or {}).get("region_names", []) or ["主区域"]),
        "result_dimensions": {
            "time_count": int(corr_arr.shape[2]),
            "region_count": int(len(list((extra_meta or {}).get("region_names", []) or ["主区域"]))),
            "has_global_grid": True,
            "has_reference_series": bool(reference_series is not None),
        },
    }
    preview_manifest = {
        "bundle_dir": str(bundle_dir),
        "method": str(method),
        "scene": scene_info or {},
        "operator": operator_info or {},
        "preview": preview_collection,
    }
    _safe_write_json(bundle_dir / "preview_manifest.json", preview_manifest)
    _safe_write_json(bundle_dir / "gallery_index.json", {"figures": figure_paths, "layers": preview_collection["layers"], "labels": labels})

    summary = {
        "output_file": str(out),
        "bundle_dir": str(bundle_dir),
        "method": str(method),
        "scene": scene_info or {},
        "operator": operator_info or {},
        "regional_series_raw": raw_series,
        "regional_series_corrected": corrected_series,
        "regional_series_reference": reference_series if reference_series is not None else [],
        "representative_index": rep_idx,
        "labels": labels,
        "figure_paths": figure_paths,
        "preview_collection": preview_collection,
        "extra_meta": extra_meta or {},
    }
    if reference_series is not None and reference_series.size == raw_series.size:
        raw_rmse = float(np.sqrt(np.nanmean((raw_series - reference_series) ** 2)))
        corrected_rmse = float(np.sqrt(np.nanmean((corrected_series - reference_series) ** 2)))
        summary["reference_comparison"] = {
            "raw_rmse": raw_rmse,
            "corrected_rmse": corrected_rmse,
            "rmse_improvement_pct": (100.0 * (raw_rmse - corrected_rmse) / raw_rmse) if raw_rmse > 0 else None,
        }
    if isinstance(validation, dict):
        summary["validation"] = validation
    _safe_write_json(bundle_dir / "summary.json", summary)
    return {
        "bundle_dir": str(bundle_dir),
        **figure_paths,
        "summary_json": str(bundle_dir / "summary.json"),
        "preview_manifest": str(bundle_dir / "preview_manifest.json"),
        "gallery_index": str(bundle_dir / "gallery_index.json"),
        "corrected_stack": str(corrected_stack_file),
        "difference_stack": str(difference_stack_file),
    }
