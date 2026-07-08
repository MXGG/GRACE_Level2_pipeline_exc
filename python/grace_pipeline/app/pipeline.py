"""
Main GRACE Level-2 processing pipeline.

This is the Python equivalent of run_pipeline.m, implementing the full
processing chain from GSM coefficients to filtered gridded products.
"""

import os
import sys
import importlib.util
import json
import re
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import time
import subprocess

import numpy as np
try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover - fallback for minimal environments
    def tqdm(iterable=None, *args, **kwargs):
        return iterable if iterable is not None else []

from grace_pipeline.domain.filters import (
    filter_grid_hsaf,
    filter_grid_hsaf_adaptive,
    filter_sh_ddk,
    filter_sh_fan,
    filter_sh_gaussian,
    filter_sh_p4m6,
)
from grace_pipeline.domain.inversion import (
    SHCoefficients,
    apply_gia,
    compute_mean_sh,
    ewh_synthesis,
    get_mean_mode,
    read_gsm_month,
    replace_low_degree,
    select_mean_sh,
)
from grace_pipeline.infra.config import Config, load_config
from grace_pipeline.infra.datasets.grid import ensure_latlon_order, make_lonlat_vec
from grace_pipeline.infra.datasets.time_index import TimeEntry, build_time_index, summarize_time_coverage
from grace_pipeline.infra.io import Product, save_product
from grace_pipeline.io.coefficients import (
    FilteredMonthlyProduct,
    coefficient_config_to_summary,
    export_monthly_coefficients,
    update_coefficient_summary,
    write_summary_json,
)
from grace_pipeline.io.stack import Stack, save_stack, save_stack_hdf5
from grace_pipeline.infra.runtime import ProgressBar, ensure_dir, limit_blas_threads


_COEFFICIENT_PRODUCTS_KEY = "__coefficient_products__"


def _get_frozen_max_workers(cfg: Config) -> int:
    try:
        val = int(getattr(cfg, "perf", {}).get("frozen_max_workers", 0))
    except Exception:
        val = 0
    return val


def _runtime_probe(cfg: Config) -> Dict[str, Any]:
    """Collect runtime information that helps explain performance choices."""
    return {
        "cpu_logical": os.cpu_count() or 1,
        "configured_workers": max(1, int(getattr(cfg.parallel, "n_workers", 1) or 1)),
        "frozen": bool(getattr(sys, "frozen", False)),
        "blas_threads": {
            "OPENBLAS_NUM_THREADS": os.environ.get("OPENBLAS_NUM_THREADS", "auto"),
            "MKL_NUM_THREADS": os.environ.get("MKL_NUM_THREADS", "auto"),
            "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS", "auto"),
            "NUMEXPR_MAX_THREADS": os.environ.get("NUMEXPR_MAX_THREADS", "auto"),
        },
        "cupy_available": importlib.util.find_spec("cupy") is not None,
        "slurm_job": bool(os.environ.get("SLURM_JOB_ID", "")),
    }


def _effective_parallel_workers(cfg: Config, probe: Dict[str, Any]) -> int:
    """Select a sane worker budget for the current runtime."""
    configured = max(1, int(probe.get("configured_workers", 1) or 1))
    cpu_logical = max(1, int(probe.get("cpu_logical", 1) or 1))
    frozen = bool(probe.get("frozen", False))
    slurm_job = bool(probe.get("slurm_job", False))

    if slurm_job:
        safe_cap = cpu_logical
    elif frozen:
        safe_cap = _get_frozen_max_workers(cfg) or min(cpu_logical, 8)
    else:
        safe_cap = cpu_logical
    return max(1, min(configured, cpu_logical, safe_cap))


def _should_log_runtime_probe(cfg: Config, probe: Dict[str, Any]) -> bool:
    try:
        debug_probe = bool(getattr(cfg, "perf", {}).get("debug_runtime_probe", False))
    except Exception:
        debug_probe = False
    return bool(probe.get("slurm_job", False) or debug_probe)


def _choose_hsaf_stack_workers(cfg: Config, total_slices: int, probe: Dict[str, Any]) -> int:
    """Choose a stable outer-parallel worker count for HSAF stack mode."""
    configured = max(1, int(probe.get("effective_workers", probe.get("configured_workers", 1)) or 1))
    cpu_logical = max(1, int(probe.get("cpu_logical", 1) or 1))
    frozen = bool(probe.get("frozen", False))
    slurm_job = bool(probe.get("slurm_job", False))

    if slurm_job:
        safe_cpu_cap = cpu_logical
    elif frozen:
        safe_cpu_cap = _get_frozen_max_workers(cfg) or 8
    elif os.name == "nt":
        safe_cpu_cap = 12
    else:
        safe_cpu_cap = cpu_logical

    return max(1, min(int(total_slices or 1), configured, cpu_logical, safe_cpu_cap))


def _get_hsaf_engine(cfg: Config) -> str:
    try:
        engine = str(getattr(cfg.filter.hankel, "engine", "matlab_v3") or "matlab_v3")
    except Exception:
        engine = "matlab_v3"
    return engine.strip().lower()


def _hsaf_prefers_single_inner_worker(cfg: Config) -> bool:
    return _get_hsaf_engine(cfg) in ("matlab", "matlab_v3", "hsa")


def _normalize_hsaf_variant(value: Any) -> str:
    key = str(value or "global").strip().lower().replace("-", "_")
    if key in ("adaptive", "lat_adaptive", "latitude_adaptive", "adaptive_lat", "latitude"):
        return "adaptive"
    return "global"


def _hsaf_adaptive_enabled_from_config(hsaf_cfg: Dict[str, Any], adaptive_cfg: Optional[List[Dict[str, Any]]]) -> bool:
    return _normalize_hsaf_variant(hsaf_cfg.get("variant", "global")) == "adaptive" and bool(adaptive_cfg)


def _build_hsaf_strategy_manifest(cfg: Config, plan: Dict[str, Any]) -> Dict[str, Any]:
    params_raw = dict(getattr(cfg.filter.hankel, "params", {}) or {})
    variant_requested = str(getattr(cfg.filter.hankel, "variant", "global") or "global")
    variant_effective = _normalize_hsaf_variant(variant_requested)
    adaptive_cfg = list(getattr(cfg.filter.hankel, "adaptive", []) or [])
    if variant_effective == "adaptive" and not adaptive_cfg:
        variant_effective = "global"

    def _pick(name: str, default: int) -> int:
        try:
            return int(params_raw.get(name, default))
        except Exception:
            return int(default)

    strategy_name = "latitude_adaptive" if variant_effective == "adaptive" else "global_fixed"
    return {
        "strategy": strategy_name,
        "variant_requested": variant_requested,
        "variant_effective": variant_effective,
        "input_tag": str(plan.get("hankel_input_tag", "P4M6") or "P4M6"),
        "stack_mode": bool(plan.get("hankel_stack_mode", False)),
        "engine": str(getattr(cfg.filter.hankel, "engine", "matlab_v3") or "matlab_v3"),
        "params": {
            "N": _pick("N", 30),
            "P": _pick("P", 10),
            "K": _pick("K", 6),
            "J": _pick("J", 1),
            "iterations": _pick("iterations", 1),
        },
        "adaptive_zone_count": len(adaptive_cfg),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _write_hsaf_strategy_manifest(paths: "OutputPaths", manifest: Dict[str, Any]) -> None:
    fp = os.path.join(paths.logs, "hsaf_strategy.json")
    tmp = fp + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, fp)


def _time_coverage_lines(report: Dict[str, Any]) -> List[str]:
    if not report.get("has_data", False):
        return ["Time coverage report", "No data detected."]
    lines = [
        "Time coverage report",
        f"Range: {report.get('start_ym', '')} -> {report.get('end_ym', '')}",
        f"Available months: {int(report.get('available_month_count', 0))}",
        f"Expected continuous months: {int(report.get('full_month_count', 0))}",
        f"Missing months (total): {int(report.get('missing_month_count', 0))}",
        f"Missing months in GRACE: {int(report.get('grace_missing_count', 0))}",
        f"Missing months in GRACE-FO: {int(report.get('grace_fo_missing_count', 0))}",
    ]
    missing_grace = report.get("missing_months_grace", []) or []
    missing_fo = report.get("missing_months_grace_fo", []) or []
    if missing_grace:
        lines.append("Missing GRACE months: " + ", ".join(missing_grace))
    if missing_fo:
        lines.append("Missing GRACE-FO months: " + ", ".join(missing_fo))
    return lines


def _write_time_coverage_report(paths: "OutputPaths", report: Dict[str, Any]) -> None:
    fp_json = os.path.join(paths.logs, "time_coverage_report.json")
    fp_txt = os.path.join(paths.logs, "time_coverage_report.txt")

    tmp_json = fp_json + ".tmp"
    with open(tmp_json, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp_json, fp_json)

    tmp_txt = fp_txt + ".tmp"
    with open(tmp_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(_time_coverage_lines(report)) + "\n")
    os.replace(tmp_txt, fp_txt)


def _get_hsaf_requested_inner_workers(cfg: Config) -> Optional[int]:
    """Read explicit inner worker request from hankel.params.workers, if any."""
    try:
        params = dict(getattr(cfg.filter.hankel, "params", {}) or {})
    except Exception:
        params = {}
    requested = params.get("workers", None)
    if requested is None:
        return None
    try:
        requested_i = int(requested)
    except Exception:
        return None
    return requested_i if requested_i > 0 else None


def _should_use_outer_hsaf_slice_parallel(
    cfg: Config,
    total_slices: int,
    worker_count: int,
    probe: Dict[str, Any],
) -> bool:
    if bool(probe.get("slurm_job", False)):
        return True
    if worker_count <= 1 or total_slices < 4:
        return False
    return _hsaf_prefers_single_inner_worker(cfg)


def _choose_hsaf_outer_inner_workers(
    cfg: Config,
    total_slices: int,
    probe: Dict[str, Any],
) -> tuple[int, int]:
    effective = max(1, int(probe.get("effective_workers", probe.get("configured_workers", 1)) or 1))
    safe_outer_cap = _choose_hsaf_stack_workers(cfg, total_slices, probe)
    requested_inner = _get_hsaf_requested_inner_workers(cfg)

    if not _hsaf_prefers_single_inner_worker(cfg) or effective <= 1 or total_slices < 4:
        outer_workers = max(1, min(total_slices, safe_outer_cap))
        return outer_workers, 1

    if requested_inner is not None:
        target_inner = max(1, min(requested_inner, effective))
    else:
        # Default to single-level parallelism for MATLAB-aligned HSAF:
        # higher outer concurrency is usually more stable and faster than
        # nested outer-process + inner-thread pools on heterogeneous CPUs.
        target_inner = 1

    outer_workers = max(1, min(total_slices, safe_outer_cap, max(1, effective // target_inner)))
    inner_workers = max(1, min(target_inner, max(1, effective // outer_workers)))
    return outer_workers, inner_workers


def _prepare_hsaf_stack_config(cfg: Config, inner_workers: Optional[int] = None) -> Dict[str, Any]:
    """Clone HSAF config and optionally override inner parallelism."""
    hsaf_cfg = vars(cfg.filter.hankel).copy()
    try:
        params = dict(hsaf_cfg.get("params", {}) or {})
    except Exception:
        params = {}
    if inner_workers is not None:
        params["workers"] = max(1, int(inner_workers))
    elif _hsaf_prefers_single_inner_worker(cfg):
        params["workers"] = 1
    hsaf_cfg["params"] = params
    return hsaf_cfg


def _format_hsaf_stack_progress(
    done: int,
    total: int,
    wall_elapsed_s: float,
    worker_count: int,
    *,
    inner_workers: Optional[int] = None,
    compute_total_s: Optional[float] = None,
    last_slice_s: Optional[float] = None,
    startup_included: bool = False,
) -> str:
    """Format HSAF stack progress without conflating pool startup with steady-state work."""
    parts = [f"[HSAF][stack] {done}/{total} slices processed"]
    if inner_workers is None:
        parts.append(f"workers={worker_count}")
    else:
        parts.append(f"outer_workers={worker_count}")
        parts.append(f"inner_workers={inner_workers}")
    parts.append(f"wall_avg={wall_elapsed_s / max(1, done):.2f}s/slice")
    if compute_total_s is not None:
        parts.append(f"compute_avg={compute_total_s / max(1, done):.2f}s/slice")
    if last_slice_s is not None:
        parts.append(f"last={last_slice_s:.2f}s")
    if startup_included:
        parts.append("note=includes pool startup")
    return " | ".join(parts)


def _run_hsaf_stack_slice(
    slice_index: int,
    grid_slice: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    hsaf_cfg: Dict[str, Any],
    adaptive_cfg: Optional[List[Dict[str, Any]]] = None,
) -> tuple[int, np.ndarray, float, Optional[str]]:
    """Run one HSAF stack slice and preserve the current output contract."""
    limit_blas_threads()
    start = time.perf_counter()
    error = None
    grid_out = np.asarray(grid_slice, dtype=np.float32)
    try:
        if _hsaf_adaptive_enabled_from_config(hsaf_cfg, adaptive_cfg):
            filtered, _ = filter_grid_hsaf_adaptive(grid_slice, lon_vec, lat_vec, adaptive_cfg)
        else:
            filtered, _ = filter_grid_hsaf(grid_slice, lon_vec, lat_vec, hsaf_cfg)
        filtered = np.squeeze(np.asarray(filtered))
        if filtered.shape != grid_out.shape:
            raise ValueError(f"shape mismatch: expected {grid_out.shape}, got {filtered.shape}")
        if np.isfinite(filtered).any() and np.nanstd(filtered) >= 1e-12:
            grid_out = filtered.astype(np.float32, copy=False)
    except Exception as exc:
        error = str(exc)
    return slice_index, np.ascontiguousarray(grid_out), time.perf_counter() - start, error


@dataclass
class OutputPaths:
    """Standard output folder paths."""
    root: str
    monthly_mat: str
    monthly_txt: str
    monthly_gfc: str
    netcdf: str
    hdf5: str
    geotiff: str
    stacks: str
    metrics: str
    basin: str
    plots: str
    logs: str
    summary: str
    tmp: str
    cache: str


@dataclass
class PipelineOutput:
    """Output from pipeline run."""
    paths: OutputPaths
    time_entries: List[TimeEntry]
    plan: Dict[str, Any]
    stacks: Dict[str, np.ndarray] = field(default_factory=dict)
    metrics: Optional[Dict] = None
    basin_stats: Optional[Dict] = None


def _save_stack_pair(
    tag: str,
    stack_arr: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    time_entries: List[TimeEntry],
    output_dir: str,
    stack_dtype: np.dtype,
    *,
    compress_mat: bool = False,
    write_hdf5: bool = False,
    hdf5_compress_level: int = 1,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    ewh = (
        stack_arr
        if stack_arr.flags["C_CONTIGUOUS"] and stack_arr.dtype == stack_dtype
        else np.ascontiguousarray(np.asarray(stack_arr, dtype=stack_dtype))
    )
    stack_obj = Stack(
        tag=tag,
        ewh=ewh,
        lon=np.asarray(lon_vec),
        lat=np.asarray(lat_vec),
        t=[te.ym for te in time_entries],
        meta=dict(meta or {}),
    )
    save_stack(stack_obj, output_dir, compress=compress_mat)
    if write_hdf5:
        try:
            save_stack_hdf5(stack_obj, output_dir, compress_level=int(hdf5_compress_level))
            print(f"[SAVE] {tag} HDF5 sidecar written.")
        except Exception as exc:
            print(f"[WARN] HDF5 sidecar save failed for {tag}: {exc}")


def run_forward_modeling(fm_cfg: Dict[str, Any], paths: OutputPaths) -> None:
    """Run external forward modeling script if configured."""
    if not isinstance(fm_cfg, dict):
        return
    if not fm_cfg.get("enable", False):
        return
    method = str(fm_cfg.get("method", "FM") or "FM").upper()
    if method != "FM":
        print(f"[FM] Method '{method}' selected; no external FM run.")
        return
    script = str(fm_cfg.get("script", "") or "").strip()
    if not script:
        print("[FM] No script path provided; skipping FM.")
        return
    matlab = str(fm_cfg.get("matlab", "matlab") or "matlab").strip()
    env = os.environ.copy()
    if fm_cfg.get("root"):
        env["IM_FM_ROOT"] = str(fm_cfg.get("root"))
    if fm_cfg.get("output"):
        env["IM_FM_OUT"] = str(fm_cfg.get("output"))
    else:
        env["IM_FM_OUT"] = paths.root
    # Run MATLAB script in batch mode
    try:
        script_arg = script.replace("'", "''")
        cmd = [matlab, "-batch", f"run('{script_arg}')"]
        print(f"[FM] Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, env=env)
    except Exception as e:
        print(f"[FM] External FM run failed: {e}")


def init_paths(cfg: Config) -> OutputPaths:
    """Initialize output paths based on configuration."""
    out_root = cfg.path.OUTPUT
    
    # Route outputs to local/ or remote/<jobid>
    slurm_job = os.environ.get('SLURM_JOB_ID', '')
    if slurm_job:
        out_root = os.path.join(out_root, 'remote', slurm_job)
    else:
        out_root = os.path.join(out_root, 'local')
    
    paths = OutputPaths(
        root=out_root,
        monthly_mat=os.path.join(out_root, 'monthly_mat'),
        monthly_txt=os.path.join(out_root, 'monthly_txt'),
        monthly_gfc=os.path.join(out_root, 'monthly_gfc'),
        netcdf=os.path.join(out_root, 'netcdf'),
        hdf5=os.path.join(out_root, 'hdf5'),
        geotiff=os.path.join(out_root, 'geotiff'),
        stacks=os.path.join(out_root, 'stacks'),
        metrics=os.path.join(out_root, 'metrics'),
        basin=os.path.join(out_root, 'basin'),
        plots=os.path.join(out_root, 'plots'),
        logs=os.path.join(out_root, 'logs'),
        summary=os.path.join(out_root, 'summary'),
        tmp=os.path.join(out_root, 'tmp'),
        cache=os.path.join(out_root, 'CACHE'),
    )
    
    # Create directories
    for path in [paths.root, paths.monthly_mat, paths.monthly_txt, paths.monthly_gfc,
                 paths.netcdf, paths.hdf5, paths.geotiff, paths.stacks, paths.metrics,
                 paths.basin, paths.plots, paths.logs, paths.summary, paths.tmp, paths.cache]:
        ensure_dir(path)
    
    return paths


def compute_plan(cfg: Config) -> Dict[str, Any]:
    """Compute processing plan based on configuration."""
    def _append_unique(items: List[str], value: str) -> None:
        if value and value not in items:
            items.append(value)

    def _resolve_ddk_types() -> List[str]:
        filter_raw = cfg.get("filter", {}) if hasattr(cfg, "get") else {}
        ddk_raw = filter_raw.get("ddk", {}) if isinstance(filter_raw, dict) else {}
        candidates = ddk_raw.get("types", None)
        tags: List[str] = []
        if isinstance(candidates, (list, tuple)):
            for value in candidates:
                token = str(value or "").strip().upper()
                if token.startswith("DDK"):
                    _append_unique(tags, token)
        fallback = str(getattr(cfg.filter.ddk, "type", "DDK4") or "DDK4").strip().upper()
        if fallback.startswith("DDK"):
            _append_unique(tags, fallback)
        return tags

    plan = {
        'order': ['RAW'],
        'ddk_tags': [],
        'hankel_stack_mode': False,
        'hankel_input_tag': 'P4M6',
        'mean_mode': get_mean_mode(cfg),
    }

    filter_cfg = cfg.filter
    ddk_tags = _resolve_ddk_types()
    plan["ddk_tags"] = ddk_tags

    # Add filters based on configuration
    if filter_cfg.gaussian.enable:
        plan['order'].append('GAUSS')
    
    if filter_cfg.p4m6.enable:
        plan['order'].append('P4M6')
    
    if filter_cfg.ddk.enable:
        for ddk_tag in ddk_tags:
            _append_unique(plan['order'], ddk_tag)
    
    if hasattr(filter_cfg, 'fan') and filter_cfg.fan.get('enable', False):
        plan['order'].append('FAN')
    
    # Combo filters
    combinations = getattr(filter_cfg, "combinations", {}) or {}
    combo_gauss_pnmn = bool(
        combinations.get("gaussian_pnmn", filter_cfg.gaussian.enable and filter_cfg.p4m6.enable)
    )
    combo_fan_pnmn = bool(
        combinations.get("fan_pnmn", hasattr(filter_cfg, 'fan') and filter_cfg.fan.get('enable', False) and filter_cfg.p4m6.enable)
    )
    if combo_gauss_pnmn:
        plan['order'].append('GAUSS+P4M6')
    
    if combo_fan_pnmn:
        plan['order'].append('FAN+P4M6')
    
    if filter_cfg.p4m6.enable and filter_cfg.ddk.enable:
        for ddk_tag in ddk_tags:
            _append_unique(plan['order'], f'P4M6+{ddk_tag}')
    
    # HSAF
    if filter_cfg.hankel.enable:
        if filter_cfg.hankel.stack_mode:
            plan['hankel_stack_mode'] = True
        else:
            plan['order'].append('HSAF')
        plan['hankel_input_tag'] = filter_cfg.pre_hankel_input
    
    return plan


def _coefficient_export_enabled(cfg: Config) -> bool:
    return bool(getattr(getattr(cfg, "io", None), "coefficient_export", None) and cfg.io.coefficient_export.enabled)


def _infer_center_from_time_entry(time_entry: TimeEntry) -> str:
    for attr in ("center", "agency"):
        value = getattr(time_entry, attr, "")
        if value:
            return str(value).upper()
    candidate = str(getattr(time_entry, "gfc_file", "") or getattr(time_entry, "path", "") or "")
    upper = Path(candidate).name.upper()
    for center in ("CSR", "GFZ", "JPL", "CNES", "ITSG"):
        if center in upper:
            return center
    return "CSR"


def _release_from_time_entry(time_entry: TimeEntry) -> str:
    candidate = str(getattr(time_entry, "gfc_file", "") or getattr(time_entry, "path", "") or "")
    match = re.search(r"RL\d{2,4}", candidate, re.IGNORECASE)
    return match.group(0).upper() if match else ""


def _common_coefficient_metadata(cfg: Config, plan: Dict[str, Any]) -> Dict[str, Any]:
    lowdeg = getattr(cfg.inversion, "lowdeg", {}) or {}
    low_parts = []
    if lowdeg.get("replace_degree1", lowdeg.get("replace_C10", False)):
        low_parts.append("degree1")
    if lowdeg.get("replace_C20", False):
        low_parts.append("c20")
    if lowdeg.get("replace_C30", False):
        low_parts.append("c30")
    baseline = ""
    if getattr(cfg.inversion, "remove_mean", False):
        baseline = f"{getattr(cfg.inversion, 'mean_start_ym', '')}_to_{getattr(cfg.inversion, 'mean_end_ym', '')}".strip("_to_")
    gia_model = ""
    try:
        if cfg.inversion.gia.get("enable", False):
            gia_model = Path(str(cfg.inversion.gia.get("file", ""))).name
    except Exception:
        gia_model = ""
    return {
        "baseline": baseline,
        "low_degree_replacement": ",".join(low_parts),
        "gia_model": gia_model,
        "mean_mode": plan.get("mean_mode", ""),
    }


def _make_coefficient_product(
    cfg: Config,
    time_entry: TimeEntry,
    tag: str,
    *,
    source_domain: str,
    clm: Optional[np.ndarray] = None,
    slm: Optional[np.ndarray] = None,
    grid: Optional[np.ndarray] = None,
    lon_vec: Optional[np.ndarray] = None,
    lat_vec: Optional[np.ndarray] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> FilteredMonthlyProduct:
    return FilteredMonthlyProduct(
        year_month=str(time_entry.ym),
        center=_infer_center_from_time_entry(time_entry),
        release=_release_from_time_entry(time_entry),
        method=str(tag),
        source_domain=source_domain,
        cs_available=clm is not None and slm is not None,
        clm=clm,
        slm=slm,
        grid_available=grid is not None,
        grid=grid,
        grid_unit=str(getattr(cfg.grid, "unit", "mmEWH") or "mmEWH"),
        lon=lon_vec,
        lat=lat_vec,
        max_degree=int(getattr(cfg.inversion, "Lmax", 60)),
        metadata=dict(metadata or {}),
    )


def process_month(
    cfg: Config,
    time_entry: TimeEntry,
    mean_sh,
    plan: Dict,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
) -> Dict[str, np.ndarray]:
    """
    Process a single month of GRACE data.
    
    Args:
        cfg: Configuration
        time_entry: Time entry for this month
        mean_sh: Mean SH coefficients (for removing mean)
        plan: Processing plan
        lon_vec, lat_vec: Grid vectors
    
    Returns:
        Dictionary of products {tag: grid}
    """
    Lmax = cfg.inversion.Lmax
    products = {}
    coeff_products: Dict[str, FilteredMonthlyProduct] = {}
    coeff_enabled = _coefficient_export_enabled(cfg)
    coeff_meta = _common_coefficient_metadata(cfg, plan) if coeff_enabled else {}
    
    # 1. Read GSM coefficients
    try:
        sh = read_gsm_month(cfg, time_entry)
    except FileNotFoundError:
        return {}
    
    # 2. Replace low-degree terms
    sh = replace_low_degree(cfg, sh, time_entry)
    
    # 3. Remove mean
    if mean_sh is not None and cfg.inversion.remove_mean:
        mean_for_month = select_mean_sh(mean_sh, time_entry, plan.get("mean_mode", "fixed_range"))
        if mean_for_month is not None:
            sh.C = sh.C - mean_for_month.C
            sh.S = sh.S - mean_for_month.S
            sh.meta['removed_mean'] = True
    
    # 4. Apply GIA correction
    if cfg.inversion.gia.get('enable', False):
        sh = apply_gia(cfg, sh, time_entry)
    
    # 5. Synthesize RAW product
    raw_grid = ewh_synthesis(sh.C, sh.S, Lmax, lon_vec, lat_vec)
    products['RAW'] = raw_grid
    
    # 6. Apply filters
    C, S = sh.C.copy(), sh.S.copy()
    
    # Gaussian
    if cfg.filter.gaussian.enable:
        C_g, S_g, _ = filter_sh_gaussian(C, S, Lmax, cfg.filter.gaussian.radius_km)
        products['GAUSS'] = ewh_synthesis(C_g, S_g, Lmax, lon_vec, lat_vec)
        if coeff_enabled:
            coeff_products['GAUSS'] = _make_coefficient_product(
                cfg, time_entry, 'GAUSS', source_domain="spherical_harmonic", clm=C_g, slm=S_g, metadata=coeff_meta
            )
    
    # P4M6
    if cfg.filter.p4m6.enable:
        C_p, S_p, _ = filter_sh_p4m6(C, S, Lmax, cfg.filter.p4m6.poly_deg, cfg.filter.p4m6.m_start)
        products['P4M6'] = ewh_synthesis(C_p, S_p, Lmax, lon_vec, lat_vec)
        if coeff_enabled:
            coeff_products['P4M6'] = _make_coefficient_product(
                cfg, time_entry, 'P4M6', source_domain="spherical_harmonic", clm=C_p, slm=S_p, metadata=coeff_meta
            )
    
    # DDK
    if cfg.filter.ddk.enable:
        ddk_tags = [str(t).strip().upper() for t in plan.get("ddk_tags", []) if str(t).strip()]
        warned_missing = getattr(process_month, "_ddk_warned_missing", set())
        warned_same = getattr(process_month, "_ddk_warned_same", set())
        for ddk_tag in ddk_tags:
            C_d, S_d, meta_d = filter_sh_ddk(C, S, Lmax, ddk_tag, cfg.filter.ddk.data_dir)
            if not meta_d.get('applied', False):
                if ddk_tag not in warned_missing:
                    print(f"[WARN] {ddk_tag} kernel not found in {cfg.filter.ddk.data_dir}. Outputs set to NaN.")
                    warned_missing.add(ddk_tag)
                grid_ddk = np.full_like(raw_grid, np.nan)
            else:
                grid_ddk = ewh_synthesis(C_d, S_d, Lmax, lon_vec, lat_vec)
                if coeff_enabled:
                    coeff_products[ddk_tag] = _make_coefficient_product(
                        cfg, time_entry, ddk_tag, source_domain="spherical_harmonic", clm=C_d, slm=S_d, metadata=coeff_meta
                    )
                # Sanity check: avoid silently passing RAW as DDK
                try:
                    diff = np.nanstd(grid_ddk - raw_grid)
                    if not np.isfinite(diff) or diff < 1e-10:
                        if ddk_tag not in warned_same:
                            print(f"[WARN] {ddk_tag} output appears identical to RAW. Check DDK kernel/data_dir.")
                            warned_same.add(ddk_tag)
                        grid_ddk = np.full_like(raw_grid, np.nan)
                        coeff_products.pop(ddk_tag, None)
                except Exception:
                    pass
            products[ddk_tag] = grid_ddk
        process_month._ddk_warned_missing = warned_missing
        process_month._ddk_warned_same = warned_same
    
    # Fan
    if hasattr(cfg.filter, 'fan') and cfg.filter.fan.get('enable', False):
        r1 = cfg.filter.fan.get('radius1_km', 300)
        r2 = cfg.filter.fan.get('radius2_km', 300)
        C_f, S_f, _ = filter_sh_fan(C, S, Lmax, r1, r2)
        products['FAN'] = ewh_synthesis(C_f, S_f, Lmax, lon_vec, lat_vec)
        if coeff_enabled:
            coeff_products['FAN'] = _make_coefficient_product(
                cfg, time_entry, 'FAN', source_domain="spherical_harmonic", clm=C_f, slm=S_f, metadata=coeff_meta
            )
    
    # Combo: GAUSS + P4M6
    combinations = getattr(cfg.filter, "combinations", {}) or {}
    combo_gauss_pnmn = bool(combinations.get("gaussian_pnmn", cfg.filter.gaussian.enable and cfg.filter.p4m6.enable))
    combo_fan_pnmn = bool(
        combinations.get(
            "fan_pnmn",
            hasattr(cfg.filter, 'fan') and cfg.filter.fan.get('enable', False) and cfg.filter.p4m6.enable,
        )
    )
    if combo_gauss_pnmn:
        # Keep the Python path aligned with the MATLAB reference chain:
        # destriping first, smoothing second.
        C_gp, S_gp, _ = filter_sh_p4m6(C, S, Lmax, cfg.filter.p4m6.poly_deg, cfg.filter.p4m6.m_start)
        C_gp, S_gp, _ = filter_sh_gaussian(C_gp, S_gp, Lmax, cfg.filter.gaussian.radius_km)
        products['GAUSS+P4M6'] = ewh_synthesis(C_gp, S_gp, Lmax, lon_vec, lat_vec)
        if coeff_enabled:
            coeff_products['GAUSS+P4M6'] = _make_coefficient_product(
                cfg, time_entry, 'GAUSS+P4M6', source_domain="spherical_harmonic", clm=C_gp, slm=S_gp, metadata=coeff_meta
            )
    
    # Combo: FAN + P4M6
    if combo_fan_pnmn:
        C_fp, S_fp, _ = filter_sh_p4m6(C, S, Lmax, cfg.filter.p4m6.poly_deg, cfg.filter.p4m6.m_start)
        r1 = cfg.filter.fan.get('radius1_km', 300) if hasattr(cfg.filter, 'fan') else 300
        r2 = cfg.filter.fan.get('radius2_km', 300) if hasattr(cfg.filter, 'fan') else 300
        C_fp, S_fp, _ = filter_sh_fan(C_fp, S_fp, Lmax, r1, r2)
        products['FAN+P4M6'] = ewh_synthesis(C_fp, S_fp, Lmax, lon_vec, lat_vec)
        if coeff_enabled:
            coeff_products['FAN+P4M6'] = _make_coefficient_product(
                cfg, time_entry, 'FAN+P4M6', source_domain="spherical_harmonic", clm=C_fp, slm=S_fp, metadata=coeff_meta
            )
    
    # Combo: P4M6 + DDK
    if cfg.filter.p4m6.enable and cfg.filter.ddk.enable:
        C_pd, S_pd, _ = filter_sh_p4m6(C, S, Lmax, cfg.filter.p4m6.poly_deg, cfg.filter.p4m6.m_start)
        for ddk_tag in [str(t).strip().upper() for t in plan.get("ddk_tags", []) if str(t).strip()]:
            C_pd_i, S_pd_i, meta_pd = filter_sh_ddk(C_pd, S_pd, Lmax, ddk_tag, cfg.filter.ddk.data_dir)
            if not meta_pd.get('applied', False):
                grid_pd = np.full_like(raw_grid, np.nan)
            else:
                grid_pd = ewh_synthesis(C_pd_i, S_pd_i, Lmax, lon_vec, lat_vec)
                if coeff_enabled:
                    coeff_products[f"P4M6+{ddk_tag}"] = _make_coefficient_product(
                        cfg,
                        time_entry,
                        f"P4M6+{ddk_tag}",
                        source_domain="spherical_harmonic",
                        clm=C_pd_i,
                        slm=S_pd_i,
                        metadata=coeff_meta,
                    )
            products[f"P4M6+{ddk_tag}"] = grid_pd

    # HSAF (non-stack mode)
    if cfg.filter.hankel.enable and not plan.get('hankel_stack_mode', False):
        input_tag = cfg.filter.pre_hankel_input
        if input_tag not in products:
            # fallback to RAW if requested input not available
            if 'RAW' in products:
                if not hasattr(process_month, '_hsaf_warned'):
                    print(f"[WARN] HSAF input '{input_tag}' not found. Falling back to RAW.")
                    process_month._hsaf_warned = True
                input_tag = 'RAW'
            else:
                if not hasattr(process_month, '_hsaf_warned'):
                    print(f"[WARN] HSAF input '{input_tag}' not found and RAW missing. Output set to NaN.")
                    process_month._hsaf_warned = True
                products['HSAF'] = np.full_like(raw_grid, np.nan)
                input_tag = None
        if input_tag:
            grid_in = products[input_tag]
            hsaf_cfg = vars(cfg.filter.hankel).copy()
            try:
                params = dict(hsaf_cfg.get("params", {}) or {})
            except Exception:
                params = {}
            # The MATLAB-style engine is numerically consistent but responds
            # poorly to threaded inner parallelism on typical desktops.
            if _hsaf_prefers_single_inner_worker(cfg):
                params["workers"] = 1
            # Avoid nested over-subscription: month-level process parallelism +
            # per-map HSAF internal workers can severely slow down in EXE.
            elif getattr(cfg.parallel, "enable", False) and int(getattr(cfg.parallel, "n_workers", 1)) > 1:
                params["workers"] = 1
            elif int(params.get("workers", 0)) <= 0 and int(getattr(cfg.parallel, "n_workers", 1)) > 1:
                params["workers"] = int(getattr(cfg.parallel, "n_workers", 1))
            hsaf_cfg["params"] = params
            if _hsaf_adaptive_enabled_from_config(hsaf_cfg, getattr(cfg.filter.hankel, 'adaptive', [])):
                grid_hsaf, _ = filter_grid_hsaf_adaptive(grid_in, lon_vec, lat_vec, cfg.filter.hankel.adaptive)
            else:
                grid_hsaf, _ = filter_grid_hsaf(grid_in, lon_vec, lat_vec, hsaf_cfg)
            # Fallback if HSAF collapses the signal
            try:
                if not np.isfinite(grid_hsaf).any() or np.nanstd(grid_hsaf) < 1e-12:
                    if not hasattr(process_month, '_hsaf_zero_warned'):
                        print("[WARN] HSAF output is near-zero/empty. Falling back to input.")
                        process_month._hsaf_zero_warned = True
                    grid_hsaf = grid_in
            except Exception:
                pass
            products['HSAF'] = grid_hsaf
            if coeff_enabled:
                metadata = dict(coeff_meta)
                metadata["note"] = "HSAF coefficients are reconstructed from filtered global EWH grid."
                coeff_products['HSAF'] = _make_coefficient_product(
                    cfg,
                    time_entry,
                    'HSAF',
                    source_domain="grid",
                    grid=grid_hsaf,
                    lon_vec=lon_vec,
                    lat_vec=lat_vec,
                    metadata=metadata,
                )

    if coeff_products:
        products[_COEFFICIENT_PRODUCTS_KEY] = coeff_products
    return products


def run_pipeline(cfg_or_path=None, pause_event=None, stop_event=None, progress_cb=None, **kwargs) -> PipelineOutput:
    """
    Run the full GRACE Level-2 processing pipeline.
    
    Args:
        cfg_or_path: Config object, path to config file, or None (use defaults)
        **kwargs: Additional configuration overrides
    
    Returns:
        PipelineOutput with results
    """
    # Force timely log flush in batch/non-interactive runs (e.g., SLURM stdout files).
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(line_buffering=True)
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(line_buffering=True)
    except Exception:
        pass

    # Load configuration
    if isinstance(cfg_or_path, Config):
        cfg = cfg_or_path
    elif isinstance(cfg_or_path, (str, Path)):
        cfg = load_config(cfg_or_path)
    else:
        cfg = load_config()
    
    # Print banner
    print("\n" + "=" * 64)
    print("  GRACE Level-2 Pipeline (Python)")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 64 + "\n")
    
    # Initialize paths
    paths = init_paths(cfg)
    print(f"[OUTPUT] {paths.root}")
    
    # Build time index
    time_entries = build_time_index(cfg)
    if not time_entries:
        raise ValueError("No time entries found. Check GFC directory or time configuration.")
    
    Nt = len(time_entries)
    print(f"[TIME] {time_entries[0].ym} -> {time_entries[-1].ym} (Nt={Nt})")
    time_report = summarize_time_coverage(time_entries)
    print(
        "[TIME] coverage | "
        f"available={int(time_report.get('available_month_count', 0))} | "
        f"expected={int(time_report.get('full_month_count', 0))} | "
        f"missing_total={int(time_report.get('missing_month_count', 0))} | "
        f"missing_grace={int(time_report.get('grace_missing_count', 0))} | "
        f"missing_grace_fo={int(time_report.get('grace_fo_missing_count', 0))}"
    )
    try:
        _write_time_coverage_report(paths, time_report)
        print(f"[OUTPUT] {os.path.join(paths.logs, 'time_coverage_report.json')}")
    except Exception as exc:
        print(f"[WARN] Failed to write time coverage report: {exc}")
    
    # Compute plan
    plan = compute_plan(cfg)
    print(f"[PLAN] order = {' -> '.join(plan['order'])}")
    hsaf_strategy: Optional[Dict[str, Any]] = None
    if getattr(cfg.filter.hankel, "enable", False):
        hsaf_strategy = _build_hsaf_strategy_manifest(cfg, plan)
        try:
            _write_hsaf_strategy_manifest(paths, hsaf_strategy)
        except Exception as exc:
            print(f"[WARN] Failed to write HSAF strategy manifest: {exc}")
        params = hsaf_strategy.get("params", {})
        if hsaf_strategy.get("variant_effective") == "adaptive":
            print(
                f"[HSAF] Strategy=latitude_adaptive | input={hsaf_strategy.get('input_tag')} | "
                f"zones={hsaf_strategy.get('adaptive_zone_count', 0)} | "
                f"stack_mode={'on' if hsaf_strategy.get('stack_mode') else 'off'}"
            )
        else:
            print(
                f"[HSAF] Strategy=global_fixed | input={hsaf_strategy.get('input_tag')} | "
                f"stack_mode={'on' if hsaf_strategy.get('stack_mode') else 'off'}"
            )
    runtime_probe = _runtime_probe(cfg)
    runtime_probe["effective_workers"] = _effective_parallel_workers(cfg, runtime_probe)
    if _should_log_runtime_probe(cfg, runtime_probe):
        print(
            "[PIPELINE] Runtime probe | "
            f"cpu={runtime_probe['cpu_logical']} | "
            f"configured_workers={runtime_probe['configured_workers']} | "
            f"effective_workers={runtime_probe['effective_workers']} | "
            f"frozen={runtime_probe['frozen']}"
        )
        print(
            "[PIPELINE] BLAS threads | "
            f"OPENBLAS={runtime_probe['blas_threads']['OPENBLAS_NUM_THREADS']} | "
            f"MKL={runtime_probe['blas_threads']['MKL_NUM_THREADS']} | "
            f"OMP={runtime_probe['blas_threads']['OMP_NUM_THREADS']} | "
            f"NUMEXPR={runtime_probe['blas_threads']['NUMEXPR_MAX_THREADS']}"
        )
        print(f"[PIPELINE] CUDA/CuPy available: {'yes' if runtime_probe['cupy_available'] else 'no'}")
    if getattr(cfg.parallel, "enable", False):
        cfg.parallel.n_workers = runtime_probe["effective_workers"]
    
    # Create grid vectors
    lon_vec, lat_vec = make_lonlat_vec(cfg)
    nLon, nLat = len(lon_vec), len(lat_vec)
    
    # Compute mean SH if needed
    mean_sh = None
    if cfg.inversion.remove_mean:
        print(f"[INV] Computing mean SH coefficients (mode={plan.get('mean_mode', 'fixed_range')})...")
        mean_sh = compute_mean_sh(cfg, time_entries)

    coefficient_summary: Optional[Dict[str, Any]] = None
    if _coefficient_export_enabled(cfg):
        coefficient_summary = coefficient_config_to_summary(
            cfg.io.coefficient_export,
            Path(paths.monthly_gfc),
            int(getattr(cfg.inversion, "Lmax", 60)),
        )

    def _save_monthly_products(products, ym):
        if not products:
            return
        try:
            for tag, grid in products.items():
                if tag == _COEFFICIENT_PRODUCTS_KEY:
                    continue
                if cfg.io.save_monthly_mat:
                    out_dir = os.path.join(paths.monthly_mat, tag)
                    save_product(Product(tag=tag, ym=ym, ewh=grid, lon=lon_vec, lat=lat_vec), out_dir, format='mat')
                if cfg.io.export_txt:
                    out_dir = os.path.join(paths.monthly_txt, tag)
                    save_product(Product(tag=tag, ym=ym, ewh=grid, lon=lon_vec, lat=lat_vec), out_dir, format='txt')
        except Exception as e:
            print(f"[WARN] Monthly save failed for {ym}: {e}")

    def _export_coefficient_products(coeff_products: Dict[str, FilteredMonthlyProduct], ym: str) -> None:
        if not coeff_products or coefficient_summary is None:
            return
        for tag, product in coeff_products.items():
            try:
                manifest = export_monthly_coefficients(
                    product,
                    cfg.io.coefficient_export,
                    Path(paths.monthly_gfc),
                )
                if manifest:
                    update_coefficient_summary(coefficient_summary, manifest)
            except Exception as exc:
                print(f"[WARN] C/S coefficient export failed for {ym} {tag}: {exc}")

    def _stack_tags_to_store() -> set:
        tags = set()
        basin_cfg = cfg.basin if isinstance(cfg.basin, dict) else getattr(cfg.basin, "__dict__", {})
        need_all_products = bool(
            getattr(cfg.io, "save_stack_mat", False)
            or getattr(cfg.io, "return_stacks", False)
            or basin_cfg.get("analysis_enable", False)
        )
        if need_all_products:
            tags.update(plan["order"])
        if plan.get("hankel_stack_mode", False):
            input_tag = plan.get("hankel_input_tag", "RAW")
            tags.add(input_tag if input_tag in plan["order"] else "RAW")
            tags.add("HSAF")
        return tags

    stack_tags = _stack_tags_to_store()
    stack_dtype = np.float32
    if stack_tags:
        print(f"[MEM] Keeping stack storage for: {', '.join(sorted(stack_tags))}")
    else:
        print("[MEM] Stack storage disabled for this run; monthly products will be streamed only.")

    # Initialize only the stacks that are needed downstream.
    stacks = {
        tag: np.full((nLon, nLat, Nt), np.nan, dtype=stack_dtype)
        for tag in plan["order"]
        if tag in stack_tags
    }
    
    # Process each month
    print("\n[PROCESSING] Monthly loop...")
    use_parallel = cfg.parallel.enable and cfg.parallel.n_workers > 1
    if use_parallel:
        limit_blas_threads()

    # Frozen Windows builds are more fragile with aggressive process counts,
    # but forcing sequential mode wastes the desktop CPU. Keep parallelism
    # enabled and rely on the earlier runtime cap instead.
    if getattr(sys, 'frozen', False):
        frozen_max = _get_frozen_max_workers(cfg)
        if use_parallel and frozen_max > 0 and cfg.parallel.n_workers > frozen_max:
            print(f"[WARN] Capping parallel workers to {frozen_max} for frozen executable")
            cfg.parallel.n_workers = frozen_max
        if cfg.parallel.n_workers < 2:
            cfg.parallel.enable = False
            use_parallel = False
    
    disable_tqdm = not getattr(sys.stdout, "isatty", lambda: False)()

    extra_units = 0
    if plan.get('hankel_stack_mode', False):
        extra_units += Nt
        if cfg.io.save_monthly_mat or cfg.io.export_txt:
            extra_units += Nt
    if cfg.io.save_stack_mat:
        extra_units += max(1, len(stacks))
    total_units = max(Nt, Nt + extra_units)

    def _emit_progress(done: int, total: int, stage: str = "", detail: str | None = None) -> None:
        if not progress_cb:
            return
        try:
            progress_cb(done, total, stage, detail)
        except TypeError:
            try:
                progress_cb(done, total, stage)
            except TypeError:
                progress_cb(done, total)
        except Exception:
            pass

    _emit_progress(0, total_units, "Preparing execution environment", f"0/{Nt}")

    if use_parallel:
        # Parallel processing
        with ProcessPoolExecutor(max_workers=cfg.parallel.n_workers) as executor:
            futures = {
                executor.submit(process_month, cfg, te, mean_sh, plan, lon_vec, lat_vec): k
                for k, te in enumerate(time_entries)
            }
            done = 0
            for future in tqdm(as_completed(futures), total=Nt, desc="Months", disable=disable_tqdm):
                if pause_event is not None:
                    while pause_event.is_set():
                        time.sleep(0.2)
                if stop_event is not None and stop_event.is_set():
                    print("[STOP] Stop requested. Cancelling remaining tasks...")
                    break
                k = futures[future]
                try:
                    products = future.result()
                    coeff_products = products.pop(_COEFFICIENT_PRODUCTS_KEY, {})
                    for tag, grid in products.items():
                        if tag in stacks:
                            stacks[tag][:, :, k] = np.asarray(grid, dtype=stack_dtype)
                    try:
                        _save_monthly_products(products, time_entries[k].ym)
                    except Exception:
                        pass
                    _export_coefficient_products(coeff_products, time_entries[k].ym)
                    products.clear()
                except Exception as e:
                    print(f"[ERROR] Month {time_entries[k].ym}: {e}")
                done += 1
                _emit_progress(done, total_units, "Running monthly loop", f"{done}/{Nt}")
    else:
        # Sequential processing
        if (
            getattr(cfg.filter, "hankel", None)
            and getattr(cfg.filter.hankel, "enable", False)
            and getattr(cfg.filter.hankel, "engine", "matlab_v3") in ("matlab", "matlab_v3", "hsa")
        ):
            try:
                params = cfg.filter.hankel.params if hasattr(cfg.filter.hankel, "params") else {}
                if isinstance(params, dict) and int(params.get("workers", 0)) <= 0 and cfg.parallel.n_workers > 1:
                    params["workers"] = int(cfg.parallel.n_workers)
            except Exception:
                pass
        for k, te in enumerate(tqdm(time_entries, desc="Months", disable=disable_tqdm)):
            if pause_event is not None:
                while pause_event.is_set():
                    time.sleep(0.2)
            if stop_event is not None and stop_event.is_set():
                print("[STOP] Stop requested. Exiting loop.")
                break
            try:
                products = process_month(cfg, te, mean_sh, plan, lon_vec, lat_vec)
                coeff_products = products.pop(_COEFFICIENT_PRODUCTS_KEY, {})
                for tag, grid in products.items():
                    if tag in stacks:
                        stacks[tag][:, :, k] = np.asarray(grid, dtype=stack_dtype)
                try:
                    _save_monthly_products(products, te.ym)
                except Exception:
                    pass
                _export_coefficient_products(coeff_products, te.ym)
                products.clear()
            except Exception as e:
                print(f"[ERROR] Month {te.ym}: {e}")
            _emit_progress(k + 1, total_units, "Running monthly loop", f"{k + 1}/{Nt}")
    
    # HSAF stack mode
    progress_offset = Nt
    if plan.get('hankel_stack_mode', False):
        print("\n[HSAF] Stack mode processing...")
        input_tag = plan['hankel_input_tag']
        if input_tag not in stacks and 'RAW' in stacks:
            print(f"[WARN] HSAF stack input '{input_tag}' not found. Falling back to RAW.")
            input_tag = 'RAW'
        if input_tag in stacks:
            stack_in = stacks[input_tag]
            n_stack = int(stack_in.shape[2]) if stack_in.ndim == 3 else 1
            adaptive_cfg = list(getattr(cfg.filter.hankel, 'adaptive', []) or [])
            stack_started = time.perf_counter()
            last_logged = {"done": 0}
            worker_count, inner_worker_count = _choose_hsaf_outer_inner_workers(cfg, n_stack, runtime_probe)
            local_stack_mode = not _should_use_outer_hsaf_slice_parallel(
                cfg,
                n_stack,
                worker_count,
                runtime_probe,
            )
            compute_stats = {"total": 0.0, "last": None}

            def _record_stack_slice(
                done: int,
                total: int,
                worker_count: int,
                *,
                inner_workers: Optional[int] = None,
                compute_elapsed_s: Optional[float] = None,
                startup_included: bool = False,
            ) -> None:
                report_step = max(1, total // 10)
                wall_elapsed_s = float(time.perf_counter() - stack_started)
                if compute_elapsed_s is not None:
                    compute_stats["total"] += float(compute_elapsed_s)
                    compute_stats["last"] = float(compute_elapsed_s)
                if done == total or done == 1 or (done - last_logged["done"]) >= report_step:
                    print(
                        _format_hsaf_stack_progress(
                            done,
                            total,
                            wall_elapsed_s,
                            worker_count,
                            inner_workers=inner_workers,
                            compute_total_s=compute_stats["total"] if compute_stats["last"] is not None else None,
                            last_slice_s=compute_stats["last"],
                            startup_included=startup_included,
                        )
                    )
                    last_logged["done"] = done
                _emit_progress(progress_offset + done, total_units, f"HSAF stack {done}/{total}", f"{done}/{total}")

            if local_stack_mode:
                hsaf_cfg = _prepare_hsaf_stack_config(cfg, inner_workers=inner_worker_count)
                inner_workers = int(hsaf_cfg.get("params", {}).get("workers", 1) or 1)
                print(
                    f"[HSAF] Filtering {n_stack} stack slices from {input_tag} "
                    f"with workers={inner_workers} (in-process stack loop)."
                )
                if inner_workers > 1:
                    limit_blas_threads()

                def _progress(done: int, total: int) -> None:
                    _record_stack_slice(done, total, inner_workers)

                if _hsaf_adaptive_enabled_from_config(hsaf_cfg, adaptive_cfg):
                    stack_hsaf, _ = filter_grid_hsaf_adaptive(stack_in, lon_vec, lat_vec, adaptive_cfg)
                    for done in range(1, n_stack + 1):
                        _record_stack_slice(done, n_stack, inner_workers)
                else:
                    stack_hsaf, _ = filter_grid_hsaf(
                        stack_in,
                        lon_vec,
                        lat_vec,
                        hsaf_cfg,
                        progress_hook=_progress,
                    )
                stacks['HSAF'] = np.ascontiguousarray(np.asarray(stack_hsaf, dtype=stack_dtype))
            else:
                hsaf_cfg = _prepare_hsaf_stack_config(cfg, inner_workers=inner_worker_count)
                inner_workers = int(hsaf_cfg.get("params", {}).get("workers", 1) or 1)
                executor_cls = ProcessPoolExecutor
                print(
                    f"[HSAF] Filtering {n_stack} stack slices from {input_tag} "
                    f"with outer_workers={worker_count}, inner_workers={inner_workers} ({executor_cls.__name__})."
                )

                stack_hsaf = np.full_like(stack_in, np.nan, dtype=stack_dtype)
                with executor_cls(max_workers=worker_count) as executor:
                    futures = {
                        executor.submit(
                            _run_hsaf_stack_slice,
                            idx,
                            np.ascontiguousarray(stack_in[:, :, idx]),
                            lon_vec,
                            lat_vec,
                            hsaf_cfg,
                            adaptive_cfg,
                        ): idx
                        for idx in range(n_stack)
                    }
                    done = 0
                    for future in as_completed(futures):
                        slice_idx, filtered_slice, elapsed_s, error = future.result()
                        if error:
                            print(f"[WARN] HSAF stack slice {slice_idx + 1}/{n_stack} failed: {error}")
                        stack_hsaf[:, :, slice_idx] = np.asarray(filtered_slice, dtype=stack_dtype)
                        done += 1
                        _record_stack_slice(
                            done,
                            n_stack,
                            worker_count,
                            inner_workers=inner_workers,
                            compute_elapsed_s=elapsed_s,
                            startup_included=(done == 1),
                        )

                stacks['HSAF'] = np.ascontiguousarray(np.asarray(stack_hsaf, dtype=stack_dtype))
            print(f"[HSAF] Stack mode filter complete in {time.perf_counter() - stack_started:.1f}s.")
        progress_offset += Nt
    
    # If HSAF stack mode produced HSAF stack, export monthly files
    if plan.get('hankel_stack_mode', False) and 'HSAF' in stacks:
        if cfg.io.save_monthly_mat or cfg.io.export_txt or _coefficient_export_enabled(cfg):
            print("[HSAF] Writing monthly products from stack...")
            export_started = time.perf_counter()
            hsaf_coeff_meta = _common_coefficient_metadata(cfg, plan) if _coefficient_export_enabled(cfg) else {}
            if hsaf_coeff_meta:
                hsaf_coeff_meta["note"] = "HSAF coefficients are reconstructed from filtered global EWH grid."
            for k, te in enumerate(time_entries):
                try:
                    grid = stacks['HSAF'][:, :, k]
                    if cfg.io.save_monthly_mat or cfg.io.export_txt:
                        _save_monthly_products({'HSAF': grid}, te.ym)
                    if _coefficient_export_enabled(cfg):
                        _export_coefficient_products(
                            {
                                "HSAF": _make_coefficient_product(
                                    cfg,
                                    te,
                                    "HSAF",
                                    source_domain="grid",
                                    grid=grid,
                                    lon_vec=lon_vec,
                                    lat_vec=lat_vec,
                                    metadata=hsaf_coeff_meta,
                                )
                            },
                            te.ym,
                        )
                except Exception as e:
                    print(f"[WARN] HSAF monthly export failed for {te.ym}: {e}")
                else:
                    done = k + 1
                    report_step = max(1, Nt // 8)
                    if done == Nt or done == 1 or done % report_step == 0:
                        print(f"[HSAF][export] {done}/{Nt} monthly outputs written...")
                _emit_progress(
                    progress_offset + k + 1,
                    total_units,
                    f"Writing HSAF monthly outputs {k + 1}/{Nt}",
                    f"{k + 1}/{Nt}",
                )
            print(f"[HSAF] Monthly stack export complete in {time.perf_counter() - export_started:.1f}s.")
        progress_offset += Nt

    # Basin analysis (optional)
    try:
        basin_cfg = cfg.basin if isinstance(cfg.basin, dict) else cfg.basin.__dict__
    except Exception:
        basin_cfg = {}
    if basin_cfg.get('analysis_enable', False) and basin_cfg.get('boundary_file'):
        try:
            from grace_pipeline.basin import read_boundary, make_mask, extract_basin_ts, fit_seasonal_trend
            bfile = basin_cfg.get('boundary_file')
            name_field = basin_cfg.get('name_field', 'Name')
            target_name = basin_cfg.get('name', '').strip() if basin_cfg.get('name') else ''
            basins = read_boundary(bfile, name_field=name_field)
            if target_name:
                basins = [b for b in basins if b.name == target_name]
            if basins is not None and len(basins) > 0:
                # time vector in years
                t_years = np.array([te.year + (te.month - 0.5)/12.0 for te in time_entries], dtype=float)
                for b in basins:
                    mask = make_mask(b, lon_vec, lat_vec)
                    ts_dict = extract_basin_ts(stacks, mask, lon_vec, lat_vec)
                    # Save timeseries CSV
                    out_csv = os.path.join(paths.basin, f"basin_{b.name}_ts.csv")
                    with open(out_csv, 'w', encoding='utf-8') as f:
                        f.write('ym,' + ','.join(ts_dict.keys()) + '\n')
                        for i, te in enumerate(time_entries):
                            row = [te.ym] + [f"{ts_dict[tag][i]:.6f}" for tag in ts_dict]
                            f.write(','.join(row) + '\n')
                    # Save stats CSV
                    out_stat = os.path.join(paths.basin, f"basin_{b.name}_stats.csv")
                    with open(out_stat, 'w', encoding='utf-8') as f:
                        f.write('tag,trend,amp_ann,amp_semi,const\n')
                        for tag, ts in ts_dict.items():
                            stat = fit_seasonal_trend(t_years, ts)
                            f.write(f"{tag},{stat.get('trend', np.nan):.6f},{stat.get('amp_ann', np.nan):.6f},{stat.get('amp_semi', np.nan):.6f},{stat.get('const', np.nan):.6f}\n")
                    print(f"[BASIN] Saved basin results for {b.name}")
        except Exception as e:
            print(f"[WARN] Basin analysis failed: {e}")


    # Save stacks
    if cfg.io.save_stack_mat and stacks:
        print("\n[SAVE] Saving stacks...")
        save_started = time.perf_counter()
        stack_count = len(stacks)
        stack_compress = bool(runtime_probe.get("slurm_job", False))
        hdf5_compress_level = 1 if runtime_probe.get("slurm_job", False) else 0
        write_hdf5_sidecar = bool(getattr(cfg.io, "save_stack_hdf5", False))
        if write_hdf5_sidecar:
            print("[SAVE] HDF5 sidecar enabled.")
        for idx, (tag, stack) in enumerate(stacks.items(), start=1):
            t0 = time.perf_counter()
            print(
                f"[SAVE] Writing {tag} stack ({idx}/{stack_count}) | "
                f"compress={'on' if stack_compress else 'off'} | "
                f"hdf5={'on' if write_hdf5_sidecar else 'off'}..."
            )
            _save_stack_pair(
                tag=tag,
                stack_arr=stack,
                lon_vec=lon_vec,
                lat_vec=lat_vec,
                time_entries=time_entries,
                output_dir=paths.stacks,
                stack_dtype=stack_dtype,
                compress_mat=stack_compress,
                write_hdf5=write_hdf5_sidecar,
                hdf5_compress_level=hdf5_compress_level,
                meta=hsaf_strategy if (tag == "HSAF" and hsaf_strategy is not None) else None,
            )
            print(f"[SAVE] {tag} stack written in {time.perf_counter() - t0:.1f}s.")
            _emit_progress(progress_offset + idx, total_units, f"Saving stack outputs {idx}/{stack_count}", f"{idx}/{stack_count}")
        print(f"[SAVE] All stacks saved in {time.perf_counter() - save_started:.1f}s.")
        progress_offset += stack_count

    if coefficient_summary is not None and bool(getattr(cfg.io, "export_json_summary", True)):
        try:
            summary_path = write_summary_json(Path(paths.summary), coefficient_summary)
            print(f"[OUTPUT] Coefficient summary: {summary_path}")
        except Exception as exc:
            print(f"[WARN] Failed to write coefficient summary: {exc}")

    _emit_progress(total_units, total_units, "Pipeline complete", f"{Nt}/{Nt}")
    print("\n[PIPELINE] Finished.")
    print("=" * 64 + "\n")
    
    return PipelineOutput(
        paths=paths,
        time_entries=time_entries,
        plan=plan,
        stacks=stacks if cfg.io.return_stacks else {},
    )

