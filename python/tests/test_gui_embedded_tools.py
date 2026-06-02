import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "Agg")

import numpy as np
import scipy.io as sio
from PySide6.QtWidgets import QApplication


ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from grace_pipeline.ui.qt.main_window import MainWindow


class GuiEmbeddedToolsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow(load_persisted=False)
        self.window._current_screen_metrics = lambda: (1920, 1040, 1.0)
        self.window._layout_bucket = None
        self.window.resize(1600, 980)
        self.window.show()
        self.app.processEvents()

        # Run tool targets inline for deterministic UI tests.
        self._orig_run_in_thread = self.window.controller._run_in_thread
        self.window.controller._run_in_thread = lambda _scope, target, _status: target()
        self.addCleanup(setattr, self.window.controller, "_run_in_thread", self._orig_run_in_thread)

    def tearDown(self):
        self.window.close()
        self.app.processEvents()

    def _create_sample_gfc(self, folder: Path) -> Path:
        gfc = folder / "sample.gfc"
        gfc.write_text(
            "\n".join(
                [
                    "product_type GSM",
                    "modelname TEST",
                    "end_of_head",
                    "gfc 0 0 1.0 0.0",
                    "gfc 1 0 0.0 0.0",
                    "gfc 1 1 0.0 0.0",
                    "gfc 2 0 0.0 0.0",
                    "gfc 2 1 0.0 0.0",
                    "gfc 2 2 0.0 0.0",
                ]
            ),
            encoding="utf-8",
        )
        return gfc

    def _create_dated_sample_gfc(self, folder: Path, name: str, c30: float) -> Path:
        gfc = folder / name
        gfc.write_text(
            "\n".join(
                [
                    "product_type gravity_field",
                    f"modelname {gfc.stem}",
                    "max_degree 3",
                    "norm fully_normalized",
                    "end_of_head",
                    "gfc 0 0 1.0 0.0",
                    "gfc 1 0 0.0 0.0",
                    "gfc 1 1 0.0 0.0",
                    "gfc 2 0 -4.84169325119e-4 0.0",
                    "gfc 2 1 0.0 0.0",
                    "gfc 2 2 0.0 0.0",
                    f"gfc 3 0 {float(c30):.12e} 0.0",
                    "gfc 3 1 0.0 0.0",
                    "gfc 3 2 0.0 0.0",
                    "gfc 3 3 0.0 0.0",
                ]
            ),
            encoding="utf-8",
        )
        return gfc

    def _create_sample_stack(self, folder: Path) -> Path:
        lon = np.array([-20.0, 0.0, 20.0], dtype=float)
        lat = np.array([-20.0, 0.0, 20.0], dtype=float)
        ewh = np.zeros((3, 3, 3), dtype=float)
        ewh[:, :, 0] = 1.0
        ewh[:, :, 1] = 2.0
        ewh[:, :, 2] = 3.0
        t = np.array(["2002-04", "2002-05", "2002-06"], dtype=object)
        stack = folder / "sample_stack.mat"
        sio.savemat(stack, {"ewh": ewh, "lon": lon, "lat": lat, "t": t})
        return stack

    def _create_sample_sh_analysis_stack(self, folder: Path) -> Path:
        lon = np.linspace(-25.0, 25.0, 6, dtype=float)
        lat = np.linspace(-25.0, 25.0, 6, dtype=float)
        ewh = np.zeros((lon.size, lat.size, 3), dtype=float)
        for i, lon_value in enumerate(lon):
            for j, lat_value in enumerate(lat):
                ewh[i, j, 0] = 1.0
                ewh[i, j, 1] = np.cos(np.deg2rad(lon_value)) + np.sin(np.deg2rad(lat_value))
                ewh[i, j, 2] = 3.0
        t = np.array(["2002-04", "2002-05", "2002-06"], dtype=object)
        stack = folder / "sample_sh_analysis_stack.mat"
        sio.savemat(stack, {"ewh": ewh, "lon": lon, "lat": lat, "t": t})
        return stack

    def _create_sample_boundary(self, folder: Path) -> Path:
        # Simple rectangle around center cell.
        boundary = folder / "sample_boundary.txt"
        boundary.write_text(
            "\n".join(
                [
                    "-10 -10",
                    "10 -10",
                    "10 10",
                    "-10 10",
                    "-10 -10",
                ]
            ),
            encoding="utf-8",
        )
        return boundary

    def test_processing_sh_to_grid_tool_runs_and_writes_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            gfc_dir = root / "gfc"
            gfc_dir.mkdir(parents=True, exist_ok=True)
            gfc = self._create_sample_gfc(gfc_dir)

            self.window.set_active_page("processing")
            self.window.page_data_paths.edit_main_output_root.setText(str(root / "output"))
            self.window.page_data_paths.edit_gfc_input_dir.setText(str(gfc_dir))
            self.window.page_preview.edit_dataset_source.setText(str(gfc))
            self.window.page_processing.slider_degree_order.setValue(2)
            self.app.processEvents()

            self.window.controller.on_tool_sh_to_grid()
            self.app.processEvents()

            out_dir = root / "output" / "local" / "tools" / "sh_grid"
            files = list(out_dir.glob("*.mat"))
            self.assertTrue(files, "Expected SH->Grid tool to produce MAT output.")
            self.assertIn("completed", self.window.page_processing.lbl_sh_tool_status.text().lower())

    def test_processing_sh_to_grid_removes_gfc_static_mean_before_ewh(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            gfc_dir = root / "gfc"
            gfc_dir.mkdir(parents=True, exist_ok=True)
            source = self._create_dated_sample_gfc(
                gfc_dir,
                "GSM-2_2006060-2006090_GRAC_UTCSR_BA01_0600.gfc",
                c30=2.0e-10,
            )
            self._create_dated_sample_gfc(
                gfc_dir,
                "GSM-2_2006091-2006120_GRAC_UTCSR_BA01_0600.gfc",
                c30=-2.0e-10,
            )

            self.window.set_active_page("processing")
            self.window.page_data_paths.edit_main_output_root.setText(str(root / "output"))
            self.window.page_data_paths.edit_gfc_input_dir.setText(str(gfc_dir))
            self.window.page_processing.edit_sh_tool_source.setText(str(source))
            self.window.page_processing.slider_degree_order.setValue(3)
            self.app.processEvents()

            self.window.controller.on_tool_sh_to_grid()
            self.app.processEvents()

            out_file = next((root / "output" / "local" / "tools" / "sh_grid").glob("*.mat"))
            payload = sio.loadmat(out_file, squeeze_me=True, struct_as_record=False)
            grid = np.asarray(payload["grid_data"], dtype=float)
            self.assertLess(float(np.nanmax(np.abs(grid))), 100.0)
            self.assertIn("anomaly_removed=True", self.window.filters_text.toPlainText())

    def test_processing_grid_to_sh_tool_runs_and_writes_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stack = self._create_sample_sh_analysis_stack(root)

            self.window.set_active_page("processing")
            self.window.page_data_paths.edit_main_output_root.setText(str(root / "output"))
            self.window.page_processing.edit_sh_tool_source.setText(str(stack))
            self.window.page_preview.edit_dataset_source.setText(str(stack))
            self.window.page_preview.slider_time_index.setValue(1)
            self.window.page_processing.slider_degree_order.setValue(2)
            self.app.processEvents()

            self.window.controller.on_tool_grid_to_sh()
            self.app.processEvents()

            out_dir = root / "output" / "local" / "tools" / "grid_sh"
            files = list(out_dir.glob("*.mat"))
            self.assertTrue(files, "Expected Grid->SH tool to produce MAT output.")
            payload = sio.loadmat(files[0])
            self.assertIn("C", payload)
            self.assertIn("S", payload)
            self.assertEqual(int(payload["Lmax"].squeeze()), 2)
            self.assertIn("completed", self.window.page_processing.lbl_sh_tool_status.text().lower())

    def test_processing_filter_checkboxes_expand_parameter_panels(self):
        self.window.set_active_page("processing")
        page = self.window.page_processing

        for checkbox in (
            page.btn_filter_gaussian,
            page.btn_filter_p4m6,
            page.btn_filter_gaussian_pnmn,
            page.btn_filter_ddk,
            page.btn_filter_fan,
            page.btn_filter_fan_pnmn,
            page.btn_filter_hsaf,
        ):
            checkbox.setChecked(False)
        self.window.controller._sync_processing_filter_button_styles()
        self.app.processEvents()

        self.assertFalse(page.panel_filter_gaussian.isVisible())
        self.assertFalse(page.panel_filter_pnmn.isVisible())
        self.assertFalse(page.panel_filter_ddk.isVisible())
        self.assertFalse(page.panel_filter_fan.isVisible())
        self.assertFalse(page.hsaf_detail_panel.isVisible())

        page.btn_filter_gaussian_pnmn.click()
        self.app.processEvents()
        self.assertTrue(page.panel_filter_gaussian.isVisible())
        self.assertTrue(page.panel_filter_pnmn.isVisible())
        self.assertFalse(page.panel_filter_ddk.isVisible())
        self.assertFalse(page.panel_filter_fan.isVisible())
        self.assertEqual(self.window.controller._enabled_filter_names(), ["P4M6_GAUSS"])

        page.btn_filter_ddk.click()
        self.app.processEvents()
        self.assertTrue(page.panel_filter_ddk.isVisible())
        self.assertFalse(page.panel_filter_gaussian.isVisible())

        page.btn_filter_hsaf.click()
        self.app.processEvents()
        self.assertTrue(page.hsaf_detail_panel.isVisible())

    def test_processing_grid_to_sh_tool_uses_explicit_source_before_preview(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stack = self._create_sample_sh_analysis_stack(root)

            self.window.set_active_page("processing")
            self.window.page_data_paths.edit_main_output_root.setText(str(root / "output"))
            self.window.page_processing.edit_sh_tool_source.setText(str(stack))
            self.window.page_preview.edit_dataset_source.setText("missing_preview_stack.nc")
            self.window.page_preview.slider_time_index.setValue(1)
            self.window.page_processing.slider_degree_order.setValue(2)
            self.app.processEvents()

            self.window.controller.on_tool_grid_to_sh()
            self.app.processEvents()

            out_dir = root / "output" / "local" / "tools" / "grid_sh"
            self.assertTrue(list(out_dir.glob("*.mat")), "Expected explicit Tool Source to override the missing Preview path.")

    def test_basin_series_and_harmonic_tools_run_and_write_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stack = self._create_sample_stack(root)
            boundary = self._create_sample_boundary(root)

            self.window.set_active_page("basin")
            self.window.page_data_paths.edit_main_output_root.setText(str(root / "output"))
            self.window.page_basin.edit_data_file.setText(str(stack))
            self.window.page_basin.edit_boundary_file.setText(str(boundary))
            self.app.processEvents()

            self.window.controller.on_tool_grid_to_series()
            self.window.controller.on_tool_harmonic_fit()
            self.app.processEvents()

            series_dir = root / "output" / "local" / "tools" / "series"
            harmonic_dir = root / "output" / "local" / "tools" / "harmonic"
            self.assertTrue(list(series_dir.glob("*.csv")), "Expected Grid->Series CSV output.")
            self.assertTrue(list(series_dir.glob("*.mat")), "Expected Grid->Series MAT output.")
            self.assertTrue(list(harmonic_dir.glob("*.txt")), "Expected Harmonic TXT output.")
            self.assertTrue(list(harmonic_dir.glob("*.mat")), "Expected Harmonic MAT output.")

    def test_basin_grid_metadata_loads_mat_without_variable_dialog(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stack = root / "diagnostic_grid.mat"
            lon = np.array([-20.0, 0.0, 20.0], dtype=float)
            lat = np.array([-20.0, 0.0, 20.0], dtype=float)
            mean = np.ones((3, 3), dtype=float)
            trend = np.ones((3, 3), dtype=float) * 2.0
            sio.savemat(stack, {"lon": lon, "lat": lat, "mean": mean, "trend": trend})

            self.window.set_active_page("basin")
            self.window.page_basin.edit_data_file.setText(str(stack))
            self.app.processEvents()

            self.window.controller.on_load_basin_info()
            self.app.processEvents()

            self.assertIn("Loaded: diagnostic_grid.mat", self.window.page_basin.lbl_basin_info.text())
            self.assertIn("Shape: 3 x 3 x 1", self.window.page_basin.lbl_basin_grid_shape.text())
            self.assertIn("Variable: mean", self.window.page_basin.lbl_basin_variable.text())

    def test_leakage_page_can_sync_input_from_preview_and_basin(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stack = self._create_sample_stack(root)

            self.window.page_preview.edit_dataset_source.setText(str(stack))
            self.window.page_basin.edit_data_file.setText(str(stack))
            self.window.page_basin.edit_boundary_file.setText(str(root / "sample_boundary.txt"))
            self.app.processEvents()

            self.window.controller.on_use_preview_stack_for_leakage()
            self.assertEqual(self.window.page_leakage.edit_lrc_input.text(), str(stack))

            self.window.controller.on_use_basin_stack_for_leakage()
            self.assertEqual(self.window.page_leakage.edit_lrc_input.text(), str(stack))

    def test_leakage_load_info_populates_workflow_summary(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stack = self._create_sample_stack(root)
            boundary = self._create_sample_boundary(root)

            self.window.page_leakage.edit_lrc_input.setText(str(stack))
            self.window.page_leakage.edit_regional_boundary.setText(str(boundary))
            self.window.page_leakage.cmb_scope.setCurrentText("regional")
            self.app.processEvents()

            self.window.controller.on_load_leakage_info()
            self.app.processEvents()

            self.assertIn("3 x 3 x 3", self.window.page_leakage.lbl_dataset_shape_value.text())
            self.assertTrue(self.window.page_leakage.lbl_product_type_value.text().strip())
            self.assertTrue(self.window.page_leakage.lbl_scene_value.text())
            self.assertTrue(self.window.page_leakage.lbl_recommendation_value.text())

    def test_leakage_strategy_switch_updates_visible_parameter_groups(self):
        page = self.window.page_leakage
        self.window.set_active_page("leakage")
        self.app.processEvents()

        page.cmb_strategy_family.setCurrentIndex(page.cmb_strategy_family.findData("regional"))
        page.cmb_correction_strategy.setCurrentIndex(page.cmb_correction_strategy.findData("forward_modeling"))
        self.window.controller.on_leakage_strategy_changed()
        self.app.processEvents()
        self.assertFalse(page.params_regional_panel.isHidden())
        self.assertTrue(page.params_coastal_panel.isHidden())
        self.assertTrue(page.params_regularized_panel.isHidden())
        self.assertFalse(page.advanced_section.isHidden())

        page.cmb_strategy_family.setCurrentIndex(page.cmb_strategy_family.findData("global_coastal"))
        page.cmb_correction_strategy.setCurrentIndex(page.cmb_correction_strategy.findData("global_coastal_gaussian"))
        self.window.controller.on_leakage_strategy_changed()
        self.app.processEvents()
        self.assertTrue(page.params_regional_panel.isHidden())
        self.assertFalse(page.params_coastal_panel.isHidden())
        self.assertTrue(page.params_regularized_panel.isHidden())

        page.cmb_strategy_family.setCurrentIndex(page.cmb_strategy_family.findData("global_regularized"))
        page.cmb_correction_strategy.setCurrentIndex(page.cmb_correction_strategy.findData("global_regularized"))
        self.window.controller.on_leakage_strategy_changed()
        self.app.processEvents()
        self.assertTrue(page.params_regional_panel.isHidden())
        self.assertTrue(page.params_coastal_panel.isHidden())
        self.assertFalse(page.params_regularized_panel.isHidden())

        page.cmb_strategy_family.setCurrentIndex(page.cmb_strategy_family.findData("official"))
        page.cmb_correction_strategy.setCurrentIndex(page.cmb_correction_strategy.findData("official_land_scaling"))
        self.window.controller.on_leakage_strategy_changed()
        self.app.processEvents()
        self.assertTrue(page.params_common_panel.isHidden())
        self.assertFalse(page.cmb_official_mode.isHidden())
        self.assertTrue(page.cmb_reference_mode.isHidden())


if __name__ == "__main__":
    unittest.main()
