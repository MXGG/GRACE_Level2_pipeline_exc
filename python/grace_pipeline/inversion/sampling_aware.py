"""Sampling-aware inversion-side prototype operators."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, Tuple

import numpy as np


def _parity_degree_indices(order_m: int, lmax: int, parity: int) -> np.ndarray:
    idx = np.arange(int(order_m), int(lmax) + 1, dtype=int)
    return idx[idx % 2 == int(parity)]


@lru_cache(maxsize=64)
def _second_difference_penalty(n: int) -> np.ndarray:
    n = int(n)
    if n < 3:
        return np.zeros((n, n), dtype=float)
    d2 = np.zeros((n - 2, n), dtype=float)
    for i in range(n - 2):
        d2[i, i] = 1.0
        d2[i, i + 1] = -2.0
        d2[i, i + 2] = 1.0
    return d2.T @ d2


def _fill_nan_1d(x: np.ndarray) -> np.ndarray:
    arr = np.asarray(x, dtype=float).ravel()
    mask = np.isfinite(arr)
    if mask.all() or np.count_nonzero(mask) < 2:
        return np.where(np.isfinite(arr), arr, 0.0)
    idx = np.arange(arr.size)
    out = arr.copy()
    out[~mask] = np.interp(idx[~mask], idx[mask], arr[mask])
    return out


def _resolve_order_score(order_m: int, m_start: int, lmax: int, params: Dict[str, Any]) -> float:
    scores = params.get("orbit_order_scores")
    if scores is None:
        den = max(1, int(lmax) - int(m_start))
        return float(np.clip((int(order_m) - int(m_start)) / den, 0.0, 1.0))
    arr = np.asarray(scores, dtype=float).ravel()
    if arr.size == 0:
        return 0.0
    idx = int(np.clip(int(order_m), 0, arr.size - 1))
    value = arr[idx]
    return float(np.clip(value, 0.0, 1.0)) if np.isfinite(value) else 0.0


def _aligned_neighbor_sequence(
    coeff: np.ndarray,
    degrees: np.ndarray,
    order_m: int,
    lmax: int,
    parity: int,
    *,
    multichannel: bool,
) -> np.ndarray | None:
    neighbors = []
    offsets = (-2, -1, 1, 2) if multichannel else (-1, 1)
    for offset in offsets:
        mm = int(order_m) + int(offset)
        if mm < 0 or mm > int(lmax):
            continue
        if mm % 2 != int(parity):
            continue
        valid = degrees >= mm
        if not np.any(valid):
            continue
        seq = np.zeros(degrees.size, dtype=float)
        seq[valid] = coeff[degrees[valid], mm]
        neighbors.append(_fill_nan_1d(seq))
    if not neighbors:
        return None
    return np.mean(np.stack(neighbors, axis=1), axis=1)


def _regularize_sequence(
    seq: np.ndarray,
    *,
    risk: float,
    lambda_degree: float,
    lambda_neighbor: float,
    neighbor_seq: np.ndarray | None,
) -> np.ndarray:
    x0 = _fill_nan_1d(seq)
    n = x0.size
    if n < 3 or risk <= 1e-6:
        return x0
    eye = np.eye(n, dtype=float)
    penalty = _second_difference_penalty(n)
    a = eye + float(lambda_degree) * float(risk) * penalty
    b = x0.copy()
    if neighbor_seq is not None and float(lambda_neighbor) > 0:
        lam_nb = float(lambda_neighbor) * float(risk)
        a = a + lam_nb * eye
        b = b + lam_nb * _fill_nan_1d(neighbor_seq)
    try:
        return np.linalg.solve(a, b)
    except np.linalg.LinAlgError:
        return np.linalg.lstsq(a, b, rcond=None)[0]


def apply_sampling_aware_inversion(
    C: np.ndarray,
    S: np.ndarray,
    Lmax: int,
    config: Dict[str, Any],
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    engine = str(config.get("engine", "sampling_inversion_v1") or "sampling_inversion_v1").strip().lower()
    params = dict(config.get("params", {}) or {})
    multichannel = engine == "sampling_inversion_multichannel_v1"
    m_start = max(6, int(params.get("m_start", 6)))
    iterations = max(1, int(params.get("iterations", 1)))
    lambda_degree = float(params.get("lambda_degree", 6.0))
    lambda_neighbor = float(params.get("lambda_neighbor", 2.0 if multichannel else 0.8))
    carrier_lmax = max(2, min(int(params.get("carrier_lmax", 20)), int(Lmax)))
    carrier_mmax = max(0, min(int(params.get("carrier_mmax", 8)), carrier_lmax))

    C_in = np.asarray(C, dtype=float)
    S_in = np.asarray(S, dtype=float)
    C_car = np.zeros_like(C_in)
    S_car = np.zeros_like(S_in)
    for ll in range(carrier_lmax + 1):
        mm_max = min(ll, carrier_mmax)
        C_car[ll, : mm_max + 1] = C_in[ll, : mm_max + 1]
        S_car[ll, : mm_max + 1] = S_in[ll, : mm_max + 1]
    C_res = C_in - C_car
    S_res = S_in - S_car

    risk_sum = 0.0
    risk_count = 0
    for _ in range(iterations):
        for m in range(m_start, int(Lmax) + 1):
            for parity in (m % 2, 1 - (m % 2)):
                degrees = _parity_degree_indices(m, Lmax, parity)
                if degrees.size < 4:
                    continue
                risk = _resolve_order_score(m, m_start, Lmax, params)
                if risk <= 1e-6:
                    continue
                neigh_c = _aligned_neighbor_sequence(C_res, degrees, m, Lmax, parity, multichannel=multichannel)
                neigh_s = _aligned_neighbor_sequence(S_res, degrees, m, Lmax, parity, multichannel=multichannel)
                C_res[degrees, m] = _regularize_sequence(
                    C_res[degrees, m],
                    risk=risk,
                    lambda_degree=lambda_degree,
                    lambda_neighbor=lambda_neighbor,
                    neighbor_seq=neigh_c,
                )
                if m > 0:
                    S_res[degrees, m] = _regularize_sequence(
                        S_res[degrees, m],
                        risk=risk,
                        lambda_degree=lambda_degree,
                        lambda_neighbor=lambda_neighbor,
                        neighbor_seq=neigh_s,
                    )
                risk_sum += risk
                risk_count += 1

    return C_car + C_res, S_car + S_res, {
        "type": "sampling_aware_inversion",
        "engine": engine,
        "params": params,
        "carrier_lmax": int(carrier_lmax),
        "carrier_mmax": int(carrier_mmax),
        "avg_risk": float(risk_sum / risk_count) if risk_count else 0.0,
        "multichannel": bool(multichannel),
    }
