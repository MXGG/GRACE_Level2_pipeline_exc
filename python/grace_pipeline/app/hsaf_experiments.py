"""Small-sample HSAF experiment runner for prototype engines."""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import matplotlib.pyplot as plt
import numpy as np

from grace_pipeline.app.leakage_helpers import build_global_land_mask
from grace_pipeline.app.grace_groundtrack import (
    build_bundle_order_scores,
    build_bundle_phase_unit,
    build_bundle_template_from_density,
    build_monthly_groundtrack_bundle,
    build_monthly_groundtrack_bundle_rl02_sampled,
)
from grace_pipeline.filters.hsaf import compute_stripe_metrics, estimate_stripe_band, filter_grid_hsaf
from grace_pipeline.filters.hsaf_sh import filter_sh_hsaf
from grace_pipeline.filters.p4m6 import filter_sh_p4m6
from grace_pipeline.inversion.adaptive_parity_hsaf import AdaptiveParityHSAF
from grace_pipeline.inversion.pseudo_moire import PseudoMoireOperator
from grace_pipeline.inversion.sampling_aware import apply_sampling_aware_inversion
from grace_pipeline.infra.datasets.time_index import build_time_index
from grace_pipeline.domain.inversion import apply_gia, compute_mean_sh, ewh_synthesis, read_gsm_month, replace_low_degree
from grace_pipeline.io.stack import find_stack_file, load_stack, load_stack_hdf5


DEFAULT_EXPERIMENT_MONTHS = ["2002-04", "2007-05", "2015-09", "2017-03"]
DEFAULT_ENGINES = ["modal_adaptive_v1", "modal_adaptive_latband_v1", "multichannel_v1"]
ADAPTIVE_PARITY_ENGINES = {"adaptive_parity_hsaf_v1"}
SAMPLING_PSEUDOMOIRE_ENGINES = {"sampling_pseudomoire_v1"}
SH_DOMAIN_ENGINES = {
    "sh_orderwise_v1",
    "sh_multichannel_v1",
    "sh_demod_v1",
    "sh_demod_multichannel_v1",
    "sh_orbit_orderwise_v1",
    "sh_orbit_multichannel_v1",
    "sh_orbit_demod_v1",
    "sh_orbit_demod_multichannel_v1",
}
HYBRID_ENGINES = {"carrier_removed_hsaf_v1", "carrier_removed_multichannel_v1"}
ORBIT_ENGINES = {"orbit_bundle_v1", "orbit_bundle_multichannel_v1"}
ORBIT_PHASE_ENGINES = {"bundle_phase_demod_v1", "bundle_phase_demod_multichannel_v1"}
PSEUDOMOIRE_ENGINES = {"pseudo_moire_operator_v1", "pseudo_moire_operator_multichannel_v1"}
SAMPLING_OPERATOR_ENGINES = {"sampling_operator_v1", "sampling_operator_multichannel_v1"}
SAMPLING_INVERSION_ENGINES = {"sampling_inversion_v1", "sampling_inversion_multichannel_v1"}
SH_ORBIT_ENGINES = {
    "sh_orbit_orderwise_v1",
    "sh_orbit_multichannel_v1",
    "sh_orbit_demod_v1",
    "sh_orbit_demod_multichannel_v1",
}
SH_CARRIER_ORBIT_ENGINES = {
    "sh_orbit_carrier_demod_v1",
    "sh_orbit_carrier_demod_multichannel_v1",
}


@dataclass
class _ExperimentRecord:
    engine: str
    month: str
    elapsed_s: float
    rmse_vs_ddk4: float
    corr_vs_ddk4: float
    ocean_anisotropy: float
    ocean_band_energy: float
    land_retention: float
    baseline_rmse: float
    baseline_corr: float
    baseline_anisotropy: float
    baseline_band_energy: float
    baseline_land_retention: float
    basis_concentration: float = float("nan")


def _prepare_monthly_sh_context(cfg, selected_months: Sequence[str]) -> Optional[Dict[str, Any]]:
    needed = set(str(m) for m in selected_months)
    time_entries = build_time_index(cfg)
    month_to_entry = {te.ym: te for te in time_entries if te.ym in needed}
    missing = sorted(needed - set(month_to_entry))
    if missing:
        raise FileNotFoundError(f"GFC time entries not found for months: {', '.join(missing)}")
    mean_sh = compute_mean_sh(cfg, time_entries) if bool(getattr(cfg.inversion, "remove_mean", False)) else None
    return {
        "month_to_entry": month_to_entry,
        "mean_sh": mean_sh,
    }


def _prepare_month_sh(cfg, sh_context: Dict[str, Any], month: str, input_tag: str) -> tuple[np.ndarray, np.ndarray]:
    te = sh_context["month_to_entry"][month]
    sh = read_gsm_month(cfg, te)
    sh = replace_low_degree(cfg, sh, te)
    mean_sh = sh_context.get("mean_sh")
    if mean_sh is not None and bool(getattr(cfg.inversion, "remove_mean", False)):
        sh.C = sh.C - mean_sh.C
        sh.S = sh.S - mean_sh.S
    if getattr(cfg.inversion, "gia", {}).get("enable", False):
        sh = apply_gia(cfg, sh, te)
    C = np.asarray(sh.C, dtype=float)
    S = np.asarray(sh.S, dtype=float)
    if str(input_tag or "RAW").strip().upper() == "P4M6":
        C, S, _ = filter_sh_p4m6(
            C,
            S,
            int(sh.Lmax),
            int(getattr(cfg.filter.p4m6, "poly_deg", 4)),
            int(getattr(cfg.filter.p4m6, "m_start", 6)),
        )
    return C, S


def _build_loworder_carrier_grid(
    C: np.ndarray,
    S: np.ndarray,
    lmax: int,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    params: Dict[str, Any],
) -> tuple[np.ndarray, Dict[str, int]]:
    carrier_lmax = max(2, min(int(params.get("carrier_lmax", 20)), int(lmax)))
    carrier_mmax = max(0, min(int(params.get("carrier_mmax", 8)), carrier_lmax))
    C_car = np.zeros_like(C, dtype=float)
    S_car = np.zeros_like(S, dtype=float)
    for ll in range(carrier_lmax + 1):
        mm_max = min(ll, carrier_mmax)
        C_car[ll, : mm_max + 1] = C[ll, : mm_max + 1]
        S_car[ll, : mm_max + 1] = S[ll, : mm_max + 1]
    carrier_grid = ewh_synthesis(C_car, S_car, int(lmax), lon_vec, lat_vec)
    return carrier_grid, {
        "carrier_lmax": int(carrier_lmax),
        "carrier_mmax": int(carrier_mmax),
    }


def _split_loworder_carrier_sh(
    C: np.ndarray,
    S: np.ndarray,
    lmax: int,
    params: Dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[str, int]]:
    carrier_lmax = max(2, min(int(params.get("carrier_lmax", 20)), int(lmax)))
    carrier_mmax = max(0, min(int(params.get("carrier_mmax", 8)), carrier_lmax))
    C_car = np.zeros_like(C, dtype=float)
    S_car = np.zeros_like(S, dtype=float)
    for ll in range(carrier_lmax + 1):
        mm_max = min(ll, carrier_mmax)
        C_car[ll, : mm_max + 1] = C[ll, : mm_max + 1]
        S_car[ll, : mm_max + 1] = S[ll, : mm_max + 1]
    C_res = np.asarray(C, dtype=float) - C_car
    S_res = np.asarray(S, dtype=float) - S_car
    return C_car, S_car, C_res, S_res, {
        "carrier_lmax": int(carrier_lmax),
        "carrier_mmax": int(carrier_mmax),
    }


def _run_hybrid_experiment(
    *,
    engine: str,
    input_grid: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    base_params: Dict[str, Any],
    baseline_cfg: Dict[str, Any],
    cfg,
    sh_context: Dict[str, Any],
    month: str,
    input_tag: str,
) -> tuple[np.ndarray, Dict[str, Any]]:
    C_in, S_in = _prepare_month_sh(cfg, sh_context, month, input_tag)
    carrier_grid, carrier_meta = _build_loworder_carrier_grid(
        C_in,
        S_in,
        int(cfg.inversion.Lmax),
        lon_vec,
        lat_vec,
        base_params,
    )
    residual_grid = np.asarray(input_grid, dtype=float) - carrier_grid
    residual_cfg = {
        "engine": "multichannel_v3" if engine == "carrier_removed_multichannel_v1" else str(baseline_cfg["engine"]),
        "params": dict(base_params),
    }
    residual_filtered, residual_info = filter_grid_hsaf(
        residual_grid,
        lon_vec,
        lat_vec,
        residual_cfg,
    )
    return carrier_grid + residual_filtered, {
        "type": "HSAF_carrier_removed_hybrid",
        "engine": engine,
        "carrier": carrier_meta,
        "residual_engine": str(residual_cfg["engine"]),
        "residual_info": residual_info,
    }


def _run_sh_carrier_orbit_experiment(
    *,
    engine: str,
    cfg,
    sh_context: Dict[str, Any],
    month: str,
    input_tag: str,
    input_grid: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    land_mask: np.ndarray,
    base_params: Dict[str, Any],
    orbit_cache_dir: Path,
) -> tuple[np.ndarray, Dict[str, Any], np.ndarray, np.ndarray]:
    C_in, S_in = _prepare_month_sh(cfg, sh_context, month, input_tag)
    C_car, S_car, C_res, S_res, carrier_meta = _split_loworder_carrier_sh(
        C_in,
        S_in,
        int(cfg.inversion.Lmax),
        base_params,
    )
    sh_params, template_grid, orbit_info = _build_sh_orbit_params(
        month=month,
        input_grid=input_grid,
        lon_vec=lon_vec,
        lat_vec=lat_vec,
        land_mask=land_mask,
        base_params=base_params,
        lmax=int(cfg.inversion.Lmax),
        orbit_cache_dir=orbit_cache_dir,
    )
    residual_engine = (
        "sh_orbit_demod_multichannel_v1"
        if engine == "sh_orbit_carrier_demod_multichannel_v1"
        else "sh_orbit_demod_v1"
    )
    C_res_f, S_res_f, residual_info = filter_sh_hsaf(
        C_res,
        S_res,
        int(cfg.inversion.Lmax),
        {"engine": residual_engine, "params": sh_params},
    )
    C_out = C_car + C_res_f
    S_out = S_car + S_res_f
    result = ewh_synthesis(
        C_out,
        S_out,
        int(cfg.inversion.Lmax),
        lon_vec,
        lat_vec,
    )
    return result, {
        "type": "HSAF_SH_carrier_orbit",
        "engine": engine,
        "carrier": carrier_meta,
        "orbit_bundle": orbit_info,
        "residual_engine": residual_engine,
        "residual_info": residual_info,
    }, template_grid, np.asarray(sh_params["orbit_order_scores"], dtype=float)


def _load_stack_auto(stack_dir: Path, tag: str):
    path = find_stack_file(str(stack_dir), tag, prefer_hdf5=True)
    if not path:
        raise FileNotFoundError(f"Stack file not found for tag '{tag}' in {stack_dir}.")
    p = Path(path)
    if p.suffix.lower() == ".h5":
        return load_stack_hdf5(str(p))
    return load_stack(str(p))


def _corrcoef(a: np.ndarray, b: np.ndarray) -> float:
    ok = np.isfinite(a) & np.isfinite(b)
    if not np.any(ok):
        return float("nan")
    a0 = a[ok] - float(np.mean(a[ok]))
    b0 = b[ok] - float(np.mean(b[ok]))
    den = float(np.linalg.norm(a0) * np.linalg.norm(b0))
    return float(np.dot(a0, b0) / den) if den > 0 else float("nan")


def _rmse(a: np.ndarray, b: np.ndarray) -> float:
    ok = np.isfinite(a) & np.isfinite(b)
    if not np.any(ok):
        return float("nan")
    return float(np.sqrt(np.mean(np.square(a[ok] - b[ok]))))


def _land_retention(grid_in: np.ndarray, grid_out: np.ndarray, land_mask: np.ndarray) -> float:
    m = np.asarray(land_mask, dtype=bool)
    ok_in = m & np.isfinite(grid_in)
    ok_out = m & np.isfinite(grid_out)
    if not np.any(ok_in) or not np.any(ok_out):
        return float("nan")
    std_in = float(np.nanstd(grid_in[ok_in]))
    std_out = float(np.nanstd(grid_out[ok_out]))
    return std_out / std_in if std_in > 0 else float("nan")


def _plot_month_compare(
    out_png: Path,
    month: str,
    baseline: np.ndarray,
    baseline_label: str,
    experiment: np.ndarray,
    ddk4: np.ndarray,
    record: _ExperimentRecord,
) -> None:
    diff = experiment - ddk4
    vmax = float(np.nanpercentile(np.abs(np.concatenate([baseline.ravel(), experiment.ravel(), ddk4.ravel()])), 98))
    vmax = max(vmax, 1.0)
    vd = float(np.nanpercentile(np.abs(diff), 98))
    vd = max(vd, 1.0)

    fig, axes = plt.subplots(2, 2, figsize=(12, 7), dpi=150)
    panels = [
        (baseline, f"{baseline_label} | RMSE={record.baseline_rmse:.2f}", "turbo", -vmax, vmax),
        (experiment, f"{record.engine} | RMSE={record.rmse_vs_ddk4:.2f}", "turbo", -vmax, vmax),
        (ddk4, "DDK4", "turbo", -vmax, vmax),
        (diff, f"Experiment - DDK4 | Corr={record.corr_vs_ddk4:.4f}", "RdBu_r", -vd, vd),
    ]
    for ax, (grid, title, cmap, vmin, vmax_i) in zip(axes.ravel(), panels):
        im = ax.imshow(grid.T, origin="lower", cmap=cmap, vmin=vmin, vmax=vmax_i, aspect="auto")
        ax.set_title(title)
        ax.set_xlabel("Lon index")
        ax.set_ylabel("Lat index")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
    fig.suptitle(month)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def _plot_single_grid(out_png: Path, title: str, grid: np.ndarray, cmap: str = "viridis") -> None:
    vmax = float(np.nanpercentile(np.abs(grid), 98))
    vmax = max(vmax, 1.0)
    fig, ax = plt.subplots(figsize=(8, 4), dpi=150)
    if np.nanmin(grid) >= 0:
        im = ax.imshow(grid.T, origin="lower", cmap=cmap, aspect="auto")
    else:
        im = ax.imshow(grid.T, origin="lower", cmap=cmap, vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_title(title)
    ax.set_xlabel("Lon index")
    ax.set_ylabel("Lat index")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def _plot_order_scores(out_png: Path, title: str, scores: np.ndarray) -> None:
    arr = np.asarray(scores, dtype=float).ravel()
    fig, ax = plt.subplots(figsize=(8, 3), dpi=150)
    ax.plot(np.arange(arr.size), arr, color="#1f77b4", lw=1.5)
    ax.set_title(title)
    ax.set_xlabel("Order m")
    ax.set_ylabel("Normalized score")
    ax.set_ylim(0.0, max(1.0, float(np.nanmax(arr)) * 1.05 if arr.size else 1.0))
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def _plot_basis_diagnostics(out_png: Path, title: str, diagnostics: Dict[str, Any]) -> None:
    order_risk = np.asarray(diagnostics.get("order_risk", []), dtype=float).ravel()
    bundle_amp = np.asarray(diagnostics.get("bundle_order_amplitude", []), dtype=float).ravel()
    carrier_power = np.asarray(diagnostics.get("carrier_order_power", []), dtype=float).ravel()
    stripe_energy = np.asarray(diagnostics.get("stripe_order_energy", []), dtype=float).ravel()
    residual_energy = np.asarray(diagnostics.get("residual_order_energy", []), dtype=float).ravel()
    basis_preview = np.asarray(diagnostics.get("basis_preview", []), dtype=float)

    fig = plt.figure(figsize=(12, 8), dpi=150)
    gs = fig.add_gridspec(2, 2)
    ax0 = fig.add_subplot(gs[0, 0])
    ax1 = fig.add_subplot(gs[0, 1])
    ax2 = fig.add_subplot(gs[1, 0])
    ax3 = fig.add_subplot(gs[1, 1])

    x = np.arange(order_risk.size)
    if order_risk.size:
        ax0.plot(x, order_risk, lw=1.4, label="order risk")
    if bundle_amp.size:
        ax0.plot(np.arange(bundle_amp.size), bundle_amp, lw=1.2, label="bundle amp")
    if carrier_power.size:
        ax0.plot(np.arange(carrier_power.size), carrier_power, lw=1.2, label="carrier power")
    ax0.set_title("Monthly order diagnostics")
    ax0.set_xlabel("Order m")
    ax0.set_ylabel("Normalized amplitude")
    ax0.grid(True, alpha=0.25)
    ax0.legend(loc="upper right")

    if stripe_energy.size or residual_energy.size:
        ax1.bar(np.arange(stripe_energy.size), stripe_energy, width=0.7, alpha=0.75, label="stripe energy")
        if residual_energy.size:
            ax1.plot(np.arange(residual_energy.size), residual_energy, color="#d62728", lw=1.1, label="residual energy")
        ax1.set_title("Separated energy by order")
        ax1.set_xlabel("Order m")
        ax1.set_ylabel("Energy")
        ax1.grid(True, alpha=0.25)
        ax1.legend(loc="upper right")

    if basis_preview.ndim == 2 and basis_preview.size:
        vmax = float(np.nanpercentile(np.abs(basis_preview), 98))
        vmax = max(vmax, 1e-6)
        im = ax2.imshow(basis_preview, aspect="auto", cmap="RdBu_r", vmin=-vmax, vmax=vmax)
        ax2.set_title(f"Basis preview | order {diagnostics.get('basis_preview_order', 'n/a')}")
        ax2.set_xlabel("Basis column")
        ax2.set_ylabel("Degree offset")
        fig.colorbar(im, ax=ax2, fraction=0.046, pad=0.02)
    else:
        ax2.axis("off")

    ax3.axis("off")
    text = [
        f"basis_concentration={float(diagnostics.get('basis_concentration_score', float('nan'))):.4f}",
        f"stripe_energy_total={float(np.nansum(stripe_energy)):.4e}",
        f"residual_energy_total={float(np.nansum(residual_energy)):.4e}",
        f"risk_peak_m={int(np.nanargmax(order_risk)) if order_risk.size and np.any(np.isfinite(order_risk)) else 0}",
    ]
    ax3.text(0.02, 0.98, "\n".join(text), va="top", ha="left", family="monospace")

    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def _write_order_profile_csv(out_csv: Path, diagnostics: Dict[str, Any]) -> None:
    order_risk = np.asarray(diagnostics.get("order_risk", []), dtype=float).ravel()
    bundle_amp = np.asarray(diagnostics.get("bundle_order_amplitude", []), dtype=float).ravel()
    carrier_power = np.asarray(diagnostics.get("carrier_order_power", []), dtype=float).ravel()
    stripe_energy = np.asarray(diagnostics.get("stripe_order_energy", []), dtype=float).ravel()
    residual_energy = np.asarray(diagnostics.get("residual_order_energy", []), dtype=float).ravel()
    n = max(order_risk.size, bundle_amp.size, carrier_power.size, stripe_energy.size, residual_energy.size)
    with out_csv.open("w", encoding="utf-8") as handle:
        handle.write("order_m,order_risk,bundle_order_amplitude,carrier_order_power,stripe_order_energy,residual_order_energy\n")
        for idx in range(n):
            def _v(arr: np.ndarray) -> float:
                return float(arr[idx]) if idx < arr.size else float("nan")
            handle.write(
                f"{idx},{_v(order_risk):.10f},{_v(bundle_amp):.10f},{_v(carrier_power):.10f},"
                f"{_v(stripe_energy):.10e},{_v(residual_energy):.10e}\n"
            )


def _row_lowpass(grid: np.ndarray, lon_window: int = 21, lat_window: int = 5) -> np.ndarray:
    arr = np.asarray(grid, dtype=float)
    out = arr.copy()
    if lon_window > 1:
        kernel = np.ones(int(lon_window), dtype=float) / float(lon_window)
        for j in range(out.shape[1]):
            pad = int(lon_window // 2)
            row = np.pad(out[:, j], (pad, pad), mode="wrap")
            out[:, j] = np.convolve(row, kernel, mode="valid")
    if lat_window > 1:
        kernel = np.ones(int(lat_window), dtype=float) / float(lat_window)
        for i in range(out.shape[0]):
            pad = int(lat_window // 2)
            col = np.pad(out[i, :], (pad, pad), mode="edge")
            out[i, :] = np.convolve(col, kernel, mode="valid")
    return out


def _row_standardize(row: np.ndarray) -> np.ndarray:
    x = np.asarray(row, dtype=float).ravel()
    x = x - float(np.nanmean(x))
    s = float(np.nanstd(x))
    return x / s if s > 0 else np.zeros_like(x)


def _fit_weighted_ridge(design: np.ndarray, target: np.ndarray, weights: np.ndarray, ridge: float) -> np.ndarray:
    X = np.asarray(design, dtype=float)
    y = np.asarray(target, dtype=float).ravel()
    w = np.asarray(weights, dtype=float).ravel()
    ok = np.isfinite(y) & np.all(np.isfinite(X), axis=1) & np.isfinite(w) & (w > 0)
    if np.count_nonzero(ok) < max(8, X.shape[1] + 2):
        return np.zeros(X.shape[1], dtype=float)
    Xw = X[ok] * np.sqrt(w[ok])[:, None]
    yw = y[ok] * np.sqrt(w[ok])
    gram = Xw.T @ Xw + float(max(ridge, 1e-6)) * np.eye(X.shape[1], dtype=float)
    rhs = Xw.T @ yw
    try:
        return np.linalg.solve(gram, rhs)
    except np.linalg.LinAlgError:
        return np.linalg.lstsq(gram, rhs, rcond=None)[0]


def _safe_hilbert_real(x: np.ndarray) -> np.ndarray:
    arr = np.asarray(x, dtype=float).ravel()
    try:
        from scipy.signal import hilbert as _hilbert

        return np.imag(_hilbert(arr))
    except Exception:
        return np.zeros_like(arr)


def _bandpass_row(row: np.ndarray, center: float, width: float) -> np.ndarray:
    x = np.asarray(row, dtype=float).ravel()
    if x.size < 8:
        return np.zeros_like(x)
    x0 = x - float(np.nanmean(x))
    spec = np.fft.rfft(x0)
    freqs = np.fft.rfftfreq(x0.size, d=1.0)
    half_width = max(1.5 * float(width), 1.0 / max(8, x0.size))
    band = np.abs(freqs - float(center)) <= half_width
    if not np.any(band):
        band[int(np.argmin(np.abs(freqs - float(center))))] = True
    filt = np.zeros_like(spec)
    filt[band] = spec[band]
    return np.fft.irfft(filt, n=x0.size)


def _run_orbit_bundle_experiment(
    *,
    month: str,
    engine: str,
    input_grid: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    land_mask: np.ndarray,
    base_params: Dict[str, Any],
    orbit_cache_dir: Path,
) -> tuple[np.ndarray, Dict[str, Any], np.ndarray]:
    bundle = build_monthly_groundtrack_bundle(
        month=month,
        lon_vec=lon_vec,
        lat_vec=lat_vec,
        cache_dir=orbit_cache_dir,
        release="RL03",
    )
    band_info = estimate_stripe_band(input_grid, land_mask=land_mask)
    template = build_bundle_template_from_density(
        bundle.density,
        center=float(band_info["center"]),
        width=float(band_info["width"]),
        lat_smooth=int(base_params.get("template_lat_smooth_window", 5)),
        lon_smooth=int(base_params.get("template_lon_window", 9)),
    )
    background = _row_lowpass(
        input_grid,
        lon_window=int(base_params.get("carrier_lon_window", 21)),
        lat_window=int(base_params.get("carrier_lat_window", 5)),
    )
    residual = np.asarray(input_grid, dtype=float) - background
    out = residual.copy()
    ocean_mask = ~np.asarray(land_mask, dtype=bool)
    multichannel = engine == "orbit_bundle_multichannel_v1"
    for j in range(out.shape[1]):
        tpl = template[:, j].copy()
        if multichannel:
            idxs = range(max(0, j - 2), min(out.shape[1], j + 3))
            weights = []
            rows = []
            center_band = _bandpass_row(residual[:, j], band_info["center"], band_info["width"])
            for jj in idxs:
                cand = template[:, jj]
                den = float(np.linalg.norm(center_band) * np.linalg.norm(cand))
                corr = 0.0 if den <= 0 else float(np.dot(center_band, cand) / den)
                w = 1.0 if jj == j else max(0.0, abs(corr))
                if w <= 0:
                    continue
                weights.append(w)
                rows.append(cand)
            if rows:
                tpl = np.average(np.stack(rows, axis=1), axis=1, weights=np.asarray(weights))
        tpl = tpl - float(np.nanmean(tpl))
        tpl_std = float(np.nanstd(tpl))
        if tpl_std <= 0:
            continue
        tpl = tpl / tpl_std
        r_band = _bandpass_row(residual[:, j], band_info["center"], band_info["width"])
        weights = np.where(ocean_mask[:, j], 1.0, 0.20)
        denom = float(np.sum(weights * tpl * tpl))
        if denom <= 0:
            continue
        coeff = float(np.sum(weights * r_band * tpl) / denom)
        gain = min(0.85, max(0.0, abs(coeff)) / max(float(np.nanstd(r_band)), np.finfo(float).eps))
        out[:, j] = residual[:, j] - gain * coeff * tpl
    result = background + out
    info = {
        "type": "HSAF_orbit_bundle",
        "engine": engine,
        "stripe_band": {
            "center": float(band_info["center"]),
            "width": float(band_info["width"]),
        },
        "bundle_counts": int(bundle.counts),
        "bundle_archive": str(bundle.archive_path),
        "bundle_meta": dict(bundle.meta),
    }
    return result, info, template


def _run_orbit_phase_demod_experiment(
    *,
    month: str,
    engine: str,
    input_grid: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    land_mask: np.ndarray,
    base_params: Dict[str, Any],
    baseline_cfg: Dict[str, Any],
    orbit_cache_dir: Path,
) -> tuple[np.ndarray, Dict[str, Any], np.ndarray]:
    bundle = build_monthly_groundtrack_bundle(
        month=month,
        lon_vec=lon_vec,
        lat_vec=lat_vec,
        cache_dir=orbit_cache_dir,
        release="RL03",
    )
    band_info = estimate_stripe_band(input_grid, land_mask=land_mask)
    template = build_bundle_template_from_density(
        bundle.density,
        center=float(band_info["center"]),
        width=float(band_info["width"]),
        lat_smooth=int(base_params.get("template_lat_smooth_window", 5)),
        lon_smooth=int(base_params.get("template_lon_window", 9)),
    )
    phase_unit = build_bundle_phase_unit(template)
    background = _row_lowpass(
        input_grid,
        lon_window=int(base_params.get("carrier_lon_window", 21)),
        lat_window=int(base_params.get("carrier_lat_window", 5)),
    )
    residual = np.asarray(input_grid, dtype=float) - background
    band_component = np.zeros_like(residual)
    baseband = np.zeros_like(residual, dtype=complex)
    for j in range(residual.shape[1]):
        band_row = _bandpass_row(residual[:, j], band_info["center"], band_info["width"])
        band_component[:, j] = band_row
        analytic = band_row.astype(complex)
        try:
            from scipy.signal import hilbert as _hilbert

            analytic = _hilbert(band_row)
        except Exception:
            analytic = band_row.astype(complex)
        baseband[:, j] = analytic * np.conj(phase_unit[:, j])
    remainder = residual - band_component
    demod_cfg = {
        "engine": "multichannel_v3" if engine == "bundle_phase_demod_multichannel_v1" else str(baseline_cfg["engine"]),
        "params": dict(base_params),
    }
    bb_real_f, real_info = filter_grid_hsaf(
        np.real(baseband),
        lon_vec,
        lat_vec,
        demod_cfg,
    )
    bb_imag_f, imag_info = filter_grid_hsaf(
        np.imag(baseband),
        lon_vec,
        lat_vec,
        demod_cfg,
    )
    cleaned_band = np.real((np.asarray(bb_real_f, dtype=float) + 1j * np.asarray(bb_imag_f, dtype=float)) * phase_unit)
    result = background + remainder + cleaned_band
    info = {
        "type": "HSAF_orbit_phase_demod",
        "engine": engine,
        "stripe_band": {
            "center": float(band_info["center"]),
            "width": float(band_info["width"]),
        },
        "bundle_counts": int(bundle.counts),
        "bundle_archive": str(bundle.archive_path),
        "bundle_meta": dict(bundle.meta),
        "demod_engine": str(demod_cfg["engine"]),
        "real_info": real_info,
        "imag_info": imag_info,
    }
    return result, info, template


def _run_pseudo_moire_experiment(
    *,
    month: str,
    engine: str,
    input_grid: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    land_mask: np.ndarray,
    base_params: Dict[str, Any],
    cfg,
    sh_context: Dict[str, Any],
    input_tag: str,
    orbit_cache_dir: Path,
) -> tuple[np.ndarray, Dict[str, Any], np.ndarray]:
    C_in, S_in = _prepare_month_sh(cfg, sh_context, month, input_tag)
    carrier_grid, carrier_meta = _build_loworder_carrier_grid(
        C_in,
        S_in,
        int(cfg.inversion.Lmax),
        lon_vec,
        lat_vec,
        base_params,
    )
    bundle = build_monthly_groundtrack_bundle(
        month=month,
        lon_vec=lon_vec,
        lat_vec=lat_vec,
        cache_dir=orbit_cache_dir,
        release="RL03",
    )
    band_info = estimate_stripe_band(input_grid, land_mask=land_mask)
    template = build_bundle_template_from_density(
        bundle.density,
        center=float(band_info["center"]),
        width=float(band_info["width"]),
        lat_smooth=int(base_params.get("template_lat_smooth_window", 5)),
        lon_smooth=int(base_params.get("template_lon_window", 9)),
    )
    background = _row_lowpass(
        input_grid,
        lon_window=int(base_params.get("carrier_lon_window", 21)),
        lat_window=int(base_params.get("carrier_lat_window", 5)),
    )
    residual = np.asarray(input_grid, dtype=float) - background
    remainder = np.zeros_like(residual)
    band_component = np.zeros_like(residual)
    stripe_est = np.zeros_like(residual)
    ocean_mask = ~np.asarray(land_mask, dtype=bool)
    dlon_carrier = np.gradient(np.asarray(carrier_grid, dtype=float), axis=0)
    multichannel = engine == "pseudo_moire_operator_multichannel_v1"
    ridge = float(base_params.get("pseudo_moire_ridge", 0.12))
    base_gain = float(base_params.get("pseudo_moire_gain", 0.70))

    for j in range(residual.shape[1]):
        target = _bandpass_row(residual[:, j], band_info["center"], band_info["width"])
        band_component[:, j] = target
        remainder[:, j] = residual[:, j] - target
        idxs = range(max(0, j - 2), min(residual.shape[1], j + 3)) if multichannel else [j]
        tpl = np.mean(np.stack([template[:, jj] for jj in idxs], axis=1), axis=1)
        car = np.mean(np.stack([carrier_grid[:, jj] for jj in idxs], axis=1), axis=1)
        dcar = np.mean(np.stack([dlon_carrier[:, jj] for jj in idxs], axis=1), axis=1)
        basis0 = _row_standardize(tpl)
        basis1 = _row_standardize(car) * basis0
        basis2 = _row_standardize(dcar) * basis0
        design = np.column_stack([basis0, basis1, basis2])
        weights = np.where(ocean_mask[:, j], 1.0, 0.15)
        coef = _fit_weighted_ridge(design, target, weights, ridge)
        pred = design @ coef
        pred_std = float(np.nanstd(pred))
        tgt_std = float(np.nanstd(target))
        if pred_std > 0 and tgt_std > 0:
            gain = min(0.85, base_gain * np.clip(pred_std / tgt_std, 0.0, 1.5))
        else:
            gain = 0.0
        stripe_est[:, j] = gain * pred

    result = background + remainder + (band_component - stripe_est)
    info = {
        "type": "HSAF_pseudo_moire_operator",
        "engine": engine,
        "stripe_band": {
            "center": float(band_info["center"]),
            "width": float(band_info["width"]),
        },
        "bundle_counts": int(bundle.counts),
        "bundle_archive": str(bundle.archive_path),
        "bundle_meta": dict(bundle.meta),
        "carrier": carrier_meta,
        "multichannel": bool(multichannel),
    }
    return result, info, stripe_est


def _run_sampling_operator_experiment(
    *,
    month: str,
    engine: str,
    input_grid: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    land_mask: np.ndarray,
    base_params: Dict[str, Any],
    cfg,
    sh_context: Dict[str, Any],
    input_tag: str,
    orbit_cache_dir: Path,
) -> tuple[np.ndarray, Dict[str, Any], np.ndarray]:
    C_in, S_in = _prepare_month_sh(cfg, sh_context, month, input_tag)
    carrier_grid, carrier_meta = _build_loworder_carrier_grid(
        C_in,
        S_in,
        int(cfg.inversion.Lmax),
        lon_vec,
        lat_vec,
        base_params,
    )
    bundle = build_monthly_groundtrack_bundle(
        month=month,
        lon_vec=lon_vec,
        lat_vec=lat_vec,
        cache_dir=orbit_cache_dir,
        release="RL03",
    )
    band_info = estimate_stripe_band(input_grid, land_mask=land_mask)
    template = build_bundle_template_from_density(
        bundle.density,
        center=float(band_info["center"]),
        width=float(band_info["width"]),
        lat_smooth=int(base_params.get("template_lat_smooth_window", 5)),
        lon_smooth=int(base_params.get("template_lon_window", 9)),
    )
    background = _row_lowpass(
        input_grid,
        lon_window=int(base_params.get("carrier_lon_window", 21)),
        lat_window=int(base_params.get("carrier_lat_window", 5)),
    )
    residual = np.asarray(input_grid, dtype=float) - background
    dlon_carrier = np.gradient(np.asarray(carrier_grid, dtype=float), axis=0)
    ocean_mask = ~np.asarray(land_mask, dtype=bool)
    multichannel = engine == "sampling_operator_multichannel_v1"
    ridge = float(base_params.get("sampling_operator_ridge", 0.18))
    base_gain = float(base_params.get("sampling_operator_gain", 0.72))
    stripe_est = np.zeros_like(residual)
    band_component = np.zeros_like(residual)
    remainder = np.zeros_like(residual)

    for j in range(residual.shape[1]):
        target = _bandpass_row(residual[:, j], band_info["center"], band_info["width"])
        band_component[:, j] = target
        remainder[:, j] = residual[:, j] - target
        idxs = range(max(0, j - 2), min(residual.shape[1], j + 3)) if multichannel else [j]
        tpl = np.mean(np.stack([template[:, jj] for jj in idxs], axis=1), axis=1)
        quad = _safe_hilbert_real(tpl)
        car = np.mean(np.stack([carrier_grid[:, jj] for jj in idxs], axis=1), axis=1)
        dcar = np.mean(np.stack([dlon_carrier[:, jj] for jj in idxs], axis=1), axis=1)

        tpl0 = _row_standardize(tpl)
        tpl1 = _row_standardize(quad)
        car0 = _row_standardize(car)
        dcar0 = _row_standardize(dcar)
        design = np.column_stack(
            [
                tpl0,
                tpl1,
                car0 * tpl0,
                car0 * tpl1,
                dcar0 * tpl0,
                dcar0 * tpl1,
            ]
        )
        weights = np.where(ocean_mask[:, j], 1.0, 0.12)
        coef = _fit_weighted_ridge(design, target, weights, ridge)
        pred = design @ coef
        pred_std = float(np.nanstd(pred))
        tgt_std = float(np.nanstd(target))
        corr = _corrcoef(pred, target)
        if pred_std > 0 and tgt_std > 0 and np.isfinite(corr):
            gain = min(0.90, base_gain * max(0.0, corr) * np.clip(pred_std / tgt_std, 0.0, 1.5))
        else:
            gain = 0.0
        stripe_est[:, j] = gain * pred

    result = background + remainder + (band_component - stripe_est)
    info = {
        "type": "HSAF_sampling_operator_proxy",
        "engine": engine,
        "stripe_band": {
            "center": float(band_info["center"]),
            "width": float(band_info["width"]),
        },
        "bundle_counts": int(bundle.counts),
        "bundle_archive": str(bundle.archive_path),
        "bundle_meta": dict(bundle.meta),
        "carrier": carrier_meta,
        "multichannel": bool(multichannel),
    }
    return result, info, stripe_est


def _build_sh_orbit_params(
    *,
    month: str,
    input_grid: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    land_mask: np.ndarray,
    base_params: Dict[str, Any],
    lmax: int,
    orbit_cache_dir: Path,
) -> tuple[Dict[str, Any], np.ndarray, Dict[str, Any]]:
    bundle = build_monthly_groundtrack_bundle(
        month=month,
        lon_vec=lon_vec,
        lat_vec=lat_vec,
        cache_dir=orbit_cache_dir,
        release="RL03",
    )
    band_info = estimate_stripe_band(input_grid, land_mask=land_mask)
    template = build_bundle_template_from_density(
        bundle.density,
        center=float(band_info["center"]),
        width=float(band_info["width"]),
        lat_smooth=int(base_params.get("template_lat_smooth_window", 5)),
        lon_smooth=int(base_params.get("template_lon_window", 9)),
    )
    order_scores = build_bundle_order_scores(
        template,
        lmax=int(lmax),
        smooth_window=int(base_params.get("orbit_order_smooth_window", 5)),
        m_start=int(base_params.get("m_start", 6)),
    )
    params = dict(base_params)
    params["orbit_order_scores"] = order_scores.tolist()
    info = {
        "stripe_band": {
            "center": float(band_info["center"]),
            "width": float(band_info["width"]),
        },
        "bundle_counts": int(bundle.counts),
        "bundle_archive": str(bundle.archive_path),
        "bundle_meta": dict(bundle.meta),
        "order_score_peak_m": int(np.nanargmax(order_scores)) if order_scores.size else 0,
    }
    return params, template, info


def _run_sampling_inversion_experiment(
    *,
    month: str,
    engine: str,
    cfg,
    sh_context: Dict[str, Any],
    input_tag: str,
    input_grid: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    land_mask: np.ndarray,
    base_params: Dict[str, Any],
    orbit_cache_dir: Path,
) -> tuple[np.ndarray, Dict[str, Any], np.ndarray, np.ndarray]:
    C_in, S_in = _prepare_month_sh(cfg, sh_context, month, input_tag)
    sh_params, template_grid, orbit_info = _build_sh_orbit_params(
        month=month,
        input_grid=input_grid,
        lon_vec=lon_vec,
        lat_vec=lat_vec,
        land_mask=land_mask,
        base_params=base_params,
        lmax=int(cfg.inversion.Lmax),
        orbit_cache_dir=orbit_cache_dir,
    )
    C_out, S_out, inv_info = apply_sampling_aware_inversion(
        C_in,
        S_in,
        int(cfg.inversion.Lmax),
        {"engine": engine, "params": sh_params},
    )
    result = ewh_synthesis(
        C_out,
        S_out,
        int(cfg.inversion.Lmax),
        lon_vec,
        lat_vec,
    )
    return result, {
        "type": "sampling_aware_inversion_experiment",
        "engine": engine,
        "orbit_bundle": orbit_info,
        "inversion_info": inv_info,
    }, template_grid, np.asarray(sh_params["orbit_order_scores"], dtype=float)


def _run_sampling_pseudomoire_experiment(
    *,
    month: str,
    engine: str,
    cfg,
    sh_context: Dict[str, Any],
    input_tag: str,
    input_grid: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    land_mask: np.ndarray,
    base_params: Dict[str, Any],
    orbit_cache_dir: Path,
) -> tuple[np.ndarray, Dict[str, Any], np.ndarray, np.ndarray, Dict[str, Any]]:
    del input_grid, land_mask  # The prototype works in SH space before map synthesis.
    C_in, S_in = _prepare_month_sh(cfg, sh_context, month, input_tag)
    bundle = build_monthly_groundtrack_bundle(
        month=month,
        lon_vec=lon_vec,
        lat_vec=lat_vec,
        cache_dir=orbit_cache_dir,
        release="RL03",
    )
    bundle_source = "RL03-monthly"
    if int(bundle.counts) <= 0:
        bundle = build_monthly_groundtrack_bundle_rl02_sampled(
            month=month,
            lon_vec=lon_vec,
            lat_vec=lat_vec,
            cache_dir=orbit_cache_dir,
            sample_days=int(base_params.get("sampling_pseudomoire_rl02_sample_days", 3)),
        )
        bundle_source = "RL02-sampled"
    operator = PseudoMoireOperator(
        lmax=int(cfg.inversion.Lmax),
        carrier_lmax=int(base_params.get("carrier_lmax", 20)),
        carrier_mmax=int(base_params.get("carrier_mmax", 10)),
        m_start=int(base_params.get("sampling_pseudomoire_m_start", 4)),
        lambda_stripe=float(base_params.get("sampling_pseudomoire_lambda_stripe", 0.35)),
        lambda_signal=float(base_params.get("sampling_pseudomoire_lambda_signal", 0.08)),
        high_risk_orders=base_params.get("sampling_pseudomoire_orders", [4, 8, 12]),
        risk_scale=float(base_params.get("sampling_pseudomoire_risk_scale", 1.6)),
        min_risk_threshold=float(base_params.get("sampling_pseudomoire_min_risk", 0.10)),
    )
    operator.fit(
        bundle.density,
        C_in,
        S_in,
        lat_vec,
        lon_vec,
    )
    C_sig, S_sig, C_str, S_str, C_rem, S_rem = operator.separate(C_in, S_in)
    result = ewh_synthesis(C_sig, S_sig, int(cfg.inversion.Lmax), lon_vec, lat_vec)
    stripe_grid = ewh_synthesis(C_str, S_str, int(cfg.inversion.Lmax), lon_vec, lat_vec)
    residual_grid = ewh_synthesis(C_rem, S_rem, int(cfg.inversion.Lmax), lon_vec, lat_vec)
    diag = operator.diagnostics()
    risk_profile = np.asarray(diag.order_risk, dtype=float)
    target_orders = [m for m in base_params.get("sampling_pseudomoire_orders", [4, 8, 12]) if 0 <= int(m) <= int(cfg.inversion.Lmax)]
    if target_orders and max(float(risk_profile[int(m)]) for m in target_orders) > 0:
        preview_order = int(max(target_orders, key=lambda m: risk_profile[int(m)]))
    else:
        preview_order = int(np.nanargmax(risk_profile)) if risk_profile.size and np.any(np.isfinite(risk_profile)) else 0
    basis_preview = operator.build_basis(preview_order, "cos")
    diag_payload = {
        "order_risk": diag.order_risk.tolist(),
        "bundle_order_amplitude": diag.bundle_order_amplitude.tolist(),
        "carrier_order_power": diag.carrier_order_power.tolist(),
        "stripe_order_energy": diag.stripe_order_energy.tolist(),
        "residual_order_energy": diag.residual_order_energy.tolist(),
        "basis_concentration_score": float(diag.basis_concentration_score),
        "basis_preview_order": int(preview_order),
        "basis_preview": basis_preview.tolist(),
    }
    info = {
        "type": "sampling_pseudomoire_operator",
        "engine": engine,
        "bundle_counts": int(bundle.counts),
        "bundle_archive": str(bundle.archive_path),
        "bundle_meta": dict(bundle.meta),
        "bundle_source": bundle_source,
        "operator": {
            "carrier_lmax": int(operator.carrier_lmax),
            "carrier_mmax": int(operator.carrier_mmax),
            "m_start": int(operator.m_start),
            "lambda_stripe": float(operator.lambda_stripe),
            "lambda_signal": float(operator.lambda_signal),
            "high_risk_orders": list(operator.high_risk_orders),
            "risk_scale": float(operator.risk_scale),
            "min_risk_threshold": float(operator.min_risk_threshold),
        },
        "basis_diagnostics": {
            "basis_concentration_score": float(diag.basis_concentration_score),
            "preview_order": int(preview_order),
            "stripe_energy_total": float(np.sum(diag.stripe_order_energy)),
            "residual_energy_total": float(np.sum(diag.residual_order_energy)),
        },
    }
    return result, info, stripe_grid, risk_profile, diag_payload


def _run_adaptive_parity_hsaf_experiment(
    *,
    month: str,
    engine: str,
    cfg,
    sh_context,
    input_tag: str,
    lon_vec,
    lat_vec,
    base_params,
    orbit_cache_dir,
):
    """Phase B: month-adaptive parity HSA experiment in SH degree sequences."""

    c_in, s_in = _prepare_month_sh(cfg, sh_context, month, input_tag)
    lmax = int(cfg.inversion.Lmax)

    bundle = build_monthly_groundtrack_bundle(
        month=month,
        lon_vec=lon_vec,
        lat_vec=lat_vec,
        cache_dir=orbit_cache_dir,
        release="RL03",
    )
    bundle_source = "RL03-monthly"
    if int(bundle.counts) <= 0:
        bundle = build_monthly_groundtrack_bundle_rl02_sampled(
            month=month,
            lon_vec=lon_vec,
            lat_vec=lat_vec,
            cache_dir=orbit_cache_dir,
            sample_days=int(base_params.get("sampling_pseudomoire_rl02_sample_days", 3)),
        )
        bundle_source = "RL02-sampled"

    operator = AdaptiveParityHSAF(
        lmax=lmax,
        m_start=int(base_params.get("aphsaf_m_start", 4)),
        window_frac=float(base_params.get("aphsaf_window_frac", 0.45)),
        max_window=int(base_params.get("aphsaf_max_window", 48)),
        n_modes=int(base_params.get("aphsaf_n_modes", 0)),
        f_split=float(base_params.get("aphsaf_f_split", 0.30)),
        f_width=float(base_params.get("aphsaf_f_width", 0.08)),
        risk_gain=float(base_params.get("aphsaf_risk_gain", 1.0)),
        min_risk=float(base_params.get("aphsaf_min_risk", 0.08)),
        risk_smooth_window=int(base_params.get("aphsaf_risk_smooth", 5)),
    )
    operator.fit(bundle.density, bundle.lat)

    c_sig, s_sig, c_str, s_str = operator.separate(c_in, s_in)
    result = ewh_synthesis(c_sig, s_sig, lmax, lon_vec, lat_vec)
    stripe_grid = ewh_synthesis(c_str, s_str, lmax, lon_vec, lat_vec)

    diag = operator.diagnostics()
    risk_profile = np.asarray(diag.order_risk, dtype=float)
    basis_diag = {
        "order_risk": diag.order_risk.tolist(),
        "bundle_order_amplitude": diag.order_risk.tolist(),
        "carrier_order_power": np.zeros_like(diag.order_risk, dtype=float).tolist(),
        "stripe_order_energy": diag.stripe_order_energy.tolist(),
        "residual_order_energy": diag.signal_order_energy.tolist(),
        "basis_concentration_score": float(diag.basis_concentration_score),
        "basis_preview_order": int(np.nanargmax(risk_profile)) if risk_profile.size and np.any(np.isfinite(risk_profile)) else 0,
        "basis_preview": [],
    }
    info = {
        "type": "adaptive_parity_hsaf",
        "engine": engine,
        "bundle_counts": int(bundle.counts),
        "bundle_archive": str(bundle.archive_path),
        "bundle_source": bundle_source,
        "bundle_meta": dict(bundle.meta),
        "operator_params": {
            "lmax": lmax,
            "m_start": int(operator.m_start),
            "window_frac": float(operator.window_frac),
            "max_window": int(operator.max_window),
            "n_modes": int(operator.n_modes),
            "f_split": float(operator.f_split),
            "f_width": float(operator.f_width),
            "risk_gain": float(operator.risk_gain),
            "min_risk": float(operator.min_risk),
            "risk_smooth_window": int(operator.risk_smooth_window),
        },
        "basis_diagnostics": {
            "basis_concentration_score": float(diag.basis_concentration_score),
            "stripe_energy_total": float(np.sum(diag.stripe_order_energy)),
            "signal_energy_total": float(np.sum(diag.signal_order_energy)),
        },
    }
    return result, info, stripe_grid, risk_profile, basis_diag


def _plot_summary(out_png: Path, records: Sequence[_ExperimentRecord]) -> None:
    if not records:
        return
    months = sorted({r.month for r in records})
    engines = list(dict.fromkeys(r.engine for r in records))
    x = np.arange(len(months))
    width = 0.8 / max(1, len(engines))

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), dpi=150)
    for idx, engine in enumerate(engines):
        rows = [r for r in records if r.engine == engine]
        rmse = [next((r.rmse_vs_ddk4 for r in rows if r.month == m), np.nan) for m in months]
        improve = [
            next(
                ((r.baseline_anisotropy - r.ocean_anisotropy) / max(r.baseline_anisotropy, np.finfo(float).eps) for r in rows if r.month == m),
                np.nan,
            )
            for m in months
        ]
        axes[0].bar(x + idx * width - 0.4 + width / 2, rmse, width=width, label=engine)
        axes[1].bar(x + idx * width - 0.4 + width / 2, improve, width=width, label=engine)
    axes[0].set_title("RMSE vs DDK4")
    axes[0].set_ylabel("mm")
    axes[1].set_title("Ocean anisotropy improvement vs current HSAF")
    axes[1].set_ylabel("relative improvement")
    axes[1].axhline(0.20, color="k", lw=0.8, ls="--")
    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(months, rotation=20, ha="right")
        ax.grid(alpha=0.25, ls="--")
        ax.legend()
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def _write_gate_summary(out_txt: Path, records: Sequence[_ExperimentRecord]) -> None:
    by_engine: Dict[str, List[_ExperimentRecord]] = {}
    for record in records:
        by_engine.setdefault(record.engine, []).append(record)

    def _count_improved(rows: Sequence[_ExperimentRecord], threshold: float) -> int:
        n = 0
        for row in rows:
            base = max(row.baseline_anisotropy, np.finfo(float).eps)
            improvement = (row.baseline_anisotropy - row.ocean_anisotropy) / base
            if improvement >= threshold:
                n += 1
        return n

    with out_txt.open("w", encoding="utf-8") as handle:
        for engine, rows in by_engine.items():
            rows = sorted(rows, key=lambda r: r.month)
            handle.write(f"[{engine}]\n")
            handle.write(f"months={', '.join(r.month for r in rows)}\n")
            handle.write(f"anisotropy_improved_20pct={_count_improved(rows, 0.20)}/{len(rows)}\n")
            bad_rows = [r for r in rows if r.month in {"2002-04", "2015-09", "2017-03"}]
            visibly_good = sum(
                1
                for r in bad_rows
                if (r.baseline_anisotropy - r.ocean_anisotropy) / max(r.baseline_anisotropy, np.finfo(float).eps) >= 0.20
            )
            handle.write(f"bad_months_improved_20pct={visibly_good}/{len(bad_rows)}\n")
            extra_loss = []
            for r in rows:
                if np.isfinite(r.baseline_land_retention) and np.isfinite(r.land_retention) and r.baseline_land_retention > 0:
                    extra_loss.append(max(0.0, (r.baseline_land_retention - r.land_retention) / r.baseline_land_retention))
            handle.write(
                f"max_extra_land_retention_loss={max(extra_loss) if extra_loss else float('nan'):.4f}\n"
            )
            if any(np.isfinite(r.basis_concentration) for r in rows):
                vals = [r.basis_concentration for r in rows if np.isfinite(r.basis_concentration)]
                handle.write(f"avg_basis_concentration={float(np.mean(vals)):.4f}\n")
            handle.write("\n")

        if "modal_adaptive_v1" in by_engine and "modal_adaptive_latband_v1" in by_engine:
            handle.write("[latband_vs_v1]\n")
            v1 = {r.month: r for r in by_engine["modal_adaptive_v1"]}
            latband = {r.month: r for r in by_engine["modal_adaptive_latband_v1"]}
            target = ["2002-04", "2015-09", "2017-03"]
            improved = 0
            for month in target:
                if month in v1 and month in latband:
                    base = max(v1[month].ocean_anisotropy, np.finfo(float).eps)
                    gain = (v1[month].ocean_anisotropy - latband[month].ocean_anisotropy) / base
                    if gain >= 0.10:
                        improved += 1
            handle.write(f"bad_months_extra_10pct={improved}/3\n")
            if "2007-05" in v1 and "2007-05" in latband:
                row_v1 = v1["2007-05"]
                row_lb = latband["2007-05"]
                base = max(row_v1.rmse_vs_ddk4, np.finfo(float).eps)
                degrade = (row_lb.rmse_vs_ddk4 - row_v1.rmse_vs_ddk4) / base
                handle.write(f"good_month_rmse_degrade={degrade:.4f}\n")
            handle.write("\n")

        if "multichannel_v1" in by_engine and "modal_adaptive_latband_v1" in by_engine:
            handle.write("[multichannel_vs_latband]\n")
            mc = {r.month: r for r in by_engine["multichannel_v1"]}
            lb = {r.month: r for r in by_engine["modal_adaptive_latband_v1"]}
            target = ["2002-04", "2015-09", "2017-03"]
            improved = 0
            runtime_ok = True
            for month in target:
                if month in mc and month in lb:
                    base = max(lb[month].ocean_anisotropy, np.finfo(float).eps)
                    gain = (lb[month].ocean_anisotropy - mc[month].ocean_anisotropy) / base
                    if gain > 0:
                        improved += 1
                    if mc[month].elapsed_s > 3.0 * lb[month].elapsed_s:
                        runtime_ok = False
            handle.write(f"bad_months_better_than_latband={improved}/3\n")
            handle.write(f"runtime_within_3x={runtime_ok}\n")

        if "sampling_pseudomoire_v1" in by_engine:
            handle.write("[sampling_pseudomoire_phase_a]\n")
            rows = {r.month: r for r in by_engine["sampling_pseudomoire_v1"]}
            target = ["2002-04", "2015-09", "2017-03"]
            improved = 0
            concentration_ok = 0
            max_loss = 0.0
            for month in target:
                row = rows.get(month)
                if row is None:
                    continue
                base = max(row.baseline_anisotropy, np.finfo(float).eps)
                gain = (row.baseline_anisotropy - row.ocean_anisotropy) / base
                if gain >= 0.15:
                    improved += 1
                if np.isfinite(row.baseline_land_retention) and np.isfinite(row.land_retention) and row.baseline_land_retention > 0:
                    max_loss = max(max_loss, max(0.0, (row.baseline_land_retention - row.land_retention) / row.baseline_land_retention))
                if np.isfinite(row.basis_concentration) and row.basis_concentration >= 0.35:
                    concentration_ok += 1
            handle.write(f"severe_months_anisotropy_improved_15pct={improved}/3\n")
            handle.write(f"basis_concentration_ge_0.35={concentration_ok}/3\n")
            handle.write(f"max_extra_land_retention_loss={max_loss:.4f}\n")

        if "adaptive_parity_hsaf_v1" in by_engine:
            handle.write("[adaptive_parity_hsaf_phase_b]\n")
            rows = {r.month: r for r in by_engine["adaptive_parity_hsaf_v1"]}
            severe = ["2002-04", "2015-09", "2017-03"]
            aniso_improved = 0
            rmse_improved = 0
            max_collapse = 0.0
            land_ok = True

            for month in severe:
                row = rows.get(month)
                if row is None:
                    continue
                base_a = max(row.baseline_anisotropy, np.finfo(float).eps)
                if (row.baseline_anisotropy - row.ocean_anisotropy) / base_a >= 0.15:
                    aniso_improved += 1
                base_r = max(row.baseline_rmse, np.finfo(float).eps)
                max_collapse = max(max_collapse, row.rmse_vs_ddk4 / base_r)

            for row in rows.values():
                if row.rmse_vs_ddk4 < row.baseline_rmse:
                    rmse_improved += 1

            if "2007-05" in rows:
                row = rows["2007-05"]
                if (
                    np.isfinite(row.land_retention)
                    and np.isfinite(row.baseline_land_retention)
                    and row.baseline_land_retention > 0
                ):
                    if row.land_retention / row.baseline_land_retention < 0.85:
                        land_ok = False

            passed = (
                aniso_improved >= 1
                and rmse_improved >= 1
                and max_collapse <= 1.5
                and land_ok
            )
            handle.write(f"severe_months_anisotropy_improved_15pct={aniso_improved}/3\n")
            handle.write(f"months_rmse_better_than_hsaf={rmse_improved}/{len(rows)}\n")
            handle.write(f"max_rmse_collapse_ratio={max_collapse:.3f}\n")
            handle.write(f"good_month_land_retention_ok={land_ok}\n")
            handle.write(f"phase_b_gate_passed={passed}\n")
            handle.write("\n")


def run_hsaf_experiments(
    *,
    cfg,
    stack_dir: Path,
    outdir: Optional[Path] = None,
    months: Optional[Iterable[str]] = None,
    engines: Optional[Iterable[str]] = None,
    input_tag: str = "P4M6",
) -> Path:
    months = list(months or DEFAULT_EXPERIMENT_MONTHS)
    engines = list(engines or DEFAULT_ENGINES)
    input_tag = str(input_tag or "P4M6").strip().upper()
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    if outdir is None:
        outdir = Path(cfg.path.OUTPUT) / "local" / "compare" / "hsaf_experiments" / run_id
    outdir.mkdir(parents=True, exist_ok=True)

    input_stack = _load_stack_auto(stack_dir, input_tag)
    ddk4 = _load_stack_auto(stack_dir, "DDK4")
    hsaf = _load_stack_auto(stack_dir, "HSAF") if input_tag == "P4M6" else None
    if input_stack.ewh.shape[:2] != ddk4.ewh.shape[:2]:
        raise ValueError(f"{input_tag}/DDK4 stack shapes do not match.")
    if hsaf is not None and input_stack.ewh.shape[:2] != hsaf.ewh.shape[:2]:
        raise ValueError(f"{input_tag}/HSAF stack shapes do not match.")

    month_to_idx = {str(m): i for i, m in enumerate(input_stack.t)}
    selected = [m for m in months if m in month_to_idx]
    if not selected:
        raise ValueError(f"None of the requested months were found in the {input_tag} stack.")
    sh_context = (
        _prepare_monthly_sh_context(cfg, selected)
        if any(
            engine in ADAPTIVE_PARITY_ENGINES
            or engine in SAMPLING_PSEUDOMOIRE_ENGINES
            or engine in SH_DOMAIN_ENGINES
            or engine in HYBRID_ENGINES
            or engine in SH_CARRIER_ORBIT_ENGINES
            or engine in PSEUDOMOIRE_ENGINES
            or engine in SAMPLING_OPERATOR_ENGINES
            or engine in SAMPLING_INVERSION_ENGINES
            for engine in engines
        )
        else None
    )
    orbit_cache_dir = Path(cfg.path.OUTPUT) / "local" / "tmp" / "grace_l1b"

    land_mask, _ = build_global_land_mask(
        np.asarray(input_stack.lon, dtype=float),
        np.asarray(input_stack.lat, dtype=float),
        root_dir=cfg.path.ROOT,
    )

    base_params = dict(getattr(cfg.filter.hankel, "params", {}) or {})
    base_params["land_mask"] = np.asarray(land_mask, dtype=bool)
    records: List[_ExperimentRecord] = []
    baseline_cfg = {
        "engine": str(getattr(cfg.filter.hankel, "engine", "matlab_v3") or "matlab_v3"),
        "params": dict(base_params),
    }
    baseline_cache: Dict[str, np.ndarray] = {}
    baseline_label = "Current HSAF" if hsaf is not None else f"Baseline HSAF ({input_tag})"

    for engine in engines:
        engine_dir = outdir / engine
        engine_dir.mkdir(parents=True, exist_ok=True)
        for month in selected:
            idx = month_to_idx[month]
            input_grid = np.asarray(input_stack.ewh[:, :, idx], dtype=float)
            if hsaf is not None:
                baseline_grid = np.asarray(hsaf.ewh[:, :, idx], dtype=float)
            else:
                if month not in baseline_cache:
                    baseline_cache[month], _ = filter_grid_hsaf(
                        input_grid,
                        np.asarray(input_stack.lon, dtype=float),
                        np.asarray(input_stack.lat, dtype=float),
                        baseline_cfg,
                    )
                baseline_grid = baseline_cache[month]
            ddk4_grid = np.asarray(ddk4.ewh[:, :, idx], dtype=float)

            cfg_dict = {
                "engine": engine,
                "params": dict(base_params),
            }
            started = time.perf_counter()
            template_grid = None
            order_scores = None
            basis_diag = None
            if engine in ADAPTIVE_PARITY_ENGINES:
                if sh_context is None:
                    raise RuntimeError("Adaptive parity HSAF experiment requires SH context.")
                exp_grid, info, template_grid, order_scores, basis_diag = _run_adaptive_parity_hsaf_experiment(
                    month=month,
                    engine=engine,
                    cfg=cfg,
                    sh_context=sh_context,
                    input_tag=input_tag,
                    lon_vec=np.asarray(input_stack.lon, dtype=float),
                    lat_vec=np.asarray(input_stack.lat, dtype=float),
                    base_params=base_params,
                    orbit_cache_dir=orbit_cache_dir,
                )
            elif engine in SAMPLING_PSEUDOMOIRE_ENGINES:
                if sh_context is None:
                    raise RuntimeError("Sampling pseudo-moire experiment context was not initialized.")
                exp_grid, info, template_grid, order_scores, basis_diag = _run_sampling_pseudomoire_experiment(
                    month=month,
                    engine=engine,
                    cfg=cfg,
                    sh_context=sh_context,
                    input_tag=input_tag,
                    input_grid=input_grid,
                    lon_vec=np.asarray(input_stack.lon, dtype=float),
                    lat_vec=np.asarray(input_stack.lat, dtype=float),
                    land_mask=np.asarray(land_mask, dtype=bool),
                    base_params=base_params,
                    orbit_cache_dir=orbit_cache_dir,
                )
            elif engine in SAMPLING_INVERSION_ENGINES:
                if sh_context is None:
                    raise RuntimeError("Sampling-aware inversion experiment context was not initialized.")
                exp_grid, info, template_grid, order_scores = _run_sampling_inversion_experiment(
                    month=month,
                    engine=engine,
                    cfg=cfg,
                    sh_context=sh_context,
                    input_tag=input_tag,
                    input_grid=input_grid,
                    lon_vec=np.asarray(input_stack.lon, dtype=float),
                    lat_vec=np.asarray(input_stack.lat, dtype=float),
                    land_mask=np.asarray(land_mask, dtype=bool),
                    base_params=base_params,
                    orbit_cache_dir=orbit_cache_dir,
                )
            elif engine in SH_CARRIER_ORBIT_ENGINES:
                if sh_context is None:
                    raise RuntimeError("SH-domain experiment context was not initialized.")
                exp_grid, info, template_grid, order_scores = _run_sh_carrier_orbit_experiment(
                    engine=engine,
                    cfg=cfg,
                    sh_context=sh_context,
                    month=month,
                    input_tag=input_tag,
                    input_grid=input_grid,
                    lon_vec=np.asarray(input_stack.lon, dtype=float),
                    lat_vec=np.asarray(input_stack.lat, dtype=float),
                    land_mask=np.asarray(land_mask, dtype=bool),
                    base_params=base_params,
                    orbit_cache_dir=orbit_cache_dir,
                )
            elif engine in SH_DOMAIN_ENGINES:
                if sh_context is None:
                    raise RuntimeError("SH-domain experiment context was not initialized.")
                orbit_info = None
                if engine in SH_ORBIT_ENGINES:
                    sh_params, template_grid, orbit_info = _build_sh_orbit_params(
                        month=month,
                        input_grid=input_grid,
                        lon_vec=np.asarray(input_stack.lon, dtype=float),
                        lat_vec=np.asarray(input_stack.lat, dtype=float),
                        land_mask=np.asarray(land_mask, dtype=bool),
                        base_params=base_params,
                        lmax=int(cfg.inversion.Lmax),
                        orbit_cache_dir=orbit_cache_dir,
                    )
                    cfg_dict["params"] = sh_params
                    order_scores = np.asarray(sh_params["orbit_order_scores"], dtype=float)
                C_in, S_in = _prepare_month_sh(cfg, sh_context, month, input_tag)
                C_exp, S_exp, info = filter_sh_hsaf(
                    C_in,
                    S_in,
                    int(cfg.inversion.Lmax),
                    cfg_dict,
                )
                if orbit_info is not None:
                    info = dict(info)
                    info["orbit_bundle"] = orbit_info
                exp_grid = ewh_synthesis(
                    C_exp,
                    S_exp,
                    int(cfg.inversion.Lmax),
                    np.asarray(input_stack.lon, dtype=float),
                    np.asarray(input_stack.lat, dtype=float),
                )
            elif engine in HYBRID_ENGINES:
                if sh_context is None:
                    raise RuntimeError("Hybrid SH/grid experiment context was not initialized.")
                exp_grid, info = _run_hybrid_experiment(
                    engine=engine,
                    input_grid=input_grid,
                    lon_vec=np.asarray(input_stack.lon, dtype=float),
                    lat_vec=np.asarray(input_stack.lat, dtype=float),
                    base_params=base_params,
                    baseline_cfg=baseline_cfg,
                    cfg=cfg,
                    sh_context=sh_context,
                    month=month,
                    input_tag=input_tag,
                )
            elif engine in ORBIT_ENGINES:
                exp_grid, info, template_grid = _run_orbit_bundle_experiment(
                    month=month,
                    engine=engine,
                    input_grid=input_grid,
                    lon_vec=np.asarray(input_stack.lon, dtype=float),
                    lat_vec=np.asarray(input_stack.lat, dtype=float),
                    land_mask=np.asarray(land_mask, dtype=bool),
                    base_params=base_params,
                    orbit_cache_dir=orbit_cache_dir,
                )
            elif engine in ORBIT_PHASE_ENGINES:
                exp_grid, info, template_grid = _run_orbit_phase_demod_experiment(
                    month=month,
                    engine=engine,
                    input_grid=input_grid,
                    lon_vec=np.asarray(input_stack.lon, dtype=float),
                    lat_vec=np.asarray(input_stack.lat, dtype=float),
                    land_mask=np.asarray(land_mask, dtype=bool),
                    base_params=base_params,
                    baseline_cfg=baseline_cfg,
                    orbit_cache_dir=orbit_cache_dir,
                )
            elif engine in PSEUDOMOIRE_ENGINES:
                if sh_context is None:
                    raise RuntimeError("Pseudo-moire experiment context was not initialized.")
                exp_grid, info, template_grid = _run_pseudo_moire_experiment(
                    month=month,
                    engine=engine,
                    input_grid=input_grid,
                    lon_vec=np.asarray(input_stack.lon, dtype=float),
                    lat_vec=np.asarray(input_stack.lat, dtype=float),
                    land_mask=np.asarray(land_mask, dtype=bool),
                    base_params=base_params,
                    cfg=cfg,
                    sh_context=sh_context,
                    input_tag=input_tag,
                    orbit_cache_dir=orbit_cache_dir,
                )
            elif engine in SAMPLING_OPERATOR_ENGINES:
                if sh_context is None:
                    raise RuntimeError("Sampling-operator experiment context was not initialized.")
                exp_grid, info, template_grid = _run_sampling_operator_experiment(
                    month=month,
                    engine=engine,
                    input_grid=input_grid,
                    lon_vec=np.asarray(input_stack.lon, dtype=float),
                    lat_vec=np.asarray(input_stack.lat, dtype=float),
                    land_mask=np.asarray(land_mask, dtype=bool),
                    base_params=base_params,
                    cfg=cfg,
                    sh_context=sh_context,
                    input_tag=input_tag,
                    orbit_cache_dir=orbit_cache_dir,
                )
            else:
                exp_grid, info = filter_grid_hsaf(
                    input_grid,
                    np.asarray(input_stack.lon, dtype=float),
                    np.asarray(input_stack.lat, dtype=float),
                    cfg_dict,
                )
            elapsed = time.perf_counter() - started

            exp_metrics = compute_stripe_metrics(exp_grid, land_mask=land_mask)
            baseline_metrics = compute_stripe_metrics(baseline_grid, land_mask=land_mask)
            record = _ExperimentRecord(
                engine=engine,
                month=month,
                elapsed_s=float(elapsed),
                rmse_vs_ddk4=_rmse(exp_grid, ddk4_grid),
                corr_vs_ddk4=_corrcoef(exp_grid, ddk4_grid),
                ocean_anisotropy=float(exp_metrics["ocean_anisotropy_index"]),
                ocean_band_energy=float(exp_metrics["ocean_stripe_band_energy"]),
                land_retention=_land_retention(input_grid, exp_grid, land_mask),
                baseline_rmse=_rmse(baseline_grid, ddk4_grid),
                baseline_corr=_corrcoef(baseline_grid, ddk4_grid),
                baseline_anisotropy=float(baseline_metrics["ocean_anisotropy_index"]),
                baseline_band_energy=float(baseline_metrics["ocean_stripe_band_energy"]),
                baseline_land_retention=_land_retention(input_grid, baseline_grid, land_mask),
                basis_concentration=float(basis_diag.get("basis_concentration_score", float("nan"))) if basis_diag else float("nan"),
            )
            records.append(record)

            month_dir = engine_dir / month
            month_dir.mkdir(parents=True, exist_ok=True)
            _plot_month_compare(
                month_dir / f"{engine}_{month}.png",
                month,
                baseline_grid,
                baseline_label,
                exp_grid,
                ddk4_grid,
                record,
            )
            if template_grid is not None:
                if engine in SAMPLING_PSEUDOMOIRE_ENGINES:
                    _plot_single_grid(
                        month_dir / f"{engine}_{month}_stripe_estimate.png",
                        f"{engine} stripe estimate | {month}",
                        template_grid,
                        cmap="RdBu_r",
                    )
                else:
                    _plot_single_grid(
                        month_dir / f"{engine}_{month}_bundle_template.png",
                        f"{engine} bundle template | {month}",
                        template_grid,
                        cmap="RdBu_r",
                    )
            if order_scores is not None:
                _plot_order_scores(
                    month_dir / f"{engine}_{month}_order_scores.png",
                    f"{engine} orbit-order scores | {month}",
                    order_scores,
                )
            if basis_diag is not None:
                _plot_basis_diagnostics(
                    month_dir / f"{engine}_{month}_basis_diagnostics.png",
                    f"{engine} basis diagnostics | {month}",
                    basis_diag,
                )
                _write_order_profile_csv(
                    month_dir / f"{engine}_{month}_order_risk_profile.csv",
                    basis_diag,
                )
            with (month_dir / f"{engine}_{month}_info.json").open("w", encoding="utf-8") as handle:
                json.dump(info, handle, indent=2, ensure_ascii=False, default=str)

    csv_path = outdir / "summary_metrics.csv"
    with csv_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "engine,month,elapsed_s,rmse_vs_ddk4,corr_vs_ddk4,ocean_anisotropy,ocean_band_energy,land_retention,"
            "baseline_rmse,baseline_corr,baseline_anisotropy,baseline_band_energy,baseline_land_retention,basis_concentration\n"
        )
        for row in records:
            handle.write(
                f"{row.engine},{row.month},{row.elapsed_s:.4f},{row.rmse_vs_ddk4:.8f},{row.corr_vs_ddk4:.10f},"
                f"{row.ocean_anisotropy:.8f},{row.ocean_band_energy:.8f},{row.land_retention:.8f},"
                f"{row.baseline_rmse:.8f},{row.baseline_corr:.10f},{row.baseline_anisotropy:.8f},"
                f"{row.baseline_band_energy:.8f},{row.baseline_land_retention:.8f},{row.basis_concentration:.8f}\n"
            )

    _plot_summary(outdir / "summary_metrics.png", records)
    _write_gate_summary(outdir / "gate_summary.txt", records)
    with (outdir / "run_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "stack_dir": str(stack_dir),
                "input_tag": input_tag,
                "months": selected,
                "engines": engines,
                "outdir": str(outdir),
            },
            handle,
            indent=2,
            ensure_ascii=False,
        )
    return outdir
