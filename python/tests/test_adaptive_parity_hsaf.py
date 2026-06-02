"""Unit tests for the adaptive parity HSA prototype."""

from __future__ import annotations

import unittest

import numpy as np

from grace_pipeline.inversion.adaptive_parity_hsaf import (
    AdaptiveParityHSAF,
    _antidiag_mean,
    _antidiag_mean_fast,
    _estimate_dominant_frequency,
    _hankel_embed,
    _sigmoid_gate,
    _tikhonov_smooth_1d,
)


class TestHankelHelpers(unittest.TestCase):
    def test_hankel_shape(self):
        x = np.arange(10, dtype=float)
        h = _hankel_embed(x, p=4)
        self.assertEqual(h.shape, (4, 7))

    def test_antidiag_reconstructs_identity(self):
        x = np.random.default_rng(0).standard_normal(20)
        h = _hankel_embed(x, p=8)
        np.testing.assert_allclose(_antidiag_mean(h, len(x)), x, atol=1e-12)

    def test_antidiag_fast_matches_slow(self):
        x = np.random.default_rng(1).standard_normal(30)
        h = _hankel_embed(x, p=12)
        slow = _antidiag_mean(h, len(x))
        fast = _antidiag_mean_fast(h, len(x))
        np.testing.assert_allclose(slow, fast, atol=1e-12)


class TestFrequencyHelpers(unittest.TestCase):
    def test_low_frequency_sequence(self):
        n = np.arange(50)
        x = np.exp(-0.05 * n)
        self.assertLess(_estimate_dominant_frequency(x), 0.15)

    def test_nyquist_like_sequence(self):
        x = np.array([1.0, -1.0] * 25, dtype=float)
        self.assertGreater(_estimate_dominant_frequency(x), 0.40)

    def test_sigmoid_gate(self):
        self.assertLess(_sigmoid_gate(0.05, 0.30, 0.08), 0.05)
        self.assertGreater(_sigmoid_gate(0.48, 0.30, 0.08), 0.90)
        self.assertAlmostEqual(_sigmoid_gate(0.30, 0.30, 0.08), 0.5, places=6)

    def test_short_sequence_tikhonov(self):
        x = np.array([1.0, 2.0, 3.0])
        out = _tikhonov_smooth_1d(x, mu=1.0)
        self.assertEqual(out.shape, x.shape)


class TestRiskComputation(unittest.TestCase):
    def _make_bundle(self, nlon=360, nlat=180, dom_freq=15):
        rng = np.random.default_rng(42)
        lon = np.linspace(0, 360, nlon, endpoint=False)
        lat = np.linspace(-90, 90, nlat)
        bundle = np.ones((nlon, nlat)) * 5.0
        bundle += 10.0 * np.sin(2 * np.pi * dom_freq * lon / 360)[:, np.newaxis]
        bundle += rng.standard_normal((nlon, nlat)) * 0.5
        return np.clip(bundle, 0, None), lat

    def test_risk_in_range(self):
        bundle, lat = self._make_bundle()
        op = AdaptiveParityHSAF(lmax=60, m_start=4)
        op.fit(bundle, lat)
        risk = op.order_risk_profile()
        self.assertTrue(np.all(risk >= 0.0))
        self.assertTrue(np.all(risk <= 1.0))

    def test_risk_tracks_dominant_frequency(self):
        bundle, lat = self._make_bundle(dom_freq=15)
        op = AdaptiveParityHSAF(lmax=60, m_start=4, risk_smooth_window=1)
        op.fit(bundle, lat)
        peak_m = int(np.argmax(op.order_risk_profile()))
        self.assertLess(abs(peak_m - 15), 8)

    def test_low_orders_zeroed(self):
        bundle, lat = self._make_bundle()
        op = AdaptiveParityHSAF(lmax=60, m_start=6)
        op.fit(bundle, lat)
        np.testing.assert_array_equal(op.order_risk_profile()[:6], 0.0)


class TestSequenceFiltering(unittest.TestCase):
    def _mixed_sequence(self, n=80, signal_amp=1.0, stripe_amp=0.5, seed=0):
        rng = np.random.default_rng(seed)
        k = np.arange(n, dtype=float)
        signal = signal_amp * np.exp(-0.03 * k)
        stripe = stripe_amp * (-1.0) ** k
        noise = rng.standard_normal(n) * 0.02
        return signal + stripe + noise, signal

    def test_high_risk_improves_signal_correlation(self):
        x_mixed, signal_true = self._mixed_sequence(stripe_amp=0.6)
        op = AdaptiveParityHSAF(lmax=96)
        x_filtered, _ = op._hsa_filter_sequence(x_mixed, risk=1.0)
        corr_before = float(np.corrcoef(x_mixed, signal_true)[0, 1])
        corr_after = float(np.corrcoef(x_filtered, signal_true)[0, 1])
        self.assertGreater(corr_after, corr_before)

    def test_zero_risk_is_identity(self):
        x_mixed, _ = self._mixed_sequence()
        op = AdaptiveParityHSAF(lmax=96)
        x_filtered, _ = op._hsa_filter_sequence(x_mixed, risk=0.0)
        np.testing.assert_allclose(x_filtered, x_mixed, atol=1e-12)

    def test_low_frequency_preservation(self):
        k = np.arange(80, dtype=float)
        x_signal = np.exp(-0.03 * k)
        op = AdaptiveParityHSAF(lmax=96, f_split=0.30)
        x_out, _ = op._hsa_filter_sequence(x_signal, risk=1.0)
        retention = float(np.sum(x_out ** 2)) / float(np.sum(x_signal ** 2))
        self.assertGreater(retention, 0.80)


class TestFullInterface(unittest.TestCase):
    def _make_synthetic_sh(self, lmax=60, stripe_orders=(8, 16, 24), stripe_amp=0.3, seed=42):
        rng = np.random.default_rng(seed)
        cnm = np.zeros((lmax + 1, lmax + 1))
        snm = np.zeros((lmax + 1, lmax + 1))
        for n in range(1, lmax + 1):
            scale = 1.0 / (n**2)
            for m in range(n + 1):
                cnm[n, m] = rng.normal(0, scale)
                if m > 0:
                    snm[n, m] = rng.normal(0, scale)
        for m in stripe_orders:
            if m > lmax:
                continue
            for k in range(lmax + 1 - m):
                sign = (-1.0) ** k
                amp = stripe_amp / (m + 1.0)
                cnm[m + k, m] += sign * amp
                if m > 0:
                    snm[m + k, m] += sign * amp * 0.8
        return cnm, snm

    def _make_synthetic_bundle(self, nlon=180, nlat=90, stripe_orders=(8, 16, 24), seed=1):
        rng = np.random.default_rng(seed)
        lon = np.linspace(0, 360, nlon, endpoint=False)
        lat = np.linspace(-90, 90, nlat)
        bundle = np.ones((nlon, nlat)) * 3.0
        for m in stripe_orders:
            bundle += 8.0 * np.abs(np.sin(2 * np.pi * m * lon / 360))[:, np.newaxis]
        bundle += rng.standard_normal((nlon, nlat)) * 0.3
        return np.clip(bundle, 0, None), lat

    def test_output_shapes(self):
        lmax = 40
        cnm, snm = self._make_synthetic_sh(lmax=lmax)
        bundle, lat = self._make_synthetic_bundle()
        op = AdaptiveParityHSAF(lmax=lmax)
        op.fit(bundle, lat)
        cnm_out, snm_out = op.filter(cnm, snm)
        self.assertEqual(cnm_out.shape, cnm.shape)
        self.assertEqual(snm_out.shape, snm.shape)

    def test_signal_plus_stripe_recovers_input(self):
        lmax = 40
        cnm, snm = self._make_synthetic_sh(lmax=lmax)
        bundle, lat = self._make_synthetic_bundle()
        op = AdaptiveParityHSAF(lmax=lmax)
        op.fit(bundle, lat)
        c_sig, s_sig, c_str, s_str = op.separate(cnm, snm)
        np.testing.assert_allclose(c_sig + c_str, cnm, atol=1e-10)
        np.testing.assert_allclose(s_sig + s_str, snm, atol=1e-10)

    def test_stripe_parity_energy_reduced(self):
        lmax = 60
        stripe_orders = (8, 16, 24)
        cnm, snm = self._make_synthetic_sh(lmax=lmax, stripe_orders=stripe_orders)
        bundle, lat = self._make_synthetic_bundle(stripe_orders=stripe_orders)
        op = AdaptiveParityHSAF(lmax=lmax, f_split=0.30, risk_gain=1.0)
        op.fit(bundle, lat)
        c_sig, _, _, _ = op.separate(cnm, snm)

        def parity_energy(col):
            even = col[0::2]
            odd = col[1::2]
            n_min = min(len(even), len(odd))
            return float(np.sum((even[:n_min] - odd[:n_min]) ** 2))

        improved = 0
        valid = 0
        for m in stripe_orders:
            if m > lmax:
                continue
            valid += 1
            if parity_energy(cnm[m:, m]) > parity_energy(c_sig[m:, m]):
                improved += 1
        self.assertGreaterEqual(improved, 1)

    def test_diagnostics_shape(self):
        lmax = 40
        cnm, snm = self._make_synthetic_sh(lmax=lmax)
        bundle, lat = self._make_synthetic_bundle()
        op = AdaptiveParityHSAF(lmax=lmax)
        op.fit(bundle, lat)
        op.separate(cnm, snm)
        diag = op.diagnostics()
        self.assertEqual(len(diag.order_risk), lmax + 1)
        self.assertEqual(len(diag.stripe_order_energy), lmax + 1)
        self.assertGreaterEqual(diag.basis_concentration_score, 0.0)
        self.assertLessEqual(diag.basis_concentration_score, 1.0)

    def test_no_fit_raises(self):
        op = AdaptiveParityHSAF(lmax=40)
        cnm = np.zeros((41, 41))
        with self.assertRaises(RuntimeError):
            op.filter(cnm, cnm)


if __name__ == "__main__":
    unittest.main(verbosity=2)
