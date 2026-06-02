import unittest
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from grace_pipeline.filters.hsaf import (
    compute_stripe_metrics,
    estimate_stripe_band,
    filter_grid_hsaf,
)
from grace_pipeline.filters.hsaf_sh import filter_sh_hsaf
from grace_pipeline.app.hsaf_experiments import _build_loworder_carrier_grid
from grace_pipeline.inversion.sh_synthesis import ewh_synthesis


def _synthetic_grid():
    nlon, nlat = 72, 24
    lon = np.linspace(-179.5, 179.5, nlon)
    lat = np.linspace(-69.5, 69.5, nlat)
    llon, llat = np.meshgrid(np.arange(nlon), lat, indexing="ij")
    stripe = 18.0 * np.sin(2.0 * np.pi * 12.0 * llon / nlon) * np.cos(np.deg2rad(llat))
    blob = 25.0 * np.exp(-((lon[:, None] + 55.0) / 24.0) ** 2 - ((lat[None, :] - 8.0) / 18.0) ** 2)
    grid = stripe + blob
    land_mask = (
        ((lon[:, None] >= -130.0) & (lon[:, None] <= 150.0) & (np.abs(lat[None, :]) <= 40.0))
        | ((lon[:, None] >= -80.0) & (lon[:, None] <= -30.0) & (lat[None, :] >= -55.0) & (lat[None, :] <= 10.0))
    )
    return grid.astype(float), lon.astype(float), lat.astype(float), land_mask.astype(bool)


def _synthetic_sh():
    lmax = 24
    C = np.zeros((lmax + 1, lmax + 1), dtype=float)
    S = np.zeros((lmax + 1, lmax + 1), dtype=float)
    for m in range(6, lmax + 1):
        deg = np.arange(m, lmax + 1, dtype=float)
        stripe = 0.02 * np.sin(2.0 * np.pi * (deg - m) / max(4.0, 0.45 * (lmax - m + 1)))
        trend = 0.10 * np.exp(-0.08 * (deg - m))
        C[m : lmax + 1, m] = trend + stripe
        if m > 0:
            S[m : lmax + 1, m] = 0.7 * trend - 0.8 * stripe
    return C, S, lmax


class HsafExperimentalTest(unittest.TestCase):
    def test_estimate_stripe_band_and_metrics_detect_directional_pattern(self):
        grid, _, _, land_mask = _synthetic_grid()
        band = estimate_stripe_band(grid, land_mask=land_mask)
        metrics = compute_stripe_metrics(grid, land_mask=land_mask, band_info=band)
        self.assertGreater(band["center"], 0.03)
        self.assertLess(band["center"], 0.30)
        self.assertGreater(metrics["ocean_anisotropy_index"], 1.0)
        self.assertGreater(metrics["ocean_stripe_band_energy"], 0.0)

    def test_modal_adaptive_engine_runs_and_preserves_shape(self):
        grid, lon, lat, land_mask = _synthetic_grid()
        filtered, info = filter_grid_hsaf(
            grid,
            lon,
            lat,
            {
                "engine": "modal_adaptive_v1",
                "params": {"N": 24, "P": 8, "K": 4, "J": 4, "iterations": 1, "land_mask": land_mask},
            },
        )
        self.assertEqual(filtered.shape, grid.shape)
        self.assertTrue(np.isfinite(filtered).any())
        self.assertEqual(info["engine"], "modal_adaptive_v1")

    def test_multichannel_engine_runs_and_preserves_shape(self):
        grid, lon, lat, land_mask = _synthetic_grid()
        filtered, info = filter_grid_hsaf(
            grid,
            lon,
            lat,
            {
                "engine": "multichannel_v1",
                "params": {"N": 24, "P": 8, "K": 4, "J": 6, "iterations": 1, "land_mask": land_mask},
            },
        )
        self.assertEqual(filtered.shape, grid.shape)
        self.assertTrue(np.isfinite(filtered).any())
        self.assertEqual(info["engine"], "multichannel_v1")

    def test_modal_adaptive_v2_engine_runs_and_preserves_shape(self):
        grid, lon, lat, land_mask = _synthetic_grid()
        filtered, info = filter_grid_hsaf(
            grid,
            lon,
            lat,
            {
                "engine": "modal_adaptive_v2",
                "params": {"N": 24, "P": 8, "K": 4, "J": 4, "iterations": 1, "land_mask": land_mask},
            },
        )
        self.assertEqual(filtered.shape, grid.shape)
        self.assertTrue(np.isfinite(filtered).any())
        self.assertEqual(info["engine"], "modal_adaptive_v2")

    def test_modal_adaptive_v3_engine_runs_and_preserves_shape(self):
        grid, lon, lat, land_mask = _synthetic_grid()
        filtered, info = filter_grid_hsaf(
            grid,
            lon,
            lat,
            {
                "engine": "modal_adaptive_v3",
                "params": {"N": 24, "P": 8, "K": 4, "J": 4, "iterations": 1, "land_mask": land_mask},
            },
        )
        self.assertEqual(filtered.shape, grid.shape)
        self.assertTrue(np.isfinite(filtered).any())
        self.assertEqual(info["engine"], "modal_adaptive_v3")

    def test_demod_profile_engine_runs_and_preserves_shape(self):
        grid, lon, lat, land_mask = _synthetic_grid()
        filtered, info = filter_grid_hsaf(
            grid,
            lon,
            lat,
            {
                "engine": "demod_profile_v1",
                "params": {"N": 24, "P": 8, "K": 4, "J": 4, "iterations": 1, "land_mask": land_mask},
            },
        )
        self.assertEqual(filtered.shape, grid.shape)
        self.assertTrue(np.isfinite(filtered).any())
        self.assertEqual(info["engine"], "demod_profile_v1")

    def test_demod_multichannel_engine_runs_and_preserves_shape(self):
        grid, lon, lat, land_mask = _synthetic_grid()
        filtered, info = filter_grid_hsaf(
            grid,
            lon,
            lat,
            {
                "engine": "demod_multichannel_v1",
                "params": {"N": 24, "P": 8, "K": 4, "J": 4, "iterations": 1, "land_mask": land_mask},
            },
        )
        self.assertEqual(filtered.shape, grid.shape)
        self.assertTrue(np.isfinite(filtered).any())
        self.assertEqual(info["engine"], "demod_multichannel_v1")

    def test_bundle_template_engine_runs_and_preserves_shape(self):
        grid, lon, lat, land_mask = _synthetic_grid()
        filtered, info = filter_grid_hsaf(
            grid,
            lon,
            lat,
            {
                "engine": "bundle_template_v1",
                "params": {"N": 24, "P": 8, "K": 4, "J": 4, "iterations": 1, "land_mask": land_mask},
            },
        )
        self.assertEqual(filtered.shape, grid.shape)
        self.assertTrue(np.isfinite(filtered).any())
        self.assertEqual(info["engine"], "bundle_template_v1")

    def test_bundle_template_multichannel_engine_runs_and_preserves_shape(self):
        grid, lon, lat, land_mask = _synthetic_grid()
        filtered, info = filter_grid_hsaf(
            grid,
            lon,
            lat,
            {
                "engine": "bundle_template_multichannel_v1",
                "params": {"N": 24, "P": 8, "K": 4, "J": 4, "iterations": 1, "land_mask": land_mask},
            },
        )
        self.assertEqual(filtered.shape, grid.shape)
        self.assertTrue(np.isfinite(filtered).any())
        self.assertEqual(info["engine"], "bundle_template_multichannel_v1")

    def test_sh_orderwise_engine_runs_and_preserves_shape(self):
        C, S, lmax = _synthetic_sh()
        C_f, S_f, info = filter_sh_hsaf(
            C,
            S,
            lmax,
            {"engine": "sh_orderwise_v1", "params": {"P": 8, "K": 4, "iterations": 1, "m_start": 6}},
        )
        self.assertEqual(C_f.shape, C.shape)
        self.assertEqual(S_f.shape, S.shape)
        self.assertTrue(np.isfinite(C_f).all())
        self.assertEqual(info["engine"], "sh_orderwise_v1")

    def test_sh_multichannel_engine_runs_and_preserves_shape(self):
        C, S, lmax = _synthetic_sh()
        C_f, S_f, info = filter_sh_hsaf(
            C,
            S,
            lmax,
            {"engine": "sh_multichannel_v1", "params": {"P": 8, "K": 4, "iterations": 1, "m_start": 6}},
        )
        self.assertEqual(C_f.shape, C.shape)
        self.assertEqual(S_f.shape, S.shape)
        self.assertTrue(np.isfinite(S_f).all())
        self.assertEqual(info["engine"], "sh_multichannel_v1")

    def test_sh_demod_engine_runs_and_preserves_shape(self):
        C, S, lmax = _synthetic_sh()
        C_f, S_f, info = filter_sh_hsaf(
            C,
            S,
            lmax,
            {"engine": "sh_demod_v1", "params": {"iterations": 1, "m_start": 6}},
        )
        self.assertEqual(C_f.shape, C.shape)
        self.assertEqual(S_f.shape, S.shape)
        self.assertTrue(np.isfinite(C_f).all())
        self.assertEqual(info["engine"], "sh_demod_v1")

    def test_sh_demod_multichannel_engine_runs_and_preserves_shape(self):
        C, S, lmax = _synthetic_sh()
        C_f, S_f, info = filter_sh_hsaf(
            C,
            S,
            lmax,
            {"engine": "sh_demod_multichannel_v1", "params": {"iterations": 1, "m_start": 6}},
        )
        self.assertEqual(C_f.shape, C.shape)
        self.assertEqual(S_f.shape, S.shape)
        self.assertTrue(np.isfinite(S_f).all())
        self.assertEqual(info["engine"], "sh_demod_multichannel_v1")

    def test_sh_orbit_orderwise_engine_accepts_orbit_scores(self):
        C, S, lmax = _synthetic_sh()
        orbit_scores = np.linspace(0.0, 1.0, lmax + 1, dtype=float)
        C_f, S_f, info = filter_sh_hsaf(
            C,
            S,
            lmax,
            {
                "engine": "sh_orbit_orderwise_v1",
                "params": {"P": 8, "K": 4, "iterations": 1, "m_start": 6, "orbit_order_scores": orbit_scores},
            },
        )
        self.assertEqual(C_f.shape, C.shape)
        self.assertEqual(S_f.shape, S.shape)
        self.assertTrue(np.isfinite(C_f).all())
        self.assertEqual(info["engine"], "sh_orbit_orderwise_v1")

    def test_sh_orbit_demod_multichannel_engine_accepts_orbit_scores(self):
        C, S, lmax = _synthetic_sh()
        orbit_scores = np.linspace(0.0, 1.0, lmax + 1, dtype=float)
        C_f, S_f, info = filter_sh_hsaf(
            C,
            S,
            lmax,
            {
                "engine": "sh_orbit_demod_multichannel_v1",
                "params": {"iterations": 1, "m_start": 6, "orbit_order_scores": orbit_scores},
            },
        )
        self.assertEqual(C_f.shape, C.shape)
        self.assertEqual(S_f.shape, S.shape)
        self.assertTrue(np.isfinite(S_f).all())
        self.assertEqual(info["engine"], "sh_orbit_demod_multichannel_v1")

    def test_build_loworder_carrier_grid_preserves_grid_shape(self):
        C, S, lmax = _synthetic_sh()
        lon = np.linspace(-179.5, 179.5, 72)
        lat = np.linspace(-89.5, 89.5, 36)
        carrier, meta = _build_loworder_carrier_grid(
            C,
            S,
            lmax,
            lon,
            lat,
            {"carrier_lmax": 12, "carrier_mmax": 4},
        )
        full = ewh_synthesis(C, S, lmax, lon, lat)
        self.assertEqual(carrier.shape, full.shape)
        self.assertTrue(np.isfinite(carrier).all())
        self.assertEqual(meta["carrier_lmax"], 12)
        self.assertEqual(meta["carrier_mmax"], 4)


if __name__ == "__main__":
    unittest.main()
