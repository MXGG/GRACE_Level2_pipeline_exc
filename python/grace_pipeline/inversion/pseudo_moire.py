"""Sampling-aware pseudo-moire SH operator prototypes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Tuple

import numpy as np


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


def _normalize_vector(x: np.ndarray) -> np.ndarray:
    arr = np.asarray(x, dtype=float).ravel()
    norm = float(np.linalg.norm(arr))
    if norm <= 0:
        return np.zeros_like(arr)
    return arr / norm


def _bundle_order_amplitude_from_density(
    density: np.ndarray,
    lat_deg: np.ndarray,
    lmax: int,
) -> np.ndarray:
    """Return a monthly bundle amplitude proxy by order using lon FFT power.

    The ground-track density grid in this project is stored as [nLon, nLat].
    For the MVP we only need an order-wise proxy, not a full Gaunt expansion.
    """
    arr = np.asarray(density, dtype=float)
    if arr.ndim != 2 or arr.size == 0:
        return np.zeros(int(lmax) + 1, dtype=float)

    lat = np.asarray(lat_deg, dtype=float).ravel()
    if lat.size != arr.shape[1]:
        raise ValueError("Latitude vector does not match bundle density shape.")

    centered = arr - np.nanmean(arr, axis=0, keepdims=True)
    spec = np.fft.rfft(centered, axis=0)
    power = np.abs(spec) ** 2
    lat_weight = np.cos(np.deg2rad(lat))
    lat_weight = np.where(np.isfinite(lat_weight), np.clip(lat_weight, 0.0, None), 0.0)
    if float(np.sum(lat_weight)) <= 0:
        lat_weight = np.ones_like(lat_weight)
    order_amp = np.average(power, axis=1, weights=lat_weight)
    out = np.zeros(int(lmax) + 1, dtype=float)
    limit = min(int(lmax), int(order_amp.size) - 1)
    if limit >= 0:
        out[: limit + 1] = np.sqrt(np.maximum(order_amp[: limit + 1], 0.0))
    peak = float(np.nanmax(out)) if out.size else 0.0
    if peak > 0:
        out = out / peak
    return np.clip(out, 0.0, 1.0)


@dataclass
class SeparationDiagnostics:
    order_risk: np.ndarray
    bundle_order_amplitude: np.ndarray
    carrier_order_power: np.ndarray
    stripe_order_energy: np.ndarray
    residual_order_energy: np.ndarray
    basis_concentration_score: float


class PseudoMoireOperator:
    """MVP pseudo-moire forward operator in SH space.

    This prototype builds a monthly stripe basis from bundle-carrier coupling
    and solves a constrained signal/stripe separation before EWH synthesis.
    """

    def __init__(
        self,
        *,
        lmax: int,
        carrier_lmax: int = 20,
        carrier_mmax: int = 10,
        m_start: int = 4,
        lambda_stripe: float = 1.0,
        lambda_signal: float = 0.12,
        high_risk_orders: Optional[Iterable[int]] = None,
        risk_scale: float = 1.6,
        min_risk_threshold: float = 0.10,
    ) -> None:
        self.lmax = int(lmax)
        self.carrier_lmax = max(2, min(int(carrier_lmax), self.lmax))
        self.carrier_mmax = max(0, min(int(carrier_mmax), self.carrier_lmax))
        self.m_start = max(0, min(int(m_start), self.lmax))
        self.lambda_stripe = float(lambda_stripe)
        self.lambda_signal = float(lambda_signal)
        self.high_risk_orders = tuple(int(v) for v in (high_risk_orders or (4, 8, 12)))
        self.risk_scale = float(risk_scale)
        self.min_risk_threshold = float(min_risk_threshold)

        self._bundle_order_amp: Optional[np.ndarray] = None
        self._order_risk: Optional[np.ndarray] = None
        self._carrier_cnm: Optional[np.ndarray] = None
        self._carrier_snm: Optional[np.ndarray] = None
        self._carrier_order_power: Optional[np.ndarray] = None
        self._stripe_order_energy: Optional[np.ndarray] = None
        self._residual_order_energy: Optional[np.ndarray] = None
        self._is_fitted = False

    def _expanded_high_risk_orders(self, top_k: int = 3) -> Tuple[int, ...]:
        bundle_amp = np.asarray(self._bundle_order_amp, dtype=float)
        candidates = list(self.high_risk_orders)
        if bundle_amp.size:
            idx = np.argsort(bundle_amp)[::-1]
            for m in idx:
                mm = int(m)
                if mm < self.m_start:
                    continue
                if mm not in candidates:
                    candidates.append(mm)
                if len(candidates) >= len(self.high_risk_orders) + int(top_k):
                    break
        return tuple(sorted(set(int(v) for v in candidates if 0 <= int(v) <= self.lmax)))

    def fit(
        self,
        bundle_density_grid: np.ndarray,
        cnm_carrier: np.ndarray,
        snm_carrier: np.ndarray,
        lat_grid: np.ndarray,
        lon_grid: np.ndarray,
    ) -> "PseudoMoireOperator":
        del lon_grid  # The MVP uses order-wise bundle amplitudes only.
        self._bundle_order_amp = _bundle_order_amplitude_from_density(
            bundle_density_grid,
            lat_grid,
            self.lmax,
        )
        c_in = np.asarray(cnm_carrier, dtype=float)
        s_in = np.asarray(snm_carrier, dtype=float)
        self._carrier_cnm = np.zeros((self.lmax + 1, self.lmax + 1), dtype=float)
        self._carrier_snm = np.zeros((self.lmax + 1, self.lmax + 1), dtype=float)
        for ll in range(self.carrier_lmax + 1):
            mm_max = min(ll, self.carrier_mmax)
            self._carrier_cnm[ll, : mm_max + 1] = c_in[ll, : mm_max + 1]
            self._carrier_snm[ll, : mm_max + 1] = s_in[ll, : mm_max + 1]
        self._carrier_order_power = self._compute_carrier_order_power()
        self._order_risk = self._compute_order_risk()
        self._stripe_order_energy = np.zeros(self.lmax + 1, dtype=float)
        self._residual_order_energy = np.zeros(self.lmax + 1, dtype=float)
        self._is_fitted = True
        return self

    def order_risk_profile(self) -> np.ndarray:
        self._check_fitted()
        return np.asarray(self._order_risk, dtype=float).copy()

    def build_basis(self, order_m: int, channel: str = "cos") -> np.ndarray:
        self._check_fitted()
        m = int(order_m)
        if m < 0 or m > self.lmax:
            return np.zeros((0, 0), dtype=float)
        n_res = self.lmax + 1 - m
        cols = []
        bundle_amp = np.asarray(self._bundle_order_amp, dtype=float)
        for m_car in range(min(self.carrier_mmax, m) + 1):
            bun_order = m - m_car
            if bun_order < 0 or bun_order >= bundle_amp.size:
                continue
            bun_scalar = float(bundle_amp[bun_order])
            if bun_scalar <= 1e-10:
                continue
            if str(channel).lower() == "sin":
                if m_car == 0:
                    continue
                carrier_profile = np.asarray(self._carrier_snm[m_car:, m_car], dtype=float)
            else:
                carrier_profile = np.asarray(self._carrier_cnm[m_car:, m_car], dtype=float)
            phi = np.zeros(n_res, dtype=float)
            offset = m - m_car
            if offset < carrier_profile.size:
                valid = min(n_res, carrier_profile.size - offset)
                phi[:valid] = carrier_profile[offset : offset + valid] * bun_scalar
            if np.any(np.abs(phi) > 0):
                base = _normalize_vector(phi)
                cols.append(base)
                ramp = np.linspace(0.0, 1.0, n_res, dtype=float) * phi
                ramp = _normalize_vector(ramp)
                if np.any(np.abs(ramp) > 0):
                    cols.append(ramp)
                if n_res >= 3:
                    rough = np.gradient(np.gradient(phi))
                    rough = _normalize_vector(rough)
                    if np.any(np.abs(rough) > 0):
                        cols.append(rough)
        if not cols:
            return np.zeros((n_res, 0), dtype=float)
        basis = np.column_stack(cols)
        return basis

    def separate(
        self,
        cnm: np.ndarray,
        snm: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        self._check_fitted()
        c_in = np.asarray(cnm, dtype=float)
        s_in = np.asarray(snm, dtype=float)
        c_sig = np.zeros_like(c_in, dtype=float)
        s_sig = np.zeros_like(s_in, dtype=float)
        c_str = np.zeros_like(c_in, dtype=float)
        s_str = np.zeros_like(s_in, dtype=float)
        c_residual = np.zeros_like(c_in, dtype=float)
        s_residual = np.zeros_like(s_in, dtype=float)

        c_car, s_car, c_hi, s_hi = self._split_carrier_residual(c_in, s_in)
        c_sig += c_car
        s_sig += s_car

        stripe_energy = np.zeros(self.lmax + 1, dtype=float)
        residual_energy = np.zeros(self.lmax + 1, dtype=float)

        for m in range(self.lmax + 1):
            if m < self.m_start:
                c_sig[m:, m] += c_hi[m:, m]
                if m > 0:
                    s_sig[m:, m] += s_hi[m:, m]
                continue
            risk = float(self._order_risk[m])
            c_basis = self.build_basis(m, "cos")
            x_sig, x_str, x_res = self._solve_channel(c_hi[m:, m], c_basis, risk)
            c_sig[m:, m] += x_sig
            c_str[m:, m] = x_str
            c_residual[m:, m] = x_res
            stripe_energy[m] += float(np.sum(x_str * x_str))
            residual_energy[m] += float(np.sum(x_res * x_res))

            if m > 0:
                s_basis = self.build_basis(m, "sin")
                y_sig, y_str, y_res = self._solve_channel(s_hi[m:, m], s_basis, risk)
                s_sig[m:, m] += y_sig
                s_str[m:, m] = y_str
                s_residual[m:, m] = y_res
                stripe_energy[m] += float(np.sum(y_str * y_str))
                residual_energy[m] += float(np.sum(y_res * y_res))

        self._stripe_order_energy = stripe_energy
        self._residual_order_energy = residual_energy
        return c_sig, s_sig, c_str, s_str, c_residual, s_residual

    def filter(self, cnm: np.ndarray, snm: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        c_sig, s_sig, _, _, _, _ = self.separate(cnm, snm)
        return c_sig, s_sig

    def get_stripe_estimate(self, cnm: np.ndarray, snm: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        _, _, c_str, s_str, _, _ = self.separate(cnm, snm)
        return c_str, s_str

    def diagnostics(self) -> SeparationDiagnostics:
        self._check_fitted()
        stripe_energy = np.asarray(self._stripe_order_energy, dtype=float)
        total = float(np.sum(stripe_energy))
        if total > 0:
            top = np.sort(stripe_energy)[-3:]
            concentration = float(np.sum(top) / total)
        else:
            concentration = 0.0
        return SeparationDiagnostics(
            order_risk=np.asarray(self._order_risk, dtype=float).copy(),
            bundle_order_amplitude=np.asarray(self._bundle_order_amp, dtype=float).copy(),
            carrier_order_power=np.asarray(self._carrier_order_power, dtype=float).copy(),
            stripe_order_energy=stripe_energy.copy(),
            residual_order_energy=np.asarray(self._residual_order_energy, dtype=float).copy(),
            basis_concentration_score=concentration,
        )

    def _compute_carrier_order_power(self) -> np.ndarray:
        power = np.zeros(self.lmax + 1, dtype=float)
        for m in range(self.lmax + 1):
            c = np.asarray(self._carrier_cnm[m:, m], dtype=float)
            s = np.asarray(self._carrier_snm[m:, m], dtype=float)
            power[m] = float(np.sum(c * c) + np.sum(s * s))
        peak = float(np.nanmax(power)) if power.size else 0.0
        if peak > 0:
            power = power / peak
        return np.clip(power, 0.0, 1.0)

    def _compute_order_risk(self) -> np.ndarray:
        bundle_amp = np.asarray(self._bundle_order_amp, dtype=float)
        carrier_power = np.asarray(self._carrier_order_power, dtype=float)
        risk = np.zeros(self.lmax + 1, dtype=float)
        for m in range(self.lmax + 1):
            accum = 0.0
            for m_car in range(min(self.carrier_mmax, m) + 1):
                bun_order = m - m_car
                accum += float(bundle_amp[bun_order] ** 2) * float(carrier_power[m_car])
            risk[m] = accum
        for m_hr in self._expanded_high_risk_orders():
            if 0 <= int(m_hr) <= self.lmax:
                risk[int(m_hr)] *= self.risk_scale
        peak = float(np.nanmax(risk)) if risk.size else 0.0
        if peak > 0:
            risk = risk / peak
        risk[: self.m_start] = 0.0
        risk[risk < self.min_risk_threshold] = 0.0
        return np.clip(risk, 0.0, 1.0)

    def _split_carrier_residual(
        self,
        cnm: np.ndarray,
        snm: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        c_car = np.zeros_like(cnm, dtype=float)
        s_car = np.zeros_like(snm, dtype=float)
        c_car[: self.carrier_lmax + 1, : self.carrier_mmax + 1] = cnm[
            : self.carrier_lmax + 1,
            : self.carrier_mmax + 1,
        ]
        s_car[: self.carrier_lmax + 1, : self.carrier_mmax + 1] = snm[
            : self.carrier_lmax + 1,
            : self.carrier_mmax + 1,
        ]
        return c_car, s_car, cnm - c_car, snm - s_car

    def _solve_channel(
        self,
        x_res: np.ndarray,
        basis: np.ndarray,
        risk: float,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        x = np.asarray(x_res, dtype=float).ravel()
        n = x.size
        if n == 0 or risk <= 1e-12 or basis.size == 0:
            zeros = np.zeros_like(x)
            return x.copy(), zeros, zeros

        k = basis.shape[1]
        lam_s = self.lambda_stripe * risk
        lam_g = self.lambda_signal * risk

        phi_t_phi = basis.T @ basis
        inner = phi_t_phi + lam_s * np.eye(k, dtype=float)
        try:
            inner_inv = np.linalg.inv(inner)
        except np.linalg.LinAlgError:
            inner_inv = np.linalg.pinv(inner)

        proj_stripe = basis @ inner_inv @ basis.T
        p_perp = np.eye(n, dtype=float) - proj_stripe
        penalty = _second_difference_penalty(n)
        lhs = p_perp + lam_g * penalty
        rhs = p_perp @ x
        try:
            x_sig = np.linalg.solve(lhs, rhs)
        except np.linalg.LinAlgError:
            x_sig = np.linalg.lstsq(lhs, rhs, rcond=None)[0]
        alpha = inner_inv @ basis.T @ (x - x_sig)
        x_str = basis @ alpha
        x_rem = x - x_sig - x_str
        return x_sig, x_str, x_rem

    def _check_fitted(self) -> None:
        if not self._is_fitted:
            raise RuntimeError("PseudoMoireOperator.fit() must be called before use.")


__all__ = ["PseudoMoireOperator", "SeparationDiagnostics"]
