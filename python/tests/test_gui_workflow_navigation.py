import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "Agg")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from grace_pipeline.ui.qt.global_monitor import configure_global_run_monitor
from grace_pipeline.ui.qt.main_window import MainWindow
from grace_pipeline.ui.qt.i18n import translate_text
from grace_pipeline.ui.qt.preferences import UIPreferences


class GuiWorkflowNavigationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow(load_persisted=False)
        configure_global_run_monitor(self.window)
        self.window._current_screen_metrics = lambda: (1920, 1040, 1.0)
        self.window._layout_bucket = None
        self.window.resize(1600, 980)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()

    def test_run_monitor_and_data_paths_are_not_user_reachable(self):
        self.assertNotIn("monitor", self.window._nav_buttons)
        self.assertNotIn("data_paths", self.window._nav_buttons)

        for key in ("monitor", "data_paths"):
            self.window.set_active_page("dashboard")
            self.app.processEvents()
            self.window.set_active_page(key)
            self.app.processEvents()
            self.assertIs(self.window.stack.currentWidget(), self.window.page_processing)
            self.assertEqual(self.window.breadcrumb.text(), "Filter Processing")
            self.assertTrue(self.window._nav_buttons["processing"].isChecked())

    def test_global_top_bar_is_run_monitor_and_processing_page_owns_run_entry(self):
        self.assertTrue(self.window.page_dashboard.card_commands.isHidden())
        self.assertFalse(self.window.page_dashboard.btn_run_full.isVisible())
        self.assertFalse(self.window.page_dashboard.btn_pause_run.isVisible())
        self.assertFalse(self.window.page_dashboard.btn_stop_run.isVisible())
        self.assertIs(self.window.btn_run, self.window.page_processing.btn_run_filters)
        self.assertIs(self.window.btn_pause, self.window.btn_top_pause)
        self.assertIs(self.window.btn_stop, self.window.btn_top_stop)

        self.window.set_run_active(True, text="RUNNING PIPELINE", indeterminate=False)
        self.window.set_run_progress(25.0, detail="3/12", stage="Monthly filter", subtask="Gaussian")
        self.app.processEvents()
        self.assertTrue(self.window.top_progress_wrap.isVisible())
        self.assertEqual(self.window.top_progress_percent.text(), "25%")
        self.assertIn("ETC", self.window.top_progress_task.text())
        self.assertIn("ETA", self.window.top_progress_task.text())
        self.assertIn("Monthly filter", self.window.page_dashboard.lbl_dashboard_stage.text())
        self.assertIn("Gaussian", self.window.page_dashboard.lbl_dashboard_stage.text())
        self.assertTrue(self.window.btn_top_pause.isEnabled())
        self.assertTrue(self.window.btn_top_stop.isEnabled())

    def test_dashboard_action_buttons_route_to_operational_pages(self):
        for button, page_key, widget in (
            (self.window.page_dashboard.btn_open_data_paths, "processing", self.window.page_processing),
            (self.window.page_dashboard.btn_open_processing, "processing", self.window.page_processing),
            (self.window.page_dashboard.btn_open_preview, "preview", self.window.page_preview),
        ):
            self.window.set_active_page("dashboard")
            self.app.processEvents()
            QTest.mouseClick(button, Qt.LeftButton)
            self.app.processEvents()
            self.assertIs(self.window.stack.currentWidget(), widget)
            self.assertTrue(self.window._nav_buttons[page_key].isChecked())

    def test_console_and_navigation_controls_stay_in_sync(self):
        self.assertEqual(self.window.btn_console.text(), "Console")
        self.assertEqual(self.window.btn_nav_toggle.text(), "☰")

        QTest.mouseClick(self.window.page_dashboard.btn_console_run, Qt.LeftButton)
        self.app.processEvents()
        self.assertTrue(self.window.console_dock.isVisible())
        self.assertTrue(self.window.btn_console.isChecked())

        QTest.mouseClick(self.window.btn_console, Qt.LeftButton)
        self.app.processEvents()
        self.assertFalse(self.window.console_dock.isVisible())
        self.assertFalse(self.window.page_dashboard.btn_console_run.isChecked())

        QTest.mouseClick(self.window.btn_nav_toggle, Qt.LeftButton)
        self.app.processEvents()
        self.assertTrue(self.window._nav_collapsed)
        self.assertTrue(self.window.btn_nav_toggle.isChecked())

    def test_dashboard_validate_paths_uses_backend_controller(self):
        messages = []
        self.window.controller._show_info = lambda title, text: messages.append((title, text))

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ("gfc", "ddk", "aux", "boundary", "mascon", "output"):
                (root / name).mkdir(parents=True, exist_ok=True)
            for name in ("c20.txt", "degree1.txt", "gia.txt", "mascon.nc", "gad.nc", "mgia.nc"):
                (root / name).write_text("placeholder", encoding="utf-8")
            (root / "boundary" / "LargeBasin.shp").write_text("placeholder", encoding="utf-8")

            page = self.window.page_data_paths
            page.edit_gfc_input_dir.setText(str(root / "gfc"))
            page.edit_ddk_data_dir.setText(str(root / "ddk"))
            page.edit_aux_path.setText(str(root / "aux"))
            page.edit_boundary_root.setText(str(root / "boundary"))
            page.edit_boundary_path.setText(str(root / "boundary" / "LargeBasin.shp"))
            page.edit_low_degree_path.setText(str(root / "c20.txt"))
            page.edit_degree1_path.setText(str(root / "degree1.txt"))
            page.edit_gia_path.setText(str(root / "gia.txt"))
            page.edit_mascon_root.setText(str(root / "mascon"))
            page.edit_mascon_reference.setText(str(root / "mascon.nc"))
            page.edit_mascon_gad.setText(str(root / "gad.nc"))
            page.edit_mascon_gia.setText(str(root / "mgia.nc"))
            page.edit_main_output_root.setText(str(root / "output"))
            self.app.processEvents()

            QTest.mouseClick(self.window.page_dashboard.btn_validate_paths, Qt.LeftButton)
            self.app.processEvents()

        self.assertTrue(messages)
        self.assertIn("Validated", messages[-1][1])
        self.assertIn("[PATH] GFC: OK", self.window.console_text.toPlainText())

    def test_chinese_mode_translates_primary_workflow_labels(self):
        self.window.apply_ui_preferences(UIPreferences(theme="light", language="zh"), persist=False)
        self.app.processEvents()

        self.assertEqual(self.window.page_processing.btn_run_filters.text(), "运行滤波")
        self.assertEqual(self.window.page_dashboard.btn_validate_paths.text(), "校验路径")
        self.assertEqual(self.window.page_leakage.btn_run_leakage.text(), "运行校正")
        self.assertEqual(self.window.page_basin.table_basins.horizontalHeaderItem(1).text(), "流域名称")
        self.assertEqual(self.window.page_basin.btn_preview_selected_basin.text(), "预览当前流域")
        self.assertEqual(self.window.page_basin.chk_basin_save_series.text(), "空间提取：面积加权流域时序")
        self.assertEqual(self.window.page_basin.table_basins.rowCount(), 0)
        self.assertEqual(self.window.page_preview.chk_layer_boundaries.text(), "边界叠加层")
        self.assertEqual(self.window.page_preview.chk_layer_rivers.text(), "附加自定义 SHP")
        self.assertEqual(translate_text("2006-03 -> 2014-10 (95 months)", "zh"), "2006-03 -> 2014-10（95 个月）")
        self.assertEqual(
            translate_text("95 GFC files | 2006-03 // 2014-10 | missing=9 (GRACE=9)", "zh"),
            "95 个 GFC 文件 | 2006-03 // 2014-10 | 缺测=9（GRACE=9）",
        )

    def test_operational_controls_update_frontend_state(self):
        page = self.window.page_processing
        self.window.set_active_page("processing")
        self.app.processEvents()
        page.btn_filter_gaussian.setChecked(False)
        page.btn_filter_p4m6.setChecked(False)
        page.btn_filter_gaussian_pnmn.setChecked(False)
        page.btn_filter_ddk.setChecked(False)
        page.btn_filter_hsaf.setChecked(False)
        self.window.controller._sync_processing_filter_button_styles()
        page.btn_filter_ddk.click()
        self.app.processEvents()
        self.assertTrue(page.panel_filter_ddk.isVisible())
        self.assertFalse(page.panel_filter_gaussian.isVisible())

        preview = self.window.page_preview
        self.window.set_active_page("preview")
        self.app.processEvents()
        QTest.mouseClick(preview.btn_toggle_sidebar, Qt.LeftButton)
        self.app.processEvents()
        self.assertFalse(preview.sidebar_panel.isVisible())
        QTest.mouseClick(preview.btn_toggle_status, Qt.LeftButton)
        self.app.processEvents()
        self.assertFalse(preview.card_status.isVisible())

        basin = self.window.page_basin
        self.window.set_active_page("basin")
        self.app.processEvents()
        QTest.mouseClick(basin.btn_mode_global, Qt.LeftButton)
        self.app.processEvents()
        self.assertEqual(basin.cmb_basin_selection_mode.currentText(), "Global Scan")
        self.assertTrue(basin.btn_mode_global.isChecked())
        self.assertFalse(basin.btn_mode_multi.isChecked())

    def test_run_buttons_reach_controller_guards(self):
        warnings = []
        starts = []
        self.window.controller._show_warning = lambda title, text: warnings.append((title, text))
        self.window.controller._run_in_thread = lambda scope, target, status_text: starts.append((scope, status_text))

        QTest.mouseClick(self.window.page_processing.btn_run_filters, Qt.LeftButton)
        self.app.processEvents()
        self.assertEqual(starts[-1][0], "all")

        QTest.mouseClick(self.window.page_basin.btn_run_basin, Qt.LeftButton)
        self.app.processEvents()
        self.assertTrue(warnings)
        self.assertEqual(starts[-1][0], "all")

        self.window.page_basin.edit_data_file.setText(str(ROOT / "not_used.mat"))
        self.window.page_basin.edit_boundary_file.setText(str(ROOT / "not_used_boundary.txt"))
        QTest.mouseClick(self.window.page_basin.btn_run_basin, Qt.LeftButton)
        self.app.processEvents()
        self.assertEqual(starts[-1][0], "basin")

        QTest.mouseClick(self.window.page_leakage.btn_run_leakage, Qt.LeftButton)
        self.app.processEvents()
        self.assertTrue(any(title == "泄漏校正" for title, _ in warnings))

    def test_basin_boundary_reader_populates_selectable_features(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            boundary = root / "sample_boundary.txt"
            boundary.write_text(
                "\n".join(["-10 -10", "10 -10", "10 10", "-10 10", "-10 -10"]),
                encoding="utf-8",
            )

            page = self.window.page_basin
            page.edit_boundary_file.setText(str(boundary))
            self.window.controller.on_load_basin_boundary_info()
            self.app.processEvents()

            self.assertEqual(page.table_basins.rowCount(), 1)
            self.assertEqual(page.table_basins.item(0, 1).text(), "poly_1")
            self.assertEqual(page.table_basins.currentRow(), 0)
            self.assertIn("1 feature", page.lbl_boundary_info.text())

    def test_basin_boundary_directory_resolves_to_supported_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            boundary_dir = root / "boundary_cache"
            boundary_dir.mkdir()
            boundary = boundary_dir / "basin.txt"
            boundary.write_text(
                "\n".join(["-10 -10", "10 -10", "10 10", "-10 10", "-10 -10"]),
                encoding="utf-8",
            )

            page = self.window.page_basin
            page.edit_boundary_file.setText(str(boundary_dir))
            self.window.controller.on_load_basin_boundary_info()
            self.app.processEvents()

            self.assertEqual(page.edit_boundary_file.text(), str(boundary))
            self.assertIn("1 feature", page.lbl_boundary_info.text())


if __name__ == "__main__":
    unittest.main()
