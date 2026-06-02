"""Process-safe workers for leakage correction."""

from typing import Any, Dict, Tuple

import numpy as np

from grace_pipeline.domain.leakage import LeakageFilterOptions, fm_correct_month


def leakage_fm_month_worker(job: Dict[str, Any]) -> Tuple[int, np.ndarray, int, float]:
    """
    Process-safe worker for one FM month.
    Keep this at module scope so it can be pickled on Windows spawn.
    """
    opts = LeakageFilterOptions(**dict(job.get("options", {}) or {}))
    corr, info = fm_correct_month(
        np.asarray(job["gobs"], dtype=float),
        np.asarray(job["mask"], dtype=bool),
        np.asarray(job["lon_vec"], dtype=float),
        np.asarray(job["lat_vec"], dtype=float),
        opts,
        n_iter=int(job.get("n_iter", 40)),
        tol_rmse_mm=float(job.get("tol", 0.01)),
        update_mode=str(job.get("update_mode", "global")),
        init_mode=str(job.get("init_mode", "obs")),
        mass_conservation=str(job.get("mass_mode", "legacy_land_mean_fill")),
        convergence_metric=str(job.get("conv_metric", "land_weighted_mean")),
        accel=float(job.get("accel", 1.1)),
        prefilter_obs=bool(job.get("prefilter_obs", False)),
        min_iter=int(job.get("min_iter", 3)),
        stagnation_patience=int(job.get("patience", 8)),
        min_improve=float(job.get("min_improve", 1.0e-4)),
        output_mode=str(job.get("output_mode", "preserve_observed_outside_mask")),
        iter_cb=None,
        should_continue=None,
    )
    n_used = int(np.asarray(info.get("nIter", [0])).reshape(-1)[0])
    final_err = float(np.asarray(info.get("final_rmse", [np.nan])).reshape(-1)[0])
    return int(job.get("k", 1)), np.asarray(corr, dtype=float), n_used, final_err
