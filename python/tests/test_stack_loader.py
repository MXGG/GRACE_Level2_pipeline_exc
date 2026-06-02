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

from grace_pipeline.infra.stack.loader import load_stack_slice_any


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
            v_lon[:] = lon
            v_lat[:] = lat
            v_time[:] = time
            v_data[:] = data

        grid, lon_out, lat_out, t_val, meta = load_stack_slice_any(
            str(path),
            time_index=1,
            active_var="lwe_thickness",
            selection_meta={
                "lon_key": "lon",
                "lat_key": "lat",
                "time_key": "time",
                "active_var": "lwe_thickness",
            },
        )

        self.assertEqual(grid.shape, (4, 3))
        np.testing.assert_allclose(grid, data[1].T)
        np.testing.assert_allclose(lon_out, lon)
        np.testing.assert_allclose(lat_out, lat)
        self.assertEqual(float(t_val), 1.0)
        self.assertEqual(meta["active_var"], "lwe_thickness")

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


if __name__ == "__main__":
    unittest.main()
