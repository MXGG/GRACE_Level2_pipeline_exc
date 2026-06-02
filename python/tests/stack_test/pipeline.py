"""
Main GRACE Level-2 processing pipeline.

This is the Python equivalent of run_pipeline.m, implementing the full
processing chain from GSM coefficients to filtered gridded products.

Optimisation changelog (2026-03-31):
  * save_stack_hdf5 sidecar – when cfg.io.save_stack_hdf5 is True (new opt-in
    flag), the pipeline writes a .h5 companion file alongside each .mat stack.
    The HDF5 file uses (nLon, nLat, 1) chunks so Preview reads a single time
    slice in one I/O call instead of materialising the full array.
  * _save_stack_pair helper – encapsulates MAT + optional HDF5 write so
    the logic isn't duplicated in the main save loop.
  * contiguousarray guard – avoids a silent re-alloc when the array is
    already C-contiguous.
  All other public contracts (run_pipeline, PipelineOutput, etc.) are
  identical to the original.
"""

import os
import sys
import importlib.util
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
except ImportError:
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
    read_gsm_month,
    replace_low_degree,
)
from grace_pipeline.infra.config import Config, load_config
from grace_pipeline.infra.datasets.grid import ensure_latlon_order, make_lonlat_vec
from grace_pipeline.infra.datasets.time_index import TimeEntry, build_time_index
from grace_pipeline.infra.io import Product, save_product
from grace_pipeline.io.stack import Stack, save_stack, save_stack_hdf5   # OPT: import new fn
from grace_pipeline.infra.runtime import ProgressBar, ensure_dir, limit_blas_threads


# ---------------------------------------------------------------------------
# Runtime helpers  (unchanged)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# HSAF worker helpers  (unchanged)
# ---------------------------------------------------------------------------

def _choose_hsaf_stack_workers(
    cfg: Config, total_slices: int, probe: Dict[str, Any]
) -> int:
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
        # Prefer one level of parallelism by default for MATLAB-aligned HSAF.
        target_inner = 1
    outer_workers = max(1, min(total_slices, safe_outer_cap, max(1, effective // target_inner)))
    inner_workers = max(1, min(target_inner, max(1, effective // outer_workers)))
    return outer_workers, inner_workers


def _prepare_hsaf_stack_config(
    cfg: Config, inner_workers: Optional[int] = None
) -> Dict[str, Any]:
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
        if hsaf_cfg.get("variant", "global") == "adaptive" and adaptive_cfg:
            filtered, _ = filter_grid_hsaf_adaptive(grid_slice, lon_vec, lat_vec, adaptive_cfg)
        else:
            filtered, _ = filter_grid_hsaf(grid_slice, lon_vec, lat_vec, hsaf_cfg)
        filtered = np.asarray(filtered)
        if np.isfinite(filtered).any() and np.nanstd(filtered) >= 1e-12:
            grid_out = filtered.astype(np.float32, copy=False)
    except Exception as exc:
        error = str(exc)
    return slice_index, np.ascontiguousarray(grid_out), time.perf_counter() - start, error


# ---------------------------------------------------------------------------
# Output structures  (unchanged)
# ---------------------------------------------------------------------------

@dataclass
class OutputPaths:
    """Standard output folder paths."""
    root: str
    monthly_mat: str
    monthly_txt: str
    stacks: str
    metrics: str
    basin: str
    plots: str
    logs: str
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


# ---------------------------------------------------------------------------
# NEW: stack save helper with optional HDF5 sidecar
# ---------------------------------------------------------------------------

def _save_stack_pair(
    tag: str,
    stack_arr: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    time_entries: List[TimeEntry],
    output_dir: str,
    stack_dtype: np.dtype,
    compress_mat: bool = False,
    write_hdf5: bool = False,
) -> None:
    """
    Write one stack as MAT and, optionally, an HDF5 sidecar.

    The HDF5 sidecar uses chunk shape (nLon, nLat, 1) so Preview can read
    any single time-slice with a single small I/O call.  The sidecar is
    written after the MAT file so that the .mat always exists even if h5py
    is unavailable.

    Args
    ----
    tag          : Product tag (e.g. "HSAF", "P4M6")
    stack_arr    : [nLon, nLat, Nt] float32 array
    lon_vec      : Longitude vector
    lat_vec      : Latitude vector
    time_entries : List[TimeEntry]
    output_dir   : Destination directory
    stack_dtype  : numpy dtype for the stack (typically np.float32)
    compress_mat : Enable scipy MATLAB compression (True on SLURM)
    write_hdf5   : Also write .h5 sidecar for fast Preview access
    """
    # OPT: avoid unnecessary re-alloc when array is already C-contiguous
    ewh = (
        stack_arr
        if stack_arr.flags["C_CONTIGUOUS"] and stack_arr.dtype == stack_dtype
        else np.ascontiguousarray(np.asarray(stack_arr, dtype=stack_dtype))
    )
    s = Stack(
        tag=tag,
        ewh=ewh,
        lon=np.asarray(lon_vec),
        lat=np.asarray(lat_vec),
        t=[te.ym for te in time_entries],
    )
    save_stack(s, output_dir, compress=compress_mat)

    if write_hdf5:
        try:
            save_stack_hdf5(s, output_dir, compress_level=1)
            print(f"[SAVE] {tag} HDF5 sidecar written.")
        except Exception as e:
            print(f"[WARN] HDF5 sidecar save failed for {tag}: {e}")


# ---------------------------------------------------------------------------
# Misc helpers  (unchanged)
# ---------------------------------------------------------------------------

def run_forward_modeling(fm_cfg: Dict[str, Any], paths: OutputPaths) -> None:
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
    try:
        script_arg = script.replace("'", "''")
        cmd = [matlab, "-batch", f"run('{script_arg}')"]
        print(f"[FM] Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, env=env)
    except Exception as e:
        print(f"[FM] External FM run failed: {e}")


def init_paths(cfg: Config) -> OutputPaths:
    out_root = cfg.path.OUTPUT
    slurm_job = os.environ.get("SLURM_JOB_ID", "")
    if slurm_job:
        out_root = os.path.join(out_root, "remote", slurm_job)
    else:
        out_root = os.path.join(out_root, "local")
    paths = OutputPaths(
        root=out_root,
        monthly_mat=os.path.join(out_root, "monthly_mat"),
        monthly_txt=os.path.join(out_root, "monthly_txt"),
        stacks=os.path.join(out_root, "stacks"),
        metrics=os.path.join(out_root, "metrics"),
        basin=os.path.join(out_root, "basin"),
        plots=os.path.join(out_root, "plots"),
        logs=os.path.join(out_root, "logs"),
        tmp=os.path.join(out_root, "tmp"),
        cache=os.path.join(out_root, "CACHE"),
    )
    for path in [
        paths.root, paths.monthly_mat, paths.monthly_txt,
        paths.stacks, paths.metrics, paths.basin,
        paths.plots, paths.logs, paths.tmp, paths.cache,
    ]:
        ensure_dir(path)
    return paths


def compute_plan(cfg: Config) -> Dict[str, Any]:
    plan = {
        "order": ["RAW"],
        "hankel_stack_mode": False,
        "hankel_input_tag": "P4M6",
    }
    filter_cfg = cfg.filter
    if filter_cfg.gaussian.enable:
        plan["order"].append("GAUSS")
    if filter_cfg.p4m6.enable:
        plan["order"].append("P4M6")
    if filter_cfg.ddk.enable:
        plan["order"].append(filter_cfg.ddk.type)
    if hasattr(filter_cfg, "fan") and filter_cfg.fan.get("enable", False):
        plan["order"].append("FAN")
    if filter_cfg.gaussian.enable and filter_cfg.p4m6.enable:
        plan["order"].append("GAUSS+P4M6")
    if filter_cfg.p4m6.enable and filter_cfg.ddk.enable:
        plan["order"].append(f"P4M6+{filter_cfg.ddk.type}")
    if filter_cfg.hankel.enable:
        if filter_cfg.hankel.stack_mode:
            plan["hankel_stack_mode"] = True
        else:
            plan["order"].append("HSAF")
        plan["hankel_input_tag"] = filter_cfg.pre_hankel_input
    return plan


# ---------------------------------------------------------------------------
# process_month  (unchanged)
# ---------------------------------------------------------------------------

def process_month(
    cfg: Config,
    time_entry: TimeEntry,
    mean_sh: Optional[SHCoefficients],
    plan: Dict,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
) -> Dict[str, np.ndarray]:
    Lmax = cfg.inversion.Lmax
    products = {}
    try:
        sh = read_gsm_month(cfg, time_entry)
    except FileNotFoundError:
        return {}
    sh = replace_low_degree(cfg, sh, time_entry)
    if mean_sh is not None and cfg.inversion.remove_mean:
        sh.C = sh.C - mean_sh.C
        sh.S = sh.S - mean_sh.S
        sh.meta["removed_mean"] = True
    if cfg.inversion.gia.get("enable", False):
        sh = apply_gia(cfg, sh, time_entry)
    raw_grid = ewh_synthesis(sh.C, sh.S, Lmax, lon_vec, lat_vec)
    products["RAW"] = raw_grid
    C, S = sh.C.copy(), sh.S.copy()
    if cfg.filter.gaussian.enable:
        C_g, S_g, _ = filter_sh_gaussian(C, S, Lmax, cfg.filter.gaussian.radius_km)
        products["GAUSS"] = ewh_synthesis(C_g, S_g, Lmax, lon_vec, lat_vec)
    if cfg.filter.p4m6.enable:
        C_p, S_p, _ = filter_sh_p4m6(C, S, Lmax, cfg.filter.p4m6.poly_deg, cfg.filter.p4m6.m_start)
        products["P4M6"] = ewh_synthesis(C_p, S_p, Lmax, lon_vec, lat_vec)
    if cfg.filter.ddk.enable:
        C_d, S_d, meta_d = filter_sh_ddk(C, S, Lmax, cfg.filter.ddk.type, cfg.filter.ddk.data_dir)
        if not meta_d.get("applied", False):
            if not hasattr(process_month, "_ddk_warned"):
                print(f"[WARN] DDK kernel not found in {cfg.filter.ddk.data_dir}. Outputs set to NaN.")
                process_month._ddk_warned = True
            grid_ddk = np.full_like(raw_grid, np.nan)
        else:
            grid_ddk = ewh_synthesis(C_d, S_d, Lmax, lon_vec, lat_vec)
            try:
                diff = np.nanstd(grid_ddk - raw_grid)
                if not np.isfinite(diff) or diff < 1e-10:
                    if not hasattr(process_month, "_ddk_same_warned"):
                        print("[WARN] DDK output appears identical to RAW. Check DDK kernel/data_dir.")
                        process_month._ddk_same_warned = True
                    grid_ddk = np.full_like(raw_grid, np.nan)
            except Exception:
                pass
        products[cfg.filter.ddk.type] = grid_ddk
    if hasattr(cfg.filter, "fan") and cfg.filter.fan.get("enable", False):
        r1 = cfg.filter.fan.get("radius1_km", 300)
        r2 = cfg.filter.fan.get("radius2_km", 300)
        C_f, S_f, _ = filter_sh_fan(C, S, Lmax, r1, r2)
        products["FAN"] = ewh_synthesis(C_f, S_f, Lmax, lon_vec, lat_vec)
    if cfg.filter.gaussian.enable and cfg.filter.p4m6.enable:
        C_gp, S_gp, _ = filter_sh_gaussian(C, S, Lmax, cfg.filter.gaussian.radius_km)
        C_gp, S_gp, _ = filter_sh_p4m6(C_gp, S_gp, Lmax, cfg.filter.p4m6.poly_deg, cfg.filter.p4m6.m_start)
        products["GAUSS+P4M6"] = ewh_synthesis(C_gp, S_gp, Lmax, lon_vec, lat_vec)
    if cfg.filter.p4m6.enable and cfg.filter.ddk.enable:
        C_pd, S_pd, _ = filter_sh_p4m6(C, S, Lmax, cfg.filter.p4m6.poly_deg, cfg.filter.p4m6.m_start)
        C_pd, S_pd, meta_pd = filter_sh_ddk(C_pd, S_pd, Lmax, cfg.filter.ddk.type, cfg.filter.ddk.data_dir)
        products[f"P4M6+{cfg.filter.ddk.type}"] = (
            ewh_synthesis(C_pd, S_pd, Lmax, lon_vec, lat_vec)
            if meta_pd.get("applied", False)
            else np.full_like(raw_grid, np.nan)
        )
    if cfg.filter.hankel.enable and not plan.get("hankel_stack_mode", False):
        input_tag = cfg.filter.pre_hankel_input
        if input_tag not in products:
            if "RAW" in products:
                if not hasattr(process_month, "_hsaf_warned"):
                    print(f"[WARN] HSAF input '{input_tag}' not found. Falling back to RAW.")
                    process_month._hsaf_warned = True
                input_tag = "RAW"
            else:
                if not hasattr(process_month, "_hsaf_warned"):
                    print(f"[WARN] HSAF input '{input_tag}' not found and RAW missing. Output set to NaN.")
                    process_month._hsaf_warned = True
                products["HSAF"] = np.full_like(raw_grid, np.nan)
                input_tag = None
        if input_tag:
            grid_in = products[input_tag]
            hsaf_cfg = vars(cfg.filter.hankel).copy()
            try:
                params = dict(hsaf_cfg.get("params", {}) or {})
            except Exception:
                params = {}
            if _hsaf_prefers_single_inner_worker(cfg):
                params["workers"] = 1
            elif getattr(cfg.parallel, "enable", False) and int(getattr(cfg.parallel, "n_workers", 1)) > 1:
                params["workers"] = 1
            elif int(params.get("workers", 0)) <= 0 and int(getattr(cfg.parallel, "n_workers", 1)) > 1:
                params["workers"] = int(getattr(cfg.parallel, "n_workers", 1))
            hsaf_cfg["params"] = params
            if (
                getattr(cfg.filter.hankel, "variant", "global") == "adaptive"
                and getattr(cfg.filter.hankel, "adaptive", [])
            ):
                grid_hsaf, _ = filter_grid_hsaf_adaptive(
                    grid_in, lon_vec, lat_vec, cfg.filter.hankel.adaptive
                )
            else:
                grid_hsaf, _ = filter_grid_hsaf(grid_in, lon_vec, lat_vec, hsaf_cfg)
            try:
                if not np.isfinite(grid_hsaf).any() or np.nanstd(grid_hsaf) < 1e-12:
                    if not hasattr(process_month, "_hsaf_zero_warned"):
                        print("[WARN] HSAF output is near-zero/empty. Falling back to input.")
                        process_month._hsaf_zero_warned = True
                    grid_hsaf = grid_in
            except Exception:
                pass
            products["HSAF"] = grid_hsaf
    return products


# ---------------------------------------------------------------------------
# run_pipeline  (HDF5 sidecar opt-in added to save section)
# ---------------------------------------------------------------------------

def run_pipeline(
    cfg_or_path=None,
    pause_event=None,
    stop_event=None,
    progress_cb=None,
    **kwargs,
) -> PipelineOutput:
    """
    Run the full GRACE Level-2 processing pipeline.

    Args
    ----
    cfg_or_path : Config object, path to config file, or None (use defaults)
    **kwargs    : Additional configuration overrides

    Returns
    -------
    PipelineOutput with results.
    """
    if isinstance(cfg_or_path, Config):
        cfg = cfg_or_path
    elif isinstance(cfg_or_path, (str, Path)):
        cfg = load_config(cfg_or_path)
    else:
        cfg = load_config()

    print("\n" + "=" * 64)
    print("  GRACE Level-2 Pipeline (Python)")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 64 + "\n")

    paths = init_paths(cfg)
    print(f"[OUTPUT] {paths.root}")

    time_entries = build_time_index(cfg)
    if not time_entries:
        raise ValueError("No time entries found. Check GFC directory or time configuration.")

    Nt = len(time_entries)
    print(f"[TIME] {time_entries[0].ym} -> {time_entries[-1].ym} (Nt={Nt})")

    plan = compute_plan(cfg)
    print(f"[PLAN] order = {' -> '.join(plan['order'])}")
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
    if getattr(cfg.parallel, "enable", False):
        cfg.parallel.n_workers = runtime_probe["effective_workers"]

    lon_vec, lat_vec = make_lonlat_vec(cfg)
    nLon, nLat = len(lon_vec), len(lat_vec)

    mean_sh = None
    if cfg.inversion.remove_mean:
        print("[INV] Computing mean SH coefficients...")
        mean_sh = compute_mean_sh(cfg, time_entries)

    def _save_monthly_products(products, ym):
        if not products:
            return
        try:
            for tag, grid in products.items():
                if cfg.io.save_monthly_mat:
                    out_dir = os.path.join(paths.monthly_mat, tag)
                    save_product(
                        Product(tag=tag, ym=ym, ewh=grid, lon=lon_vec, lat=lat_vec),
                        out_dir,
                        format="mat",
                    )
                if cfg.io.export_txt:
                    out_dir = os.path.join(paths.monthly_txt, tag)
                    save_product(
                        Product(tag=tag, ym=ym, ewh=grid, lon=lon_vec, lat=lat_vec),
                        out_dir,
                        format="txt",
                    )
        except Exception as e:
            print(f"[WARN] Monthly save failed for {ym}: {e}")

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

    stacks = {
        tag: np.full((nLon, nLat, Nt), np.nan, dtype=stack_dtype)
        for tag in plan["order"]
        if tag in stack_tags
    }

    print("\n[PROCESSING] Monthly loop...")
    use_parallel = cfg.parallel.enable and cfg.parallel.n_workers > 1
    if use_parallel:
        limit_blas_threads()

    if getattr(sys, "frozen", False):
        allow_frozen_parallel = False
        try:
            allow_frozen_parallel = bool(
                getattr(cfg, "perf", {}).get("allow_frozen_parallel", False)
            )
        except Exception:
            allow_frozen_parallel = False
        if use_parallel and not allow_frozen_parallel:
            print("[WARN] Parallel processing disabled in frozen executable (using sequential mode)")
            cfg.parallel.enable = False
            cfg.parallel.n_workers = 1
            use_parallel = False
        elif use_parallel:
            frozen_max = _get_frozen_max_workers(cfg)
            if frozen_max > 0 and cfg.parallel.n_workers > frozen_max:
                print(f"[WARN] Capping parallel workers to {frozen_max} for frozen executable")
                cfg.parallel.n_workers = frozen_max
            if cfg.parallel.n_workers < 2:
                cfg.parallel.enable = False
                use_parallel = False

    disable_tqdm = not getattr(sys.stdout, "isatty", lambda: False)()

    extra_units = 0
    if plan.get("hankel_stack_mode", False):
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
                    for tag, grid in products.items():
                        if tag in stacks:
                            stacks[tag][:, :, k] = np.asarray(grid, dtype=stack_dtype)
                    try:
                        _save_monthly_products(products, time_entries[k].ym)
                    except Exception:
                        pass
                    products.clear()
                except Exception as e:
                    print(f"[ERROR] Month {time_entries[k].ym}: {e}")
                done += 1
                _emit_progress(done, total_units, "Running monthly loop", f"{done}/{Nt}")
    else:
        if (
            getattr(cfg.filter, "hankel", None)
            and getattr(cfg.filter.hankel, "enable", False)
            and getattr(cfg.filter.hankel, "engine", "matlab_v3") in ("matlab", "matlab_v3", "hsa")
        ):
            try:
                params = (
                    cfg.filter.hankel.params if hasattr(cfg.filter.hankel, "params") else {}
                )
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
                for tag, grid in products.items():
                    if tag in stacks:
                        stacks[tag][:, :, k] = np.asarray(grid, dtype=stack_dtype)
                try:
                    _save_monthly_products(products, te.ym)
                except Exception:
                    pass
                products.clear()
            except Exception as e:
                print(f"[ERROR] Month {te.ym}: {e}")
            _emit_progress(k + 1, total_units, "Running monthly loop", f"{k + 1}/{Nt}")

    # ── HSAF stack mode ───────────────────────────────────────────────────
    progress_offset = Nt
    if plan.get("hankel_stack_mode", False):
        print("\n[HSAF] Stack mode processing...")
        input_tag = plan["hankel_input_tag"]
        if input_tag not in stacks and "RAW" in stacks:
            print(f"[WARN] HSAF stack input '{input_tag}' not found. Falling back to RAW.")
            input_tag = "RAW"
        if input_tag in stacks:
            stack_in = stacks[input_tag]
            n_stack = int(stack_in.shape[2]) if stack_in.ndim == 3 else 1
            adaptive_cfg = (
                getattr(cfg.filter.hankel, "adaptive", [])
                if getattr(cfg.filter.hankel, "variant", "global") == "adaptive"
                else None
            )
            stack_started = time.perf_counter()
            last_logged = {"done": 0}
            worker_count, inner_worker_count = _choose_hsaf_outer_inner_workers(
                cfg, n_stack, runtime_probe
            )
            local_stack_mode = not _should_use_outer_hsaf_slice_parallel(
                cfg, n_stack, worker_count, runtime_probe
            )

            def _record_stack_slice(done: int, total: int, wc: int) -> None:
                report_step = max(1, total // 10)
                avg_s = float((time.perf_counter() - stack_started) / max(1, done))
                if done == total or done == 1 or (done - last_logged["done"]) >= report_step:
                    print(
                        f"[HSAF][stack] {done}/{total} slices processed | "
                        f"workers={wc} | avg={avg_s:.2f}s/slice"
                    )
                    last_logged["done"] = done
                _emit_progress(
                    progress_offset + done,
                    total_units,
                    f"HSAF stack {done}/{total}",
                    f"{done}/{total}",
                )

            if local_stack_mode:
                hsaf_cfg = _prepare_hsaf_stack_config(
                    cfg,
                    inner_workers=inner_worker_count,
                )
                inner_workers = int(hsaf_cfg.get("params", {}).get("workers", 1) or 1)
                print(
                    f"[HSAF] Filtering {n_stack} stack slices from {input_tag} "
                    f"with workers={inner_workers} (in-process stack loop)."
                )
                if inner_workers > 1:
                    limit_blas_threads()

                def _progress(done: int, total: int) -> None:
                    _record_stack_slice(done, total, inner_workers)

                if (
                    getattr(cfg.filter.hankel, "variant", "global") == "adaptive"
                    and adaptive_cfg
                ):
                    stack_hsaf, _ = filter_grid_hsaf_adaptive(
                        stack_in, lon_vec, lat_vec, adaptive_cfg
                    )
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
                stacks["HSAF"] = np.ascontiguousarray(
                    np.asarray(stack_hsaf, dtype=stack_dtype)
                )
            else:
                hsaf_cfg = _prepare_hsaf_stack_config(cfg, inner_workers=inner_worker_count)
                inner_workers = int(hsaf_cfg.get("params", {}).get("workers", 1) or 1)
                executor_cls = ProcessPoolExecutor
                print(
                    f"[HSAF] Filtering {n_stack} stack slices from {input_tag} "
                    f"with outer_workers={worker_count}, inner_workers={inner_workers} "
                    f"({executor_cls.__name__})."
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
                            print(
                                f"[WARN] HSAF stack slice {slice_idx + 1}/{n_stack} failed: {error}"
                            )
                        stack_hsaf[:, :, slice_idx] = np.asarray(
                            filtered_slice, dtype=stack_dtype
                        )
                        done += 1
                        _record_stack_slice(done, n_stack, worker_count)

                stacks["HSAF"] = np.ascontiguousarray(
                    np.asarray(stack_hsaf, dtype=stack_dtype)
                )
            print(f"[HSAF] Stack mode filter complete in {time.perf_counter() - stack_started:.1f}s.")
        progress_offset += Nt

    if plan.get("hankel_stack_mode", False) and "HSAF" in stacks:
        if cfg.io.save_monthly_mat or cfg.io.export_txt:
            print("[HSAF] Writing monthly products from stack...")
            export_started = time.perf_counter()
            for k, te in enumerate(time_entries):
                try:
                    grid = stacks["HSAF"][:, :, k]
                    _save_monthly_products({"HSAF": grid}, te.ym)
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
            print(
                f"[HSAF] Monthly stack export complete in {time.perf_counter() - export_started:.1f}s."
            )
        progress_offset += Nt

    # Basin analysis (unchanged)
    try:
        basin_cfg = cfg.basin if isinstance(cfg.basin, dict) else cfg.basin.__dict__
    except Exception:
        basin_cfg = {}
    if basin_cfg.get("analysis_enable", False) and basin_cfg.get("boundary_file"):
        try:
            from grace_pipeline.basin import (
                read_boundary, make_mask, extract_basin_ts, fit_seasonal_trend,
            )
            bfile = basin_cfg.get("boundary_file")
            name_field = basin_cfg.get("name_field", "Name")
            target_name = (
                basin_cfg.get("name", "").strip() if basin_cfg.get("name") else ""
            )
            basins = read_boundary(bfile, name_field=name_field)
            if target_name:
                basins = [b for b in basins if b.name == target_name]
            if basins is not None and len(basins) > 0:
                t_years = np.array(
                    [te.year + (te.month - 0.5) / 12.0 for te in time_entries],
                    dtype=float,
                )
                for b in basins:
                    mask = make_mask(b, lon_vec, lat_vec)
                    ts_dict = extract_basin_ts(stacks, mask, lon_vec, lat_vec)
                    out_csv = os.path.join(paths.basin, f"basin_{b.name}_ts.csv")
                    with open(out_csv, "w", encoding="utf-8") as f:
                        f.write("ym," + ",".join(ts_dict.keys()) + "\n")
                        for i, te in enumerate(time_entries):
                            row = [te.ym] + [f"{ts_dict[tag][i]:.6f}" for tag in ts_dict]
                            f.write(",".join(row) + "\n")
                    out_stat = os.path.join(paths.basin, f"basin_{b.name}_stats.csv")
                    with open(out_stat, "w", encoding="utf-8") as f:
                        f.write("tag,trend,amp_ann,amp_semi,const\n")
                        for tag, ts in ts_dict.items():
                            stat = fit_seasonal_trend(t_years, ts)
                            f.write(
                                f"{tag},{stat.get('trend', np.nan):.6f},"
                                f"{stat.get('amp_ann', np.nan):.6f},"
                                f"{stat.get('amp_semi', np.nan):.6f},"
                                f"{stat.get('const', np.nan):.6f}\n"
                            )
                    print(f"[BASIN] Saved basin results for {b.name}")
        except Exception as e:
            print(f"[WARN] Basin analysis failed: {e}")

    # ── Stack save  (OPT: optional HDF5 sidecar via cfg.io.save_stack_hdf5) ──
    if cfg.io.save_stack_mat and stacks:
        print("\n[SAVE] Saving stacks...")
        save_started = time.perf_counter()
        stack_count = len(stacks)
        # Compress MAT only on SLURM (matches original behaviour).
        stack_compress = bool(runtime_probe.get("slurm_job", False))
        # New opt-in: write HDF5 sidecar for fast Preview slice reads.
        write_hdf5_sidecar = bool(getattr(cfg.io, "save_stack_hdf5", False))
        if write_hdf5_sidecar:
            print("[SAVE] HDF5 sidecar enabled — Preview will use O(1) slice reads.")

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
            )
            print(f"[SAVE] {tag} stack written in {time.perf_counter() - t0:.1f}s.")
            _emit_progress(
                progress_offset + idx,
                total_units,
                f"Saving stack outputs {idx}/{stack_count}",
                f"{idx}/{stack_count}",
            )
        print(f"[SAVE] All stacks saved in {time.perf_counter() - save_started:.1f}s.")
        progress_offset += stack_count

    _emit_progress(total_units, total_units, "Pipeline complete", f"{Nt}/{Nt}")
    print("\n[PIPELINE] Finished.")
    print("=" * 64 + "\n")

    return PipelineOutput(
        paths=paths,
        time_entries=time_entries,
        plan=plan,
        stacks=stacks if cfg.io.return_stacks else {},
    )
