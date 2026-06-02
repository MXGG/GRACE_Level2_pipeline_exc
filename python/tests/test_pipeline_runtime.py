import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from grace_pipeline.app import pipeline as pipeline_module
from grace_pipeline.infra.config import Config


class PipelineRuntimeTest(unittest.TestCase):
    def _make_cfg(self, out_dir: str) -> Config:
        return Config(
            {
                "path": {"OUTPUT": out_dir},
                "time": {"auto_detect_gfc": True, "start_ym": "2002-04", "end_ym": "2002-05"},
                "grid": {"lon": [-179.5, 179.5], "lat": [-89.5, 89.5], "dlon": 120.0, "dlat": 90.0},
                "inversion": {
                    "Lmax": 60,
                    "remove_mean": False,
                    "lowdeg": {"enable": False},
                    "gia": {"enable": False},
                },
                "filter": {
                    "gaussian": {"enable": False},
                    "p4m6": {"enable": False},
                    "ddk": {"enable": False},
                    "fan": {"enable": False},
                    "pre_hankel_input": "RAW",
                    "hankel": {
                        "enable": True,
                        "stack_mode": True,
                        "engine": "matlab_v3",
                        "variant": "global",
                        "params": {"N": 10, "P": 4, "K": 3, "J": 1},
                    },
                },
                "io": {
                    "save_monthly_mat": False,
                    "save_stack_mat": False,
                    "export_txt": False,
                    "return_stacks": True,
                },
                "parallel": {"enable": False, "nWorkers": 52},
            }
        )

    def test_prepare_hsaf_stack_config_defaults_matlab_style_engine_to_single_inner_worker(self):
        out_dir = tempfile.mkdtemp()
        cfg = self._make_cfg(out_dir)

        matlab_cfg = pipeline_module._prepare_hsaf_stack_config(cfg)
        self.assertEqual(matlab_cfg["params"]["workers"], 1)

        cfg.filter.hankel.engine = "svd"
        svd_cfg = pipeline_module._prepare_hsaf_stack_config(cfg, inner_workers=8)
        self.assertEqual(svd_cfg["params"]["workers"], 8)

    def test_choose_hsaf_outer_inner_workers_balances_budget_for_large_matlab_stack(self):
        out_dir = tempfile.mkdtemp()
        cfg = self._make_cfg(out_dir)

        outer_workers, inner_workers = pipeline_module._choose_hsaf_outer_inner_workers(
            cfg,
            total_slices=163,
            probe={
                "effective_workers": 20,
                "configured_workers": 20,
                "cpu_logical": 20,
                "frozen": False,
                "slurm_job": False,
            },
        )

        self.assertEqual((outer_workers, inner_workers), (5, 4))

    def test_format_hsaf_stack_progress_distinguishes_wall_and_compute_time(self):
        msg = pipeline_module._format_hsaf_stack_progress(
            1,
            163,
            80.32,
            5,
            inner_workers=4,
            compute_total_s=14.50,
            last_slice_s=14.50,
            startup_included=True,
        )

        self.assertIn("outer_workers=5", msg)
        self.assertIn("inner_workers=4", msg)
        self.assertIn("wall_avg=80.32s/slice", msg)
        self.assertIn("compute_avg=14.50s/slice", msg)
        self.assertIn("last=14.50s", msg)
        self.assertIn("note=includes pool startup", msg)

    def test_run_hsaf_stack_slice_rejects_shape_mismatch_and_keeps_input(self):
        out_dir = tempfile.mkdtemp()
        cfg = self._make_cfg(out_dir)
        grid = np.ones((3, 2), dtype=np.float32)
        lon_vec = np.array([0.0, 120.0, 240.0], dtype=float)
        lat_vec = np.array([-45.0, 45.0], dtype=float)
        hsaf_cfg = pipeline_module._prepare_hsaf_stack_config(cfg, inner_workers=1)

        with mock.patch.object(
            pipeline_module,
            "filter_grid_hsaf",
            return_value=(np.ones((2, 3), dtype=np.float32), {"engine": "matlab_v3"}),
        ):
            slice_idx, filtered, _, error = pipeline_module._run_hsaf_stack_slice(
                0,
                grid,
                lon_vec,
                lat_vec,
                hsaf_cfg,
                None,
            )

        self.assertEqual(slice_idx, 0)
        self.assertIsNotNone(error)
        self.assertIn("shape mismatch", error)
        np.testing.assert_allclose(filtered, grid)

    def test_local_runtime_probe_is_suppressed_and_small_local_hsaf_keeps_in_process_path(self):
        out_dir = tempfile.mkdtemp()
        cfg = self._make_cfg(out_dir)
        entries = [
            SimpleNamespace(ym="2002-04", year=2002, month=4),
            SimpleNamespace(ym="2002-05", year=2002, month=5),
        ]
        lon_vec = np.array([0.0, 120.0, 240.0], dtype=float)
        lat_vec = np.array([-45.0, 45.0], dtype=float)

        def fake_process_month(_cfg, _te, _mean_sh, _plan, _lon_vec, _lat_vec):
            return {"RAW": np.ones((3, 2), dtype=np.float32)}

        def fake_filter_grid_hsaf(stack_in, _lon_vec, _lat_vec, hsaf_cfg, progress_hook=None):
            self.assertEqual(stack_in.shape, (3, 2, 2))
            self.assertEqual(hsaf_cfg["params"]["workers"], 1)
            if progress_hook is not None:
                progress_hook(1, 2)
                progress_hook(2, 2)
            return stack_in + 2.0, {"engine": "matlab_v3"}

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), \
            mock.patch.object(pipeline_module, "build_time_index", return_value=entries), \
            mock.patch.object(pipeline_module, "make_lonlat_vec", return_value=(lon_vec, lat_vec)), \
            mock.patch.object(pipeline_module, "process_month", side_effect=fake_process_month), \
            mock.patch.object(pipeline_module, "filter_grid_hsaf", side_effect=fake_filter_grid_hsaf) as filter_mock, \
            mock.patch.object(pipeline_module, "_run_hsaf_stack_slice") as slice_mock, \
            mock.patch.object(
                pipeline_module,
                "_runtime_probe",
                return_value={
                    "cpu_logical": 8,
                    "configured_workers": 52,
                    "frozen": False,
                    "blas_threads": {
                        "OPENBLAS_NUM_THREADS": "1",
                        "MKL_NUM_THREADS": "1",
                        "OMP_NUM_THREADS": "1",
                        "NUMEXPR_MAX_THREADS": "1",
                    },
                    "cupy_available": False,
                    "slurm_job": False,
                },
            ):
            result = pipeline_module.run_pipeline(cfg)

        output = stdout.getvalue()
        self.assertNotIn("Runtime probe", output)
        self.assertIn("in-process stack loop", output)
        self.assertEqual(filter_mock.call_count, 1)
        self.assertEqual(slice_mock.call_count, 0)
        self.assertIn("HSAF", result.stacks)
        np.testing.assert_allclose(result.stacks["HSAF"], np.ones((3, 2, 2), dtype=np.float32) + 2.0)


if __name__ == "__main__":
    unittest.main()
