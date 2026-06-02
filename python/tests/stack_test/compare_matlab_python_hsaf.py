from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Tuple

import h5py
import matplotlib.pyplot as plt
import numpy as np


def _decode_h5_string(f: h5py.File, obj) -> str:
    if isinstance(obj, h5py.Reference):
        arr = np.array(f[obj])
    else:
        arr = np.array(obj)
    if arr.dtype == object and arr.size == 1 and isinstance(arr.item(), h5py.Reference):
        arr = np.array(f[arr.item()])
    if arr.dtype.kind in ("S", "U"):
        if arr.ndim == 0:
            return str(arr.item())
        return "".join(
            x.decode("utf-8") if isinstance(x, (bytes, np.bytes_)) else str(x)
            for x in arr.ravel()
        )
    if arr.dtype.kind in ("i", "u"):
        return "".join(chr(int(v)) for v in arr.ravel() if int(v) != 0)
    v = arr.item() if arr.size == 1 else arr
    if isinstance(v, (bytes, np.bytes_)):
        return v.decode("utf-8")
    return str(v)


def _clean_month_label(s: str) -> str:
    s = s.strip()
    if s.startswith("b'") and s.endswith("'"):
        s = s[2:-1]
    if s.startswith('b"') and s.endswith('"'):
        s = s[2:-1]
    return s


def load_matlab_stack(mat_path: Path) -> Tuple[np.ndarray, List[str], Dict[str, float]]:
    with h5py.File(mat_path, "r") as f:
        ewh = np.array(f["Stack/ewh"], dtype=np.float32)  # (Nt, nLat, nLon)
        t_ds = f["Stack/t"]
        months = [_clean_month_label(_decode_h5_string(f, t_ds[i, 0])) for i in range(t_ds.shape[0])]
        used = f["Stack/meta/info/used"]
        meta = {}
        for k in ("N", "P", "K", "J", "iterations"):
            if k in used:
                meta[k] = float(np.array(used[k]).squeeze())
        if "variant" in used:
            meta["variant"] = _clean_month_label(_decode_h5_string(f, used["variant"]))
    return ewh, months, meta


def load_python_stack(h5_path: Path) -> Tuple[np.ndarray, List[str]]:
    with h5py.File(h5_path, "r") as f:
        ewh = np.array(f["ewh"], dtype=np.float32)  # (nLon, nLat, Nt)
        t_ds = f["t"]
        months = []
        for i in range(t_ds.shape[0]):
            months.append(_clean_month_label(_decode_h5_string(f, t_ds[i])))
    return ewh, months


def monthly_metrics(mat_slices: np.ndarray, py_slices: np.ndarray, months: List[str]) -> Dict[str, np.ndarray]:
    n = len(months)
    rmse = np.full(n, np.nan, dtype=np.float64)
    corr = np.full(n, np.nan, dtype=np.float64)
    mean_diff = np.full(n, np.nan, dtype=np.float64)
    max_abs = np.full(n, np.nan, dtype=np.float64)
    zonal_ratio = np.full(n, np.nan, dtype=np.float64)

    for i in range(n):
        m = mat_slices[i]
        p = py_slices[i]
        ok = np.isfinite(m) & np.isfinite(p)
        if not np.any(ok):
            continue
        d = p - m
        d_ok = d[ok]
        rmse[i] = np.sqrt(np.mean(d_ok ** 2))
        mean_diff[i] = np.mean(d_ok)
        max_abs[i] = np.max(np.abs(d_ok))

        m_ok = m[ok]
        p_ok = p[ok]
        m0 = m_ok - np.mean(m_ok)
        p0 = p_ok - np.mean(p_ok)
        den = np.linalg.norm(m0) * np.linalg.norm(p0)
        corr[i] = float(np.dot(m0, p0) / den) if den > 0 else np.nan

        # Horizontal-stripe indicator: latitude-mean component energy share.
        zonal = np.nanmean(d, axis=1, keepdims=True)  # (nLat,1)
        z_var = float(np.nanvar(zonal))
        d_var = float(np.nanvar(d))
        zonal_ratio[i] = z_var / d_var if d_var > 0 else np.nan

    return {
        "rmse": rmse,
        "corr": corr,
        "mean_diff": mean_diff,
        "max_abs": max_abs,
        "zonal_ratio": zonal_ratio,
    }


def save_monthly_curve(months: List[str], rmse: np.ndarray, out_png: Path) -> None:
    x = np.arange(len(months))
    fig = plt.figure(figsize=(14, 4), dpi=150)
    ax = fig.add_subplot(1, 1, 1)
    ax.plot(x, rmse, lw=1.5)
    ax.set_title("Python vs MATLAB HSAF monthly RMSE")
    ax.set_ylabel("RMSE (mm)")
    ax.set_xlabel("Month index")
    ax.grid(alpha=0.25, ls="--")
    step = max(1, len(months) // 8)
    tick_idx = np.arange(0, len(months), step)
    ax.set_xticks(tick_idx)
    ax.set_xticklabels([months[i] for i in tick_idx], rotation=30, ha="right")
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def save_selected_months_plot(
    months: List[str],
    mat_slices: np.ndarray,
    py_slices: np.ndarray,
    rmse: np.ndarray,
    out_png: Path,
) -> None:
    idx = [0, len(months) // 2, len(months) - 1]
    if np.any(np.isfinite(rmse)):
        idx.append(int(np.nanargmax(rmse)))
    idx = sorted(set(idx))

    nrows = len(idx)
    fig, axes = plt.subplots(nrows=nrows, ncols=4, figsize=(16, 3.6 * nrows), dpi=150)
    if nrows == 1:
        axes = np.expand_dims(axes, axis=0)

    for r, i in enumerate(idx):
        m = mat_slices[i]
        p = py_slices[i]
        d = p - m
        v = np.nanpercentile(np.abs(np.concatenate([m.ravel(), p.ravel()])), 99)
        vd = np.nanpercentile(np.abs(d), 99)

        im0 = axes[r, 0].imshow(m, cmap="jet", origin="lower", vmin=-v, vmax=v, aspect="auto")
        axes[r, 0].set_title(f"MATLAB {months[i]}")
        plt.colorbar(im0, ax=axes[r, 0], fraction=0.046, pad=0.02)

        im1 = axes[r, 1].imshow(p, cmap="jet", origin="lower", vmin=-v, vmax=v, aspect="auto")
        axes[r, 1].set_title(f"Python {months[i]}")
        plt.colorbar(im1, ax=axes[r, 1], fraction=0.046, pad=0.02)

        im2 = axes[r, 2].imshow(d, cmap="RdBu_r", origin="lower", vmin=-vd, vmax=vd, aspect="auto")
        axes[r, 2].set_title(f"Diff (Py-MAT), RMSE={rmse[i]:.3f}")
        plt.colorbar(im2, ax=axes[r, 2], fraction=0.046, pad=0.02)

        zonal = np.nanmean(d, axis=1)
        axes[r, 3].plot(zonal, np.arange(len(zonal)))
        axes[r, 3].axvline(0, color="k", lw=0.8)
        axes[r, 3].set_title("Zonal mean(diff) vs lat index")
        axes[r, 3].set_xlabel("mm")
        axes[r, 3].set_ylabel("lat index")
        axes[r, 3].grid(alpha=0.25, ls="--")

    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description="Compare MATLAB vs Python HSAF stacks")
    ap.add_argument("--matlab-mat", type=Path, required=True)
    ap.add_argument("--python-h5", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    args = ap.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)

    mat_ewh, mat_months, mat_meta = load_matlab_stack(args.matlab_mat)
    py_ewh_raw, py_months = load_python_stack(args.python_h5)
    py_ewh = np.transpose(py_ewh_raw, (2, 1, 0))  # -> (Nt, nLat, nLon)

    m_map = {m: i for i, m in enumerate(mat_months)}
    p_map = {m: i for i, m in enumerate(py_months)}
    common = [m for m in mat_months if m in p_map]

    if not common:
        raise RuntimeError("No overlapping months between MATLAB and Python stacks.")

    mat_aligned = np.stack([mat_ewh[m_map[m]] for m in common], axis=0)
    py_aligned = np.stack([py_ewh[p_map[m]] for m in common], axis=0)

    metrics = monthly_metrics(mat_aligned, py_aligned, common)

    rmse = metrics["rmse"]
    corr = metrics["corr"]
    mean_diff = metrics["mean_diff"]
    max_abs = metrics["max_abs"]
    zonal_ratio = metrics["zonal_ratio"]

    worst_idx = int(np.nanargmax(rmse))

    report = args.outdir / "matlab_vs_python_hsaf_summary.txt"
    with report.open("w", encoding="utf-8") as f:
        f.write(f"MATLAB file: {args.matlab_mat}\n")
        f.write(f"Python file: {args.python_h5}\n")
        f.write(f"MATLAB shape (Nt,nLat,nLon): {mat_ewh.shape}\n")
        f.write(f"Python shape raw (nLon,nLat,Nt): {py_ewh_raw.shape}\n")
        f.write(f"Python shape aligned (Nt,nLat,nLon): {py_ewh.shape}\n")
        f.write(f"MATLAB months: {len(mat_months)}\n")
        f.write(f"Python months: {len(py_months)}\n")
        f.write(f"Common months: {len(common)}\n")
        f.write("MATLAB meta used:\n")
        for k in sorted(mat_meta):
            f.write(f"  {k}: {mat_meta[k]}\n")
        f.write("\nGlobal metrics over common months:\n")
        f.write(f"  mean RMSE: {np.nanmean(rmse):.6f}\n")
        f.write(f"  median RMSE: {np.nanmedian(rmse):.6f}\n")
        f.write(f"  mean corr: {np.nanmean(corr):.8f}\n")
        f.write(f"  mean(diff): {np.nanmean(mean_diff):.6f}\n")
        f.write(f"  mean(max|diff|): {np.nanmean(max_abs):.6f}\n")
        f.write(f"  mean zonal_ratio: {np.nanmean(zonal_ratio):.6f}\n")
        f.write("\nWorst month by RMSE:\n")
        f.write(f"  month: {common[worst_idx]}\n")
        f.write(f"  rmse: {rmse[worst_idx]:.6f}\n")
        f.write(f"  corr: {corr[worst_idx]:.8f}\n")
        f.write(f"  zonal_ratio: {zonal_ratio[worst_idx]:.6f}\n")

    csv_path = args.outdir / "matlab_vs_python_hsaf_monthly_metrics.csv"
    with csv_path.open("w", encoding="utf-8") as f:
        f.write("month,rmse,corr,mean_diff,max_abs,zonal_ratio\n")
        for m, r, c, md, ma, zr in zip(common, rmse, corr, mean_diff, max_abs, zonal_ratio):
            f.write(f"{m},{r:.8f},{c:.10f},{md:.8f},{ma:.8f},{zr:.8f}\n")

    save_monthly_curve(common, rmse, args.outdir / "matlab_vs_python_hsaf_rmse_curve.png")
    save_selected_months_plot(
        common,
        mat_aligned,
        py_aligned,
        rmse,
        args.outdir / "matlab_vs_python_hsaf_selected_months.png",
    )

    print(f"[DONE] report: {report}")
    print(f"[DONE] csv: {csv_path}")
    print(f"[DONE] plot: {args.outdir / 'matlab_vs_python_hsaf_rmse_curve.png'}")
    print(f"[DONE] plot: {args.outdir / 'matlab_vs_python_hsaf_selected_months.png'}")


if __name__ == "__main__":
    main()

