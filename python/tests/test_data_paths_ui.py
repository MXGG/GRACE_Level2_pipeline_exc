import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "Agg")

from PySide6.QtCore import QPoint, Qt, QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
os.environ["GRACE_L2_HOME"] = str(ROOT)
os.environ["GRACE_L2_DATA"] = str(ROOT / "data")
os.environ["GRACE_L2_OUTPUT"] = str(ROOT / "outputs")
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from grace_pipeline.infra.config import Config
from grace_pipeline.services.gfc_download import DownloadResult
from grace_pipeline.ui.qt.main_window import MainWindow
from grace_pipeline.ui.qt.global_monitor import configure_global_run_monitor
from grace_pipeline.ui.qt.path_defaults import DEFAULT_DATA_PATHS
from grace_pipeline.ui.qt.preferences import UIPreferences
import grace_pipeline.ui.qt.controller as qt_controller


class DataPathsUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow(load_persisted=False)
        self.window._current_screen_metrics = lambda: (1920, 1040, 1.0)
        self.window._layout_bucket = None
        self.window.resize(1600, 980)
        self.window.show()
        self.window.set_active_page("data_paths")
        self.window._apply_responsive_layout(force=True)
        self.page = self.window.page_data_paths
        self.window.controller._show_info = lambda *_args, **_kwargs: None
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()

    def _native(self, path: Path) -> str:
        return os.path.normpath(str(path))

    def test_page_initializes_with_real_project_paths(self):
        self.assertNotIn("data_paths", self.window._nav_buttons)
        self.assertEqual(self.window.breadcrumb.text(), "Data Paths")

        expected = {
            "gfc": self._native(DEFAULT_DATA_PATHS["GFC"]),
            "ddk": self._native(DEFAULT_DATA_PATHS["DDK"]),
            "output": self._native(DEFAULT_DATA_PATHS["OUTPUT"]),
            "logs": self._native(DEFAULT_DATA_PATHS["LOGS"]),
            "aux": self._native(DEFAULT_DATA_PATHS["AUX"]),
            "boundary_root": self._native(DEFAULT_DATA_PATHS["BOUNDARY"]),
            "boundary": self._native(DEFAULT_DATA_PATHS["BOUNDARY_SHP"]),
            "low_degree": self._native(DEFAULT_DATA_PATHS["LOW_DEGREE_C20"]),
            "degree1": self._native(DEFAULT_DATA_PATHS["LOW_DEGREE_DEGREE1"]),
            "gia": self._native(DEFAULT_DATA_PATHS["GIA"]),
            "mascon_root": self._native(DEFAULT_DATA_PATHS["MASCON_DIR"]),
            "mascon_reference": self._native(DEFAULT_DATA_PATHS["MASCON_REFERENCE_FILE"]),
            "mascon_gad": self._native(DEFAULT_DATA_PATHS["MASCON_GAD"]),
            "mascon_gia": self._native(DEFAULT_DATA_PATHS["MASCON_GIA"]),
        }

        self.assertEqual(self.page.edit_gfc_input_dir.text(), expected["gfc"])
        self.assertEqual(self.page.edit_ddk_data_dir.text(), expected["ddk"])
        self.assertEqual(self.page.edit_main_output_root.text(), expected["output"])
        self.assertEqual(self.page.edit_logs_dir.text(), expected["logs"])
        self.assertEqual(self.page.edit_aux_path.text(), expected["aux"])
        self.assertEqual(self.page.edit_boundary_root.text(), expected["boundary_root"])
        self.assertEqual(self.page.edit_boundary_path.text(), expected["boundary"])
        self.assertEqual(self.page.edit_low_degree_path.text(), expected["low_degree"])
        self.assertEqual(self.page.edit_degree1_path.text(), expected["degree1"])
        self.assertEqual(self.page.edit_gia_path.text(), expected["gia"])
        self.assertEqual(self.page.edit_mascon_root.text(), expected["mascon_root"])
        self.assertEqual(self.page.edit_mascon_reference.text(), expected["mascon_reference"])
        self.assertEqual(self.page.edit_mascon_gad.text(), expected["mascon_gad"])
        self.assertEqual(self.page.edit_mascon_gia.text(), expected["mascon_gia"])
        self.assertFalse(self.page.reference_roots_panel.isVisible())
        self.assertEqual(self.page.btn_toggle_reference_roots.text(), "Show Root Paths")
        self.assertRegex(self.page.lbl_gfc_detected_range.text(), r"\d{4}-\d{2} -> \d{4}-\d{2}")

        if os.name == "nt":
            for value in expected.values():
                self.assertNotIn("/", value)

        self.assertEqual(self.page.badge_boundary_root.text(), "OK")
        self.assertEqual(self.page.badge_gfc_input.text(), "Verified")
        self.assertFalse(self.page.row_ddk_data_dir.isVisible())
        self.assertEqual(self.page.badge_ddk_data.text(), "Built-in")
        self.assertEqual(self.page.badge_aux_path.text(), "OK")
        self.assertEqual(self.page.badge_boundary_path.text(), "OK")
        self.assertEqual(self.page.badge_degree1.text(), "OK")
        self.assertEqual(self.page.badge_mascon_root.text(), "OK")
        self.assertEqual(self.page.badge_mascon_gad.text(), "OK")
        self.assertEqual(self.page.badge_mascon_gia.text(), "OK")
        self.assertEqual(self.page.edit_gfc_input_dir.cursorPosition(), 0)
        self.assertEqual(self.page.edit_ddk_data_dir.cursorPosition(), 0)
        self.assertEqual(self.page.edit_main_output_root.cursorPosition(), 0)
        self.assertEqual(
            len([btn for btn in self.page.findChildren(type(self.page.btn_validate_paths)) if btn.text() == "Validate All Paths"]),
            1,
        )

    def test_push_config_to_ui_repairs_stale_paths(self):
        stale = copy.deepcopy(getattr(self.window.controller.host.cfg, "_raw", {}))
        stale.setdefault("path", {})
        stale.setdefault("filter", {}).setdefault("ddk", {})
        stale.setdefault("reference", {}).setdefault("mascon_undo", {})
        stale.setdefault("inversion", {}).setdefault("lowdeg", {}).setdefault("files", {})

        stale["path"]["DDK"] = str(ROOT / "data" / "Aux" / "DDK")
        stale["filter"]["ddk"]["data_dir"] = str(ROOT / "data" / "Aux" / "DDK")
        stale["inversion"]["lowdeg"]["files"]["C20"] = str(ROOT / "data" / "GRACE" / "LowDegree" / "TN-14_C20_SLR.txt")
        stale["reference"]["mascon_undo"]["gad_file"] = "CSR_GRACE_GRACE-FO_RL0603_Mascons_GAD-component.nc"
        stale["reference"]["mascon_undo"]["gia_file"] = "CSR_GRACE_GRACE-FO_RL0603_Mascons_GIA-component.nc"

        self.window.controller.push_config_to_ui(Config(stale))
        self.app.processEvents()

        self.assertEqual(self.page.edit_ddk_data_dir.text(), self._native(DEFAULT_DATA_PATHS["DDK"]))
        self.assertEqual(self.page.edit_low_degree_path.text(), self._native(DEFAULT_DATA_PATHS["LOW_DEGREE_C20"]))
        self.assertEqual(self.page.edit_boundary_path.text(), self._native(DEFAULT_DATA_PATHS["BOUNDARY_SHP"]))
        self.assertEqual(self.page.edit_degree1_path.text(), self._native(DEFAULT_DATA_PATHS["LOW_DEGREE_DEGREE1"]))
        self.assertEqual(self.page.edit_mascon_gad.text(), self._native(DEFAULT_DATA_PATHS["MASCON_GAD"]))
        self.assertEqual(self.page.edit_mascon_gia.text(), self._native(DEFAULT_DATA_PATHS["MASCON_GIA"]))

    def test_manual_entries_are_normalized_to_native_paths(self):
        self.page.edit_ddk_data_dir.setText(str(DEFAULT_DATA_PATHS["DDK"]).replace("\\", "/"))
        self.page.edit_ddk_data_dir.editingFinished.emit()
        self.app.processEvents()
        self.assertEqual(self.page.edit_ddk_data_dir.text(), self._native(DEFAULT_DATA_PATHS["DDK"]))
        self.assertEqual(self.page.badge_ddk_data.text(), "Built-in")
        self.assertEqual(self.page.edit_ddk_data_dir.cursorPosition(), 0)

        self.page.edit_mascon_gad.setText("CSR_GRACE_GRACE-FO_RL0603_Mascons_GAD-component.nc")
        self.page.edit_mascon_gad.editingFinished.emit()
        self.app.processEvents()
        self.assertEqual(self.page.edit_mascon_gad.text(), self._native(DEFAULT_DATA_PATHS["MASCON_GAD"]))

        self.page.edit_boundary_root.setText(str(DEFAULT_DATA_PATHS["BOUNDARY"]).replace("\\", "/"))
        self.page.edit_boundary_root.editingFinished.emit()
        self.app.processEvents()
        self.assertEqual(self.page.edit_boundary_path.text(), self._native(DEFAULT_DATA_PATHS["BOUNDARY_SHP"]))

        self.page.edit_main_output_root.setText(str(DEFAULT_DATA_PATHS["OUTPUT"]).replace("\\", "/"))
        self.page.edit_main_output_root.editingFinished.emit()
        self.app.processEvents()
        self.assertEqual(self.page.edit_main_output_root.text(), self._native(DEFAULT_DATA_PATHS["OUTPUT"]))
        self.assertEqual(self.page.edit_logs_dir.text(), self._native(DEFAULT_DATA_PATHS["LOGS"]))
        self.assertEqual(self.page.edit_main_output_root.cursorPosition(), 0)

        self.page.btn_toggle_reference_roots.click()
        self.app.processEvents()
        self.assertTrue(self.page.reference_roots_panel.isVisible())
        self.assertEqual(self.page.btn_toggle_reference_roots.text(), "Hide Root Paths")

    def test_console_toggle_preserves_main_content_width(self):
        nav_width = self.window.nav_rail.width()
        page_width_before = self.page.card_reference_paths.width()

        QTest.mouseClick(self.window.btn_console, Qt.LeftButton)
        self.app.processEvents()

        self.assertTrue(self.window.console_dock.isVisible())
        self.assertTrue(self.window.btn_console.isChecked())
        self.assertEqual(self.window.nav_rail.width(), nav_width)
        self.assertGreater(self.window.content_splitter.sizes()[1], 0)
        self.assertGreater(self.page.card_reference_paths.width(), 900)
        self.assertLessEqual(abs(self.page.card_reference_paths.width() - page_width_before), 16)

        QTest.mouseClick(self.window.btn_console, Qt.LeftButton)
        self.app.processEvents()
        self.assertFalse(self.window.console_dock.isVisible())

    def test_reference_path_inputs_share_the_same_left_edge(self):
        if not self.page.reference_roots_panel.isVisible():
            self.page.btn_toggle_reference_roots.click()
        self.app.processEvents()

        widgets = [
            self.page.edit_boundary_path,
            self.page.edit_low_degree_path,
            self.page.edit_degree1_path,
            self.page.edit_gia_path,
            self.page.edit_mascon_reference,
        ]
        x_positions = [widget.mapTo(self.window, QPoint(0, 0)).x() for widget in widgets]
        self.assertEqual(len(set(x_positions)), 1)

    def test_run_monitor_page_is_available_from_navigation(self):
        configure_global_run_monitor(self.window)
        self.assertNotIn("monitor", self.window._nav_buttons)
        self.assertTrue(hasattr(self.window, "btn_top_pause"))
        self.assertTrue(hasattr(self.window, "btn_top_stop"))
        self.assertTrue(hasattr(self.window, "top_progress_bar"))
        self.app.processEvents()
        self.assertFalse(self.window.btn_top_pause.isEnabled())
        self.assertFalse(self.window.btn_top_stop.isEnabled())
        self.assertEqual(self.window.top_progress_label.text(), "Idle")
        self.assertNotIn("Processing tile 42 of 180", self.window.page_monitor.text_live_logs.toPlainText())

    def test_dashboard_preview_only_shows_output_structure(self):
        self.window.controller.on_log("[HSAF][stack] 32/163 slices processed...", "stdout")
        self.window.controller.on_progress("all", 20.0, "32/163::HSAF stack 32/163")
        self.app.processEvents()

        self.assertFalse(hasattr(self.window.page_dashboard, "text_run_preview"))
        self.assertIn("[HSAF][stack] 32/163 slices processed...", self.window.console_text.toPlainText())
        self.assertEqual(self.window.page_dashboard.lbl_dashboard_counts.text(), "32 / 163")
        self.assertEqual(self.window.page_dashboard.lbl_dashboard_stage.text(), "HSAF stack 32/163")
        self.assertIn("Output Root:", self.window.page_dashboard.lbl_preview_root.text())
        self.assertIn("Stacks:", self.window.page_dashboard.lbl_preview_stacks.text())
        self.assertIn("Logs:", self.window.page_dashboard.lbl_preview_logs.text())

    def test_pipeline_progress_prefers_stage_counts_over_internal_work_units(self):
        original_run_pipeline = qt_controller.run_pipeline
        original_run_in_thread = self.window.controller._run_in_thread

        def fake_run_pipeline(_cfg, pause_event=None, stop_event=None, progress_cb=None):
            self.assertIsNotNone(progress_cb)
            progress_cb(12, 496, "Running monthly loop", "12/163")

        def inline_run(_scope, target, status_text):
            self.window.set_top_status(status_text, "warning")
            self.window.set_run_active(True, text="Preparing...", indeterminate=True)
            target()

        qt_controller.run_pipeline = fake_run_pipeline
        self.window.controller._run_in_thread = inline_run
        self.addCleanup(setattr, qt_controller, "run_pipeline", original_run_pipeline)
        self.addCleanup(setattr, self.window.controller, "_run_in_thread", original_run_in_thread)

        self.window.controller.on_run_pipeline()
        self.app.processEvents()

        self.assertEqual(self.window.top_progress_detail.text(), "12 / 163")
        self.assertEqual(self.window.page_dashboard.lbl_dashboard_counts.text(), "12 / 163")
        self.assertEqual(self.window.top_progress_percent.text(), "7%")

    def test_top_progress_bar_keeps_visible_width_with_long_stage_text(self):
        self.window.resize(1280, 900)
        self.window.set_run_active(True, text="Preparing...", indeterminate=False)
        self.window.set_run_progress(
            63.0,
            detail="103/163",
            stage="Running monthly loop with a deliberately long stage label for width checks",
        )
        self.app.processEvents()

        self.assertTrue(self.window.top_progress_wrap.isVisible())
        self.assertGreaterEqual(self.window.top_progress_bar.width(), 220)
        self.assertEqual(self.window.top_progress_detail.text(), "103 / 163")
        self.assertEqual(self.window.top_progress_percent.text(), "63%")
        self.assertIn("Running monthly loop", self.window.top_progress_label.toolTip() or self.window.top_progress_label.text())

    def test_run_button_shows_immediate_feedback(self):
        original_run_in_thread = self.window.controller._run_in_thread

        def fake_run_in_thread(_scope, _target, status_text):
            self.window.set_top_status(status_text, "warning")
            self.window.set_run_active(True, text="Preparing...", indeterminate=True)
            self.window.set_console_visible(True)
            self.window.page_dashboard.lbl_dashboard_status.setText(status_text)
            self.window.page_dashboard.lbl_dashboard_stage.setText("Preparing execution environment and validating configuration.")
            self.window.page_dashboard.lbl_active_run_name.setText(status_text)
            self.window.page_dashboard.lbl_active_task.setText("Preparing execution environment and validating configuration.")
            self.window.page_monitor.lbl_pipeline_status.setText(status_text)
            self.window.set_run_progress(25.0, detail="1/4", stage="Running monthly loop")

        self.window.controller._run_in_thread = fake_run_in_thread
        self.addCleanup(setattr, self.window.controller, "_run_in_thread", original_run_in_thread)

        self.window.set_active_page("dashboard")
        self.app.processEvents()
        QTest.mouseClick(self.window.btn_run, Qt.LeftButton)
        QTest.qWait(40)
        self.app.processEvents()

        self.assertTrue(self.window.top_progress_wrap.isVisible())
        self.assertTrue(self.window.console_dock.isVisible())
        self.assertFalse(self.window.btn_run.isEnabled())
        self.assertTrue(self.window.btn_pause.isEnabled())
        self.assertTrue(self.window.btn_stop.isEnabled())
        self.assertEqual(self.window.pipeline_status.text(), "RUNNING PIPELINE")
        self.assertEqual(self.window.top_progress_label.full_text(), "Running monthly loop")
        self.assertEqual(self.window.top_progress_detail.text(), "1 / 4")
        self.assertEqual(self.window.top_progress_percent.text(), "25%")

    def test_card_headers_and_processing_columns_are_balanced(self):
        self.assertEqual(
            self.page.card_input_dirs.layout.itemAt(0).widget().height(),
            self.page.card_output_dirs.layout.itemAt(0).widget().height(),
        )

        self.window.set_active_page("processing")
        self.window._apply_responsive_layout(force=True)
        self.app.processEvents()
        page_processing = self.window.page_processing

        cards = (
            page_processing.card_time_range,
            page_processing.card_filters,
            page_processing.card_inversion,
            page_processing.card_grid_settings,
        )
        header_heights = [card.layout.itemAt(0).widget().height() for card in cards]
        self.assertEqual(len(set(header_heights)), 1)
        self.assertFalse(hasattr(page_processing, "edit_step_days"))
        self.assertLessEqual(abs(page_processing.card_time_range.width() - page_processing.card_filters.width()), 180)
        self.assertLessEqual(abs(page_processing.card_inversion.width() - page_processing.card_grid_settings.width()), 180)

    def test_processing_setup_supports_detected_time_override_and_corrections(self):
        self.window.set_active_page("processing")
        self.app.processEvents()
        page = self.window.page_processing

        self.assertTrue(page.edit_start_date.isReadOnly())
        self.assertTrue(page.edit_end_date.isReadOnly())
        self.assertRegex(page.lbl_detected_time_range.text(), r"\d{4}-\d{2} -> \d{4}-\d{2}")

        page.chk_manual_time_override.setChecked(True)
        self.app.processEvents()
        self.assertFalse(page.edit_start_date.isReadOnly())
        self.assertFalse(page.edit_end_date.isReadOnly())

        page.edit_start_date.setText("2005-01-01")
        page.edit_end_date.setText("2010-12-01")
        page.chk_remove_mean.setChecked(True)
        self.window.controller._set_combo_value(page.cmb_anomaly_baseline, "input_full")
        page.chk_lowdeg_enable.setChecked(True)
        page.chk_replace_degree1.setChecked(False)
        page.chk_replace_c20.setChecked(True)
        page.chk_replace_c30.setChecked(False)
        page.chk_apply_gia.setChecked(True)
        cfg_dict = self.window.controller.collect_config_dict({})

        self.assertFalse(cfg_dict["time"]["auto_detect_gfc"])
        self.assertEqual(cfg_dict["time"]["start_ym"], "2005-01")
        self.assertEqual(cfg_dict["time"]["end_ym"], "2010-12")
        self.assertEqual(cfg_dict["inversion"]["mean_baseline_mode"], "input_full")
        self.assertEqual(cfg_dict["inversion"]["mean_start_ym"], "")
        self.assertEqual(cfg_dict["inversion"]["mean_end_ym"], "")
        self.assertFalse(cfg_dict["inversion"]["lowdeg"]["replace_degree1"])
        self.assertTrue(cfg_dict["inversion"]["lowdeg"]["replace_C20"])
        self.assertFalse(cfg_dict["inversion"]["lowdeg"]["replace_C30"])
        self.assertTrue(cfg_dict["inversion"]["gia"]["enable"])

        page.chk_manual_time_override.setChecked(False)
        self.window.controller._set_combo_value(page.cmb_anomaly_baseline, "standard_2004_2009")
        cfg_dict = self.window.controller.collect_config_dict({})
        self.assertTrue(cfg_dict["time"]["auto_detect_gfc"])
        self.assertEqual(cfg_dict["time"]["start_ym"], page.edit_start_date.text()[:7])
        self.assertEqual(cfg_dict["time"]["end_ym"], page.edit_end_date.text()[:7])
        self.assertEqual(cfg_dict["inversion"]["mean_baseline_mode"], "standard_2004_2009")
        self.assertEqual(cfg_dict["inversion"]["mean_start_ym"], "2004-01")
        self.assertEqual(cfg_dict["inversion"]["mean_end_ym"], "2009-12")

        self.window.controller._set_combo_value(page.cmb_anomaly_baseline, "custom")
        page.edit_mean_start_ym.setText("1999-01")
        page.edit_mean_end_ym.setText("2099-12")
        cfg_dict = self.window.controller.collect_config_dict({})
        self.assertEqual(cfg_dict["inversion"]["mean_baseline_mode"], "custom")
        self.assertEqual(cfg_dict["inversion"]["mean_start_ym"], cfg_dict["time"]["start_ym"])
        self.assertEqual(cfg_dict["inversion"]["mean_end_ym"], cfg_dict["time"]["end_ym"])

    def test_auto_low_degree_selects_tn13_from_detected_gsm_center(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gfc_dir = root / "GSM"
            low_dir = root / "LowDegree"
            gfc_dir.mkdir()
            low_dir.mkdir()
            (gfc_dir / "GSM-2_2020001-2020031_GRFO_JPLEM_BA01_0603.gfc").write_text(
                "modelname GSM-2_2020001-2020031_GRFO_JPLEM_BA01_0603\nend_of_head\n",
                encoding="utf-8",
            )
            c20 = low_dir / "TN-14_C30_C20_GSFC_SLR.txt"
            deg_jpl = low_dir / "TN-13_GEOC_JPL_RL0603.txt"
            c20.write_text("# c20\n", encoding="utf-8")
            deg_jpl.write_text("# jpl degree1\n", encoding="utf-8")

            self.page.edit_gfc_input_dir.setText(str(gfc_dir))
            self.page.edit_download_dir.setText(str(gfc_dir))
            self.page.edit_low_degree_path.setText(str(c20))
            self.page.edit_degree1_path.setText(str(low_dir / "placeholder.txt"))
            self.window.controller.on_auto_low_degree_from_gsm()
            self.app.processEvents()

            self.assertEqual(self.page.cmb_gfc_center.currentText(), "JPL")
            self.assertEqual(self.page.edit_low_degree_path.text(), self._native(c20))
            self.assertEqual(self.page.edit_degree1_path.text(), self._native(deg_jpl))

    def test_collect_config_writes_center_specific_tn13_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            low_dir = Path(tmp)
            paths = {
                "CSR": low_dir / "TN-13_GEOC_CSR_RL0603.txt",
                "JPL": low_dir / "TN-13_GEOC_JPL_RL0603.txt",
                "GFZ": low_dir / "TN-13_GEOC_GFZ_RL0603.txt",
            }
            c20 = low_dir / "TN-14_C30_C20_GSFC_SLR.txt"
            c20.write_text("# c20\n", encoding="utf-8")
            for path in paths.values():
                path.write_text("# degree1\n", encoding="utf-8")

            self.page.edit_low_degree_path.setText(str(c20))
            self.page.edit_degree1_path.setText(str(paths["JPL"]))
            self.page.cmb_gfc_center.setCurrentText("JPL")
            cfg_dict = self.window.controller.collect_config_dict({})
            files = cfg_dict["inversion"]["lowdeg"]["files"]

            self.assertEqual(files["C20"], self._native(c20))
            self.assertEqual(files["DEGREE1"], self._native(paths["JPL"]))
            self.assertEqual(files["DEGREE1_CSR"], self._native(paths["CSR"]))
            self.assertEqual(files["DEGREE1_JPL"], self._native(paths["JPL"]))
            self.assertEqual(files["DEGREE1_GFZ"], self._native(paths["GFZ"]))

    def test_download_button_uses_configured_range_and_updates_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gfc_dir = root / "GSM"
            low_dir = root / "LowDegree"
            gfc_dir.mkdir()
            low_dir.mkdir()
            c20 = low_dir / "TN-14_C30_C20_GSFC_SLR.txt"
            deg_csr = low_dir / "TN-13_GEOC_CSR_RL0603.txt"
            c20.write_text("# c20\n", encoding="utf-8")
            deg_csr.write_text("# csr degree1\n", encoding="utf-8")
            gfc_file = gfc_dir / "GSM-2_2024001-2024031_GRFO_UTCSR_BA01_0603.gfc"

            calls = []
            original_download = qt_controller.download_gfc_range
            original_run = self.window.controller._run_in_thread
            original_has_auth = qt_controller.has_earthdata_credentials

            def fake_download_gfc_range(**kwargs):
                calls.append(kwargs)
                gfc_file.write_text("modelname GSM-2_2024001-2024031_GRFO_UTCSR_BA01_0603\n", encoding="utf-8")
                return DownloadResult(
                    files=(gfc_file,),
                    skipped=(),
                    center="CSR",
                    low_degree_files={"C20": c20, "DEGREE1_CSR": deg_csr},
                )

            def inline_run(_scope, target, _status):
                target()

            qt_controller.download_gfc_range = fake_download_gfc_range
            self.window.controller._run_in_thread = inline_run
            qt_controller.has_earthdata_credentials = lambda: True
            self.addCleanup(setattr, qt_controller, "download_gfc_range", original_download)
            self.addCleanup(setattr, self.window.controller, "_run_in_thread", original_run)
            self.addCleanup(setattr, qt_controller, "has_earthdata_credentials", original_has_auth)

            self.page.edit_gfc_input_dir.setText(str(gfc_dir))
            self.page.edit_download_dir.setText(str(gfc_dir))
            self.page.edit_low_degree_path.setText(str(c20))
            self.page.cmb_gfc_center.setCurrentText("CSR")
            self.page.edit_download_start_ym.setText("2024-01")
            self.page.edit_download_end_ym.setText("2024-01")
            self.window.set_active_page("processing")
            self.window.page_processing.chk_manual_time_override.setChecked(True)
            self.window.page_processing.edit_start_date.setText("2024-01-01")
            self.window.page_processing.edit_end_date.setText("2024-01-01")
            self.window.set_active_page("data_paths")
            self.window.controller.on_download_gfc_range()
            self.app.processEvents()

            self.assertEqual(calls[0]["gfc_dir"], self._native(gfc_dir))
            self.assertEqual(calls[0]["start_ym"], "2024-01")
            self.assertEqual(calls[0]["end_ym"], "2024-01")
            self.assertEqual(calls[0]["center"], "CSR")
            self.assertEqual(calls[0]["low_degree_dir"], low_dir)
            self.assertEqual(self.page.edit_degree1_path.text(), self._native(deg_csr))
            self.assertIn("新增 1 个", self.page.lbl_gfc_download_status.text())

    def test_mascon_download_sources_include_gsfc_and_resolution(self):
        self.page.cmb_download_product.setCurrentText("Mascon NC")
        self.window.controller._sync_download_source_controls(update_options=True)
        self.app.processEvents()

        centers = [self.page.cmb_gfc_center.itemText(i) for i in range(self.page.cmb_gfc_center.count())]
        self.assertEqual(centers, ["CSR", "JPL", "GSFC"])
        self.assertTrue(self.page.cmb_mascon_resolution.isVisible())
        self.assertEqual(
            [self.page.cmb_mascon_resolution.itemText(i) for i in range(self.page.cmb_mascon_resolution.count())],
            ["0.25°", "0.5°", "1°"],
        )

        self.page.cmb_download_product.setCurrentText("GSM 文件")
        self.window.controller._sync_download_source_controls(update_options=True)
        centers = [self.page.cmb_gfc_center.itemText(i) for i in range(self.page.cmb_gfc_center.count())]
        self.assertEqual(centers, ["自动", "CSR", "JPL", "GFZ", "HUST", "ITSG"])
        self.assertFalse(self.page.cmb_mascon_resolution.isVisible())

    def test_mascon_download_passes_selected_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "mascon"
            out_dir.mkdir()
            mascon_file = out_dir / "GSFC.glb.200204_202511_RL06v2.0_OBP-ICE6GD_HALFDEGREE.nc"
            calls = []
            original_download = qt_controller.download_mascon_nc
            original_run = self.window.controller._run_in_thread

            def fake_download_mascon_nc(**kwargs):
                calls.append(kwargs)
                mascon_file.write_text("nc\n", encoding="utf-8")
                return DownloadResult(
                    files=(mascon_file,),
                    skipped=(),
                    center="GSFC",
                    low_degree_files={},
                    product_type="MASCON_NC",
                )

            def inline_run(_scope, target, _status):
                target()

            qt_controller.download_mascon_nc = fake_download_mascon_nc
            self.window.controller._run_in_thread = inline_run
            self.addCleanup(setattr, qt_controller, "download_mascon_nc", original_download)
            self.addCleanup(setattr, self.window.controller, "_run_in_thread", original_run)

            self.page.cmb_download_product.setCurrentText("Mascon NC")
            self.window.controller._sync_download_source_controls(update_options=True)
            self.page.cmb_gfc_center.setCurrentText("GSFC")
            self.page.cmb_mascon_resolution.setCurrentText("0.5°")
            self.page.edit_download_dir.setText(str(out_dir))
            self.page.edit_download_start_ym.setText("2024-01")
            self.page.edit_download_end_ym.setText("2024-01")
            self.window.controller.on_download_gfc_range()
            self.app.processEvents()

            self.assertEqual(calls[0]["source"], "GSFC")
            self.assertEqual(calls[0]["resolution"], "0.5")
            self.assertEqual(self.page.edit_mascon_reference.text(), self._native(mascon_file))

    def test_download_source_button_opens_selected_product_page(self):
        opened = []
        original_open = qt_controller.webbrowser.open
        qt_controller.webbrowser.open = lambda url: opened.append(url) or True
        self.addCleanup(setattr, qt_controller.webbrowser, "open", original_open)

        self.page.cmb_download_product.setCurrentText("Mascon NC")
        self.window.controller._sync_download_source_controls(update_options=True)
        self.page.cmb_gfc_center.setCurrentText("GSFC")
        self.window.controller.on_open_download_site()

        self.assertTrue(opened)
        self.assertIn("gsfc", opened[-1].lower())

        self.page.cmb_download_product.setCurrentText("GSM 文件")
        self.window.controller._sync_download_source_controls(update_options=True)
        self.page.cmb_gfc_center.setCurrentText("HUST")
        self.window.controller.on_open_download_site()
        self.assertIn("icgem", opened[-1].lower())

    def test_ddk_filter_requires_kernel_files_when_enabled(self):
        configure_global_run_monitor(self.window)
        with tempfile.TemporaryDirectory() as tmp:
            warnings = []
            self.window.controller._show_warning = lambda title, text: warnings.append((title, text))
            self.page.edit_ddk_data_dir.setText(str(Path(tmp) / "empty_ddk"))
            Path(self.page.edit_ddk_data_dir.text()).mkdir()
            self.window.page_processing.btn_filter_ddk.setChecked(True)
            self.window.controller.on_run_pipeline()

        self.assertTrue(warnings)
        self.assertIn("Wbd_*", warnings[-1][1])

    def test_console_ignores_page_navigation_noise(self):
        self.window.console_text.clear()
        self.window.set_active_page("processing")
        self.window.set_active_page("dashboard")
        self.app.processEvents()
        self.assertNotIn("[MOCK UI]", self.window.console_text.toPlainText())

    def test_dashboard_run_click_starts_pipeline_only_once(self):
        starts: list[tuple[str, str, str]] = []
        warnings: list[tuple[str, str]] = []
        original_run_in_thread = self.window.controller._run_in_thread
        original_show_warning = self.window.controller._show_warning

        def fake_run_in_thread(scope, target, status_text):
            starts.append((scope, target, status_text))
            self.window._active_scope = scope
            self.window.set_run_active(True, text="Preparing...", indeterminate=True)

        self.window.controller._run_in_thread = fake_run_in_thread
        self.window.controller._show_warning = lambda title, message: warnings.append((title, message))
        self.addCleanup(setattr, self.window.controller, "_run_in_thread", original_run_in_thread)
        self.addCleanup(setattr, self.window.controller, "_show_warning", original_show_warning)

        self.window.set_active_page("dashboard")
        self.app.processEvents()
        QTest.mouseClick(self.window.page_dashboard.btn_run_full, Qt.LeftButton)
        QTest.qWait(40)
        self.app.processEvents()

        self.assertEqual(len(starts), 1)
        self.assertEqual(starts[0][0], "all")
        self.assertEqual(warnings, [])

    def test_language_switch_translates_shell_labels(self):
        self.window.apply_ui_preferences(UIPreferences(theme="light", language="zh"), persist=False)
        self.app.processEvents()

        self.assertNotIn("data_paths", self.window._nav_buttons)
        self.assertNotEqual(self.window.breadcrumb.text(), "Data Paths")
        self.assertNotEqual(self.window.btn_settings.text(), "Settings")
        self.assertNotEqual(self.window.console_tabs.tabText(0), "Console")
        self.assertNotEqual(self.page.btn_toggle_reference_roots.text(), "Show Root Paths")
        self.assertNotEqual(self.page.btn_validate_paths.text(), "Validate All Paths")

    def test_preferences_persist_across_windows(self):
        settings_file = Path(tempfile.mkdtemp()) / "ui_settings.ini"
        store_one = QSettings(str(settings_file), QSettings.Format.IniFormat)
        store_one.clear()
        store_one.sync()

        first = MainWindow(load_persisted=False, settings_store=store_one)
        first._current_screen_metrics = lambda: (1920, 1040, 1.0)
        first.resize(1600, 980)
        first.show()
        first.apply_ui_preferences(UIPreferences(theme="dark", language="zh"), persist=True)
        self.app.processEvents()
        first.close()
        self.app.processEvents()

        store_two = QSettings(str(settings_file), QSettings.Format.IniFormat)
        second = MainWindow(load_persisted=True, settings_store=store_two)
        second._current_screen_metrics = lambda: (1920, 1040, 1.0)
        second.resize(1600, 980)
        second.show()
        second.set_active_page("data_paths")
        self.app.processEvents()
        self.addCleanup(second.close)

        self.assertEqual(second.ui_preferences.theme, "dark")
        self.assertEqual(second.ui_preferences.language, "zh")
        self.assertEqual(second._resolved_theme, "dark")
        self.assertNotIn("data_paths", second._nav_buttons)
        self.assertNotEqual(second.breadcrumb.text(), "Data Paths")
        self.assertIn("#0d1726", self.app.styleSheet())


if __name__ == "__main__":
    unittest.main()
