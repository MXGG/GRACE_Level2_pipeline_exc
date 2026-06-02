"""Adaptive parity HSA filter prototype for SH-domain GRACE destriping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
from scipy.ndimage import uniform_filter1d


@dataclass
class ParityHSAFDiagnostics:
    """Per-month diagnostics returned after SH separation."""

    order_risk: np.ndarray
    stripe_order_energy: np.ndarray
    signal_order_energy: np.ndarray
    freq_profile: np.ndarray
    basis_concentration_score: float


class AdaptiveParityHSAF:
    """Month-adaptive parity HSA filter working on fixed-order degree sequences.

    The design assumption is:

    - for each fixed order m, the degree sequence x[k] = C_{m+k,m} contains
      both a smooth low-frequency signal component and a near-Nyquist stripe
      component caused by odd/even degree alternation;
    - bundle-density FFT power provides a monthly risk score risk[m];
    - only risk-bearing orders are processed by HSA, with attenuation strength
      controlled by both risk[m] and the dominant modal frequency.
    """

    def __init__(
        self,
        lmax: int = 96,
        m_start: int = 4,
        window_frac: float = 0.45,
        max_window: int = 48,
        n_modes: int = 0,
        f_split: float = 0.30,
        f_width: float = 0.08,
        risk_gain: float = 1.0,
        min_risk: float = 0.08,
        risk_smooth_window: int = 5,
    ) -> None:
        self.lmax = int(lmax)
        self.m_start = max(0, min(int(m_start), self.lmax))
        self.window_frac = float(window_frac)
        self.max_window = max(3, int(max_window))
        self.n_modes = max(0, int(n_modes))
        self.f_split = float(f_split)
        self.f_width = max(1e-4, float(f_width))
        self.risk_gain = float(risk_gain)
        self.min_risk = float(min_risk)
        self.risk_smooth_window = max(1, int(risk_smooth_window))

        self._order_risk: Optional[np.ndarray] = None
        self._stripe_energy: Optional[np.ndarray] = None
        self._signal_energy: Optional[np.ndarray] = None
        self._freq_profile: Optional[np.ndarray] = None
        self._is_fitted = False

    def fit(
        self,
        bundle_density_grid: np.ndarray,
        lat_grid: np.ndarray,
    ) -> "AdaptiveParityHSAF":
        """Estimate monthly order risk from bundle-density longitude spectra."""

        self._order_risk = self._compute_risk(bundle_density_grid, lat_grid)
        self._is_fitted = True
        return self

    def filter(
        self,
        cnm: np.ndarray,
        snm: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Return only the signal component, matching existing SH filter APIs."""

        c_sig, s_sig, _, _ = self.separate(cnm, snm)
        return c_sig, s_sig

    def separate(
        self,
        cnm: np.ndarray,
        snm: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Split input SH coefficients into signal and stripe components."""

        self._check_fitted()
        c_in = np.asarray(cnm, dtype=float)
        s_in = np.asarray(snm, dtype=float)
        c_sig = c_in.copy()
        s_sig = s_in.copy()

        stripe_energy = np.zeros(self.lmax + 1, dtype=float)
        signal_energy = np.zeros(self.lmax + 1, dtype=float)
        freq_profile = np.zeros(self.lmax + 1, dtype=float)

        for m in range(self.m_start, self.lmax + 1):
            risk_m = float(self._order_risk[m])
            if risk_m < self.min_risk:
                continue

            eff_risk = min(1.0, self.risk_gain * risk_m)

            x_c = c_in[m:, m].copy()
            if x_c.size >= 4:
                x_c_sig, dom_freq = self._hsa_filter_sequence(x_c, eff_risk)
                c_sig[m:, m] = x_c_sig
                stripe_energy[m] += float(np.sum((x_c - x_c_sig) ** 2))
                signal_energy[m] += float(np.sum(x_c_sig ** 2))
                freq_profile[m] = max(freq_profile[m], float(dom_freq))

            if m > 0:
                x_s = s_in[m:, m].copy()
                if x_s.size >= 4:
                    x_s_sig, dom_freq = self._hsa_filter_sequence(x_s, eff_risk)
                    s_sig[m:, m] = x_s_sig
                    stripe_energy[m] += float(np.sum((x_s - x_s_sig) ** 2))
                    signal_energy[m] += float(np.sum(x_s_sig ** 2))
                    freq_profile[m] = max(freq_profile[m], float(dom_freq))

        self._stripe_energy = stripe_energy
        self._signal_energy = signal_energy
        self._freq_profile = freq_profile

        c_str = c_in - c_sig
        s_str = s_in - s_sig
        return c_sig, s_sig, c_str, s_str

    def diagnostics(self) -> ParityHSAFDiagnostics:
        """Return experiment diagnostics after `separate()` or `filter()`."""

        self._check_fitted()
        stripe_e = np.asarray(self._stripe_energy if self._stripe_energy is not None else np.zeros(self.lmax + 1), dtype=float)
        signal_e = np.asarray(self._signal_energy if self._signal_energy is not None else np.zeros(self.lmax + 1), dtype=float)
        freq_p = np.asarray(self._freq_profile if self._freq_profile is not None else np.zeros(self.lmax + 1), dtype=float)
        total = float(np.sum(stripe_e))
        concentration = float(np.sum(np.sort(stripe_e)[-3:]) / total) if total > 0 else 0.0
        return ParityHSAFDiagnostics(
            order_risk=np.asarray(self._order_risk, dtype=float).copy(),
            stripe_order_energy=stripe_e.copy(),
            signal_order_energy=signal_e.copy(),
            freq_profile=freq_p.copy(),
            basis_concentration_score=concentration,
        )

    def order_risk_profile(self) -> np.ndarray:
        self._check_fitted()
        return np.asarray(self._order_risk, dtype=float).copy()

    def _hsa_filter_sequence(self, x: np.ndarray, risk: float) -> Tuple[np.ndarray, float]:
        """Apply modal HSA attenuation to a single degree sequence."""

        n = len(x)
        if n < 4 or risk < 1e-12:
            return x.copy(), 0.0

        p = max(3, min(self.max_window, int(n * self.window_frac)))
        k_win = n - p + 1
        if k_win < 2:
            return _tikhonov_smooth_1d(x, mu=risk * 10.0), 0.0

        h = _hankel_embed(x, p)
        try:
            u, sigma, vt = np.linalg.svd(h, full_matrices=False)
        except np.linalg.LinAlgError:
            return x.copy(), 0.0

        max_modes = min(p, k_win)
        if self.n_modes > 0:
            max_modes = min(max_modes, self.n_modes)

        x_stripe = np.zeros(n, dtype=float)
        dom_freq = 0.0
        dom_contrib = 0.0

        for idx in range(max_modes):
            if sigma[idx] < 1e-14 * sigma[0]:
                break
            h_k = sigma[idx] * np.outer(u[:, idx], vt[idx, :])
            x_k = _antidiag_mean_fast(h_k, n)
            f_k = _estimate_dominant_frequency(x_k)
            gate = _sigmoid_gate(f_k, self.f_split, self.f_width)
            attenuation = risk * gate
            x_stripe += attenuation * x_k
            contrib = attenuation * float(np.sum(x_k ** 2))
            if contrib > dom_contrib:
                dom_contrib = contrib
                dom_freq = f_k

        x_signal = x - x_stripe
        pair_weight = float(np.clip(risk * _sigmoid_gate(dom_freq, self.f_split, self.f_width), 0.0, 1.0))
        if pair_weight > 1e-6:
            x_pair = _parity_pair_smooth(x)
            blend = 0.90 * pair_weight
            x_signal = (1.0 - blend) * x_signal + blend * x_pair
        return x_signal, dom_freq

    def _compute_risk(
        self,
        bundle_density: np.ndarray,
        lat_deg: np.ndarray,
    ) -> np.ndarray:
        """Estimate monthly order risk from longitude FFT power of bundle density."""

        arr = np.asarray(bundle_density, dtype=float)
        lat = np.asarray(lat_deg, dtype=float).ravel()

        if arr.ndim != 2 or arr.size == 0:
            return np.zeros(self.lmax + 1, dtype=float)
        if lat.size != arr.shape[1]:
            if lat.size == arr.shape[0]:
                arr = arr.T
            else:
                return np.zeros(self.lmax + 1, dtype=float)

        centered = arr - np.nanmean(arr, axis=0, keepdims=True)
        spec = np.fft.rfft(centered, axis=0)
        power = np.abs(spec) ** 2

        lat_w = np.cos(np.deg2rad(lat))
        lat_w = np.where(np.isfinite(lat_w), np.clip(lat_w, 0.0, None), 0.0)
        w_sum = float(np.sum(lat_w))
        if w_sum <= 0:
            lat_w = np.ones_like(lat_w)
            w_sum = float(lat_w.size)
        lat_w = lat_w / w_sum

        order_power = power @ lat_w
        risk = np.zeros(self.lmax + 1, dtype=float)
        limit = min(self.lmax, int(order_power.size) - 1)
        risk[: limit + 1] = np.sqrt(np.maximum(order_power[: limit + 1], 0.0))
        if self.risk_smooth_window > 1:
            risk = uniform_filter1d(risk, size=self.risk_smooth_window, mode="nearest")
        risk[: self.m_start] = 0.0
        peak = float(np.nanmax(risk))
        if peak > 0:
            risk = risk / peak
        return np.clip(risk, 0.0, 1.0)

    def _check_fitted(self) -> None:
        if not self._is_fitted:
            raise RuntimeError("AdaptiveParityHSAF.fit() must be called before filter()/separate().")


def _hankel_embed(x: np.ndarray, p: int) -> np.ndarray:
    """Build a Hankel embedding matrix with shape (p, N-p+1)."""

    n = len(x)
    k = n - p + 1
    h = np.empty((p, k), dtype=float)
    for i in range(p):
        h[i, :] = x[i : i + k]
    return h


def _antidiag_mean(h: np.ndarray, n: int) -> np.ndarray:
    """Reconstruct a 1D sequence by averaging anti-diagonals."""

    p, k_win = h.shape
    out = np.zeros(n, dtype=float)
    counts = np.zeros(n, dtype=int)
    for d in range(n):
        i_min = max(0, d - k_win + 1)
        i_max = min(p - 1, d)
        for i in range(i_min, i_max + 1):
            j = d - i
            out[d] += h[i, j]
            counts[d] += 1
    counts = np.maximum(counts, 1)
    return out / counts


def _antidiag_mean_fast(h: np.ndarray, n: int) -> np.ndarray:
    """Fast anti-diagonal averaging using indexed accumulation."""

    rows, cols = np.indices(h.shape)
    diag = (rows + cols).ravel()
    out = np.zeros(n, dtype=float)
    counts = np.zeros(n, dtype=int)
    np.add.at(out, diag, h.ravel())
    np.add.at(counts, diag, 1)
    counts = np.maximum(counts, 1)
    return out / counts


def _estimate_dominant_frequency(x: np.ndarray) -> float:
    """Estimate dominant normalized frequency in [0, 0.5] using FFT power."""

    n = len(x)
    if n < 4:
        return 0.0
    xc = x - float(np.mean(x))
    spec = np.abs(np.fft.rfft(xc)) ** 2
    freqs = np.fft.rfftfreq(n)
    if spec.size <= 1:
        return 0.0
    spec[0] = 0.0
    return float(freqs[int(np.argmax(spec))])


def _sigmoid_gate(freq: float, f_split: float, f_width: float) -> float:
    """Soft high-frequency gate used to attenuate near-Nyquist stripe modes."""

    z = float(np.clip((freq - f_split) / f_width, -30.0, 30.0))
    return 1.0 / (1.0 + np.exp(-z))


def _tikhonov_smooth_1d(x: np.ndarray, mu: float) -> np.ndarray:
    """Fallback first-order Tikhonov smoothing for very short sequences."""

    n = len(x)
    if n <= 2 or mu <= 0:
        return x.copy()
    diag = np.ones(n) * (1.0 + 2.0 * mu)
    diag[0] = 1.0 + mu
    diag[-1] = 1.0 + mu
    off = np.full(n - 1, -mu)
    return _tridiag_solve(diag, off, off, x)


def _parity_pair_smooth(x: np.ndarray) -> np.ndarray:
    """Suppress odd/even alternation by averaging adjacent parity pairs."""

    arr = np.asarray(x, dtype=float)
    out = arr.copy()
    n_pairs = len(arr) // 2
    if n_pairs <= 0:
        return out
    pair = 0.5 * (arr[0 : 2 * n_pairs : 2] + arr[1 : 2 * n_pairs : 2])
    out[0 : 2 * n_pairs : 2] = pair
    out[1 : 2 * n_pairs : 2] = pair
    if len(arr) % 2 == 1 and len(arr) >= 3:
        out[-1] = 0.5 * (out[-1] + out[-3])
    return _tikhonov_smooth_1d(out, mu=0.25)


def _tridiag_solve(
    diag: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    b: np.ndarray,
) -> np.ndarray:
    """Thomas algorithm for tridiagonal systems."""

    n = len(b)
    c = upper.copy().astype(float)
    d = b.copy().astype(float)
    a = lower.astype(float)
    e = diag.copy().astype(float)
    for i in range(1, n):
        w = a[i - 1] / e[i - 1]
        e[i] -= w * c[i - 1]
        d[i] -= w * d[i - 1]
    x = np.zeros(n)
    x[-1] = d[-1] / e[-1]
    for i in range(n - 2, -1, -1):
        x[i] = (d[i] - c[i] * x[i + 1]) / e[i]
    return x


__all__ = [
    "AdaptiveParityHSAF",
    "ParityHSAFDiagnostics",
    "_hankel_embed",
    "_antidiag_mean",
    "_antidiag_mean_fast",
    "_estimate_dominant_frequency",
    "_sigmoid_gate",
    "_tikhonov_smooth_1d",
]
