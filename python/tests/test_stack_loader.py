import importlib.util
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

from grace_pipeline.infra.stack.loader import load_stack_any, load_stack_slice_any
from grace_pipeline.infra.stack.probe import probe_stack_any
from grace_pipeline.ui.qt.preview_science import variable_unit_from_file


@unittest.skipUnless(importlib.util.find_spec("netCDF4") is not None, "netCDF4 not available")
class StackLoaderTest(unittest.TestCase):
    def test_load_stack_slice_any_reads_single_netcdf_frame_in_lon_lat_order(self):
        import netCDF4 as nc

        handle, path_text = tempfile.mkstemp(suffix="_stack.nc")
        os.close(handle)
        path = Path(path_text)
        self.addCleanup(lambda: path.unlink(missing_ok=True))

        lon = np.array([10.0, 20.0, 30.0, 40.0], dtype=np.float32)
        lat = np.array([-15.0, 0.0, 15.0], dtype=np.float32)
        time = np.array([0.0, 1.0, 2.0], dtype=np.float32)
        data = np.arange(3 * 3 * 4, dtype=np.float32).reshape(3, 3, 4)

        with nc.Dataset(path, "w") as ds:
            ds.createDimension("time", 3)
            ds.createDimension("lat", 3)
            ds.createDimension("lon", 4)
            v_lon = ds.createVariable("lon", "f4", ("lon",))
            v_lat = ds.createVariable("lat", "f4", ("lat",))
            v_time = ds.createVariable("time", "f4", ("time",))
            v_data = ds.createVariable("lwe_thickness", "f4", ("time", "lat", "lon"))
            v_lon.setncattr("Units", "degrees_east")
            v_lat.setncattr("Units", "degrees_north")
            v_time.setncattr("Units", "days since 2002-01-01")
            v_time.setncattr("Calendar", "gregorian")
            v_data.setncattr("Units", "cm")
            v_lon[:] = lon
            v_lat[:] = lat
            v_time[:] = time
            v_data[:] = data

        shape, _, _, _, probe_meta = probe_stack_any(str(path), load_stack_any)
        self.assertEqual(shape, (4, 3, 3))
        self.assertEqual(probe_meta["time_units"], "days since 2002-01-01")
        self.assertEqual(probe_meta["time_calendar"], "gregorian")
        self.assertEqual(probe_meta["units"], "cm")
        self.assertEqual(variable_unit_from_file(str(path), "lwe_thickness"), "cm")

        grid, lon_out, lat_out, t_val, meta = load_stack_slice_any(
            str(path),
            time_index=1,
            active_var="lwe_thickness",
            selection_meta=probe_meta,
        )

        self.assertEqual(grid.shape, (4, 3))
        np.testing.assert_allclose(grid, data[1].T)
        np.testing.assert_allclose(lon_out, lon)
        np.testing.assert_allclose(lat_out, lat)
        self.assertEqual(float(t_val), 1.0)
        self.assertEqual(meta["active_var"], "lwe_thickness")
        self.assertEqual(meta["units"], "cm")
        self.assertEqual(meta["time_units"], "days since 2002-01-01")

    @unittest.skipUnless(importlib.util.find_spec("h5py") is not None, "h5py not available")
    def test_load_stack_slice_any_prefers_hdf5_sidecar_for_mat_preview(self):
        from grace_pipeline.io.stack import Stack, save_stack, save_stack_hdf5

        out_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(out_dir, ignore_errors=True))

        stack = Stack(
            tag="P4M6",
            ewh=np.arange(4 * 3 * 2, dtype=np.float32).reshape(4, 3, 2),
            lon=np.array([10.0, 20.0, 30.0, 40.0], dtype=np.float32),
            lat=np.array([-15.0, 0.0, 15.0], dtype=np.float32),
            t=["2002-04", "2002-05"],
        )

        mat_path = Path(save_stack(stack, str(out_dir), compress=False))
        save_stack_hdf5(stack, str(out_dir), compress_level=0)

        grid, lon_out, lat_out, t_val, meta = load_stack_slice_any(str(mat_path), time_index=1)

        self.assertEqual(grid.shape, (4, 3))
        np.testing.assert_allclose(grid, stack.ewh[:, :, 1])
        np.testing.assert_allclose(lon_out, stack.lon)
        np.testing.assert_allclose(lat_out, stack.lat)
        self.assertEqual(t_val, "2002-05")
        self.assertEqual(meta["source"], "hdf5_sidecar")


class TextGridLoaderTest(unittest.TestCase):
    def test_comma_and_whitespace_text_grids_load_with_identical_values(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        comma_path = root / "exported_grid.txt"
        space_path = root / "legacy_grid.txt"
        from grace_pipeline.ui.qt.controller import QtWorkflowHost

        writer = QtWorkflowHost.__new__(QtWorkflowHost)
        writer._save_grid_txt(
            str(comma_path),
            np.asarray([0.0, 1.0]),
            np.asarray([-1.0, 1.0]),
            np.asarray([[10.0, 30.0], [20.0, 40.0]]),
        )
        space_path.write_text(
            "# lon lat value\n0 -1 10\n1 -1 20\n0 1 30\n1 1 40\n",
            encoding="utf-8",
        )

        comma = load_stack_any(str(comma_path))
        space = load_stack_any(str(space_path))

        self.assertEqual(comma[0].shape, (2, 2, 1))
        np.testing.assert_allclose(comma[0], space[0])
        np.testing.assert_allclose(comma[1], [0.0, 1.0])
        np.testing.assert_allclose(comma[2], [-1.0, 1.0])
        np.testing.assert_allclose(comma[0][:, :, 0], [[10.0, 30.0], [20.0, 40.0]])


if __name__ == "__main__":
    unittest.main()
