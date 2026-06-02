import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from grace_pipeline.app.leakage_helpers import build_leakage_filter_options, save_leakage_bundle
from grace_pipeline.domain.leakage import (
    LeakageFilterOptions,
    apply_scale_factors_stack,
    apply_forward_operator,
    apply_gridded_gain_factors_stack,
    classify_leakage_scene,
    compute_basin_scale_factor_from_reference,
    compute_gridded_gain_factors,
    compute_masked_series,
    compute_scale_factor_series,
    fm_correct_month,
    fm_estimate_scale_factor_from_rate,
    infer_leakage_product_type,
    model_based_additive_correct_stack,
    recommend_correction_method,
)


class LeakageWorkflowTest(unittest.TestCase):
    def test_build_options_uses_identity_operator_for_mascon_auto(self):
        opts = build_leakage_filter_options(
            raw_method="AUTO",
            in_path="data/Reference/Mascon/CSR_GRACE_GRACE-FO_RL06_Mascons_all-corrections_v02.nc",
            data_meta={"active_var": "lwe_thickness"},
        )
        self.assertEqual(opts.method, "NONE")
        self.assertEqual(infer_leakage_product_type("example_mascon.nc", {"product_tag": "mascon"}), "mascon_native")

    def test_build_options_detects_ddk_from_filename(self):
        opts = build_leakage_filter_options(
            raw_method="AUTO",
            in_path="output/local/stacks/DDK4_stack.mat",
        )
        self.assertEqual(opts.method, "DDK4")
        self.assertEqual(opts.ddk_type, "DDK4")

    def test_scene_classifier_marks_coastal_region(self):
        lon = np.linspace(-20.0, 20.0, 8)
        lat = np.linspace(-15.0, 15.0, 6)
        mask = np.zeros((lon.size, lat.size), dtype=bool)
        mask[2:6, 2:4] = True
        land = np.zeros_like(mask, dtype=bool)
        land[:4, :] = True
        scene = classify_leakage_scene(mask, lon, lat, global_land_mask=land)
        self.assertEqual(scene.scene, "coastal")
        gaussian_op = type("Op", (), {"product_type": "grid_stack", "is_gaussian_equivalent": True})()
        non_gaussian_op = type("Op", (), {"product_type": "grid_stack", "is_gaussian_equivalent": False})()
        self.assertEqual(
            recommend_correction_method("auto", scene, gaussian_op, has_reference_model=True),
            "GLOBAL_COASTAL_GAUSSIAN",
        )
        self.assertEqual(
            recommend_correction_method("auto", scene, non_gaussian_op, has_reference_model=True),
            "GLOBAL_REGULARIZED",
        )

    def test_basin_scale_factor_from_reference_reduces_reference_bias(self):
        lon = np.linspace(-20.0, 20.0, 12)
        lat = np.linspace(-10.0, 10.0, 8)
        mask = np.zeros((lon.size, lat.size), dtype=bool)
        mask[3:9, 2:6] = True
        reference = np.zeros((lon.size, lat.size, 4), dtype=float)
        observed = np.zeros_like(reference)
        for k in range(reference.shape[2]):
            amp = 1.0 + 0.25 * k
            pattern = amp * np.outer(np.cos(np.deg2rad(lon)), np.cos(np.deg2rad(lat)))
            reference[:, :, k] = pattern
            observed[:, :, k] = apply_forward_operator(
                pattern,
                lon,
                lat,
                LeakageFilterOptions(method="GAUSSIAN", gaussian_km=300.0, lmax=10),
            )
        factor, _ = compute_basin_scale_factor_from_reference(
            reference,
            mask,
            lon,
            lat,
            LeakageFilterOptions(method="GAUSSIAN", gaussian_km=300.0, lmax=10),
        )
        corrected = apply_scale_factors_stack(observed, mask, np.asarray([factor]))
        raw_series = compute_masked_series(reference, mask, lat)
        obs_series = compute_masked_series(observed, mask, lat)
        corr_series = compute_masked_series(corrected, mask, lat)
        self.assertLess(np.sqrt(np.mean((corr_series - raw_series) ** 2)), np.sqrt(np.mean((obs_series - raw_series) ** 2)))

    def test_gridded_gain_factors_reduce_grid_bias(self):
        lon = np.linspace(-30.0, 30.0, 10)
        lat = np.linspace(-20.0, 20.0, 8)
        target_mask = np.zeros((lon.size, lat.size), dtype=bool)
        target_mask[2:8, 2:6] = True
        reference = np.zeros((lon.size, lat.size, 4), dtype=float)
        observed = np.zeros_like(reference)
        opts = LeakageFilterOptions(method="GAUSSIAN", gaussian_km=300.0, lmax=10)
        for k in range(reference.shape[2]):
            phase = 1.0 + 0.2 * k
            pattern = np.outer(np.cos(np.deg2rad(lon * phase)), np.cos(np.deg2rad(lat)))
            reference[:, :, k] = pattern
            observed[:, :, k] = apply_forward_operator(pattern, lon, lat, opts)
        gains, _ = compute_gridded_gain_factors(reference, lon, lat, opts, target_mask=target_mask)
        corrected = apply_gridded_gain_factors_stack(observed, gains, target_mask=target_mask)
        obs_err = np.sqrt(np.nanmean((observed[target_mask] - reference[target_mask]) ** 2))
        corr_err = np.sqrt(np.nanmean((corrected[target_mask] - reference[target_mask]) ** 2))
        self.assertLess(corr_err, obs_err)

    def test_model_based_additive_stack_preserves_shape_and_respects_mask(self):
        lon = np.linspace(-30.0, 30.0, 10)
        lat = np.linspace(-20.0, 20.0, 8)
        grid = np.zeros((lon.size, lat.size, 3), dtype=float)
        for k in range(grid.shape[2]):
            grid[:, :, k] = np.outer(np.cos(np.deg2rad(lon + k * 2.0)), np.cos(np.deg2rad(lat)))
        mask = np.zeros((lon.size, lat.size), dtype=bool)
        mask[3:7, 2:6] = True
        ref = np.outer(np.cos(np.deg2rad(lon)), np.cos(np.deg2rad(lat)))
        corrected, info = model_based_additive_correct_stack(
            grid,
            ref,
            lon,
            lat,
            LeakageFilterOptions(method="GAUSSIAN", gaussian_km=300.0, lmax=10),
            mask=mask,
            restrict_to_mask=True,
        )
        self.assertEqual(corrected.shape, grid.shape)
        np.testing.assert_allclose(corrected[~mask], grid[~mask])
        self.assertEqual(info["leakage_term"].shape, ref.shape)

    def test_forward_modeling_preserves_input_outside_mask_by_default(self):
        lon = np.linspace(-20.0, 20.0, 10)
        lat = np.linspace(-10.0, 10.0, 8)
        mask = np.zeros((lon.size, lat.size), dtype=bool)
        mask[3:7, 2:6] = True
        gobs = np.outer(np.sin(np.deg2rad(lon * 3.0)), np.cos(np.deg2rad(lat * 2.0)))
        gobs[~mask] += 5.0
        corr, info = fm_correct_month(
            gobs,
            mask,
            lon,
            lat,
            LeakageFilterOptions(method="GAUSSIAN", gaussian_km=300.0, lmax=10),
            n_iter=3,
            tol_rmse_mm=0.0,
            update_mode="mask",
            mass_conservation="ocean_uniform_land_balance",
            output_mode="preserve_observed_outside_mask",
        )
        np.testing.assert_allclose(corr[~mask], gobs[~mask])
        self.assertEqual(info["final_balanced"].shape, gobs.shape)

    def test_fm_rate_scale_factor_recovers_attenuated_regional_rate(self):
        lon = np.linspace(-40.0, 40.0, 16)
        lat = np.linspace(-20.0, 20.0, 12)
        mask = np.zeros((lon.size, lat.size), dtype=bool)
        mask[5:11, 3:9] = True
        rate_true = np.zeros((lon.size, lat.size), dtype=float)
        rate_true[mask] = -12.0
        opts = LeakageFilterOptions(method="GAUSSIAN", gaussian_km=300.0, lmax=15)
        rate_obs = apply_forward_operator(rate_true, lon, lat, opts)
        sf, info = fm_estimate_scale_factor_from_rate(
            rate_obs,
            mask,
            lon,
            lat,
            opts,
            n_iter=30,
            tol_rmse_mm_per_yr=0.0,
            accel=1.2,
            convergence_metric="modeled_area_abs_integral",
        )
        self.assertGreater(sf, 1.0)
        rec_mean = float(np.asarray(info["mean_rec"]).reshape(-1)[0])
        self.assertTrue(np.isfinite(rec_mean))
        corrected_mean = np.nanmean(rate_obs[mask]) * sf
        self.assertGreater(abs(corrected_mean), abs(np.nanmean(rate_obs[mask])))

    def test_save_leakage_bundle_writes_summary_and_figures(self):
        with tempfile.TemporaryDirectory() as td:
            out_file = Path(td) / "demo_lrc.mat"
            raw = np.zeros((6, 5, 3), dtype=float)
            corrected = raw.copy()
            corrected[2:4, 2:4, :] = 1.5
            mask = np.zeros((6, 5), dtype=bool)
            mask[2:4, 2:4] = True
            bundle = save_leakage_bundle(
                output_file=str(out_file),
                raw_stack=raw,
                corrected_stack=corrected,
                lon_vec=np.linspace(-10.0, 10.0, 6),
                lat_vec=np.linspace(-8.0, 8.0, 5),
                labels=["2002-04", "2002-05", "2002-06"],
                mask=mask,
                method="SCALE_FACTOR",
                scene_info={"scene": "inland_basin", "reasoning": ["Synthetic inland test."]},
                operator_info={"method": "GAUSSIAN", "product_type": "grid_stack"},
                validation={"residual_metric_by_month": np.array([0.1, 0.2, 0.3])},
                extra_meta={"scope": "regional"},
            )
            self.assertTrue(Path(bundle["bundle_dir"]).exists())
            self.assertTrue(Path(bundle["summary_json"]).exists())
            self.assertTrue(Path(bundle["regional_series"]).exists())
            self.assertTrue(Path(bundle["representative_map"]).exists())
            self.assertTrue(Path(bundle["representative_map_roi"]).exists())
            self.assertTrue(Path(bundle["preview_manifest"]).exists())
            self.assertTrue(Path(bundle["gallery_index"]).exists())

            bundle2 = save_leakage_bundle(
                output_file=str(Path(td) / "demo_fm.mat"),
                raw_stack=raw,
                corrected_stack=corrected,
                lon_vec=np.linspace(-10.0, 10.0, 6),
                lat_vec=np.linspace(-8.0, 8.0, 5),
                labels=["2002-04", "2002-05", "2002-06"],
                mask=mask,
                method="FORWARD_MODELING",
                scene_info={"scene": "inland_basin"},
                operator_info={"method": "GAUSSIAN", "product_type": "grid_stack"},
                validation={
                    "fm_rate_observed": raw[:, :, 0],
                    "fm_rate_recovered": corrected[:, :, 0],
                    "fm_rate_predicted": raw[:, :, 0],
                    "fm_rate_residual": corrected[:, :, 0] - raw[:, :, 0],
                    "fm_rate_residual_history": np.array([1.0, 0.5, 0.2]),
                },
            )
            self.assertTrue(Path(bundle2["fm_rate_diagnostics"]).exists())
            self.assertTrue(Path(bundle2["fm_rate_history"]).exists())


if __name__ == "__main__":
    unittest.main()
