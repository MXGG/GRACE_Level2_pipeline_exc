import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "Agg")

import numpy as np
import scipy.io as sio
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from grace_pipeline.ui.qt.main_window import MainWindow
from grace_pipeline.ui.qt.preferences import UIPreferences
from grace_pipeline.ui.qt.app import start_gui


class PreviewUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow(load_persisted=False)
        self.window._current_screen_metrics = lambda: (1920, 1040, 1.0)
        self.window._layout_bucket = None
        self.window.resize(1600, 980)
        self.window.show()
        self.window.set_active_page("preview")
        self.window._apply_responsive_layout(force=True)
        self.page = self.window.page_preview
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()

    def _create_sample_stack(self) -> Path:
        lon = np.linspace(0.125, 359.875, 72)
        lat = np.linspace(-89.875, 89.875, 36)
        t = np.arange(4, dtype=float)
        lon_wave = np.deg2rad(lon)[:, None, None]
        lat_wave = np.deg2rad(lat)[None, :, None]
        time_wave = np.arange(4, dtype=float)[None, None, :]
        ewh = np.sin(lon_wave) * np.cos(lat_wave) + 0.15 * time_wave
        handle, path_text = tempfile.mkstemp(suffix="_preview_stack.mat")
        os.close(handle)
        path = Path(path_text)
        sio.savemat(
            path,
            {
                "ewh": ewh.astype(float),
                "lon": lon,
                "lat": lat,
                "t": t,
            },
        )
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    def _create_regional_stack(self) -> Path:
        lon = np.linspace(90.0, 125.0, 18)
        lat = np.linspace(15.0, 45.0, 16)
        t = np.arange(2, dtype=float)
        ewh = np.zeros((lon.size, lat.size, t.size), dtype=float)
        ewh[:, :, 0] = np.sin(np.deg2rad(lon))[:, None] + np.cos(np.deg2rad(lat))[None, :]
        ewh[:, :, 1] = ewh[:, :, 0] + 0.2
        handle, path_text = tempfile.mkstemp(suffix="_regional_preview_stack.mat")
        os.close(handle)
        path = Path(path_text)
        sio.savemat(path, {"ewh": ewh, "lon": lon, "lat": lat, "t": t})
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    def test_toolbar_starts_hidden_and_button_text_stays_in_sync(self):
        self.assertFalse(self.page.plot_toolbar_host.isVisible())
        self.assertEqual(self.page.btn_toggle_tools.text(), "Tools")

        QTest.mouseClick(self.page.btn_toggle_tools, Qt.LeftButton)
        self.app.processEvents()
        self.assertTrue(self.page.plot_toolbar_host.isVisible())
        self.assertEqual(self.page.btn_toggle_tools.text(), "Hide Tools")

        QTest.mouseClick(self.page.btn_toggle_tools, Qt.LeftButton)
        self.app.processEvents()
        self.assertFalse(self.page.plot_toolbar_host.isVisible())
        self.assertEqual(self.page.btn_toggle_tools.text(), "Tools")

    def test_render_button_keeps_label_after_language_refresh(self):
        self.assertEqual(self.page.btn_plot.text(), "Render Preview")

        self.window.apply_ui_preferences(UIPreferences(theme="light", language="zh"), persist=False)
        self.app.processEvents()
        self.assertEqual(self.page.btn_plot.text(), "渲染预览")

        self.window.apply_ui_preferences(UIPreferences(theme="blue", language="en"), persist=False)
        self.app.processEvents()
        self.assertEqual(self.page.btn_plot.text(), "Render Preview")

    def test_full_gui_refresh_survives_enhancement_patches(self):
        window = start_gui([])
        self.addCleanup(lambda: window.exit_application())
        self.app.processEvents()

        window.apply_ui_preferences(UIPreferences(theme="green", language="zh"), persist=False)
        self.app.processEvents()
        window.controller.refresh_dashboard()
        window.refresh_translations()
        self.app.processEvents()

        self.assertEqual(window.page_preview.btn_plot.text(), "渲染预览")
        self.assertEqual(window.page_preview.btn_export_figure.text(), "导出图像")

    def test_preview_render_survives_layout_toggles(self):
        sample_stack = self._create_sample_stack()
        self.page.edit_dataset_source.setText(str(sample_stack))

        self.window.controller.on_load_stack_info()
        self.window.controller.on_render_preview()
        self.app.processEvents()

        self.assertIn("72 x 36 x 4", self.page.lbl_stack_info.text())
        self.assertTrue(self.window.controller._figure.axes)
        self.assertGreater(self.page.plot_container.width(), 400)
        self.assertGreater(self.page.plot_container.height(), 350)
        y_values = np.asarray(self.window.controller._preview_pick_state["y"], dtype=float)
        finite_y = y_values[np.isfinite(y_values)]
        ylim = self.window.controller._ax.get_ylim()
        padding_bottom = float(np.nanmin(finite_y)) - float(ylim[0])
        self.assertGreaterEqual(padding_bottom, 0.15)

        initial_width = self.page.plot_container.width()

        QTest.mouseClick(self.page.btn_toggle_status, Qt.LeftButton)
        QTest.qWait(20)
        self.assertFalse(self.page.card_status.isVisible())
        self.assertGreater(self.page.plot_container.height(), 350)

        QTest.mouseClick(self.page.btn_toggle_status, Qt.LeftButton)
        QTest.qWait(20)
        self.assertTrue(self.page.card_status.isVisible())

        QTest.mouseClick(self.page.btn_toggle_sidebar, Qt.LeftButton)
        QTest.qWait(20)
        self.assertFalse(self.page.sidebar_panel.isVisible())
        self.assertGreater(self.page.plot_container.width(), initial_width)

        QTest.mouseClick(self.page.btn_toggle_sidebar, Qt.LeftButton)
        QTest.qWait(20)
        self.assertTrue(self.page.sidebar_panel.isVisible())
        self.assertGreater(self.page.plot_container.width(), 400)

    def test_regional_stack_renders_without_global_pole_extension(self):
        regional_stack = self._create_regional_stack()
        self.page.edit_dataset_source.setText(str(regional_stack))
        self.page.cmb_projection.setCurrentText("Robinson (Global)")
        self.page.chk_auto_region.setChecked(True)

        self.window.controller.on_load_stack_info()
        self.window.controller.on_render_preview()
        self.app.processEvents()

        self.assertIn("18 x 16 x 2", self.page.lbl_stack_info.text())
        y_values = np.asarray(self.window.controller._preview_pick_state["lat"], dtype=float)
        finite_y = y_values[np.isfinite(y_values)]
        self.assertGreater(float(np.nanmin(finite_y)), 10.0)
        self.assertLess(float(np.nanmax(finite_y)), 50.0)
        self.assertLess(float(np.diff(self.window.controller._ax.get_ylim())[0]), 1.5)

    def test_responsive_layout_respects_small_available_geometry(self):
        self.window._current_screen_metrics = lambda: (1100, 700, 1.0)
        self.window._layout_bucket = None
        self.window._apply_responsive_layout(force=True)
        self.assertLessEqual(self.window.minimumWidth(), 1100)
        self.assertLessEqual(self.window.minimumHeight(), 700)


if __name__ == "__main__":
    unittest.main()
