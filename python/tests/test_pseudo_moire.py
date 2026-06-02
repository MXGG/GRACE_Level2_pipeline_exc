import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from grace_pipeline.inversion.pseudo_moire import PseudoMoireOperator


def _synthetic_bundle():
    nlon, nlat = 72, 24
    lon = np.linspace(-179.5, 179.5, nlon)
    lat = np.linspace(-69.5, 69.5, nlat)
    x = np.arange(nlon, dtype=float)[:, None]
    y = np.cos(np.deg2rad(lat))[None, :]
    density = (
        1.0
        + 0.35 * np.sin(2.0 * np.pi * 4.0 * x / nlon)
        + 0.45 * np.sin(2.0 * np.pi * 8.0 * x / nlon)
        + 0.20 * np.sin(2.0 * np.pi * 12.0 * x / nlon)
    ) * y
    return density.astype(float), lon.astype(float), lat.astype(float)


def _synthetic_sh():
    lmax = 24
    C = np.zeros((lmax + 1, lmax + 1), dtype=float)
    S = np.zeros((lmax + 1, lmax + 1), dtype=float)
    for ll in range(0, 10):
        mm_max = min(ll, 4)
        for mm in range(mm_max + 1):
            C[ll, mm] = 0.03 * np.exp(-0.1 * ll) * (1.0 + 0.1 * mm)
            if mm > 0:
                S[ll, mm] = -0.02 * np.exp(-0.08 * ll) * (1.0 + 0.05 * mm)
    for m in range(4, lmax + 1):
        deg = np.arange(m, lmax + 1, dtype=float)
        stripe = 0.015 * np.sin(2.0 * np.pi * (deg - m) / max(4.0, 0.45 * (lmax - m + 1)))
        C[m : lmax + 1, m] += stripe
        if m > 0:
            S[m : lmax + 1, m] -= 0.8 * stripe
    return C, S, lmax


class PseudoMoireOperatorTest(unittest.TestCase):
    def test_fit_and_filter_preserve_shapes(self):
        density, lon, lat = _synthetic_bundle()
        C, S, lmax = _synthetic_sh()
        op = PseudoMoireOperator(lmax=lmax, carrier_lmax=10, carrier_mmax=4, m_start=4)
        op.fit(density, C, S, lat, lon)
        C_f, S_f = op.filter(C, S)
        self.assertEqual(C_f.shape, C.shape)
        self.assertEqual(S_f.shape, S.shape)
        self.assertTrue(np.isfinite(C_f).all())
        self.assertTrue(np.isfinite(S_f).all())

    def test_diagnostics_expose_order_risk_and_basis_concentration(self):
        density, lon, lat = _synthetic_bundle()
        C, S, lmax = _synthetic_sh()
        op = PseudoMoireOperator(
            lmax=lmax,
            carrier_lmax=10,
            carrier_mmax=4,
            m_start=4,
            high_risk_orders=[4, 8, 12],
        )
        op.fit(density, C, S, lat, lon)
        op.separate(C, S)
        diag = op.diagnostics()
        self.assertEqual(diag.order_risk.shape[0], lmax + 1)
        self.assertEqual(diag.bundle_order_amplitude.shape[0], lmax + 1)
        self.assertGreaterEqual(diag.basis_concentration_score, 0.0)
        self.assertLessEqual(diag.basis_concentration_score, 1.0)
        self.assertGreater(diag.order_risk[8], 0.0)

    def test_build_basis_returns_degree_aligned_columns(self):
        density, lon, lat = _synthetic_bundle()
        C, S, lmax = _synthetic_sh()
        op = PseudoMoireOperator(lmax=lmax, carrier_lmax=10, carrier_mmax=4, m_start=4)
        op.fit(density, C, S, lat, lon)
        basis = op.build_basis(8, "cos")
        self.assertEqual(basis.shape[0], lmax + 1 - 8)
        self.assertGreaterEqual(basis.shape[1], 1)
        self.assertTrue(np.isfinite(basis).all())


if __name__ == "__main__":
    unittest.main()
