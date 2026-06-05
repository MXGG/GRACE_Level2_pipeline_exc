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

from grace_pipeline.ui.qt.main_window import MainWindow
from grace_pipeline.ui.qt.i18n import translate_text
from grace_pipeline.ui.qt.preferences import UIPreferences


class GuiWorkflowNavigationTest(unittest.TestCase):
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

    def tearDown(self):
        self.window.close()
        self.app.processEvents()

    def test_run_monitor_page_is_available_from_navigation(self):
        self.assertIn("monitor", self.window._nav_buttons)

        self.window.set_active_page("monitor")
        self.app.processEvents()
        self.assertIs(self.window.stack.currentWidget(), self.window.page_monitor)
        self.assertEqual(self.window.breadcrumb.text(), "Run Monitor")
        self.assertTrue(self.window._nav_buttons["monitor"].isChecked())

    def test_dashboard_action_buttons_route_to_operational_pages(self):
        for button, page_key, widget in (
            (self.window.page_dashboard.btn_open_data_paths, "data_paths", self.window.page_data_paths),
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

        self.assertEqual(self.window.page_dashboard.btn_run_full.text(), "\u8fd0\u884c\u6ee4\u6ce2")
        self.assertEqual(self.window.page_dashboard.btn_validate_paths.text(), "\u6821\u9a8c\u8def\u5f84")
        self.assertEqual(self.window.page_leakage.btn_run_leakage.text(), "\u8fd0\u884c\u6821\u6b63")
        self.assertEqual(self.window.page_basin.table_basins.horizontalHeaderItem(1).text(), "\u6d41\u57df\u540d\u79f0")
        self.assertEqual(self.window.page_basin.btn_preview_selected_basin.text(), "\u9884\u89c8\u5f53\u524d\u6d41\u57df")
        self.assertEqual(self.window.page_basin.chk_basin_save_series.text(), "\u7a7a\u95f4\u63d0\u53d6\uff1a\u9762\u79ef\u52a0\u6743\u6d41\u57df\u65f6\u5e8f")
        self.assertEqual(self.window.page_basin.table_basins.rowCount(), 0)
        self.assertEqual(self.window.page_preview.chk_layer_boundaries.text(), "\u8fb9\u754c\u53e0\u52a0\u5c42")
        self.assertEqual(self.window.page_preview.chk_layer_rivers.text(), "\u9644\u52a0\u81ea\u5b9a\u4e49 SHP")
        self.assertEqual(translate_text("2006-03 -> 2014-10 (95 months)", "zh"), "2006-03 -> 2014-10\uff0895 \u4e2a\u6708\uff09")
        self.assertEqual(
            translate_text("95 GFC files | 2006-03 // 2014-10 | missing=9 (GRACE=9)", "zh"),
            "95 \u4e2a GFC \u6587\u4ef6 | 2006-03 // 2014-10 | \u7f3a\u6d4b=9\uff08GRACE=9\uff09",
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

        QTest.mouseClick(self.window.page_dashboard.btn_run_full, Qt.LeftButton)
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
        self.assertTrue(any(title == "\u6cc4\u6f0f\u6821\u6b63" for title, _ in warnings))

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
