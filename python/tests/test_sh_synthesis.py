import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from grace_pipeline.inversion.sh_synthesis import compute_legendre, ewh_analysis, ewh_synthesis


class ShSynthesisTest(unittest.TestCase):
    def test_compute_legendre_matches_matlab_norm_convention(self):
        x = np.array([-0.7, 0.0, 0.3], dtype=float)

        # Reference values obtained from local MATLAB:
        # legendre(l, x, 'norm') with the same real-form sqrt(2) scaling
        # applied for m > 0, matching inv_prepare_synthesis.m.
        expected = {
            (1, 0): np.array([-0.85732141, 0.0, 0.36742346]),
            (1, 1): np.array([0.87464278, 1.22474487, 1.16833214]),
            (2, 0): np.array([0.37157805, -0.79056942, -0.57711567]),
            (2, 1): np.array([-1.36898245, 0.0, 0.78374172]),
            (2, 2): np.array([0.69828558, 1.36930639, 1.24611378]),
        }

        for (l, m), ref in expected.items():
            got = compute_legendre(l, m, x)
            np.testing.assert_allclose(got, ref, rtol=5e-5, atol=5e-5)

    def test_ewh_synthesis_returns_lon_lat_grid(self):
        Lmax = 4
        C = np.zeros((Lmax + 1, Lmax + 1), dtype=float)
        S = np.zeros((Lmax + 1, Lmax + 1), dtype=float)
        C[2, 0] = 1e-10
        C[2, 1] = -2e-10
        S[2, 1] = 3e-10
        lon = np.arange(-179.5, 180.0, 2.0)
        lat = np.arange(-89.5, 90.0, 2.0)

        grid = ewh_synthesis(C, S, Lmax, lon, lat)
        self.assertEqual(grid.shape, (lon.size, lat.size))
        self.assertTrue(np.isfinite(grid).all())

    def test_ewh_analysis_round_trips_synthesis_coefficients(self):
        Lmax = 4
        C = np.zeros((Lmax + 1, Lmax + 1), dtype=float)
        S = np.zeros((Lmax + 1, Lmax + 1), dtype=float)
        C[2, 0] = 1.0e-10
        C[2, 1] = -2.0e-10
        S[2, 1] = 3.0e-10
        C[3, 2] = 1.5e-10
        S[4, 3] = -0.5e-10
        lon = np.arange(0.0, 360.0, 5.0)
        lat = np.arange(-87.5, 90.0, 5.0)

        grid = ewh_synthesis(C, S, Lmax, lon, lat)
        c_back, s_back = ewh_analysis(grid, Lmax, lon, lat)

        np.testing.assert_allclose(c_back, C, rtol=1e-8, atol=1e-18)
        np.testing.assert_allclose(s_back, S, rtol=1e-8, atol=1e-18)


if __name__ == "__main__":
    unittest.main()
