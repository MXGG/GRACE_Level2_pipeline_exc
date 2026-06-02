import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from grace_pipeline.inversion.sampling_aware import apply_sampling_aware_inversion


def _synthetic_sh():
    lmax = 24
    C = np.zeros((lmax + 1, lmax + 1), dtype=float)
    S = np.zeros((lmax + 1, lmax + 1), dtype=float)
    for m in range(6, lmax + 1):
        deg = np.arange(m, lmax + 1, dtype=float)
        stripe = 0.03 * np.sin(2.0 * np.pi * (deg - m) / max(4.0, 0.40 * (lmax - m + 1)))
        trend = 0.08 * np.exp(-0.07 * (deg - m))
        C[m : lmax + 1, m] = trend + stripe
        if m > 0:
            S[m : lmax + 1, m] = 0.6 * trend - 0.9 * stripe
    return C, S, lmax


class SamplingAwareInversionTest(unittest.TestCase):
    def test_sampling_inversion_v1_runs(self):
        C, S, lmax = _synthetic_sh()
        orbit_scores = np.linspace(0.0, 1.0, lmax + 1, dtype=float)
        C_f, S_f, info = apply_sampling_aware_inversion(
            C,
            S,
            lmax,
            {"engine": "sampling_inversion_v1", "params": {"orbit_order_scores": orbit_scores, "iterations": 1}},
        )
        self.assertEqual(C_f.shape, C.shape)
        self.assertEqual(S_f.shape, S.shape)
        self.assertTrue(np.isfinite(C_f).all())
        self.assertEqual(info["engine"], "sampling_inversion_v1")

    def test_sampling_inversion_multichannel_v1_runs(self):
        C, S, lmax = _synthetic_sh()
        orbit_scores = np.linspace(0.0, 1.0, lmax + 1, dtype=float)
        C_f, S_f, info = apply_sampling_aware_inversion(
            C,
            S,
            lmax,
            {
                "engine": "sampling_inversion_multichannel_v1",
                "params": {"orbit_order_scores": orbit_scores, "iterations": 1},
            },
        )
        self.assertEqual(C_f.shape, C.shape)
        self.assertEqual(S_f.shape, S.shape)
        self.assertTrue(np.isfinite(S_f).all())
        self.assertEqual(info["engine"], "sampling_inversion_multichannel_v1")


if __name__ == "__main__":
    unittest.main()
