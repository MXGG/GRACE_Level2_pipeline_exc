"""Experimental SH-domain HSA prototypes for GRACE stripe studies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

import numpy as np
from scipy.linalg import hankel, svd
from scipy.signal import hilbert

from grace_pipeline.filters.hsaf import h_rcs


@dataclass
class _SequenceDecomposition:
    valid: bool
    modes: np.ndarray
    freq_norm: np.ndarray
    energy_ratio: np.ndarray
    pole_mag: np.ndarray


def _fill_nan_1d(x: np.ndarray) -> np.ndarray:
    arr = np.asarray(x, dtype=float).ravel()
    mask = np.isfinite(arr)
    if mask.all() or np.count_nonzero(mask) < 2:
        return arr.copy()
    idx = np.arange(arr.size)
    out = arr.copy()
    out[~mask] = np.interp(idx[~mask], idx[mask], arr[mask])
    return out


def _dominant_frequency_norm(signal: np.ndarray) -> float:
    x = np.asarray(signal, dtype=float).ravel()
    if x.size < 4:
        return 0.0
    x = x - float(np.nanmean(x))
    spec = np.abs(np.fft.rfft(x))
    if spec.size <= 1:
        return 0.0
    idx = int(np.argmax(spec[1:]) + 1)
    freqs = np.fft.rfftfreq(x.size, d=1.0)
    return float(freqs[idx]) if idx < freqs.size else 0.0


def _rolling_mean_1d(x: np.ndarray, window: int) -> np.ndarray:
    arr = np.asarray(x, dtype=float).ravel()
    window = int(max(1, window))
    if arr.size == 0 or window <= 1 or arr.size < window:
        return arr.copy()
    if window % 2 == 0:
        window += 1
    kernel = np.ones(window, dtype=float) / float(window)
    return np.convolve(arr, kernel, mode="same")


def _bandpass_profile_fft(signal: np.ndarray, center: float, width: float) -> np.ndarray:
    x = np.asarray(signal, dtype=float).ravel()
    if x.size < 8:
        return np.zeros_like(x)
    x0 = x - float(np.nanmean(x))
    spec = np.fft.rfft(x0)
    freqs = np.fft.rfftfreq(x0.size, d=1.0)
    width = max(float(width), 1e-6)
    band = np.abs(freqs - float(center)) <= 1.5 * width
    if np.count_nonzero(band) == 0:
        idx = int(np.argmin(np.abs(freqs - float(center))))
        band[idx] = True
    filt = np.zeros_like(spec)
    filt[band] = spec[band]
    return np.fft.irfft(filt, n=x0.size)


def _safe_abs_corr(a: np.ndarray, b: np.ndarray) -> float:
    x = np.asarray(a).ravel()
    y = np.asarray(b).ravel()
    ok = np.isfinite(x) & np.isfinite(y)
    if np.count_nonzero(ok) < 4:
        return 0.0
    x = x[ok]
    y = y[ok]
    x = x - np.mean(x)
    y = y - np.mean(y)
    den = float(np.linalg.norm(x) * np.linalg.norm(y))
    if den <= 0:
        return 0.0
    return float(np.clip(abs(np.vdot(x, y) / den), 0.0, 1.0))


def _estimate_coeff_stripe_band(C: np.ndarray, S: np.ndarray, lmax: int, m_start: int) -> Dict[str, float]:
    freq_acc = None
    power_acc = None
    for coeff in (np.asarray(C, dtype=float), np.asarray(S, dtype=float)):
        for m in range(max(6, int(m_start)), int(lmax) + 1):
            for parity in (m % 2, 1 - (m % 2)):
                deg = _parity_degree_indices(m, lmax, parity)
                if deg.size < 8:
                    continue
                seq = _fill_nan_1d(coeff[deg, m])
                resid = seq - _rolling_mean_1d(seq, max(5, min(seq.size - (1 - seq.size % 2), 9)))
                spec = np.abs(np.fft.rfft(resid)) ** 2
                freqs = np.fft.rfftfreq(resid.size, d=1.0)
                candidate = (freqs >= 0.08) & (freqs <= 0.45)
                if not np.any(candidate):
                    continue
                if freq_acc is None:
                    freq_acc = freqs
                    power_acc = np.zeros_like(freqs)
                if len(freq_acc) == len(freqs):
                    power_acc += np.where(np.isfinite(spec), spec, 0.0)
    if freq_acc is None or power_acc is None or len(freq_acc) == 0:
        return {"center": 0.22, "width": 0.05}
    cand_idx = np.where((freq_acc >= 0.08) & (freq_acc <= 0.45))[0]
    if cand_idx.size == 0 or not np.any(power_acc[cand_idx] > 0):
        return {"center": 0.22, "width": 0.05}
    top_n = min(5, cand_idx.size)
    order = cand_idx[np.argsort(power_acc[cand_idx])[-top_n:]]
    weights = power_acc[order]
    center = float(np.average(freq_acc[order], weights=weights))
    variance = float(np.average((freq_acc[order] - center) ** 2, weights=weights)) if np.sum(weights) > 0 else 0.0
    width = max(0.03, float(np.sqrt(max(variance, 0.0))))
    return {"center": center, "width": width}


def _build_sequence_decomposition(seq: np.ndarray, p: int, order: int) -> _SequenceDecomposition:
    x = _fill_nan_1d(seq)
    if x.size < max(6, p + 1):
        return _SequenceDecomposition(False, np.empty((0, x.size)), np.empty(0), np.empty(0), np.empty(0))
    p_eff = max(2, min(int(p), x.size - 2))
    k_eff = max(1, min(int(order), x.size - 2))
    try:
        _, alfa, _, _, modes, _, _ = h_rcs(x, 1.0, p_eff, k_eff)
    except Exception:
        return _SequenceDecomposition(False, np.empty((0, x.size)), np.empty(0), np.empty(0), np.empty(0))
    modes = np.asarray(modes, dtype=float)
    if modes.ndim != 2 or modes.shape[0] == 0 or not np.isfinite(modes).all():
        return _SequenceDecomposition(False, np.empty((0, x.size)), np.empty(0), np.empty(0), np.empty(0))
    energies = np.sum(np.square(modes), axis=1)
    total = float(np.sum(energies))
    if total <= 0:
        return _SequenceDecomposition(False, np.empty((0, x.size)), np.empty(0), np.empty(0), np.empty(0))
    freq_norm = np.asarray([_dominant_frequency_norm(mode) for mode in modes], dtype=float)
    pole_mag = np.exp(np.asarray(alfa[: modes.shape[0]], dtype=float))
    energy_ratio = np.asarray(energies / total, dtype=float)
    return _SequenceDecomposition(True, modes, freq_norm, energy_ratio, pole_mag)


def _mode_highdegree_score(mode_signal: np.ndarray) -> float:
    x = np.asarray(mode_signal, dtype=float).ravel()
    energy = np.square(x)
    total = float(np.sum(energy))
    if total <= 0:
        return 0.0
    pos = np.linspace(0.0, 1.0, x.size)
    score = float(np.sum(energy * (pos ** 1.6)) / total)
    return float(np.clip(score, 0.0, 1.0))


def _mode_roughness_score(mode_signal: np.ndarray) -> float:
    x = np.asarray(mode_signal, dtype=float).ravel()
    if x.size < 3:
        return 0.0
    dx = np.diff(x)
    num = float(np.sum(np.square(dx)))
    den = float(np.sum(np.square(x)))
    if den <= 0:
        return 0.0
    return float(np.clip(num / (4.0 * den), 0.0, 1.0))


def _mode_order_score(order_m: int, m_start: int, lmax: int) -> float:
    den = max(1, int(lmax) - int(m_start))
    return float(np.clip((int(order_m) - int(m_start)) / den, 0.0, 1.0))


def _resolve_order_score(order_m: int, m_start: int, lmax: int, params: Dict[str, Any]) -> float:
    scores = params.get("orbit_order_scores")
    if scores is None:
        return _mode_order_score(order_m, m_start, lmax)
    arr = np.asarray(scores, dtype=float).ravel()
    if arr.size == 0:
        return _mode_order_score(order_m, m_start, lmax)
    idx = int(np.clip(int(order_m), 0, arr.size - 1))
    value = arr[idx]
    if not np.isfinite(value):
        return _mode_order_score(order_m, m_start, lmax)
    return float(np.clip(value, 0.0, 1.0))


def _mode_energy_score(energy_ratio: float) -> float:
    return float(np.clip((0.18 - float(energy_ratio)) / 0.18, 0.0, 1.0))


def _mode_frequency_score(freq_norm: float) -> float:
    return float(np.clip((float(freq_norm) - 0.10) / 0.28, 0.0, 1.0))


def _parity_degree_indices(order_m: int, lmax: int, parity: int) -> np.ndarray:
    idx = np.arange(int(order_m), int(lmax) + 1, dtype=int)
    return idx[idx % 2 == int(parity)]


def _apply_orderwise_channel(
    coeff: np.ndarray,
    lmax: int,
    params: Dict[str, Any],
) -> Tuple[np.ndarray, Dict[str, float]]:
    out = np.asarray(coeff, dtype=float).copy()
    p = int(params.get("P", 10))
    order_rank = int(params.get("K", 6))
    iterations = max(1, int(params.get("iterations", 1)))
    m_start = max(6, int(params.get("m_start", 6)))
    mode_score_sum = 0.0
    mode_count = 0

    for _ in range(iterations):
        for m in range(m_start, int(lmax) + 1):
            for parity in (m % 2, 1 - (m % 2)):
                degrees = _parity_degree_indices(m, lmax, parity)
                if degrees.size < max(6, p + 1):
                    continue
                seq = out[degrees, m]
                dec = _build_sequence_decomposition(seq, p=p, order=order_rank)
                if not dec.valid:
                    continue
                dominant = set(int(v) for v in np.argsort(dec.energy_ratio)[::-1][:2])
                noise = np.zeros_like(seq, dtype=float)
                order_score = _resolve_order_score(m, m_start, lmax, params)
                for mode_idx in range(dec.modes.shape[0]):
                    freq_score = _mode_frequency_score(dec.freq_norm[mode_idx])
                    highdeg_score = _mode_highdegree_score(dec.modes[mode_idx])
                    roughness_score = _mode_roughness_score(dec.modes[mode_idx])
                    energy_score = _mode_energy_score(dec.energy_ratio[mode_idx])
                    stripe_score = (
                        0.30 * freq_score
                        + 0.25 * highdeg_score
                        + 0.20 * roughness_score
                        + 0.15 * order_score
                        + 0.10 * energy_score
                    )
                    attenuation = min(0.90, float(stripe_score ** 1.35) * (0.65 + 0.35 * order_score))
                    if mode_idx in dominant:
                        attenuation = min(attenuation, 0.35)
                    noise += attenuation * dec.modes[mode_idx]
                    mode_score_sum += stripe_score
                    mode_count += 1
                out[degrees, m] = _fill_nan_1d(seq) - noise
    return out, {
        "avg_mode_score": float(mode_score_sum / mode_count) if mode_count else 0.0,
        "mode_count": float(mode_count),
    }


def filter_sh_hsaf_orderwise(
    C: np.ndarray,
    S: np.ndarray,
    Lmax: int,
    params: Dict[str, Any],
    *,
    engine_name: str = "sh_orderwise_v1",
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    c_out, c_meta = _apply_orderwise_channel(C, Lmax, params)
    s_out, s_meta = _apply_orderwise_channel(S, Lmax, params)
    info = {
        "type": "HSAF_SH",
        "engine": engine_name,
        "params": dict(params),
        "c_meta": c_meta,
        "s_meta": s_meta,
    }
    return c_out, s_out, info


def _reconstruct_antidiagonal(block: np.ndarray) -> np.ndarray:
    H = np.asarray(block, dtype=float)
    nrow, ncol = H.shape
    out_len = nrow + ncol - 1
    out = np.zeros(out_len, dtype=float)
    cnt = np.zeros(out_len, dtype=np.int32)
    rows, cols = np.indices((nrow, ncol))
    diag = (rows + cols).ravel()
    np.add.at(out, diag, H.ravel())
    np.add.at(cnt, diag, 1)
    cnt[cnt == 0] = 1
    return out / cnt


def _aligned_order_sequence(coeff: np.ndarray, base_degrees: np.ndarray, order_m: int) -> np.ndarray:
    seq = np.zeros(base_degrees.size, dtype=float)
    mask = base_degrees >= int(order_m)
    seq[mask] = coeff[base_degrees[mask], int(order_m)]
    return _fill_nan_1d(seq)


def _apply_multichannel_coeffs(
    C: np.ndarray,
    S: np.ndarray,
    lmax: int,
    params: Dict[str, Any],
) -> Tuple[np.ndarray, np.ndarray, Dict[str, float]]:
    c_out = np.asarray(C, dtype=float).copy()
    s_out = np.asarray(S, dtype=float).copy()
    p = int(params.get("P", 10))
    rank = int(params.get("K", 6))
    iterations = max(1, int(params.get("iterations", 1)))
    m_start = max(6, int(params.get("m_start", 6)))
    score_sum = 0.0
    component_count = 0

    for _ in range(iterations):
        for m in range(m_start, int(lmax) + 1):
            for parity in (m % 2, 1 - (m % 2)):
                base_degrees = _parity_degree_indices(m, lmax, parity)
                n = int(base_degrees.size)
                if n < max(6, p + 1):
                    continue
                p_eff = max(2, min(int(p), n - 2))
                q = n - p_eff + 1
                if q < 2:
                    continue
                channels = []
                labels = []
                for mm in range(max(m_start, m - 1), min(int(lmax), m + 1) + 1):
                    channels.append(_aligned_order_sequence(c_out, base_degrees, mm))
                    labels.append(("C", mm))
                    if mm > 0:
                        channels.append(_aligned_order_sequence(s_out, base_degrees, mm))
                        labels.append(("S", mm))
                if len(channels) < 4:
                    continue
                try:
                    blocks = [hankel(ch[:p_eff], ch[p_eff - 1 :]) for ch in channels]
                    H = np.vstack(blocks)
                    U, singular, Vh = svd(H, full_matrices=False, check_finite=False)
                except Exception:
                    continue
                rank_eff = min(int(rank), int(len(singular)))
                if rank_eff <= 0:
                    continue
                sing_sq = np.square(singular[:rank_eff])
                total_sing = float(np.sum(sing_sq))
                noise_c = np.zeros(n, dtype=float)
                noise_s = np.zeros(n, dtype=float)
                dominant = set(range(min(2, rank_eff)))

                center_c = next((idx for idx, label in enumerate(labels) if label == ("C", m)), None)
                center_s = next((idx for idx, label in enumerate(labels) if label == ("S", m)), None)
                if center_c is None:
                    continue

                for r in range(rank_eff):
                    Hr = singular[r] * np.outer(U[:, r], Vh[r, :])
                    reconstructed = []
                    for cidx in range(len(channels)):
                        block = Hr[cidx * p_eff : (cidx + 1) * p_eff, :]
                        reconstructed.append(_reconstruct_antidiagonal(block))
                    center_c_sig = reconstructed[center_c]
                    center_s_sig = reconstructed[center_s] if center_s is not None else np.zeros_like(center_c_sig)
                    combined = np.sqrt(np.square(center_c_sig) + np.square(center_s_sig))
                    freq_score = _mode_frequency_score(_dominant_frequency_norm(combined))
                    highdeg_score = _mode_highdegree_score(combined)
                    roughness_score = _mode_roughness_score(combined)
                    order_score = _resolve_order_score(m, m_start, lmax, params)
                    center_energy = float(np.sum(np.square(center_c_sig)) + np.sum(np.square(center_s_sig)))
                    total_energy = float(sum(np.sum(np.square(ch)) for ch in reconstructed))
                    persistence_score = 0.0
                    if total_energy > 0:
                        persistence_score = float(np.clip((total_energy - center_energy) / total_energy, 0.0, 1.0))
                    energy_score = _mode_energy_score(float(sing_sq[r] / total_sing) if total_sing > 0 else 0.0)
                    stripe_score = (
                        0.25 * freq_score
                        + 0.20 * highdeg_score
                        + 0.15 * roughness_score
                        + 0.25 * persistence_score
                        + 0.10 * order_score
                        + 0.05 * energy_score
                    )
                    attenuation = min(0.90, float(stripe_score ** 1.35) * (0.65 + 0.35 * order_score))
                    if r in dominant:
                        attenuation = min(attenuation, 0.30)
                    noise_c += attenuation * center_c_sig
                    noise_s += attenuation * center_s_sig
                    score_sum += stripe_score
                    component_count += 1

                c_out[base_degrees, m] = _fill_nan_1d(c_out[base_degrees, m]) - noise_c
                if m > 0 and center_s is not None:
                    s_out[base_degrees, m] = _fill_nan_1d(s_out[base_degrees, m]) - noise_s

    return c_out, s_out, {
        "avg_component_score": float(score_sum / component_count) if component_count else 0.0,
        "component_count": float(component_count),
    }


def filter_sh_hsaf_multichannel(
    C: np.ndarray,
    S: np.ndarray,
    Lmax: int,
    params: Dict[str, Any],
    *,
    engine_name: str = "sh_multichannel_v1",
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    c_out, s_out, meta = _apply_multichannel_coeffs(C, S, Lmax, params)
    info = {
        "type": "HSAF_SH",
        "engine": engine_name,
        "params": dict(params),
        "meta": meta,
    }
    return c_out, s_out, info


def _aligned_residual_baseband(
    coeff: np.ndarray,
    base_degrees: np.ndarray,
    order_m: int,
    *,
    center: float,
    width: float,
) -> Tuple[np.ndarray, np.ndarray]:
    seq = _aligned_order_sequence(coeff, base_degrees, order_m)
    trend = _rolling_mean_1d(seq, max(5, min(seq.size - (1 - seq.size % 2), 9)))
    resid = seq - trend
    band = _bandpass_profile_fft(resid, center=center, width=width)
    try:
        analytic = hilbert(np.asarray(band, dtype=float))
    except Exception:
        analytic = np.asarray(band, dtype=float).astype(complex)
    x = np.arange(seq.size, dtype=float)
    carrier = np.exp(-1j * 2.0 * np.pi * float(center) * x)
    baseband = analytic * carrier
    return trend, baseband


def _apply_demod_coeffs(
    C: np.ndarray,
    S: np.ndarray,
    lmax: int,
    params: Dict[str, Any],
    *,
    multichannel: bool = False,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, float]]:
    c_out = np.asarray(C, dtype=float).copy()
    s_out = np.asarray(S, dtype=float).copy()
    m_start = max(6, int(params.get("m_start", 6)))
    iterations = max(1, int(params.get("iterations", 1)))
    band = _estimate_coeff_stripe_band(c_out, s_out, lmax, m_start)
    center = float(band["center"])
    width = float(band["width"])
    score_sum = 0.0
    channel_count = 0

    for _ in range(iterations):
        for m in range(m_start, int(lmax) + 1):
            for parity in (m % 2, 1 - (m % 2)):
                base_degrees = _parity_degree_indices(m, lmax, parity)
                n = int(base_degrees.size)
                if n < 8:
                    continue
                carrier = np.exp(1j * 2.0 * np.pi * center * np.arange(n, dtype=float))
                neigh_orders = list(range(max(m_start, m - 2), min(int(lmax), m + 2) + 1))
                center_c = None
                center_s = None
                c_neighbors = []
                s_neighbors = []
                for mm in neigh_orders:
                    trend_c, bb_c = _aligned_residual_baseband(c_out, base_degrees, mm, center=center, width=width)
                    c_neighbors.append((mm, trend_c, bb_c))
                    if mm == m:
                        center_c = (trend_c, bb_c)
                    if mm > 0:
                        trend_s, bb_s = _aligned_residual_baseband(s_out, base_degrees, mm, center=center, width=width)
                        s_neighbors.append((mm, trend_s, bb_s))
                        if mm == m:
                            center_s = (trend_s, bb_s)
                if center_c is None:
                    continue
                weights_c = []
                bb_c_list = []
                for mm, _, bb in c_neighbors:
                    score = 1.0 if mm == m else _safe_abs_corr(center_c[1], bb)
                    if score <= 0.05:
                        continue
                    weights_c.append(score)
                    bb_c_list.append(bb)
                if not weights_c:
                    continue
                bb_c_stack = np.stack(bb_c_list, axis=1)
                if multichannel and bb_c_stack.shape[1] >= 2:
                    try:
                        U, s, Vh = np.linalg.svd(bb_c_stack, full_matrices=False)
                        rank = max(1, min(2, s.size))
                        template_c_bb = (U[:, :rank] * s[:rank]) @ Vh[:rank, :]
                        template_c = np.mean(template_c_bb, axis=1)
                    except Exception:
                        template_c = np.average(bb_c_stack, axis=1, weights=np.asarray(weights_c))
                else:
                    template_c = np.average(bb_c_stack, axis=1, weights=np.asarray(weights_c))
                stripe_c = np.real(template_c * carrier)
                order_score = _resolve_order_score(m, m_start, lmax, params)
                gain_c = min(
                    0.85,
                    (0.45 + 0.30 * order_score)
                    * np.clip(
                        np.nanstd(stripe_c)
                        / max(np.nanstd(center_c[0] + np.real(center_c[1] * carrier)), np.finfo(float).eps),
                        0.0,
                        1.5,
                    ),
                )
                c_out[base_degrees, m] = center_c[0] + np.real(center_c[1] * carrier) - gain_c * stripe_c
                score_sum += float(np.nanstd(stripe_c))
                channel_count += 1

                if m > 0 and center_s is not None:
                    weights_s = []
                    bb_s_list = []
                    for mm, _, bb in s_neighbors:
                        score = 1.0 if mm == m else _safe_abs_corr(center_s[1], bb)
                        if score <= 0.05:
                            continue
                        weights_s.append(score)
                        bb_s_list.append(bb)
                    if weights_s:
                        bb_s_stack = np.stack(bb_s_list, axis=1)
                        if multichannel and bb_s_stack.shape[1] >= 2:
                            try:
                                U, s, Vh = np.linalg.svd(bb_s_stack, full_matrices=False)
                                rank = max(1, min(2, s.size))
                                template_s_bb = (U[:, :rank] * s[:rank]) @ Vh[:rank, :]
                                template_s = np.mean(template_s_bb, axis=1)
                            except Exception:
                                template_s = np.average(bb_s_stack, axis=1, weights=np.asarray(weights_s))
                        else:
                            template_s = np.average(bb_s_stack, axis=1, weights=np.asarray(weights_s))
                        stripe_s = np.real(template_s * carrier)
                        gain_s = min(
                            0.85,
                            (0.45 + 0.30 * order_score)
                            * np.clip(
                                np.nanstd(stripe_s)
                                / max(np.nanstd(center_s[0] + np.real(center_s[1] * carrier)), np.finfo(float).eps),
                                0.0,
                                1.5,
                            ),
                        )
                        s_out[base_degrees, m] = center_s[0] + np.real(center_s[1] * carrier) - gain_s * stripe_s
                        score_sum += float(np.nanstd(stripe_s))
                        channel_count += 1

    return c_out, s_out, {
        "center": center,
        "width": width,
        "avg_template_std": float(score_sum / channel_count) if channel_count else 0.0,
        "channel_count": float(channel_count),
    }


def filter_sh_hsaf_demod(
    C: np.ndarray,
    S: np.ndarray,
    Lmax: int,
    params: Dict[str, Any],
    *,
    multichannel: bool = False,
    engine_name: str | None = None,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    c_out, s_out, meta = _apply_demod_coeffs(C, S, Lmax, params, multichannel=multichannel)
    if not engine_name:
        engine_name = "sh_demod_multichannel_v1" if multichannel else "sh_demod_v1"
    return c_out, s_out, {
        "type": "HSAF_SH",
        "engine": engine_name,
        "params": dict(params),
        "meta": meta,
    }


def filter_sh_hsaf(
    C: np.ndarray,
    S: np.ndarray,
    Lmax: int,
    config: Dict[str, Any],
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    engine = str(config.get("engine", "sh_orderwise_v1") or "sh_orderwise_v1").strip().lower()
    params = dict(config.get("params", {}) or {})
    if engine == "sh_orderwise_v1":
        return filter_sh_hsaf_orderwise(C, S, Lmax, params, engine_name=engine)
    if engine == "sh_orbit_orderwise_v1":
        return filter_sh_hsaf_orderwise(C, S, Lmax, params, engine_name=engine)
    if engine == "sh_multichannel_v1":
        return filter_sh_hsaf_multichannel(C, S, Lmax, params, engine_name=engine)
    if engine == "sh_orbit_multichannel_v1":
        return filter_sh_hsaf_multichannel(C, S, Lmax, params, engine_name=engine)
    if engine == "sh_demod_v1":
        return filter_sh_hsaf_demod(C, S, Lmax, params, multichannel=False, engine_name=engine)
    if engine == "sh_orbit_demod_v1":
        return filter_sh_hsaf_demod(C, S, Lmax, params, multichannel=False, engine_name=engine)
    if engine == "sh_demod_multichannel_v1":
        return filter_sh_hsaf_demod(C, S, Lmax, params, multichannel=True, engine_name=engine)
    if engine == "sh_orbit_demod_multichannel_v1":
        return filter_sh_hsaf_demod(C, S, Lmax, params, multichannel=True, engine_name=engine)
    raise ValueError(f"Unsupported SH-domain HSA engine: {engine}")
