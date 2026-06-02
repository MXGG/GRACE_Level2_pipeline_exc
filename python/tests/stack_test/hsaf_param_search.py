#!/usr/bin/env python3
"""
HSAF global-parameter search against Mascon reference.

Usage example (from repo root):
  set PYTHONPATH=python
  python python/tests/stack_test/hsaf_param_search.py ^
    --p4m6-stack output/local/stacks/P4M6_stack.h5 ^
    --mascon-nc data/Reference/Mascon/CSR_GRACE_GRACE-FO_RL06_Mascons_all-corrections_v02.nc ^
    --out-dir output/local/hsaf_tuning ^
    --sample-count 16 ^
    --outer-workers 8
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from itertools import product
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import h5py
import netCDF4 as nc
import numpy as np
import scipy.io as sio

from concurrent.futures import ProcessPoolExecutor, as_completed

from grace_pipeline.filters.hsaf import filter_grid_hsaf


@dataclass(frozen=True)
class Combo:
    N: int
    P: int
    K: int
    J: int

    def key(self) -> str:
        return f"N{self.N}_P{self.P}_K{self.K}_J{self.J}"


def _decode_time_values(values: np.ndarray) -> List[str]:
    out: List[str] = []
    for v in np.asarray(values).reshape(-1):
        if isinstance(v, (bytes, np.bytes_)):
            out.append(v.decode("utf-8", errors="ignore"))
        else:
            out.append(str(v))
    return out


def _load_stack(path: Path) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[str]]:
    ext = path.suffix.lower()
    if ext in (".h5", ".hdf5", ".hdf", ".he5"):
        with h5py.File(path, "r") as f:
            if "ewh" in f:
                ewh = np.asarray(f["ewh"][...], dtype=np.float32)
                lon = np.asarray(f["lon"][...]).reshape(-1)
                lat = np.asarray(f["lat"][...]).reshape(-1)
                t = _decode_time_values(f["t"][...])
                return ewh, lon, lat, t
            if "Stack" in f and "ewh" in f["Stack"]:
                # MATLAB v7.3 struct layout: Stack/ewh is usually [Nt, nLat, nLon]
                e = np.asarray(f["Stack"]["ewh"][...], dtype=np.float32)
                if e.ndim == 3 and e.shape[0] < e.shape[-1]:
                    e = np.transpose(e, (2, 1, 0))
                lon = np.asarray(f["Stack"]["lon"][...]).reshape(-1)
                lat = np.asarray(f["Stack"]["lat"][...]).reshape(-1)
                t = _decode_time_values(f["Stack"]["t"][...])
                return e, lon, lat, t
        raise RuntimeError(f"Unsupported HDF5 stack layout: {path}")

    if ext == ".mat":
        mat = sio.loadmat(
            str(path),
            squeeze_me=True,
            struct_as_record=False,
            variable_names=["ewh", "lon", "lat", "t", "Stack"],
        )
        if "ewh" in mat:
            ewh = np.asarray(mat["ewh"], dtype=np.float32)
            lon = np.asarray(mat["lon"]).reshape(-1)
            lat = np.asarray(mat["lat"]).reshape(-1)
            t = _decode_time_values(np.asarray(mat["t"]))
            if ewh.ndim == 2:
                ewh = ewh[:, :, None]
            return ewh, lon, lat, t
        if "Stack" in mat:
            st = mat["Stack"]
            ewh = np.asarray(st.ewh, dtype=np.float32)
            if ewh.ndim == 3 and ewh.shape[0] < ewh.shape[-1]:
                ewh = np.transpose(ewh, (2, 1, 0))
            lon = np.asarray(st.lon).reshape(-1)
            lat = np.asarray(st.lat).reshape(-1)
            t = _decode_time_values(np.asarray(st.t))
            return ewh, lon, lat, t
        raise RuntimeError(f"Unsupported MAT stack layout: {path}")

    raise RuntimeError(f"Unsupported stack file extension: {path.suffix}")


def _month_to_mid_date(ym: str) -> datetime:
    return datetime.strptime(ym + "-15", "%Y-%m-%d")


def _mascon_month_indices(
    mascon_nc: Path,
    months: Sequence[str],
    tolerance_days: int = 45,
) -> List[Optional[int]]:
    with nc.Dataset(str(mascon_nc)) as ds:
        tvar = ds.variables["time"]
        units = getattr(tvar, "units", None) or getattr(tvar, "Units", None)
        cal = getattr(tvar, "calendar", "gregorian")
        ref_dt = [datetime(x.year, x.month, x.day) for x in nc.num2date(tvar[:], units=units, calendar=cal)]
    out: List[Optional[int]] = []
    for ym in months:
        dt = _month_to_mid_date(ym)
        d = np.array([abs((r - dt).days) for r in ref_dt], dtype=np.int32)
        i = int(np.argmin(d))
        out.append(i if int(d[i]) <= int(tolerance_days) else None)
    return out


def _mascon_slice_to_1deg_lonlat(m: np.ndarray) -> np.ndarray:
    # m: [nLat=720, nLon=1440], units cm
    x = np.asarray(m, dtype=np.float64)
    x *= 10.0  # cm -> mm
    # lon shift from [0,360) to [-180,180)
    x = np.concatenate([x[:, 720:], x[:, :720]], axis=1)
    # 0.25° -> 1.0° block mean
    x = x.reshape(180, 4, 360, 4).mean(axis=(1, 3))  # [lat, lon]
    return x.T  # [lon, lat]


def _build_reference_grids(
    mascon_nc: Path,
    month_indices: Sequence[Optional[int]],
) -> Dict[int, np.ndarray]:
    needed = sorted({int(i) for i in month_indices if i is not None})
    out: Dict[int, np.ndarray] = {}
    if not needed:
        return out
    with nc.Dataset(str(mascon_nc)) as ds:
        var = ds.variables["lwe_thickness"]
        for i in needed:
            m = var[i, :, :]
            if isinstance(m, np.ma.MaskedArray):
                m = m.filled(np.nan)
            out[i] = _mascon_slice_to_1deg_lonlat(m)
    return out


def _select_sample_indices(
    valid_indices: Sequence[int],
    sample_count: int,
) -> List[int]:
    if sample_count <= 0 or sample_count >= len(valid_indices):
        return list(valid_indices)
    pos = np.linspace(0, len(valid_indices) - 1, sample_count).round().astype(int)
    picked = sorted({valid_indices[int(p)] for p in pos})
    return picked


def _eval_slice(
    grid_slice: np.ndarray,
    ref_slice: np.ndarray,
    lon: np.ndarray,
    lat: np.ndarray,
    combo: Combo,
) -> Tuple[float, float, float]:
    cfg = {
        "engine": "matlab_v3",
        "variant": "global",
        "params": {
            "N": int(combo.N),
            "P": int(combo.P),
            "K": int(combo.K),
            "J": int(combo.J),
            "iterations": 1,
            "workers": 1,
        },
    }
    t0 = time.perf_counter()
    out, _ = filter_grid_hsaf(grid_slice, lon, lat, cfg)
    dt = time.perf_counter() - t0

    x = np.asarray(out, dtype=np.float64)
    r = np.asarray(ref_slice, dtype=np.float64)
    m = np.isfinite(x) & np.isfinite(r)
    if not np.any(m):
        return float("nan"), float("nan"), dt
    d = x[m] - r[m]
    rmse = float(np.sqrt(np.mean(d * d)))
    sx = float(np.std(x[m]))
    sr = float(np.std(r[m]))
    corr = float(np.corrcoef(x[m], r[m])[0, 1]) if sx > 0 and sr > 0 else float("nan")
    return rmse, corr, dt


def _eval_combo(
    combo: Combo,
    stack: np.ndarray,
    refs: Dict[int, np.ndarray],
    month_to_ref: Sequence[Optional[int]],
    eval_indices: Sequence[int],
    lon: np.ndarray,
    lat: np.ndarray,
    outer_workers: int,
) -> Dict[str, Any]:
    tasks: List[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Combo]] = []
    for k in eval_indices:
        ri = month_to_ref[k]
        if ri is None:
            continue
        ref = refs.get(int(ri))
        if ref is None:
            continue
        tasks.append(
            (
                np.ascontiguousarray(stack[:, :, k], dtype=np.float64),
                np.ascontiguousarray(ref, dtype=np.float64),
                np.asarray(lon),
                np.asarray(lat),
                combo,
            )
        )

    rmses: List[float] = []
    corrs: List[float] = []
    times: List[float] = []

    if not tasks:
        return {
            "combo": combo.key(),
            "N": combo.N,
            "P": combo.P,
            "K": combo.K,
            "J": combo.J,
            "n_eval": 0,
            "mean_rmse": float("nan"),
            "median_rmse": float("nan"),
            "mean_corr": float("nan"),
            "mean_time_s": float("nan"),
            "wall_time_s": 0.0,
        }

    wall0 = time.perf_counter()
    if outer_workers > 1 and len(tasks) > 1:
        with ProcessPoolExecutor(max_workers=min(outer_workers, len(tasks))) as ex:
            futs = [ex.submit(_eval_slice, *t) for t in tasks]
            for fut in as_completed(futs):
                rmse, corr, dt = fut.result()
                rmses.append(rmse)
                corrs.append(corr)
                times.append(dt)
    else:
        for t in tasks:
            rmse, corr, dt = _eval_slice(*t)
            rmses.append(rmse)
            corrs.append(corr)
            times.append(dt)
    wall = time.perf_counter() - wall0

    ra = np.asarray(rmses, dtype=float)
    ca = np.asarray(corrs, dtype=float)
    ta = np.asarray(times, dtype=float)
    valid = np.isfinite(ra)

    return {
        "combo": combo.key(),
        "N": combo.N,
        "P": combo.P,
        "K": combo.K,
        "J": combo.J,
        "n_eval": int(np.sum(valid)),
        "mean_rmse": float(np.nanmean(ra[valid])) if np.any(valid) else float("nan"),
        "median_rmse": float(np.nanmedian(ra[valid])) if np.any(valid) else float("nan"),
        "mean_corr": float(np.nanmean(ca[valid])) if np.any(valid) else float("nan"),
        "mean_time_s": float(np.nanmean(ta[valid])) if np.any(valid) else float("nan"),
        "wall_time_s": float(wall),
    }


def _parse_int_list(s: str) -> List[int]:
    vals: List[int] = []
    for x in str(s).split(","):
        x = x.strip()
        if not x:
            continue
        vals.append(int(x))
    if not vals:
        raise ValueError(f"Empty integer list: {s}")
    return vals


def _build_combos(Ns: Sequence[int], Ps: Sequence[int], Ks: Sequence[int], Js: Sequence[int]) -> List[Combo]:
    combos: List[Combo] = []
    for N, P, K, J in product(Ns, Ps, Ks, Js):
        if N < 4 or P < 2 or K < 1 or J < 1:
            continue
        if K > P:
            continue
        if N <= P:
            # keep Hankel geometry reasonable
            continue
        combos.append(Combo(int(N), int(P), int(K), int(J)))
    return combos


def main() -> None:
    parser = argparse.ArgumentParser(description="HSAF global parameter search (non-iterative).")
    parser.add_argument("--p4m6-stack", type=Path, required=True, help="Path to P4M6 stack (.h5 or .mat)")
    parser.add_argument("--mascon-nc", type=Path, required=True, help="Path to Mascon NetCDF")
    parser.add_argument("--out-dir", type=Path, required=True, help="Output directory for tuning results")
    parser.add_argument("--N-list", type=str, default="24,30,36")
    parser.add_argument("--P-list", type=str, default="8,10,12")
    parser.add_argument("--K-list", type=str, default="4,6,8")
    parser.add_argument("--J-list", type=str, default="1,2")
    parser.add_argument("--sample-count", type=int, default=16, help="How many matched months to evaluate (0=all)")
    parser.add_argument("--tolerance-days", type=int, default=45)
    parser.add_argument("--outer-workers", type=int, default=max(1, (os.cpu_count() or 4) // 2))
    parser.add_argument("--topk", type=int, default=10)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    t_start = time.perf_counter()

    stack, lon, lat, months = _load_stack(args.p4m6_stack)
    month_to_ref = _mascon_month_indices(args.mascon_nc, months, tolerance_days=args.tolerance_days)
    valid_indices = [i for i, ri in enumerate(month_to_ref) if ri is not None]
    eval_indices = _select_sample_indices(valid_indices, int(args.sample_count))
    refs = _build_reference_grids(args.mascon_nc, month_to_ref)

    Ns = _parse_int_list(args.N_list)
    Ps = _parse_int_list(args.P_list)
    Ks = _parse_int_list(args.K_list)
    Js = _parse_int_list(args.J_list)
    combos = _build_combos(Ns, Ps, Ks, Js)
    if not combos:
        raise RuntimeError("No valid parameter combinations after constraints (N>P, K<=P).")

    print(
        f"[TUNE] months_total={len(months)} matched={len(valid_indices)} eval={len(eval_indices)} "
        f"combos={len(combos)} outer_workers={args.outer_workers}"
    )

    results: List[Dict[str, Any]] = []
    for i, combo in enumerate(combos, start=1):
        print(f"[TUNE] {i}/{len(combos)} {combo.key()} ...")
        res = _eval_combo(
            combo=combo,
            stack=stack,
            refs=refs,
            month_to_ref=month_to_ref,
            eval_indices=eval_indices,
            lon=lon,
            lat=lat,
            outer_workers=max(1, int(args.outer_workers)),
        )
        results.append(res)
        print(
            f"        mean_rmse={res['mean_rmse']:.4f} mean_corr={res['mean_corr']:.6f} "
            f"mean_time={res['mean_time_s']:.3f}s"
        )

    valid_results = [r for r in results if np.isfinite(r["mean_rmse"])]
    valid_results.sort(key=lambda r: (r["mean_rmse"], -r["mean_corr"]))

    csv_path = args.out_dir / "hsaf_param_search_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "combo",
                "N",
                "P",
                "K",
                "J",
                "n_eval",
                "mean_rmse",
                "median_rmse",
                "mean_corr",
                "mean_time_s",
                "wall_time_s",
            ],
        )
        writer.writeheader()
        writer.writerows(results)

    summary = {
        "stack_path": str(args.p4m6_stack),
        "mascon_path": str(args.mascon_nc),
        "months_total": len(months),
        "matched_months": len(valid_indices),
        "eval_months": len(eval_indices),
        "eval_month_labels": [months[i] for i in eval_indices],
        "tolerance_days": int(args.tolerance_days),
        "grid": {
            "N_list": Ns,
            "P_list": Ps,
            "K_list": Ks,
            "J_list": Js,
        },
        "combo_count": len(combos),
        "topk": valid_results[: max(1, int(args.topk))],
        "elapsed_s": float(time.perf_counter() - t_start),
    }
    json_path = args.out_dir / "hsaf_param_search_summary.json"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[TUNE] done in {summary['elapsed_s']:.1f}s")
    if valid_results:
        best = valid_results[0]
        print(
            "[TUNE] best:",
            f"{best['combo']} mean_rmse={best['mean_rmse']:.4f} "
            f"mean_corr={best['mean_corr']:.6f} mean_time={best['mean_time_s']:.3f}s",
        )
    print(f"[TUNE] results: {csv_path}")
    print(f"[TUNE] summary: {json_path}")


if __name__ == "__main__":
    main()

