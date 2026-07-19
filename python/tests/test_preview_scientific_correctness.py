import os
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "Agg")

import h5py
import matplotlib as mpl
import numpy as np
import scipy.io as sio
from matplotlib.figure import Figure


ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from grace_pipeline.ui.qt import preview_enhancements as pe
from grace_pipeline.ui.qt import preview_stable_rendering as stable
from grace_pipeline.ui.qt.preview_science import (
    YearMonth,
    month_from_value,
    open_shapefile_reader,
    select_layer_time_index,
    unit_from_metadata,
    variable_unit_from_file,
)


class _TextWidget:
    def __init__(self, value=""):
        self.value = value
        self.visible = True

    def currentText(self):
        return self.value

    def text(self):
        return self.value

    def setText(self, value):
        self.value = str(value)

    def setVisible(self, visible):
        self.visible = bool(visible)


class _CheckWidget:
    def __init__(self, checked=False):
        self.checked = bool(checked)

    def isChecked(self):
        return self.checked


class PreviewTimeMatchingTest(unittest.TestCase):
    def test_exact_then_nearest_month_with_tolerance(self):
        values = ["2002-01", "2002-04", "2002-06"]
        exact = select_layer_time_index(
            "2002-04",
            values,
            requested_index=99,
            layer_length=3,
            tolerance_months=1,
        )
        self.assertEqual((exact.index, exact.method, exact.distance_months), (1, "exact", 0))

        nearest = select_layer_time_index(
            "2002-05",
            values,
            requested_index=99,
            layer_length=3,
            tolerance_months=1,
        )
        self.assertEqual(nearest.index, 1)
        self.assertEqual(nearest.method, "nearest")
        self.assertEqual(nearest.matched_month, YearMonth(2002, 4))

    def test_no_match_does_not_clamp_to_last_frame(self):
        unmatched = select_layer_time_index(
            "2002-10",
            ["2002-01", "2002-04"],
            requested_index=200,
            layer_length=2,
            tolerance_months=1,
        )
        self.assertIsNone(unmatched.index)
        self.assertIn("within 1 month", unmatched.message)

        no_axis = select_layer_time_index(
            None,
            None,
            requested_index=200,
            layer_length=2,
        )
        self.assertIsNone(no_axis.index)
        self.assertIn("was not clamped", no_axis.message)

    def test_cf_numeric_time_coordinates_match_by_month(self):
        target = month_from_value(45.0, units="days since 2002-01-01")
        self.assertEqual(target, YearMonth(2002, 2))
        match = select_layer_time_index(
            45.0,
            [14.0, 45.0, 73.0],
            requested_index=0,
            layer_length=3,
            target_units="days since 2002-01-01",
            layer_units="days since 2002-01-01",
        )
        self.assertEqual((match.index, match.method), (1, "exact"))


class PreviewResourceAndUnitTest(unittest.TestCase):
    def test_shapefile_reader_closes_even_when_drawing_raises(self):
        class FakeReader:
            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True

        reader = FakeReader()
        module = SimpleNamespace(Reader=lambda *_args, **_kwargs: reader)
        with mock.patch.dict(sys.modules, {"shapefile": module}):
            with self.assertRaisesRegex(RuntimeError, "draw failed"):
                with open_shapefile_reader("coast.shp"):
                    raise RuntimeError("draw failed")
        self.assertTrue(reader.closed)

    def test_units_are_read_from_metadata_and_file_attributes(self):
        self.assertEqual(unit_from_metadata({"var_units": {"ewh": "cm"}}, "ewh"), "cm")
        self.assertEqual(unit_from_metadata({"Units": "mm"}, "ewh"), "mm")
        self.assertEqual(unit_from_metadata({}, "ewh"), "")
        handle, path_text = tempfile.mkstemp(suffix=".h5")
        os.close(handle)
        path = Path(path_text)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        with h5py.File(path, "w") as h5:
            data = h5.create_dataset("ewh", data=np.zeros((2, 2, 1)))
            data.attrs["Units"] = "kg m-2"
        self.assertEqual(variable_unit_from_file(str(path), "ewh"), "kg m-2")

        handle, mat_path_text = tempfile.mkstemp(suffix=".mat")
        os.close(handle)
        mat_path = Path(mat_path_text)
        self.addCleanup(lambda: mat_path.unlink(missing_ok=True))
        sio.savemat(
            mat_path,
            {
                "ewh": np.zeros((2, 2, 1)),
                "meta": json.dumps({"var_units": {"ewh": "mm"}}),
            },
        )
        self.assertEqual(variable_unit_from_file(str(mat_path), "ewh"), "mm")

    def test_status_value_preserves_supplied_unit(self):
        page = SimpleNamespace(
            cmb_data_var=_TextWidget("ewh"),
            lbl_dataset=_TextWidget(),
            lbl_grid_value=_TextWidget(),
            lbl_engine_latency=_TextWidget(),
            canvas_preview_title=_TextWidget(),
        )
        controller = SimpleNamespace(window=SimpleNamespace(page_preview=page))
        frame = {"meta": {"active_var": "ewh", "units": "cm"}}
        pe._update_preview_status(controller, "sample.mat", 0, frame, np.asarray([[1.0, 3.0]]), 2.5)
        self.assertEqual(page.lbl_grid_value.value, "2.000 cm")
        self.assertEqual(controller._preview_value_unit, "cm")

    def test_colorbar_label_preserves_frame_unit(self):
        figure = Figure()
        axes = figure.add_subplot(111)
        image = axes.imshow(np.asarray([[1.0, 2.0], [3.0, 4.0]]))
        colorbar = figure.colorbar(image, ax=axes)
        page = SimpleNamespace(
            cmb_data_var=_TextWidget("ewh"),
            edit_dataset_source=_TextWidget("sample.mat"),
            canvas_preview_title=_TextWidget(),
        )
        controller = SimpleNamespace(
            window=SimpleNamespace(page_preview=page),
            _figure=figure,
            _ax=axes,
            _preview_current_frame={"meta": {"active_var": "ewh", "units": "cm"}},
        )
        pe._polish_rendered_figure(controller)
        self.assertEqual(colorbar.ax.get_ylabel(), "ewh (cm)")

    def test_cursor_value_status_keeps_active_unit(self):
        value = _TextWidget("12.375")
        controller = SimpleNamespace(
            _preview_value_unit="cm",
            window=SimpleNamespace(page_preview=SimpleNamespace(lbl_grid_value=value)),
        )
        stable._append_preview_value_unit(controller)
        self.assertEqual(value.value, "12.375 cm")
        stable._append_preview_value_unit(controller)
        self.assertEqual(value.value, "12.375 cm")


class PreviewThreeDimensionalIntegrityTest(unittest.TestCase):
    def test_hidden_base_raster_uses_constant_neutral_surface(self):
        grid = np.asarray([[-2.0, 0.0], [1.0, 3.0]])
        cmap = mpl.colormaps["RdBu_r"]
        norm = mpl.colors.Normalize(vmin=-3.0, vmax=3.0)
        radius, colors = pe._globe_surface_visuals(grid, cmap, norm, 0.05, data_visible=False)
        self.assertEqual(radius, 1.0)
        np.testing.assert_allclose(colors, np.broadcast_to(colors[0, 0], colors.shape))

        visible_radius, visible_colors = pe._globe_surface_visuals(grid, cmap, norm, 0.05, data_visible=True)
        self.assertIsInstance(visible_radius, np.ndarray)
        self.assertFalse(np.allclose(visible_colors[0, 0], visible_colors[-1, -1]))

    def test_imported_3d_raster_is_logged_and_annotated(self):
        base = SimpleNamespace(type="raster", path=None, visible=False)
        overlay = SimpleNamespace(type="raster", path="overlay.mat", name="overlay.mat", visible=True)
        logs = []
        annotations = []

        class FakeAxes:
            transAxes = object()

            def text2D(self, *_args, **kwargs):
                annotations.append((_args, kwargs))

        controller = SimpleNamespace(
            preview_layers=[base, overlay],
            _ensure_preview_layers=lambda: None,
            _preview_layers_by_type=lambda *_args, **_kwargs: [overlay],
            window=SimpleNamespace(
                ui_preferences=SimpleNamespace(language="en"),
                page_preview=SimpleNamespace(chk_layer_data=None),
            ),
            on_log=lambda message, channel: logs.append((message, channel)),
        )
        self.assertFalse(pe._preview_base_raster_visible(controller))
        layers = pe._visible_imported_raster_layers(controller)
        names = pe._surface_unsupported_3d_rasters(controller, FakeAxes(), layers)
        self.assertEqual(names, ("overlay.mat",))
        self.assertTrue(any("does not support imported raster" in message for message, _ in logs))
        self.assertEqual(len(annotations), 1)

    def test_full_3d_render_hides_data_colorbar_and_surfaces_overlay_warning(self):
        base = SimpleNamespace(type="raster", path=None, name="data", visible=False)
        overlay = SimpleNamespace(type="raster", path="overlay.mat", name="overlay.mat", visible=True)
        page = SimpleNamespace(
            projection_param_widgets={},
            edit_cmin=_TextWidget(""),
            edit_cmax=_TextWidget(""),
            cmb_cmap=_TextWidget("RdBu_r"),
            chk_layer_data=_CheckWidget(False),
            chk_layer_coastlines=_CheckWidget(False),
            chk_enable_spatial_grid=_CheckWidget(False),
            chk_layer_grid=_CheckWidget(False),
            chk_show_colorbar=_CheckWidget(True),
            lbl_grid_value=_TextWidget("99.0"),
        )
        logs = []
        controller = SimpleNamespace(
            preview_layers=[base, overlay],
            window=SimpleNamespace(
                page_preview=page,
                ui_preferences=SimpleNamespace(language="en"),
            ),
            _ensure_preview_layers=lambda: None,
            _sync_preview_legacy_layer_controls=lambda: None,
            _preview_layers_by_type=lambda *types, **_kwargs: [base, overlay] if "raster" in types else [],
            _preview_layer_visible=lambda layer_type, **_kwargs: layer_type == "colorbar",
            _figure=Figure(),
            _canvas=SimpleNamespace(draw_idle=lambda: None),
            _sync_preview_toolbar_mode=lambda: None,
            on_log=lambda message, channel: logs.append((message, channel)),
        )
        lon = np.asarray([-90.0, 0.0, 90.0])
        lat = np.asarray([-45.0, 0.0, 45.0])
        grid = np.arange(9, dtype=float).reshape(3, 3)
        frame = {"t": "2002-04", "meta": {"active_var": "ewh", "units": "cm"}}
        with (
            mock.patch.object(pe, "_grid_context", return_value=("base.mat", 0, frame, grid, lon, lat)),
            mock.patch.object(pe, "_apply_bbox", return_value=(grid, lon, lat, None)),
            mock.patch.object(pe, "_draw_3d_boundary_layers"),
            mock.patch.object(pe, "_polish_rendered_figure"),
            mock.patch.object(pe, "apply_3d_globe_view"),
            mock.patch.object(pe, "_update_preview_status"),
        ):
            pe._render_3d_globe(controller)

        self.assertEqual(len(controller._figure.axes), 1, "hidden data must not create a colorbar")
        self.assertEqual(page.lbl_grid_value.value, "—")
        self.assertEqual(controller._preview_3d_unsupported_raster_layers, ("overlay.mat",))
        self.assertTrue(any("does not support imported raster" in message for message, _ in logs))


class ImportedRasterRenderMatchingTest(unittest.TestCase):
    def setUp(self):
        lon = np.asarray([0.0, 90.0, 180.0, 270.0])
        lat = np.asarray([-45.0, 0.0, 45.0])
        stack = np.zeros((lon.size, lat.size, 2), dtype=float)
        stack[:, :, 0] = 1.0
        stack[:, :, 1] = 4.0
        handle, path_text = tempfile.mkstemp(suffix="_overlay.mat")
        os.close(handle)
        self.path = Path(path_text)
        sio.savemat(
            self.path,
            {
                "ewh": stack,
                "lon": lon,
                "lat": lat,
                "t": np.asarray(["2002-01", "2002-04"], dtype=object),
            },
        )
        self.addCleanup(lambda: self.path.unlink(missing_ok=True))
        self.figure = Figure()
        page = SimpleNamespace(cmb_data_var=_TextWidget("ewh"))
        self.logs = []
        self.controller = SimpleNamespace(
            window=SimpleNamespace(page_preview=page),
            _ax=self.figure.add_subplot(111),
            on_log=lambda message, channel: self.logs.append((message, channel)),
        )
        self.layer = SimpleNamespace(
            path=str(self.path),
            name="independent months",
            metadata={"active_var": "ewh", "units": "cm"},
            opacity=0.7,
            zorder=10,
        )

    def test_renderer_uses_exact_preview_month_not_requested_position(self):
        artist = stable._draw_imported_raster_layer(
            self.controller,
            self.layer,
            99,
            "PlateCarree",
            0.0,
            0.0,
            30.0,
            60.0,
            "RdBu_r",
            None,
            None,
            target_time="2002-04",
            target_meta={},
        )
        self.assertIsNotNone(artist)
        self.assertEqual(artist._grace_preview_time_match.index, 1)
        self.assertEqual(artist._grace_preview_time_match.method, "exact")
        self.assertEqual(artist._grace_preview_mean, 4.0)
        self.assertEqual(artist._grace_preview_label, "ewh (cm)")
        self.assertEqual(artist.get_zorder(), 12.0)

    def test_renderer_skips_nonmatching_month_without_preview_tolerance(self):
        artist = stable._draw_imported_raster_layer(
            self.controller,
            self.layer,
            99,
            "PlateCarree",
            0.0,
            0.0,
            30.0,
            60.0,
            "RdBu_r",
            None,
            None,
            target_time="2002-03",
            target_meta={},
        )
        self.assertIsNone(artist)
        self.assertTrue(any("skipped" in message and "within 0 month" in message for message, _ in self.logs))


if __name__ == "__main__":
    unittest.main()
