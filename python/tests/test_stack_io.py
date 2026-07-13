import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import scipy.io as sio


ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from grace_pipeline.io.stack import (
    Stack,
    find_stack_file,
    load_stack,
    load_stack_hdf5,
    load_stack_slice_hdf5,
    save_stack,
    save_stack_hdf5,
)
from grace_pipeline.infra.stack.loader import load_stack_any, load_stack_slice_any
from grace_pipeline.infra.stack.probe import probe_stack_any
from grace_pipeline.ui.qt.preview_science import variable_unit_from_file


class StackIoTest(unittest.TestCase):
    def test_save_stack_preserves_preview_contract_without_tmp_mat_leak(self):
        out_dir = Path(tempfile.mkdtemp())
        stack = Stack(
            tag="HSAF",
            ewh=np.arange(4 * 3 * 2, dtype=np.float64).reshape(4, 3, 2),
            lon=np.linspace(-180, 180, 4, dtype=np.float64),
            lat=np.linspace(-90, 90, 3, dtype=np.float64),
            t=["2002-04", "2002-05"],
            meta={"units": "cm", "active_var": "ewh"},
        )

        filepath = Path(save_stack(stack, str(out_dir), compress=False))
        self.assertTrue(filepath.exists())
        self.assertFalse((out_dir / "HSAF_stack.mat.tmp").exists())
        self.assertFalse((out_dir / "HSAF_stack.mat.tmp.mat").exists())

        raw = sio.loadmat(filepath)
        self.assertIn("ewh", raw)
        self.assertEqual(raw["ewh"].shape, (4, 3, 2))
        self.assertEqual(raw["ewh"].dtype, np.float32)
        self.assertIn("lon", raw)
        self.assertIn("lat", raw)
        self.assertIn("t", raw)
        self.assertIn("tag", raw)

        loaded = load_stack(str(filepath))
        self.assertEqual(loaded.tag, "HSAF")
        self.assertEqual(loaded.ewh.shape, (4, 3, 2))
        self.assertEqual(list(loaded.t), ["2002-04", "2002-05"])
        self.assertEqual(loaded.meta["units"], "cm")

        shape, _, _, times, meta = probe_stack_any(str(filepath), load_stack_any)
        self.assertEqual(shape, (4, 3, 2))
        self.assertEqual(list(np.asarray(times).reshape(-1)), ["2002-04", "2002-05"])
        self.assertEqual(meta["units"], "cm")
        self.assertEqual(variable_unit_from_file(str(filepath), "ewh"), "cm")

    @unittest.skipUnless(importlib.util.find_spec("h5py") is not None, "h5py not available")
    def test_hdf5_sidecar_roundtrip_and_slice_read(self):
        out_dir = Path(tempfile.mkdtemp())
        stack = Stack(
            tag="HSAF",
            ewh=np.arange(4 * 3 * 2, dtype=np.float64).reshape(4, 3, 2),
            lon=np.linspace(-180, 180, 4, dtype=np.float64),
            lat=np.linspace(-90, 90, 3, dtype=np.float64),
            t=["2002-04", "2002-05"],
            meta={"units": "cm", "active_var": "ewh"},
        )

        mat_path = Path(save_stack(stack, str(out_dir), compress=False))
        h5_path = Path(save_stack_hdf5(stack, str(out_dir), compress_level=0))

        loaded = load_stack_hdf5(str(h5_path))
        self.assertEqual(loaded.ewh.shape, (4, 3, 2))
        self.assertEqual(list(loaded.t), ["2002-04", "2002-05"])

        grid, lon, lat, t_val = load_stack_slice_hdf5(str(h5_path), 1)
        self.assertEqual(grid.shape, (4, 3))
        np.testing.assert_allclose(grid, stack.ewh[:, :, 1])
        np.testing.assert_allclose(lon, stack.lon)
        np.testing.assert_allclose(lat, stack.lat)
        self.assertEqual(t_val, "2002-05")

        shape, _, _, times, meta = probe_stack_any(str(h5_path), load_stack_any)
        self.assertEqual(shape, (4, 3, 2))
        self.assertEqual(list(np.asarray(times).reshape(-1)), ["2002-04", "2002-05"])
        self.assertEqual(meta["units"], "cm")
        self.assertEqual(variable_unit_from_file(str(h5_path), "ewh"), "cm")

        grid_any, _, _, time_any, frame_meta = load_stack_slice_any(
            str(h5_path), time_index=1, active_var="ewh", selection_meta=meta
        )
        np.testing.assert_allclose(grid_any, stack.ewh[:, :, 1])
        self.assertEqual(time_any, "2002-05")
        self.assertIsInstance(time_any, str)
        self.assertEqual(frame_meta["units"], "cm")

        found = find_stack_file(str(out_dir), "HSAF")
        self.assertEqual(Path(found), h5_path)
        self.assertTrue(mat_path.exists())


if __name__ == "__main__":
    unittest.main()
