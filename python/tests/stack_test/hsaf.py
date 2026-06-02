"""
HSAF (Hankel-SVD Adaptive Filter) for grid-domain filtering.

This filter works directly on spatial grids rather than SH coefficients,
using Hankel matrix SVD for noise reduction.

Optimisation changelog (2026-03-31):
  htls_pm  – SVD1 uses full_matrices=False (saves ~30 % compute on
              the right-singular-vector block we never use);
             – Both SVD calls carry check_finite=False (skip redundant
               input-validation copy);
             – Z-matrix built with vectorised broadcasting instead of
               a Python vstack loop.
  hsaf_1d  – Anti-diagonal averaging replaced by np.add.at; removes
              O(N×P) pure-Python loop entirely.
"""

import numpy as np
from scipy.linalg import hankel, svd
from typing import Callable, Tuple, Dict, Any, Optional, List

from grace_pipeline.core.grid import ensure_latlon_order


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fill_nan_profile(profile: np.ndarray) -> np.ndarray:
    mask = np.isfinite(profile)
    if mask.all():
        return profile
    if mask.sum() < 2:
        return profile
    idx = np.arange(profile.size)
    filled = profile.copy()
    filled[~mask] = np.interp(idx[~mask], idx[mask], profile[mask])
    return filled


def _fill_nan_grid(grid: np.ndarray) -> np.ndarray:
    g = grid.copy()
    if g.ndim != 2:
        return g
    for j in range(g.shape[1]):
        g[:, j] = _fill_nan_profile(g[:, j])
    return g


# ---------------------------------------------------------------------------
# Core HTLS / H_RCS
# ---------------------------------------------------------------------------

def htls_pm(x: np.ndarray, Ts: float, p: int, k: int):
    """
    Port of MATLAB HTLS_PM for Hankel-SSA parameters.
    Returns Amp, alfa, freq, theta, Ex, Ex_flag.

    Optimisations vs original
    -------------------------
    * SVD1: full_matrices=False  – for a p×(N-p+1) matrix we only need the
      first k right singular vectors (k ≤ p ≤ N-p+1 in typical usage), so
      full_matrices=False skips computing the trailing (N-p+1-p) columns of V
      that are never read.  Result is identical for all k ≤ min(p, N-p+1).
    * check_finite=False on both SVDs – scipy normally allocates a clean copy
      to validate the input; skipping saves one alloc+scan cycle per call.
    * Z-matrix is built with vectorised broadcasting (l[:,None]**n[None,:])
      instead of a Python list-comprehension + vstack, cutting per-call
      overhead from O(k) iterator frames to a single numpy ufunc call.
    """
    x = np.asarray(x, dtype=float).ravel()
    N = x.size
    p = int(p)
    k = int(k)
    if N < max(p + 1, 3) or p < 2 or k < 1:
        raise ValueError("HTLS_PM: invalid dimensions")

    X1 = hankel(x[:p], x[p - 1:])
    # OPT: full_matrices=False — we only consume Vh[:k, :], so skip the
    # trailing (N-p+1 - min(p,N-p+1)) right singular vectors entirely.
    U, S, Vh = svd(X1, full_matrices=False, check_finite=False)
    Ex = S.copy()
    Ex_flag = int(np.sum(Ex > 0.001))

    Ux = Vh.T                          # (N-p+1) × min(p, N-p+1)
    if Ux.shape[1] == 0:
        raise ValueError("HTLS_PM: empty SVD")
    k = min(k, Ux.shape[1])
    if k < 1:
        raise ValueError("HTLS_PM: k too small")

    Us = Ux[:, :k]
    U1 = Us[:-1, :]
    U2 = Us[1:, :]
    D12 = np.hstack([U1, U2])          # (p-1) × 2k

    # Must retain full 2k right singular vectors for the null-space partition
    # (D12 may be rank-deficient), so full_matrices=True is required here.
    Ud, Sd, Vhd = svd(D12, full_matrices=True, check_finite=False)
    UD = Vhd.T                         # (2k) × (2k)
    U12 = UD[:k, k: 2 * k]
    U22 = UD[k: 2 * k, k: 2 * k]

    fai = -U12 @ np.linalg.pinv(U22)
    l = np.linalg.eigvals(fai)

    alfa = np.log(np.abs(l)) / Ts
    freq = np.arctan2(l.imag, l.real) / (2 * np.pi * Ts)

    n = np.arange(N)
    # OPT: vectorised outer-power instead of vstack([li**n for li in l]).T
    # l has shape (k,); n has shape (N,); result Z has shape (N, k).
    Z = (l[:, None] ** n[None, :]).T   # (N, k)
    ck, *_ = np.linalg.lstsq(Z, x, rcond=None)

    Amp = np.abs(ck)
    theta = np.arctan2(ck.imag, ck.real)
    return Amp, alfa, freq, theta, Ex, Ex_flag


def h_rcs(x: np.ndarray, Ts: float, p: int, k: int):
    """
    Port of MATLAB H_RCs.  Returns Amp, alfa, freq, theta, Y, Ex, Ex_flag.
    Unchanged from original except for htls_pm internal optimisations.
    """
    Amp, alfa, freq, theta, Ex, Ex_flag = htls_pm(x, Ts, p, k)
    if not (
        np.isfinite(Amp).all()
        and np.isfinite(alfa).all()
        and np.isfinite(freq).all()
        and np.isfinite(theta).all()
    ):
        raise ValueError("H_RCs: non-finite parameters")
    idx = np.argsort(freq)
    Amp = Amp[idx]
    alfa = alfa[idx]
    freq = freq[idx]
    theta = theta[idx]

    N = len(x)
    n = np.arange(N)
    n2 = np.tile(n, (len(freq), 1))
    exp_term = np.exp(alfa[:, None] * n2 * Ts)
    Y = (Amp[:, None] * exp_term) * np.cos(
        2 * np.pi * Ts * freq[:, None] * n2 + theta[:, None]
    )
    if not np.isfinite(Y).all():
        raise ValueError("H_RCs: non-finite reconstruction")
    return Amp, alfa, freq, theta, Y, Ex, Ex_flag


# ---------------------------------------------------------------------------
# Bidirectional sliding-window HSA
# ---------------------------------------------------------------------------

def hsa_bidirectional_map(
    grid: np.ndarray,
    Ts: float,
    window_size: int,
    p: int,
    order: int,
    buffer: int,
    workers: int = 0,
) -> np.ndarray:
    """
    Port of MATLAB HSA.m (bidirectional sliding window) for a single map.
    grid : [nLon × nLat]
    returns Hankel_Mode : [nLon × nLat × order]

    Optimisation: weight_sum is the same for every latitude column when all
    windows succeed (the common case), so it is pre-computed once outside the
    latitude loop and reused, eliminating nLat redundant np.zeros + loop
    accumulations.  A per-column fallback handles the rare failure path.
    """
    g = np.asarray(grid, dtype=float)
    if g.ndim != 2:
        raise ValueError("HSA expects 2D grid")
    nLon, nLat = g.shape
    order = int(order)
    window_size = int(window_size)
    buffer = max(1, int(buffer))
    if window_size > nLon:
        window_size = nLon

    Hankel_Mode = np.zeros((nLon, nLat, order), dtype=float)
    forward_starts = list(range(0, nLon - window_size + 1, buffer))
    backward_starts = [
        end_idx - window_size + 1
        for end_idx in range(nLon - 1, window_size - 2, -buffer)
    ]
    window_starts = sorted(set(forward_starts + backward_starts))

    # Pre-compute the weight template (only valid when every h_rcs call
    # succeeds; _process_lat falls back to per-column counting on failure).
    weight_template = np.zeros(nLon, dtype=float)
    for s in window_starts:
        weight_template[s: s + window_size] += 1.0

    def _process_lat(j):
        x1 = g[:, j]
        Y1 = np.zeros((order, nLon), dtype=float)
        failed_windows = []

        for start_idx in window_starts:
            x1_slice = x1[start_idx: start_idx + window_size]
            try:
                _, _, _, _, Y, _, _ = h_rcs(x1_slice, Ts, p, order)
            except Exception:
                failed_windows.append(start_idx)
                continue
            Y1[:, start_idx: start_idx + window_size] += Y

        # Use the cheap pre-computed template if no failures occurred.
        if failed_windows:
            w = weight_template.copy()
            for s in failed_windows:
                w[s: s + window_size] -= 1.0
            valid = w > 0
            if np.any(valid):
                Y1[:, valid] /= w[valid]
        else:
            valid = weight_template > 0
            if np.any(valid):
                Y1[:, valid] /= weight_template[valid]

        return j, Y1.T  # (nLon, order)

    n_workers = int(workers) if workers else 0
    if n_workers > 1 and nLat > 1:
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            n_workers = min(n_workers, nLat)
            with ThreadPoolExecutor(max_workers=n_workers) as ex:
                futures = {ex.submit(_process_lat, j): j for j in range(nLat)}
                for fut in as_completed(futures):
                    j, yj = fut.result()
                    Hankel_Mode[:, j, :] = yj
        except Exception:
            for j in range(nLat):
                jj, yj = _process_lat(j)
                Hankel_Mode[:, jj, :] = yj
    else:
        for j in range(nLat):
            jj, yj = _process_lat(j)
            Hankel_Mode[:, jj, :] = yj

    return Hankel_Mode


# ---------------------------------------------------------------------------
# Noise-mode index table
# ---------------------------------------------------------------------------

def hsaf_noise_mode_indices(order: int) -> List[int]:
    """
    Noise mode selection consistent with HSAF_Global_V6Template_v3.m.
    Returns zero-based indices.
    """
    mapping = {
        3: [1, 3],
        4: [1, 4],
        5: [1, 2, 4, 5],
        6: [1, 2, 5, 6],
        7: [1, 2, 6, 7],
        8: [1, 2, 3, 6, 7, 8],
        9: [1, 2, 3, 7, 8, 9],
        10: [1, 2, 3, 8, 9, 10],
    }
    idx = mapping.get(int(order), [])
    return [i - 1 for i in idx]


# ---------------------------------------------------------------------------
# MATLAB-aligned global HSAF map filter
# ---------------------------------------------------------------------------

def hsaf_global_filter_map_matlab(
    X: np.ndarray, Ts: float, params: Dict[str, Any]
) -> Tuple[np.ndarray, int, bool]:
    """
    MATLAB-aligned global HSAF: HSA.m + noise mode removal.
    Unchanged public contract; benefits from htls_pm/hsa improvements above.
    """
    Y = X.copy()
    nRemoved = 0
    ok = False

    nIter = max(1, int(params.get("iterations", 1)))
    for _ in range(nIter):
        nanMask = ~np.isfinite(Y)
        if np.any(nanMask):
            Y = _fill_nan_grid(Y)

        try:
            Hankel_Mode = hsa_bidirectional_map(
                Y,
                Ts,
                params.get("N", 30),
                params.get("P", 10),
                params.get("K", 6),
                params.get("J", 1),
                params.get("workers", 0),
            )
        except Exception:
            return Y, nRemoved, False

        if not np.isfinite(Hankel_Mode).all():
            return Y, nRemoved, False

        order = int(params.get("K", 6))
        if Hankel_Mode.shape[2] < order:
            return Y, nRemoved, False

        idx = hsaf_noise_mode_indices(order)
        if not idx:
            return Y, nRemoved, False

        Y_noise = np.sum(Hankel_Mode[:, :, idx], axis=2)
        Y = Y - Y_noise
        if np.any(nanMask):
            Y[nanMask] = np.nan
        nRemoved += len(idx)

    ok = True
    return Y, nRemoved, ok


def filter_grid_hsaf_matlab(
    grid: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    config: Dict[str, Any],
    Ts: Optional[float] = None,
    progress_hook: Optional[Callable[[int, int], None]] = None,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    MATLAB-aligned global HSAF filter (HSAF_Global_V6Template_v3.m/HSA.m style).
    """
    grid = ensure_latlon_order(grid, lon_vec, lat_vec, target_order="lon_lat")
    is_3d = grid.ndim == 3
    if not is_3d:
        grid = grid[:, :, np.newaxis]

    if Ts is None:
        Ts = float(np.abs(lon_vec[1] - lon_vec[0])) if len(lon_vec) > 1 else 1.0

    params = (
        config.get("params", {}) if isinstance(config, dict) else getattr(config, "params", {})
    )
    grid_f = np.zeros_like(grid)

    total_slices = int(grid.shape[2])
    for t in range(total_slices):
        Y = grid[:, :, t]
        Yf, nRemoved, ok = hsaf_global_filter_map_matlab(Y, Ts, params)
        grid_f[:, :, t] = Yf if ok else Y
        if progress_hook is not None:
            progress_hook(t + 1, total_slices)

    if not is_3d:
        grid_f = grid_f[:, :, 0]

    info = {
        "type": "HSAF_matlab_v3",
        "engine": "matlab_v3",
        "params": params,
    }
    return grid_f, info


# ---------------------------------------------------------------------------
# SVD engine — 1-D helpers
# ---------------------------------------------------------------------------

def hsaf_1d(
    signal: np.ndarray, N: int, P: int, K: int, iterations: int = 1
) -> np.ndarray:
    """
    Apply HSAF filter to 1D signal (full-profile mode).

    Optimisation: the original nested i/j loop for anti-diagonal Hankel
    averaging is replaced by np.add.at with pre-computed index arrays,
    removing O(N×P) pure-Python iterations per call.

    Args
    ----
    signal     : 1-D input
    N          : Window size (rows of Hankel matrix)
    P          : Embedding dimension (columns)
    K          : Singular values to retain
    iterations : Filter passes

    Returns
    -------
    Filtered signal (same length as input).
    """
    n = len(signal)
    if n < N + P - 1:
        return signal

    # Pre-compute anti-diagonal index map once for this (N, P) shape.
    # H[i, j] contributes to reconstructed[i+j].
    rows_idx, cols_idx = np.indices((N, P))
    diag_idx_flat = (rows_idx + cols_idx).ravel()   # length N*P, values in [0, N+P-2]

    result = signal.copy()
    for _ in range(max(1, int(iterations))):
        col = result[:N]
        row = result[N - 1: N + P - 1]
        H = hankel(col, row)

        try:
            U, s, Vh = svd(H, full_matrices=False, check_finite=False)
        except Exception:
            return signal

        k = min(K, len(s))
        # Equivalent to U[:,:k] @ diag(s[:k]) @ Vh[:k,:] but avoids diag alloc.
        H_approx = (U[:, :k] * s[:k]) @ Vh[:k, :]

        # OPT: vectorised anti-diagonal averaging via np.add.at.
        reconstructed = np.zeros(n)
        counts = np.zeros(n, dtype=np.int32)
        np.add.at(reconstructed, diag_idx_flat, H_approx.ravel())
        np.add.at(counts, diag_idx_flat, 1)
        counts[counts == 0] = 1
        result = reconstructed / counts

    return result


def hsaf_1d_ola(
    signal: np.ndarray,
    N: int,
    P: int,
    K: int,
    step: int,
    iterations: int = 1,
    window: str = "hann",
) -> np.ndarray:
    """Apply HSAF in sliding-window OLA mode."""
    n = len(signal)
    win_len = N + P - 1
    if n < win_len or win_len <= 1:
        return signal
    step = int(step) if step is not None else win_len
    if step <= 0:
        step = win_len

    if window == "hann":
        w = np.hanning(win_len)
    else:
        w = np.ones(win_len)
    w = w.astype(float)
    w[w == 0] = 1e-12

    result = signal.copy()
    for _ in range(max(1, int(iterations))):
        acc = np.zeros(n)
        wacc = np.zeros(n)
        starts = list(range(0, n - win_len + 1, step))
        if not starts or starts[-1] != n - win_len:
            starts.append(n - win_len)
        for s in starts:
            seg = result[s: s + win_len]
            seg_f = hsaf_1d(seg, N, P, K, iterations=1)
            acc[s: s + win_len] += seg_f * w
            wacc[s: s + win_len] += w
        wacc[wacc == 0] = 1
        result = acc / wacc

    return result


# ---------------------------------------------------------------------------
# SVD engine — grid-level dispatcher
# ---------------------------------------------------------------------------

def filter_grid_hsaf_svd(
    grid: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    config: Dict[str, Any],
    Ts: float = 1.0,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Apply HSAF filter to spatial grid (SVD/OLA engine).

    Args
    ----
    grid    : [nLon, nLat] or [nLon, nLat, Nt]
    lon_vec : Longitude vector
    lat_vec : Latitude vector
    config  : HSAF configuration dictionary
    Ts      : Spatial sampling interval (degrees)

    Returns
    -------
    (filtered_grid, info)
    """
    grid = ensure_latlon_order(grid, lon_vec, lat_vec, target_order="lon_lat")

    if hasattr(config, "params"):
        params = config.params
    else:
        params = config.get("params", {})

    N = params.get("N", 30)
    P = params.get("P", 10)
    K = params.get("K", 6)
    J = params.get("J", 1)
    iterations = params.get("iterations", 1)

    mode = (
        config.get("mode", "profile") if isinstance(config, dict)
        else getattr(config, "mode", "profile")
    )
    variant = (
        config.get("variant", "global") if isinstance(config, dict)
        else getattr(config, "variant", "global")
    )

    lon_span = None
    if len(lon_vec) > 1:
        step = float(np.abs(lon_vec[1] - lon_vec[0]))
        lon_span = float(np.abs(lon_vec[-1] - lon_vec[0]) + step)
    is_global = lon_span is not None and lon_span >= 359.0

    def _maybe_wrap(
        profile_clean: np.ndarray, win_len: int
    ) -> Tuple[np.ndarray, int]:
        if not is_global or win_len <= 1:
            return profile_clean, 0
        pad = int(win_len)
        return np.pad(profile_clean, pad_width=pad, mode="wrap"), pad

    is_3d = grid.ndim == 3
    if not is_3d:
        grid = grid[:, :, np.newaxis]

    nLon, nLat, Nt = grid.shape
    grid_f = np.zeros_like(grid)

    for t in range(Nt):
        g = grid[:, :, t]

        if mode in ("profile", "ola"):
            for j in range(nLat):
                profile = g[:, j]
                if np.any(np.isfinite(profile)):
                    mask = np.isfinite(profile)
                    if np.sum(mask) > N + P:
                        profile_clean = np.interp(
                            np.arange(nLon),
                            np.where(mask)[0],
                            profile[mask],
                        )
                        win_len = N + P - 1
                        prof_in, pad = _maybe_wrap(profile_clean, win_len)
                        if mode == "ola":
                            prof_f = hsaf_1d_ola(
                                prof_in, N, P, K, step=J, iterations=iterations
                            )
                        else:
                            prof_f = hsaf_1d(prof_in, N, P, K, iterations=iterations)
                        if pad > 0:
                            prof_f = prof_f[pad: pad + nLon]
                        if not np.isfinite(prof_f).any() or np.nanstd(prof_f) < 1e-12:
                            prof_f = profile_clean
                        grid_f[:, j, t] = prof_f
                    else:
                        grid_f[:, j, t] = profile
                else:
                    grid_f[:, j, t] = profile

        elif mode == "both":
            g_lon = np.zeros_like(g)
            g_lat = np.zeros_like(g)
            for j in range(nLat):
                profile = g[:, j]
                mask = np.isfinite(profile)
                if np.sum(mask) > N + P:
                    profile_clean = np.interp(
                        np.arange(nLon), np.where(mask)[0], profile[mask]
                    )
                    g_lon[:, j] = hsaf_1d(profile_clean, N, P, K, iterations=iterations)
                else:
                    g_lon[:, j] = profile
            for i in range(nLon):
                profile = g[i, :]
                mask = np.isfinite(profile)
                if np.sum(mask) > N + P:
                    profile_clean = np.interp(
                        np.arange(nLat), np.where(mask)[0], profile[mask]
                    )
                    g_lat[i, :] = hsaf_1d(profile_clean, N, P, K, iterations=iterations)
                else:
                    g_lat[i, :] = profile
            grid_f[:, :, t] = (g_lon + g_lat) / 2

        else:
            grid_f[:, :, t] = g

    if not is_3d:
        grid_f = grid_f[:, :, 0]

    info = {
        "type": "HSAF",
        "mode": mode,
        "variant": variant,
        "N": N,
        "P": P,
        "K": K,
        "J": J,
        "iterations": iterations,
    }
    return grid_f, info


# ---------------------------------------------------------------------------
# Public dispatch
# ---------------------------------------------------------------------------

def filter_grid_hsaf(
    grid: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    config: Dict[str, Any],
    Ts: float = 1.0,
    progress_hook: Optional[Callable[[int, int], None]] = None,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Dispatch HSAF engine.  Default uses MATLAB-aligned global HSAF.
    Signature identical to original.
    """
    if isinstance(config, dict):
        engine = config.get("engine")
    else:
        engine = getattr(config, "engine", None)
    engine = (engine or "matlab_v3").lower()

    if engine in ("matlab", "matlab_v3", "hsa"):
        return filter_grid_hsaf_matlab(
            grid, lon_vec, lat_vec, config, Ts=None, progress_hook=progress_hook
        )

    return filter_grid_hsaf_svd(grid, lon_vec, lat_vec, config, Ts=Ts)


def filter_grid_hsaf_adaptive(
    grid: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    adaptive_config: List[Dict],
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Apply HSAF with latitude-dependent parameters.

    Args
    ----
    grid            : Input grid
    lon_vec         : Longitude vector
    lat_vec         : Latitude vector
    adaptive_config : List of {lat_range: [min, max], params: {...}}

    Returns
    -------
    (filtered_grid, info)
    """
    grid_f = grid.copy()

    for zone in adaptive_config:
        lat_range = zone.get("lat_range", [-90, 90])
        params = zone.get("params", {})

        lat_mask = (lat_vec >= lat_range[0]) & (lat_vec <= lat_range[1])
        lat_idx = np.where(lat_mask)[0]
        if len(lat_idx) == 0:
            continue

        if grid.ndim == 3:
            zone_grid = grid[:, lat_idx, :]
        else:
            zone_grid = grid[:, lat_idx]

        config = {"params": params, "mode": zone.get("mode", "profile")}
        zone_f, _ = filter_grid_hsaf_svd(
            zone_grid, lon_vec, lat_vec[lat_idx], config
        )

        if grid.ndim == 3:
            grid_f[:, lat_idx, :] = zone_f
        else:
            grid_f[:, lat_idx] = zone_f

    info = {
        "type": "HSAF_adaptive",
        "zones": len(adaptive_config),
    }
    return grid_f, info
