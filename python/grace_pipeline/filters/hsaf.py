"""
HSAF (Hankel-SVD Adaptive Filter) for grid-domain filtering.

This filter works directly on spatial grids rather than SH coefficients,
using Hankel matrix SVD for noise reduction.
"""

from dataclasses import dataclass
import numpy as np
from scipy.linalg import hankel, svd
from scipy.signal import hilbert
from typing import Callable, Tuple, Dict, Any, Optional, List

from grace_pipeline.core.grid import ensure_latlon_order


@dataclass
class _WindowDecomposition:
    valid: bool
    modes: np.ndarray
    freq_norm: np.ndarray
    energy_ratio: np.ndarray
    pole_mag: np.ndarray


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


def htls_pm(x: np.ndarray, Ts: float, p: int, k: int):
    """
    Port of MATLAB HTLS_PM for Hankel-SSA parameters.
    Returns Amp, alfa, freq, theta, Ex, Ex_flag.
    """
    x = np.asarray(x, dtype=float).ravel()
    N = x.size
    p = int(p)
    k = int(k)
    if N < max(p + 1, 3) or p < 2 or k < 1:
        raise ValueError("HTLS_PM: invalid dimensions")

    X1 = hankel(x[:p], x[p - 1 :])
    # We only consume the leading right-singular vectors, so there is no
    # value in computing the trailing dense block here.
    U, S, Vh = svd(X1, full_matrices=False, check_finite=False)
    Ex = S.copy()
    Ex_flag = int(np.sum(Ex > 0.001))

    Ux = Vh.T
    if Ux.shape[1] == 0:
        raise ValueError("HTLS_PM: empty SVD")
    k = min(k, Ux.shape[1])
    if k < 1:
        raise ValueError("HTLS_PM: k too small")

    Us = Ux[:, :k]
    U1 = Us[:-1, :]
    U2 = Us[1:, :]
    D12 = np.hstack([U1, U2])

    # Keep the full null-space partition for the second decomposition.
    Ud, Sd, Vhd = svd(D12, full_matrices=True, check_finite=False)
    UD = Vhd.T
    U12 = UD[:k, k : 2 * k]
    U22 = UD[k : 2 * k, k : 2 * k]

    fai = -U12 @ np.linalg.pinv(U22)
    l = np.linalg.eigvals(fai)

    alfa = np.log(np.abs(l)) / Ts
    freq = np.arctan2(l.imag, l.real) / (2 * np.pi * Ts)

    n = np.arange(N)
    Z = (l[:, None] ** n[None, :]).T
    ck, *_ = np.linalg.lstsq(Z, x, rcond=None)

    Amp = np.abs(ck)
    theta = np.arctan2(ck.imag, ck.real)
    return Amp, alfa, freq, theta, Ex, Ex_flag


def h_rcs(x: np.ndarray, Ts: float, p: int, k: int):
    """
    Port of MATLAB H_RCs. Returns Amp, alfa, freq, theta, Y, Ex, Ex_flag.
    """
    Amp, alfa, freq, theta, Ex, Ex_flag = htls_pm(x, Ts, p, k)
    if not (np.isfinite(Amp).all() and np.isfinite(alfa).all() and np.isfinite(freq).all() and np.isfinite(theta).all()):
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
    Y = (Amp[:, None] * exp_term) * np.cos(2 * np.pi * Ts * freq[:, None] * n2 + theta[:, None])
    if not np.isfinite(Y).all():
        raise ValueError("H_RCs: non-finite reconstruction")
    return Amp, alfa, freq, theta, Y, Ex, Ex_flag


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
    grid: [nLon x nLat]
    returns Hankel_Mode: [nLon x nLat x order]
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

    weight_template = np.zeros(nLon, dtype=float)
    for start_idx in window_starts:
        weight_template[start_idx : start_idx + window_size] += 1.0

    def _process_lat(j):
        x1 = g[:, j]
        Y1 = np.zeros((order, nLon), dtype=float)
        failed_windows = []
        for start_idx in window_starts:
            x1_slice = x1[start_idx : start_idx + window_size]
            try:
                _, _, _, _, Y, _, _ = h_rcs(x1_slice, Ts, p, order)
            except Exception:
                failed_windows.append(start_idx)
                continue
            Y1[:, start_idx : start_idx + window_size] += Y

        if failed_windows:
            weight_sum = weight_template.copy()
            for start_idx in failed_windows:
                weight_sum[start_idx : start_idx + window_size] -= 1.0
        else:
            weight_sum = weight_template

        valid = weight_sum > 0
        if np.any(valid):
            Y1[:, valid] /= weight_sum[valid]
        return j, Y1.T

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


def hsaf_noise_mode_indices(order: int) -> List[int]:
    """
    Noise mode selection logic consistent with HSAF_Global_V6Template_v3.m
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


def hsaf_global_filter_map_matlab(
    X: np.ndarray, Ts: float, params: Dict[str, Any]
) -> Tuple[np.ndarray, int, bool]:
    """
    MATLAB-aligned global HSAF: HSA.m + noise mode removal.
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

    params = config.get("params", {}) if isinstance(config, dict) else getattr(config, "params", {})
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


def hsaf_1d(signal: np.ndarray, N: int, P: int, K: int, iterations: int = 1) -> np.ndarray:
    """
    Apply HSAF filter to 1D signal (full-profile mode).

    Args:
        signal: 1D input signal
        N: Window size for Hankel matrix
        P: Embedding dimension
        K: Number of singular values to keep
        iterations: Number of iterations

    Returns:
        Filtered signal
    """
    n = len(signal)
    if n < N + P - 1:
        return signal

    rows_idx, cols_idx = np.indices((N, P))
    diag_idx_flat = (rows_idx + cols_idx).ravel()
    result = signal.copy()

    for _ in range(max(1, int(iterations))):
        # Build Hankel matrix
        col = result[:N]
        row = result[N-1:N+P-1]
        H = hankel(col, row)

        # SVD
        try:
            U, s, Vh = svd(H, full_matrices=False, check_finite=False)
        except Exception:
            return signal

        # Truncate to K components
        k = min(K, len(s))
        H_approx = (U[:, :k] * s[:k]) @ Vh[:k, :]

        # Reconstruct signal by averaging anti-diagonals
        reconstructed = np.zeros(n)
        counts = np.zeros(n, dtype=np.int32)
        np.add.at(reconstructed, diag_idx_flat, H_approx.ravel())
        np.add.at(counts, diag_idx_flat, 1)

        counts[counts == 0] = 1
        result = reconstructed / counts

    return result


def hsaf_1d_ola(signal: np.ndarray, N: int, P: int, K: int, step: int, iterations: int = 1, window: str = 'hann') -> np.ndarray:
    """
    Apply HSAF in sliding-window OLA mode.
    Uses window length (N+P-1) and step size J.
    """
    n = len(signal)
    win_len = N + P - 1
    if n < win_len or win_len <= 1:
        return signal
    step = int(step) if step is not None else win_len
    if step <= 0:
        step = win_len

    # Window
    if window == 'hann':
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
            seg = result[s:s + win_len]
            seg_f = hsaf_1d(seg, N, P, K, iterations=1)
            acc[s:s + win_len] += seg_f * w
            wacc[s:s + win_len] += w
        wacc[wacc == 0] = 1
        result = acc / wacc

    return result


def filter_grid_hsaf_svd(
    grid: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    config: Dict[str, Any],
    Ts: float = 1.0,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Apply HSAF filter to spatial grid.
    
    Args:
        grid: Input grid [nLon, nLat] or [nLon, nLat, Nt]
        lon_vec: Longitude vector
        lat_vec: Latitude vector
        config: HSAF configuration dictionary
        Ts: Spatial sampling interval (degrees)
    
    Returns:
        Tuple of (filtered_grid, info)
    """
    # Ensure [nLon, nLat, Nt] order
    grid = ensure_latlon_order(grid, lon_vec, lat_vec, target_order="lon_lat")

    # Get parameters from config
    if hasattr(config, 'params'):
        params = config.params
    else:
        params = config.get('params', {})
    
    N = params.get('N', 30)
    P = params.get('P', 10)
    K = params.get('K', 6)
    J = params.get('J', 1)
    iterations = params.get('iterations', 1)
    
    mode = config.get('mode', 'profile') if isinstance(config, dict) else getattr(config, 'mode', 'profile')
    variant = config.get('variant', 'global') if isinstance(config, dict) else getattr(config, 'variant', 'global')

    # Detect global longitude span for wrap-around to avoid edge artifacts
    lon_span = None
    if len(lon_vec) > 1:
        step = float(np.abs(lon_vec[1] - lon_vec[0]))
        lon_span = float(np.abs(lon_vec[-1] - lon_vec[0]) + step)
    is_global = lon_span is not None and lon_span >= 359.0

    def _maybe_wrap(profile_clean: np.ndarray, win_len: int) -> Tuple[np.ndarray, int]:
        if not is_global or win_len <= 1:
            return profile_clean, 0
        pad = int(win_len)
        return np.pad(profile_clean, pad_width=pad, mode='wrap'), pad
    
    is_3d = grid.ndim == 3
    if not is_3d:
        grid = grid[:, :, np.newaxis]
    
    nLon, nLat, Nt = grid.shape
    grid_f = np.zeros_like(grid)
    
    # Process each time slice
    for t in range(Nt):
        g = grid[:, :, t]
        
        if mode in ('profile', 'ola'):
            # Filter along longitude profiles
            for j in range(nLat):
                profile = g[:, j]
                if np.any(np.isfinite(profile)):
                    # Handle NaN values
                    mask = np.isfinite(profile)
                    if np.sum(mask) > N + P:
                        profile_clean = np.interp(
                            np.arange(nLon),
                            np.where(mask)[0],
                            profile[mask]
                        )

                        win_len = N + P - 1
                        prof_in, pad = _maybe_wrap(profile_clean, win_len)
                        if mode == 'ola':
                            prof_f = hsaf_1d_ola(prof_in, N, P, K, step=J, iterations=iterations)
                        else:
                            prof_f = hsaf_1d(prof_in, N, P, K, iterations=iterations)
                        if pad > 0:
                            prof_f = prof_f[pad:pad + nLon]

                        # Fallback if filter collapses signal
                        if not np.isfinite(prof_f).any() or np.nanstd(prof_f) < 1e-12:
                            prof_f = profile_clean

                        grid_f[:, j, t] = prof_f
                    else:
                        grid_f[:, j, t] = profile
                else:
                    grid_f[:, j, t] = profile
        
        elif mode == 'both':
            # Filter both longitude and latitude
            g_lon = np.zeros_like(g)
            g_lat = np.zeros_like(g)
            
            # Longitude direction
            for j in range(nLat):
                profile = g[:, j]
                mask = np.isfinite(profile)
                if np.sum(mask) > N + P:
                    profile_clean = np.interp(
                        np.arange(nLon),
                        np.where(mask)[0],
                        profile[mask]
                    )
                    g_lon[:, j] = hsaf_1d(profile_clean, N, P, K, iterations=iterations)
                else:
                    g_lon[:, j] = profile
            
            # Latitude direction
            for i in range(nLon):
                profile = g[i, :]
                mask = np.isfinite(profile)
                if np.sum(mask) > N + P:
                    profile_clean = np.interp(
                        np.arange(nLat),
                        np.where(mask)[0],
                        profile[mask]
                    )
                    g_lat[i, :] = hsaf_1d(profile_clean, N, P, K, iterations=iterations)
                else:
                    g_lat[i, :] = profile
            
            # Average both directions
            grid_f[:, :, t] = (g_lon + g_lat) / 2
        
        else:
            grid_f[:, :, t] = g
    
    if not is_3d:
        grid_f = grid_f[:, :, 0]
    
    info = {
        'type': 'HSAF',
        'mode': mode,
        'variant': variant,
        'N': N,
        'P': P,
        'K': K,
        'J': J,
        'iterations': iterations,
    }
    
    return grid_f, info


def _rolling_mean_1d(x: np.ndarray, window: int) -> np.ndarray:
    x = np.asarray(x, dtype=float).ravel()
    window = int(max(1, window))
    if x.size == 0 or window <= 1 or x.size < window:
        return x.copy()
    if window % 2 == 0:
        window += 1
    kernel = np.ones(window, dtype=float) / float(window)
    return np.convolve(x, kernel, mode="same")


def _highpass_profile(signal: np.ndarray, smooth_window: int = 21) -> np.ndarray:
    x = np.asarray(signal, dtype=float).ravel()
    if x.size == 0:
        return x.copy()
    smooth_window = int(max(3, min(smooth_window, x.size - (1 - x.size % 2))))
    if smooth_window <= 3:
        return x - np.nanmean(x)
    return x - _rolling_mean_1d(x, smooth_window)


def _smooth_grid_separable(grid: np.ndarray, lon_window: int, lat_window: int) -> np.ndarray:
    g = np.asarray(grid, dtype=float)
    out = g.copy()
    if g.ndim != 2:
        return out
    lon_window = max(1, int(lon_window))
    lat_window = max(1, int(lat_window))
    for j in range(out.shape[1]):
        out[:, j] = _rolling_mean_1d(out[:, j], lon_window)
    for i in range(out.shape[0]):
        out[i, :] = _rolling_mean_1d(out[i, :], lat_window)
    return out


def _smooth_weighted_1d(signal: np.ndarray, weights: np.ndarray, window: int) -> np.ndarray:
    x = np.asarray(signal, dtype=float).ravel()
    w = np.asarray(weights, dtype=float).ravel()
    if x.size == 0:
        return x.copy()
    window = int(max(1, window))
    if window <= 1 or x.size < window:
        den = np.maximum(w, np.finfo(float).eps)
        return x * w / den
    if window % 2 == 0:
        window += 1
    kernel = np.ones(window, dtype=float)
    num = np.convolve(x * w, kernel, mode="same")
    den = np.convolve(w, kernel, mode="same")
    return num / np.maximum(den, np.finfo(float).eps)


def _smooth_grid_separable_weighted(grid: np.ndarray, weights: np.ndarray, lon_window: int, lat_window: int) -> np.ndarray:
    arr = np.asarray(grid, dtype=float)
    w = np.asarray(weights, dtype=float)
    out = arr.copy()
    ww = w.copy()
    if arr.ndim != 2 or w.shape != arr.shape:
        return out
    lon_window = max(1, int(lon_window))
    lat_window = max(1, int(lat_window))
    for j in range(out.shape[1]):
        out[:, j] = _smooth_weighted_1d(out[:, j], ww[:, j], lon_window)
        ww[:, j] = _smooth_weighted_1d(ww[:, j], np.ones_like(ww[:, j]), lon_window)
    for i in range(out.shape[0]):
        out[i, :] = _smooth_weighted_1d(out[i, :], ww[i, :], lat_window)
    return out


def _smooth_complex_grid_weighted(arr: np.ndarray, weights: np.ndarray, lon_window: int, lat_window: int) -> np.ndarray:
    z = np.asarray(arr, dtype=complex)
    return (
        _smooth_grid_separable_weighted(np.real(z), weights, lon_window, lat_window)
        + 1j * _smooth_grid_separable_weighted(np.imag(z), weights, lon_window, lat_window)
    )


def _complex_rank_k_approx(arr: np.ndarray, rank: int) -> np.ndarray:
    z = np.asarray(arr, dtype=complex)
    if z.ndim != 2 or z.size == 0:
        return z.copy()
    try:
        U, s, Vh = np.linalg.svd(z, full_matrices=False)
    except Exception:
        return z.copy()
    r = max(1, min(int(rank), int(s.size)))
    return (U[:, :r] * s[:r]) @ Vh[:r, :]


def _decompose_background_residual(
    grid: np.ndarray,
    params: Dict[str, Any],
) -> Tuple[np.ndarray, np.ndarray, Dict[str, int]]:
    g = np.asarray(grid, dtype=float)
    nlon, nlat = g.shape
    lon_window = int(params.get("background_lon_window", max(15, min(45, (int(params.get("N", 30)) // 2) * 2 + 1))))
    lat_window = int(params.get("background_lat_window", 5))
    lon_window = min(lon_window | 1, max(3, nlon - (1 - nlon % 2)))
    lat_window = min(lat_window | 1, max(3, nlat - (1 - nlat % 2))) if nlat > 2 else 1
    background = _smooth_grid_separable(g, lon_window=lon_window, lat_window=lat_window)
    residual = g - background
    return background, residual, {"background_lon_window": lon_window, "background_lat_window": lat_window}


def _dominant_frequency_norm(signal: np.ndarray) -> float:
    x = np.asarray(signal, dtype=float).ravel()
    if x.size < 4:
        return 0.0
    x = x - np.nanmean(x)
    spec = np.abs(np.fft.rfft(x))
    if spec.size <= 1 or not np.any(np.isfinite(spec[1:])):
        return 0.0
    spec = np.where(np.isfinite(spec), spec, 0.0)
    idx = int(np.argmax(spec[1:]) + 1)
    freqs = np.fft.rfftfreq(x.size, d=1.0)
    return float(freqs[idx]) if idx < freqs.size else 0.0


def _bandpass_profile_fft(signal: np.ndarray, center: float, width: float) -> np.ndarray:
    x = np.asarray(signal, dtype=float).ravel()
    if x.size < 8:
        return np.zeros_like(x)
    x0 = x - np.nanmean(x)
    spec = np.fft.rfft(x0)
    freqs = np.fft.rfftfreq(x0.size, d=1.0)
    width = max(float(width), 1e-6)
    band = np.abs(freqs - float(center)) <= 1.5 * width
    if np.count_nonzero(band) == 0:
        idx = int(np.argmin(np.abs(freqs - float(center))))
        band[idx] = True
    filtered = np.zeros_like(spec)
    filtered[band] = spec[band]
    return np.fft.irfft(filtered, n=x0.size)


def _safe_abs_corr(a: np.ndarray, b: np.ndarray) -> float:
    x = np.asarray(a, dtype=float).ravel()
    y = np.asarray(b, dtype=float).ravel()
    ok = np.isfinite(x) & np.isfinite(y)
    if np.count_nonzero(ok) < 4:
        return 0.0
    x = x[ok] - float(np.mean(x[ok]))
    y = y[ok] - float(np.mean(y[ok]))
    den = float(np.linalg.norm(x) * np.linalg.norm(y))
    if den <= 0:
        return 0.0
    return float(np.clip(abs(np.dot(x, y) / den), 0.0, 1.0))


def _signed_corr(a: np.ndarray, b: np.ndarray) -> float:
    x = np.asarray(a, dtype=float).ravel()
    y = np.asarray(b, dtype=float).ravel()
    ok = np.isfinite(x) & np.isfinite(y)
    if np.count_nonzero(ok) < 4:
        return 0.0
    x = x[ok] - float(np.mean(x[ok]))
    y = y[ok] - float(np.mean(y[ok]))
    den = float(np.linalg.norm(x) * np.linalg.norm(y))
    if den <= 0:
        return 0.0
    return float(np.clip(np.dot(x, y) / den, -1.0, 1.0))


def _derive_ocean_mask(grid: np.ndarray, land_mask: Optional[np.ndarray]) -> np.ndarray:
    g = np.asarray(grid, dtype=float)
    if land_mask is None:
        return np.isfinite(g)
    lm = np.asarray(land_mask, dtype=bool)
    if lm.shape != g.shape:
        raise ValueError("land_mask shape mismatch for HSAF stripe analysis.")
    return (~lm) & np.isfinite(g)


def estimate_stripe_band(
    grid: np.ndarray,
    land_mask: Optional[np.ndarray] = None,
    min_ocean_fraction: float = 0.55,
) -> Dict[str, Any]:
    """Estimate the monthly stripe band from ocean-dominant longitude profiles."""
    g = np.asarray(grid, dtype=float)
    if g.ndim != 2:
        raise ValueError("estimate_stripe_band expects a 2-D grid.")

    ocean_mask = _derive_ocean_mask(g, land_mask)
    nlon, nlat = g.shape
    freqs = np.fft.rfftfreq(nlon, d=1.0)
    candidate = (freqs >= 0.03) & (freqs <= 0.45)
    power_sum = np.zeros_like(freqs, dtype=float)
    n_used = 0

    smooth_window = min(31, max(9, (nlon // 18) | 1))
    for j in range(nlat):
        ocean_frac = float(np.mean(ocean_mask[:, j])) if ocean_mask.size else 0.0
        if ocean_frac < float(min_ocean_fraction):
            continue
        prof = _fill_nan_profile(g[:, j])
        if np.count_nonzero(np.isfinite(prof)) < max(16, nlon // 6):
            continue
        hp = _highpass_profile(prof, smooth_window=smooth_window)
        spec = np.abs(np.fft.rfft(hp)) ** 2
        if np.any(np.isfinite(spec[candidate])):
            power_sum += np.where(np.isfinite(spec), spec, 0.0)
            n_used += 1

    freq_step = float(freqs[1] - freqs[0]) if freqs.size > 1 else 0.01
    if n_used <= 0 or not np.any(power_sum[candidate] > 0):
        return {
            "center": 0.12,
            "width": max(0.02, 2.0 * freq_step),
            "freqs": freqs,
            "power": power_sum,
            "n_profiles": n_used,
        }

    cand_idx = np.where(candidate)[0]
    top_n = min(5, cand_idx.size)
    order = cand_idx[np.argsort(power_sum[cand_idx])[-top_n:]]
    weights = power_sum[order]
    center = float(np.average(freqs[order], weights=weights))
    variance = float(np.average((freqs[order] - center) ** 2, weights=weights)) if np.sum(weights) > 0 else 0.0
    width = max(0.015, 2.0 * freq_step, float(np.sqrt(max(variance, 0.0))))
    return {
        "center": center,
        "width": width,
        "freqs": freqs,
        "power": power_sum,
        "n_profiles": n_used,
    }


def build_stripe_template_map(
    grid: np.ndarray,
    band_info: Dict[str, Any],
    land_mask: Optional[np.ndarray] = None,
    lat_smooth_window: int = 5,
    min_ocean_fraction: float = 0.40,
) -> np.ndarray:
    """Build a directional stripe template map using narrow-band FFT profiles."""
    g = np.asarray(grid, dtype=float)
    if g.ndim != 2:
        raise ValueError("build_stripe_template_map expects a 2-D grid.")
    center = float(band_info.get("center", 0.12))
    width = float(band_info.get("width", 0.03))
    ocean_mask = _derive_ocean_mask(g, land_mask)
    template = np.zeros_like(g, dtype=float)
    valid_cols = np.zeros(g.shape[1], dtype=bool)
    for j in range(g.shape[1]):
        ocean_frac = float(np.mean(ocean_mask[:, j])) if ocean_mask.size else 0.0
        if ocean_frac < float(min_ocean_fraction):
            continue
        prof = _fill_nan_profile(g[:, j])
        if np.count_nonzero(np.isfinite(prof)) < max(16, g.shape[0] // 6):
            continue
        template[:, j] = _bandpass_profile_fft(prof, center=center, width=width)
        valid_cols[j] = True
    if np.count_nonzero(valid_cols) == 0:
        return template
    lat_smooth_window = max(1, int(lat_smooth_window))
    for i in range(template.shape[0]):
        template[i, :] = _rolling_mean_1d(template[i, :], lat_smooth_window)
    return template


def _analytic_profile_components(signal: np.ndarray, center: float, width: float) -> Dict[str, np.ndarray]:
    band = _bandpass_profile_fft(signal, center=center, width=width)
    try:
        analytic = hilbert(np.asarray(band, dtype=float))
    except Exception:
        analytic = np.asarray(band, dtype=float).astype(complex)
    env = np.abs(analytic)
    phase = np.angle(analytic)
    unit = analytic / np.maximum(env, np.finfo(float).eps)
    return {
        "band": np.asarray(band, dtype=float),
        "analytic": np.asarray(analytic, dtype=complex),
        "env": np.asarray(env, dtype=float),
        "phase": np.asarray(phase, dtype=float),
        "unit": np.asarray(unit, dtype=complex),
    }


def _demod_gain(
    profile: np.ndarray,
    stripe_component: np.ndarray,
    ocean_fraction: float,
    *,
    severity_gain: float = 1.0,
    land_penalty: float = 1.0,
) -> float:
    prof = np.asarray(profile, dtype=float).ravel()
    stripe = np.asarray(stripe_component, dtype=float).ravel()
    prof_std = float(np.nanstd(prof))
    stripe_std = float(np.nanstd(stripe))
    if prof_std <= 0 or stripe_std <= 0:
        return 0.0
    relative = np.clip(stripe_std / prof_std, 0.0, 1.5)
    ocean_gain = 0.75 + 0.50 * float(np.clip(ocean_fraction, 0.0, 1.0))
    gain = 0.55 * relative * ocean_gain * float(severity_gain) * float(land_penalty)
    return float(np.clip(gain, 0.0, 0.90))


def compute_stripe_metrics(
    grid: np.ndarray,
    land_mask: Optional[np.ndarray] = None,
    band_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    """Compute ocean stripe-band energy and anisotropy metrics for one grid."""
    g = np.asarray(grid, dtype=float)
    if g.ndim != 2:
        raise ValueError("compute_stripe_metrics expects a 2-D grid.")

    band = band_info or estimate_stripe_band(g, land_mask=land_mask)
    center = float(band.get("center", 0.12))
    width = float(band.get("width", 0.03))
    freqs = np.asarray(band.get("freqs"), dtype=float)
    if freqs.size == 0:
        freqs = np.fft.rfftfreq(g.shape[0], d=1.0)
    candidate = (freqs >= 0.03) & (freqs <= 0.45)
    band_mask = np.abs(freqs - center) <= 1.5 * width

    ocean_mask = _derive_ocean_mask(g, land_mask)
    smooth_window = min(31, max(9, (g.shape[0] // 18) | 1))
    band_ratios = []
    hp_grid = np.full_like(g, np.nan, dtype=float)
    for j in range(g.shape[1]):
        ocean_frac = float(np.mean(ocean_mask[:, j])) if ocean_mask.size else 0.0
        if ocean_frac < 0.55:
            continue
        prof = _fill_nan_profile(g[:, j])
        if np.count_nonzero(np.isfinite(prof)) < max(16, g.shape[0] // 6):
            continue
        hp = _highpass_profile(prof, smooth_window=smooth_window)
        hp_grid[:, j] = hp
        spec = np.abs(np.fft.rfft(hp)) ** 2
        denom = float(np.sum(spec[candidate]))
        if denom > 0:
            band_ratios.append(float(np.sum(spec[band_mask]) / denom))

    gx = np.diff(hp_grid, axis=0)
    gy = np.diff(hp_grid, axis=1)
    mx = ocean_mask[1:, :] & ocean_mask[:-1, :] & np.isfinite(gx)
    my = ocean_mask[:, 1:] & ocean_mask[:, :-1] & np.isfinite(gy)
    rms_x = float(np.sqrt(np.mean(np.square(gx[mx])))) if np.any(mx) else 0.0
    rms_y = float(np.sqrt(np.mean(np.square(gy[my])))) if np.any(my) else 0.0
    anisotropy = rms_x / (rms_y + np.finfo(float).eps)

    return {
        "ocean_stripe_band_energy": float(np.nanmean(band_ratios)) if band_ratios else 0.0,
        "ocean_anisotropy_index": float(anisotropy),
    }


def _build_window_decomposition(profile: np.ndarray, Ts: float, p: int, order: int) -> _WindowDecomposition:
    prof = np.asarray(profile, dtype=float).ravel()
    if np.count_nonzero(np.isfinite(prof)) < max(4, p + 1):
        return _WindowDecomposition(False, np.empty((0, prof.size)), np.empty(0), np.empty(0), np.empty(0))
    try:
        _, alfa, _, _, Y, _, _ = h_rcs(prof, Ts, p, order)
    except Exception:
        return _WindowDecomposition(False, np.empty((0, prof.size)), np.empty(0), np.empty(0), np.empty(0))

    modes = np.asarray(Y, dtype=float)
    if modes.ndim != 2 or modes.shape[0] == 0 or not np.isfinite(modes).all():
        return _WindowDecomposition(False, np.empty((0, prof.size)), np.empty(0), np.empty(0), np.empty(0))

    energies = np.sum(np.square(modes), axis=1)
    total_energy = float(np.sum(energies))
    if total_energy <= 0:
        return _WindowDecomposition(False, np.empty((0, prof.size)), np.empty(0), np.empty(0), np.empty(0))

    freq_norm = np.asarray([_dominant_frequency_norm(mode) for mode in modes], dtype=float)
    pole_mag = np.exp(np.asarray(alfa[: modes.shape[0]], dtype=float) * float(Ts))
    energy_ratio = np.asarray(energies / total_energy, dtype=float)
    return _WindowDecomposition(True, modes, freq_norm, energy_ratio, pole_mag)


def _mode_band_score(freq_norm: float, center: float, width: float) -> float:
    width = max(float(width), 1e-6)
    d = (float(freq_norm) - float(center)) / width
    return float(np.exp(-0.5 * d * d))


def _mode_match(freq_target: float, freq_candidates: np.ndarray, freq_tol: float) -> Tuple[int, float]:
    if freq_candidates.size == 0:
        return -1, 0.0
    d = np.abs(np.asarray(freq_candidates, dtype=float) - float(freq_target))
    idx = int(np.argmin(d))
    if d[idx] > freq_tol:
        return idx, 0.0
    closeness = 1.0 - float(d[idx] / max(freq_tol, np.finfo(float).eps))
    return idx, float(np.clip(closeness, 0.0, 1.0))


def _mode_ocean_bias_score(mode_signal: np.ndarray, ocean_mask: Optional[np.ndarray]) -> float:
    if ocean_mask is None:
        return 0.5
    mask = np.asarray(ocean_mask, dtype=bool).ravel()
    if mask.size != np.asarray(mode_signal).size:
        return 0.5
    ocean_frac = float(np.mean(mask))
    if ocean_frac <= 0.05 or ocean_frac >= 0.95:
        return 0.5
    energy = np.abs(np.asarray(mode_signal, dtype=float).ravel())
    total = float(np.sum(energy))
    if total <= 0:
        return 0.0
    ocean_ratio = float(np.sum(energy[mask]) / total)
    score = (ocean_ratio - ocean_frac) / max(1e-6, 1.0 - ocean_frac)
    return float(np.clip(score, 0.0, 1.0))


def _mode_pole_aux_score(energy_ratio: float, pole_mag: float) -> float:
    energy_term = np.clip((0.18 - float(energy_ratio)) / 0.18, 0.0, 1.0)
    safe_mag = max(float(pole_mag), 1e-9)
    pole_term = np.clip(abs(np.log(safe_mag)) / 0.15, 0.0, 1.0)
    return float(0.6 * energy_term + 0.4 * pole_term)


def _patch_anisotropy_score(patch: np.ndarray) -> float:
    arr = np.asarray(patch, dtype=float)
    if arr.ndim != 2 or arr.shape[1] < 2:
        return 0.5
    gx = np.diff(arr, axis=1)
    rms_x = float(np.sqrt(np.mean(np.square(gx)))) if gx.size else 0.0
    if arr.shape[0] >= 2:
        gy = np.diff(arr, axis=0)
        rms_y = float(np.sqrt(np.mean(np.square(gy)))) if gy.size else 0.0
    else:
        rms_y = 0.0
    return float(rms_x / (rms_x + rms_y + np.finfo(float).eps))


def _window_starts(nlon: int, window_size: int, step: int) -> Tuple[List[int], np.ndarray]:
    step = max(1, int(step))
    window_size = min(int(window_size), int(nlon))
    forward_starts = list(range(0, nlon - window_size + 1, step))
    backward_starts = [
        end_idx - window_size + 1
        for end_idx in range(nlon - 1, window_size - 2, -step)
    ]
    starts = sorted(set(forward_starts + backward_starts))
    weight_template = np.zeros(nlon, dtype=float)
    for start in starts:
        weight_template[start : start + window_size] += 1.0
    return starts, weight_template


def _classify_month_severity(month_metrics: Dict[str, float]) -> Tuple[str, float, int]:
    band_energy = float(month_metrics.get("ocean_stripe_band_energy", 0.0))
    anisotropy = float(month_metrics.get("ocean_anisotropy_index", 0.0))
    z_band = (band_energy - 0.12) / 0.04
    z_aniso = (anisotropy - 1.6) / 0.5
    severity = z_band + z_aniso
    if severity < 1.0:
        return "low", 1.00, 3
    if severity < 2.5:
        return "medium", 1.15, 5
    return "high", 1.30, 5


def _latband_adjustments(lat_value: float) -> Tuple[float, int]:
    lat_abs = abs(float(lat_value))
    if lat_abs < 20.0:
        return 0.95, 0
    if lat_abs < 50.0:
        return 1.00, 0
    return 1.05, 1


def _summarize_params(params: Dict[str, Any]) -> Dict[str, Any]:
    summary = {}
    for key, value in dict(params).items():
        if isinstance(value, np.ndarray):
            summary[key] = f"ndarray{tuple(int(v) for v in value.shape)}"
        else:
            summary[key] = value
    return summary


def _run_modal_adaptive_map(
    grid: np.ndarray,
    lat_vec: np.ndarray,
    Ts: float,
    params: Dict[str, Any],
    *,
    latband: bool = False,
    residual_first: bool = False,
    directional_template: bool = False,
    engine_name: str = "modal_adaptive_v1",
) -> Tuple[np.ndarray, Dict[str, Any]]:
    Y = np.asarray(grid, dtype=float).copy()
    nan_mask = ~np.isfinite(Y)
    if np.any(nan_mask):
        Y = _fill_nan_grid(Y)

    land_mask = params.get("land_mask")
    if land_mask is not None:
        land_mask = np.asarray(land_mask, dtype=bool)
    source_grid = Y
    background = np.zeros_like(Y)
    residual_meta = {}
    if residual_first:
        background, source_grid, residual_meta = _decompose_background_residual(Y, params)

    ocean_mask = _derive_ocean_mask(source_grid, land_mask)
    band_info = estimate_stripe_band(source_grid, land_mask=land_mask)
    month_metrics = compute_stripe_metrics(source_grid, land_mask=land_mask, band_info=band_info)
    stripe_template = None
    if directional_template:
        stripe_template = build_stripe_template_map(
            source_grid,
            band_info,
            land_mask=land_mask,
            lat_smooth_window=int(params.get("template_lat_smooth_window", 5)),
        )
    severity_label = "fixed"
    severity_gain = 1.0
    severity_neighbors = 2
    if latband:
        severity_label, severity_gain, severity_neighbors = _classify_month_severity(month_metrics)

    window_size = int(params.get("N", 30))
    p = int(params.get("P", 10))
    order = int(params.get("K", 6))
    step = int(params.get("J", 1))
    iterations = max(1, int(params.get("iterations", 1)))
    starts, _ = _window_starts(Y.shape[0], window_size, step)

    noise_acc = np.zeros_like(Y, dtype=float)
    noise_w = np.zeros_like(Y, dtype=float)
    freq_tol = max(1.5 * float(band_info["width"]), 2.0 / max(1, window_size))
    center = float(band_info["center"])
    width = float(band_info["width"])

    result = source_grid.copy()
    for _ in range(iterations):
        noise_acc.fill(0.0)
        noise_w.fill(0.0)
        for start in starts:
            end = start + window_size
            window_recs: List[_WindowDecomposition] = []
            for j in range(result.shape[1]):
                window_recs.append(_build_window_decomposition(result[start:end, j], Ts, p, order))

            for j, rec in enumerate(window_recs):
                if not rec.valid:
                    continue
                lat_gain, lat_neighbor_bonus = _latband_adjustments(lat_vec[j]) if latband else (1.0, 0)
                neighbor_width = severity_neighbors + lat_neighbor_bonus if latband else 2
                ocean_seg = ocean_mask[start:end, j] if ocean_mask.size else None
                energy_order = np.argsort(rec.energy_ratio)[::-1]
                dominant = set(int(v) for v in energy_order[:2])
                noise_seg = np.zeros(window_size, dtype=float)

                for mode_idx in range(rec.modes.shape[0]):
                    band_score = _mode_band_score(rec.freq_norm[mode_idx], center, width)
                    persistence_scores = []
                    patch_rows = [rec.modes[mode_idx]]
                    for dj in range(1, neighbor_width + 1):
                        for jj in (j - dj, j + dj):
                            if jj < 0 or jj >= len(window_recs):
                                continue
                            neighbor = window_recs[jj]
                            if not neighbor.valid:
                                continue
                            best_idx, closeness = _mode_match(rec.freq_norm[mode_idx], neighbor.freq_norm, freq_tol)
                            persistence_scores.append(closeness)
                            if closeness > 0 and best_idx >= 0:
                                patch_rows.append(neighbor.modes[best_idx])
                    if persistence_scores:
                        match_frac = float(np.mean(np.asarray(persistence_scores) > 0))
                        mean_close = float(np.mean([s for s in persistence_scores if s > 0])) if any(s > 0 for s in persistence_scores) else 0.0
                        persistence = 0.5 * (match_frac + mean_close)
                    else:
                        persistence = 0.0
                    anisotropy = _patch_anisotropy_score(np.vstack(patch_rows))
                    ocean_bias = _mode_ocean_bias_score(rec.modes[mode_idx], ocean_seg)
                    pole_aux = _mode_pole_aux_score(rec.energy_ratio[mode_idx], rec.pole_mag[mode_idx] if mode_idx < rec.pole_mag.size else 1.0)
                    template_score = 0.0
                    template_strength = 0.0
                    if directional_template and stripe_template is not None:
                        template_seg = stripe_template[start:end, j]
                        template_score = _safe_abs_corr(rec.modes[mode_idx], template_seg)
                        src_seg = source_grid[start:end, j]
                        src_std = float(np.nanstd(src_seg))
                        if src_std > 0:
                            template_strength = float(np.clip(np.nanstd(template_seg) / src_std, 0.0, 1.0))
                    if directional_template:
                        stripe_score = (
                            0.40 * template_score
                            + 0.20 * band_score
                            + 0.15 * persistence
                            + 0.10 * ocean_bias
                            + 0.10 * anisotropy
                            + 0.05 * pole_aux
                        )
                        if template_score < 0.45 or template_strength < 0.15:
                            attenuation = min(0.20, 0.25 * stripe_score)
                        else:
                            attenuation = min(0.65, float(stripe_score ** 1.15) * (0.75 + 0.25 * template_strength))
                    elif residual_first:
                        stripe_score = (
                            0.35 * band_score
                            + 0.25 * persistence
                            + 0.15 * ocean_bias
                            + 0.20 * anisotropy
                            + 0.05 * pole_aux
                        )
                        attenuation = min(0.75, float(stripe_score ** 1.25))
                    else:
                        stripe_score = (
                            0.30 * band_score
                            + 0.25 * persistence
                            + 0.20 * ocean_bias
                            + 0.15 * anisotropy
                            + 0.10 * pole_aux
                        )
                        attenuation = min(0.85, float(stripe_score ** 1.5))
                    attenuation = min(0.95, attenuation * severity_gain * lat_gain)
                    if mode_idx in dominant:
                        if directional_template:
                            attenuation = min(attenuation, 0.25)
                        else:
                            attenuation = min(attenuation, 0.35 if residual_first else 0.50)
                    noise_seg += attenuation * rec.modes[mode_idx]

                noise_acc[start:end, j] += noise_seg
                noise_w[start:end, j] += 1.0

        valid = noise_w > 0
        if not np.any(valid):
            break
        noise_map = np.zeros_like(result, dtype=float)
        noise_map[valid] = noise_acc[valid] / noise_w[valid]
        result = source_grid - noise_map

    if residual_first:
        result = background + result

    if np.any(nan_mask):
        result[nan_mask] = np.nan
    info = {
        "type": "HSAF_modal_adaptive",
        "engine": engine_name,
        "params": _summarize_params(params),
        "stripe_band": {
            "center": center,
            "width": width,
            "n_profiles": int(band_info.get("n_profiles", 0)),
        },
        "month_metrics": month_metrics,
        "month_severity": severity_label,
        "residual_first": bool(residual_first),
        "residual_meta": residual_meta,
        "directional_template": bool(directional_template),
    }
    return result, info


def _reconstruct_hankel_antidiagonal(H_block: np.ndarray) -> np.ndarray:
    H = np.asarray(H_block, dtype=float)
    nrow, ncol = H.shape
    out_len = nrow + ncol - 1
    rows_idx, cols_idx = np.indices((nrow, ncol))
    diag_idx = (rows_idx + cols_idx).ravel()
    out = np.zeros(out_len, dtype=float)
    cnt = np.zeros(out_len, dtype=np.int32)
    np.add.at(out, diag_idx, H.ravel())
    np.add.at(cnt, diag_idx, 1)
    cnt[cnt == 0] = 1
    return out / cnt


def _run_multichannel_map(
    grid: np.ndarray,
    lat_vec: np.ndarray,
    params: Dict[str, Any],
    *,
    residual_first: bool = False,
    directional_template: bool = False,
    engine_name: str = "multichannel_v1",
) -> Tuple[np.ndarray, Dict[str, Any]]:
    Y = np.asarray(grid, dtype=float).copy()
    nan_mask = ~np.isfinite(Y)
    if np.any(nan_mask):
        Y = _fill_nan_grid(Y)

    land_mask = params.get("land_mask")
    if land_mask is not None:
        land_mask = np.asarray(land_mask, dtype=bool)
    source_grid = Y
    background = np.zeros_like(Y)
    residual_meta = {}
    if residual_first:
        background, source_grid, residual_meta = _decompose_background_residual(Y, params)

    ocean_mask = _derive_ocean_mask(source_grid, land_mask)
    band_info = estimate_stripe_band(source_grid, land_mask=land_mask)
    month_metrics = compute_stripe_metrics(source_grid, land_mask=land_mask, band_info=band_info)
    stripe_template = None
    if directional_template:
        stripe_template = build_stripe_template_map(
            source_grid,
            band_info,
            land_mask=land_mask,
            lat_smooth_window=int(params.get("template_lat_smooth_window", 5)),
        )

    window_size = int(params.get("N", 30))
    p = int(params.get("P", 10))
    rank = int(params.get("K", 6))
    step = int(params.get("J", 1))
    iterations = max(1, int(params.get("iterations", 1)))
    starts, _ = _window_starts(Y.shape[0], window_size, step)
    q = max(1, window_size - p + 1)
    center = float(band_info["center"])
    width = float(band_info["width"])

    result = source_grid.copy()
    noise_acc = np.zeros_like(Y, dtype=float)
    noise_w = np.zeros_like(Y, dtype=float)
    for _ in range(iterations):
        noise_acc.fill(0.0)
        noise_w.fill(0.0)
        for j in range(result.shape[1]):
            lat0 = max(0, j - 2)
            lat1 = min(result.shape[1], j + 3)
            lat_idx = np.arange(lat0, lat1)
            center_idx = int(np.where(lat_idx == j)[0][0])
            for start in starts:
                end = start + window_size
                patch = np.asarray(result[start:end, lat_idx], dtype=float).T
                if patch.size == 0 or patch.shape[1] < window_size:
                    continue
                try:
                    blocks = [hankel(row[:p], row[p - 1 :]) for row in patch]
                    H = np.vstack(blocks)
                    U, s, Vh = svd(H, full_matrices=False, check_finite=False)
                except Exception:
                    continue
                rank_eff = min(rank, len(s))
                if rank_eff <= 0:
                    continue
                singular_energy = np.square(s[:rank_eff])
                total_singular = float(np.sum(singular_energy))
                noise_seg = np.zeros(window_size, dtype=float)
                dominant = set(range(min(2, rank_eff)))
                for r in range(rank_eff):
                    H_r = s[r] * np.outer(U[:, r], Vh[r, :])
                    component_patch = np.zeros((patch.shape[0], window_size), dtype=float)
                    for c in range(patch.shape[0]):
                        block = H_r[c * p : (c + 1) * p, :]
                        component_patch[c] = _reconstruct_hankel_antidiagonal(block)
                    center_signal = component_patch[center_idx]
                    freq_norm = _dominant_frequency_norm(center_signal)
                    band_score = _mode_band_score(freq_norm, center, width)
                    channel_energy = np.sum(np.square(component_patch), axis=1)
                    total_energy = float(np.sum(channel_energy))
                    center_energy = float(channel_energy[center_idx]) if center_idx < channel_energy.size else 0.0
                    persistence = 0.0
                    if total_energy > 0 and component_patch.shape[0] > 1:
                        persistence = np.clip(
                            (total_energy - center_energy) / total_energy * (component_patch.shape[0] / max(1, component_patch.shape[0] - 1)),
                            0.0,
                            1.0,
                        )
                    anisotropy = _patch_anisotropy_score(component_patch)
                    ocean_seg = ocean_mask[start:end, j] if ocean_mask.size else None
                    ocean_bias = _mode_ocean_bias_score(center_signal, ocean_seg)
                    sv_ratio = float(singular_energy[r] / total_singular) if total_singular > 0 else 0.0
                    pole_aux = float(np.clip((0.15 - sv_ratio) / 0.15, 0.0, 1.0))
                    template_score = 0.0
                    template_strength = 0.0
                    if directional_template and stripe_template is not None:
                        template_seg = stripe_template[start:end, j]
                        template_score = _safe_abs_corr(center_signal, template_seg)
                        src_seg = source_grid[start:end, j]
                        src_std = float(np.nanstd(src_seg))
                        if src_std > 0:
                            template_strength = float(np.clip(np.nanstd(template_seg) / src_std, 0.0, 1.0))
                    if directional_template:
                        stripe_score = (
                            0.40 * template_score
                            + 0.20 * band_score
                            + 0.15 * persistence
                            + 0.10 * ocean_bias
                            + 0.10 * anisotropy
                            + 0.05 * pole_aux
                        )
                        if template_score < 0.45 or template_strength < 0.15:
                            attenuation = min(0.20, 0.25 * stripe_score)
                        else:
                            attenuation = min(0.60, float(stripe_score ** 1.10) * (0.75 + 0.25 * template_strength))
                    elif residual_first:
                        stripe_score = (
                            0.30 * band_score
                            + 0.35 * persistence
                            + 0.15 * ocean_bias
                            + 0.15 * anisotropy
                            + 0.05 * pole_aux
                        )
                        attenuation = min(0.70, float(stripe_score ** 1.20))
                    else:
                        stripe_score = (
                            0.25 * band_score
                            + 0.35 * persistence
                            + 0.20 * ocean_bias
                            + 0.15 * anisotropy
                            + 0.05 * pole_aux
                        )
                        attenuation = min(0.85, float(stripe_score ** 1.5))
                    if r in dominant:
                        if directional_template:
                            attenuation = min(attenuation, 0.20)
                        else:
                            attenuation = min(attenuation, 0.30 if residual_first else 0.50)
                    noise_seg += attenuation * center_signal
                noise_acc[start:end, j] += noise_seg
                noise_w[start:end, j] += 1.0

        valid = noise_w > 0
        if not np.any(valid):
            break
        noise_map = np.zeros_like(result, dtype=float)
        noise_map[valid] = noise_acc[valid] / noise_w[valid]
        result = source_grid - noise_map

    if residual_first:
        result = background + result

    if np.any(nan_mask):
        result[nan_mask] = np.nan
    info = {
        "type": "HSAF_multichannel",
        "engine": engine_name,
        "params": _summarize_params(params),
        "stripe_band": {
            "center": center,
            "width": width,
            "n_profiles": int(band_info.get("n_profiles", 0)),
        },
        "month_metrics": month_metrics,
        "residual_first": bool(residual_first),
        "residual_meta": residual_meta,
        "directional_template": bool(directional_template),
    }
    return result, info


def _run_demod_profile_map(
    grid: np.ndarray,
    lat_vec: np.ndarray,
    params: Dict[str, Any],
    *,
    multichannel: bool = False,
    engine_name: str = "demod_profile_v1",
) -> Tuple[np.ndarray, Dict[str, Any]]:
    Y = np.asarray(grid, dtype=float).copy()
    nan_mask = ~np.isfinite(Y)
    if np.any(nan_mask):
        Y = _fill_nan_grid(Y)

    land_mask = params.get("land_mask")
    if land_mask is not None:
        land_mask = np.asarray(land_mask, dtype=bool)

    background, residual, residual_meta = _decompose_background_residual(Y, params)
    band_info = estimate_stripe_band(residual, land_mask=land_mask)
    month_metrics = compute_stripe_metrics(residual, land_mask=land_mask, band_info=band_info)
    severity_label, severity_gain, severity_neighbors = _classify_month_severity(month_metrics)
    center = float(band_info["center"])
    width = float(band_info["width"])

    nlon, nlat = residual.shape
    band_profiles: List[np.ndarray] = []
    env_profiles: List[np.ndarray] = []
    unit_profiles: List[np.ndarray] = []
    ocean_fracs = np.zeros(nlat, dtype=float)

    ocean_mask = _derive_ocean_mask(residual, land_mask)
    for j in range(nlat):
        comp = _analytic_profile_components(residual[:, j], center=center, width=width)
        band_profiles.append(comp["band"])
        env_profiles.append(comp["env"])
        unit_profiles.append(comp["unit"])
        ocean_fracs[j] = float(np.mean(ocean_mask[:, j])) if ocean_mask.size else 1.0

    band_profiles_arr = np.column_stack(band_profiles)
    stripe_map = np.zeros_like(residual, dtype=float)
    used_neighbors = []

    for j in range(nlat):
        lat_gain, lat_neighbor_bonus = _latband_adjustments(lat_vec[j])
        neighbor_width = int(severity_neighbors + lat_neighbor_bonus)
        idxs = list(range(max(0, j - neighbor_width), min(nlat, j + neighbor_width + 1)))
        coherence_weights = []
        aligned_envs = []
        aligned_units = []
        center_band = band_profiles_arr[:, j]
        center_unit = unit_profiles[j]
        for jj in idxs:
            cand_band = band_profiles_arr[:, jj]
            corr = _signed_corr(center_band, cand_band)
            if jj == j:
                weight = 1.0
                sign = 1.0
            else:
                sign = -1.0 if corr < 0 else 1.0
                weight = max(0.0, abs(corr) - 0.10)
                if weight <= 0:
                    continue
            coherence_weights.append(weight)
            aligned_envs.append(env_profiles[jj])
            aligned_units.append(sign * unit_profiles[jj])

        if not coherence_weights:
            stripe_component = center_band.copy()
            used_neighbors.append(1)
        else:
            weights = np.asarray(coherence_weights, dtype=float)
            env_shared = np.average(np.stack(aligned_envs, axis=0), axis=0, weights=weights)
            if multichannel:
                unit_stack = np.stack(aligned_units, axis=0)
                unit_shared = np.sum(unit_stack * weights[:, None], axis=0)
                unit_shared /= np.maximum(np.abs(unit_shared), np.finfo(float).eps)
                stripe_component = env_shared * np.real(unit_shared)
            else:
                stripe_component = env_shared * np.real(center_unit)
            used_neighbors.append(len(coherence_weights))

        land_penalty = 0.75 if (1.0 - ocean_fracs[j]) > 0.55 else 1.0
        gain = _demod_gain(
            residual[:, j],
            stripe_component,
            ocean_fracs[j],
            severity_gain=severity_gain * lat_gain,
            land_penalty=land_penalty,
        )
        stripe_map[:, j] = gain * stripe_component

    stripe_map = _smooth_grid_separable(
        stripe_map,
        lon_window=max(5, int(params.get("template_lon_window", 9))),
        lat_window=max(3, int(params.get("template_lat_smooth_window", 5))),
    )
    result = background + (residual - stripe_map)
    if np.any(nan_mask):
        result[nan_mask] = np.nan
    info = {
        "type": "HSAF_demodulation",
        "engine": engine_name,
        "params": _summarize_params(params),
        "stripe_band": {
            "center": center,
            "width": width,
            "n_profiles": int(band_info.get("n_profiles", 0)),
        },
        "month_metrics": month_metrics,
        "month_severity": severity_label,
        "residual_meta": residual_meta,
        "avg_neighbors": float(np.mean(used_neighbors)) if used_neighbors else 0.0,
        "multichannel": bool(multichannel),
    }
    return result, info


def filter_grid_hsaf_demod(
    grid: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    config: Dict[str, Any],
    *,
    multichannel: bool = False,
    engine_name: str = "demod_profile_v1",
) -> Tuple[np.ndarray, Dict[str, Any]]:
    grid = ensure_latlon_order(grid, lon_vec, lat_vec, target_order="lon_lat")
    is_3d = grid.ndim == 3
    if not is_3d:
        grid = grid[:, :, np.newaxis]

    params = config.get("params", {}) if isinstance(config, dict) else getattr(config, "params", {})
    out = np.zeros_like(grid)
    slice_info = []
    for t in range(grid.shape[2]):
        out[:, :, t], info_t = _run_demod_profile_map(
            grid[:, :, t],
            lat_vec,
            params,
            multichannel=multichannel,
            engine_name=engine_name,
        )
        slice_info.append(info_t)
    if not is_3d:
        out = out[:, :, 0]
    return out, {
        "type": "HSAF_demodulation",
        "engine": engine_name,
        "params": _summarize_params(params),
        "slices": slice_info,
    }


def _run_bundle_template_map(
    grid: np.ndarray,
    lat_vec: np.ndarray,
    params: Dict[str, Any],
    *,
    multichannel: bool = False,
    engine_name: str = "bundle_template_v1",
) -> Tuple[np.ndarray, Dict[str, Any]]:
    Y = np.asarray(grid, dtype=float).copy()
    nan_mask = ~np.isfinite(Y)
    if np.any(nan_mask):
        Y = _fill_nan_grid(Y)

    land_mask = params.get("land_mask")
    if land_mask is not None:
        land_mask = np.asarray(land_mask, dtype=bool)

    background, residual, residual_meta = _decompose_background_residual(Y, params)
    band_info = estimate_stripe_band(residual, land_mask=land_mask)
    month_metrics = compute_stripe_metrics(residual, land_mask=land_mask, band_info=band_info)
    severity_label, severity_gain, severity_neighbors = _classify_month_severity(month_metrics)

    center = float(band_info["center"])
    width = float(band_info["width"])
    nlon, nlat = residual.shape
    x = np.arange(nlon, dtype=float)
    carrier = np.exp(-1j * 2.0 * np.pi * center * x)[:, None]
    baseband = np.zeros((nlon, nlat), dtype=complex)
    ocean_mask = _derive_ocean_mask(residual, land_mask)
    ocean_fracs = np.zeros(nlat, dtype=float)
    weights = np.full((nlon, nlat), 0.25, dtype=float)

    for j in range(nlat):
        band = _bandpass_profile_fft(residual[:, j], center=center, width=width)
        try:
            analytic = hilbert(np.asarray(band, dtype=float))
        except Exception:
            analytic = np.asarray(band, dtype=float).astype(complex)
        baseband[:, j] = analytic * carrier[:, 0]
        ocean_fracs[j] = float(np.mean(ocean_mask[:, j])) if ocean_mask.size else 1.0
        weights[:, j] = np.where(ocean_mask[:, j], 1.0, 0.20)

    lon_window = max(9, int(params.get("bundle_lon_window", max(9, (nlon // 12) | 1))))
    lat_window = max(3, int(params.get("bundle_lat_window", 2 * severity_neighbors + 1)))
    if lon_window % 2 == 0:
        lon_window += 1
    if lat_window % 2 == 0:
        lat_window += 1

    template_baseband = _smooth_complex_grid_weighted(baseband, weights, lon_window=lon_window, lat_window=lat_window)
    if multichannel:
        rank = int(params.get("bundle_rank", 2 if severity_label != "high" else 3))
        template_baseband = _complex_rank_k_approx(template_baseband, rank=rank)

    stripe_template = np.real(template_baseband * np.conj(carrier))
    stripe_template = _smooth_grid_separable(
        stripe_template,
        lon_window=max(5, lon_window // 2),
        lat_window=max(3, lat_window),
    )

    stripe_map = np.zeros_like(residual, dtype=float)
    for j in range(nlat):
        lat_gain, _ = _latband_adjustments(lat_vec[j])
        land_penalty = 0.70 if (1.0 - ocean_fracs[j]) > 0.55 else 1.0
        gain = 0.60 * _demod_gain(
            residual[:, j],
            stripe_template[:, j],
            ocean_fracs[j],
            severity_gain=severity_gain * lat_gain,
            land_penalty=land_penalty,
        )
        stripe_map[:, j] = gain * stripe_template[:, j]

    result = background + (residual - stripe_map)
    if np.any(nan_mask):
        result[nan_mask] = np.nan
    info = {
        "type": "HSAF_bundle_template",
        "engine": engine_name,
        "params": _summarize_params(params),
        "stripe_band": {
            "center": center,
            "width": width,
            "n_profiles": int(band_info.get("n_profiles", 0)),
        },
        "month_metrics": month_metrics,
        "month_severity": severity_label,
        "residual_meta": residual_meta,
        "bundle_windows": {
            "lon_window": int(lon_window),
            "lat_window": int(lat_window),
        },
        "multichannel": bool(multichannel),
    }
    return result, info


def filter_grid_hsaf_bundle_template(
    grid: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    config: Dict[str, Any],
    *,
    multichannel: bool = False,
    engine_name: str = "bundle_template_v1",
) -> Tuple[np.ndarray, Dict[str, Any]]:
    grid = ensure_latlon_order(grid, lon_vec, lat_vec, target_order="lon_lat")
    is_3d = grid.ndim == 3
    if not is_3d:
        grid = grid[:, :, np.newaxis]

    params = config.get("params", {}) if isinstance(config, dict) else getattr(config, "params", {})
    out = np.zeros_like(grid)
    slice_info = []
    for t in range(grid.shape[2]):
        out[:, :, t], info_t = _run_bundle_template_map(
            grid[:, :, t],
            lat_vec,
            params,
            multichannel=multichannel,
            engine_name=engine_name,
        )
        slice_info.append(info_t)
    if not is_3d:
        out = out[:, :, 0]
    return out, {
        "type": "HSAF_bundle_template",
        "engine": engine_name,
        "params": _summarize_params(params),
        "slices": slice_info,
    }


def filter_grid_hsaf_modal_adaptive(
    grid: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    config: Dict[str, Any],
    *,
    latband: bool = False,
    residual_first: bool = False,
    directional_template: bool = False,
    engine_name: Optional[str] = None,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    grid = ensure_latlon_order(grid, lon_vec, lat_vec, target_order="lon_lat")
    is_3d = grid.ndim == 3
    if not is_3d:
        grid = grid[:, :, np.newaxis]

    params = config.get("params", {}) if isinstance(config, dict) else getattr(config, "params", {})
    Ts = float(np.abs(lon_vec[1] - lon_vec[0])) if len(lon_vec) > 1 else 1.0
    out = np.zeros_like(grid)
    slice_info = []
    if engine_name is None:
        engine_name = "modal_adaptive_latband_v1" if latband else "modal_adaptive_v1"
    for t in range(grid.shape[2]):
        out[:, :, t], info_t = _run_modal_adaptive_map(
            grid[:, :, t],
            lat_vec,
            Ts,
            params,
            latband=latband,
            residual_first=residual_first,
            directional_template=directional_template,
            engine_name=engine_name,
        )
        slice_info.append(info_t)
    if not is_3d:
        out = out[:, :, 0]
    info = {
        "type": "HSAF_modal_adaptive",
        "engine": engine_name,
        "params": _summarize_params(params),
        "slices": slice_info,
    }
    return out, info


def filter_grid_hsaf_multichannel(
    grid: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    config: Dict[str, Any],
    *,
    residual_first: bool = False,
    directional_template: bool = False,
    engine_name: str = "multichannel_v1",
) -> Tuple[np.ndarray, Dict[str, Any]]:
    grid = ensure_latlon_order(grid, lon_vec, lat_vec, target_order="lon_lat")
    is_3d = grid.ndim == 3
    if not is_3d:
        grid = grid[:, :, np.newaxis]

    params = config.get("params", {}) if isinstance(config, dict) else getattr(config, "params", {})
    out = np.zeros_like(grid)
    slice_info = []
    for t in range(grid.shape[2]):
        out[:, :, t], info_t = _run_multichannel_map(
            grid[:, :, t],
            lat_vec,
            params,
            residual_first=residual_first,
            directional_template=directional_template,
            engine_name=engine_name,
        )
        slice_info.append(info_t)
    if not is_3d:
        out = out[:, :, 0]
    info = {
        "type": "HSAF_multichannel",
        "engine": engine_name,
        "params": _summarize_params(params),
        "slices": slice_info,
    }
    return out, info


def filter_grid_hsaf(
    grid: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
    config: Dict[str, Any],
    Ts: float = 1.0,
    progress_hook: Optional[Callable[[int, int], None]] = None,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Dispatch HSAF engine. Default uses MATLAB-aligned global HSAF.
    """
    if isinstance(config, dict):
        engine = config.get("engine")
    else:
        engine = getattr(config, "engine", None)
    engine = (engine or "matlab_v3").lower()

    if engine in ("matlab", "matlab_v3", "hsa"):
        return filter_grid_hsaf_matlab(grid, lon_vec, lat_vec, config, Ts=None, progress_hook=progress_hook)
    if engine == "modal_adaptive_v1":
        return filter_grid_hsaf_modal_adaptive(grid, lon_vec, lat_vec, config, latband=False)
    if engine == "modal_adaptive_latband_v1":
        return filter_grid_hsaf_modal_adaptive(grid, lon_vec, lat_vec, config, latband=True)
    if engine == "multichannel_v1":
        return filter_grid_hsaf_multichannel(grid, lon_vec, lat_vec, config)
    if engine == "modal_adaptive_v2":
        return filter_grid_hsaf_modal_adaptive(
            grid,
            lon_vec,
            lat_vec,
            config,
            latband=False,
            residual_first=True,
            engine_name="modal_adaptive_v2",
        )
    if engine == "modal_adaptive_latband_v2":
        return filter_grid_hsaf_modal_adaptive(
            grid,
            lon_vec,
            lat_vec,
            config,
            latband=True,
            residual_first=True,
            engine_name="modal_adaptive_latband_v2",
        )
    if engine == "multichannel_v2":
        return filter_grid_hsaf_multichannel(
            grid,
            lon_vec,
            lat_vec,
            config,
            residual_first=True,
            engine_name="multichannel_v2",
        )
    if engine == "modal_adaptive_v3":
        return filter_grid_hsaf_modal_adaptive(
            grid,
            lon_vec,
            lat_vec,
            config,
            latband=False,
            residual_first=True,
            directional_template=True,
            engine_name="modal_adaptive_v3",
        )
    if engine == "modal_adaptive_latband_v3":
        return filter_grid_hsaf_modal_adaptive(
            grid,
            lon_vec,
            lat_vec,
            config,
            latband=True,
            residual_first=True,
            directional_template=True,
            engine_name="modal_adaptive_latband_v3",
        )
    if engine == "multichannel_v3":
        return filter_grid_hsaf_multichannel(
            grid,
            lon_vec,
            lat_vec,
            config,
            residual_first=True,
            directional_template=True,
            engine_name="multichannel_v3",
        )
    if engine == "demod_profile_v1":
        return filter_grid_hsaf_demod(
            grid,
            lon_vec,
            lat_vec,
            config,
            multichannel=False,
            engine_name="demod_profile_v1",
        )
    if engine == "demod_multichannel_v1":
        return filter_grid_hsaf_demod(
            grid,
            lon_vec,
            lat_vec,
            config,
            multichannel=True,
            engine_name="demod_multichannel_v1",
        )
    if engine == "bundle_template_v1":
        return filter_grid_hsaf_bundle_template(
            grid,
            lon_vec,
            lat_vec,
            config,
            multichannel=False,
            engine_name="bundle_template_v1",
        )
    if engine == "bundle_template_multichannel_v1":
        return filter_grid_hsaf_bundle_template(
            grid,
            lon_vec,
            lat_vec,
            config,
            multichannel=True,
            engine_name="bundle_template_multichannel_v1",
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
    
    Args:
        grid: Input grid
        lon_vec: Longitude vector
        lat_vec: Latitude vector
        adaptive_config: List of {lat_range: [min, max], params: {...}}
    
    Returns:
        Tuple of (filtered_grid, info)
    """
    grid_f = grid.copy()
    
    for zone in adaptive_config:
        lat_range = zone.get('lat_range', [-90, 90])
        params = zone.get('params', {})
        
        # Find latitude indices in this zone
        lat_mask = (lat_vec >= lat_range[0]) & (lat_vec <= lat_range[1])
        lat_idx = np.where(lat_mask)[0]
        
        if len(lat_idx) == 0:
            continue
        
        # Extract and filter this zone
        if grid.ndim == 3:
            zone_grid = grid[:, lat_idx, :]
        else:
            zone_grid = grid[:, lat_idx]
        
        config = {'params': params, 'mode': zone.get('mode', 'profile')}
        zone_f, _ = filter_grid_hsaf_svd(zone_grid, lon_vec, lat_vec[lat_idx], config)
        
        if grid.ndim == 3:
            grid_f[:, lat_idx, :] = zone_f
        else:
            grid_f[:, lat_idx] = zone_f
    
    info = {
        'type': 'HSAF_adaptive',
        'zones': len(adaptive_config),
    }
    
    return grid_f, info

