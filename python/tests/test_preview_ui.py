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
from PySide6.QtWidgets import QApplication, QWidget


ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from grace_pipeline.ui.qt.main_window import MainWindow
from grace_pipeline.ui.qt.preferences import UIPreferences
from grace_pipeline.ui.qt.app import start_gui
from grace_pipeline.ui.qt.i18n import translate_text
from grace_pipeline.ui.qt.preview_enhancements import _sync_projection_parameter_panel
from grace_pipeline.ui.qt.projection_registry import (
    is_global_extent,
    projection_default_extent,
    projection_supports_global_extent,
    visible_projection_params,
)


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
        location_label = self.window.controller._nav_toolbar.locLabel
        location_label.setText("1.23e+06, 4.56e+06")
        self.assertTrue(location_label.isHidden())
        self.assertEqual(location_label.maximumWidth(), 0)
        self.assertTrue(self.page.lbl_cursor_position.isVisible())

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

    def test_projection_parameter_panel_tracks_selected_projection(self):
        self.page.cmb_projection.setCurrentText("Robinson")
        _sync_projection_parameter_panel(self.window)
        self.assertTrue(self.page.projection_param_widgets["central_longitude"]["field"].isVisible())
        self.assertFalse(self.page.projection_param_widgets["extent"]["field"].isVisible())

        self.page.cmb_projection.setCurrentText("Lambert Conformal")
        _sync_projection_parameter_panel(self.window)
        self.assertTrue(self.page.projection_param_widgets["central_longitude"]["field"].isVisible())
        self.assertTrue(self.page.projection_param_widgets["central_latitude"]["field"].isVisible())
        self.assertTrue(self.page.projection_param_widgets["standard_parallels"]["field"].isVisible())
        self.assertTrue(self.page.projection_param_widgets["extent"]["field"].isVisible())
        self.assertFalse(self.page.projection_param_widgets["azimuth"]["field"].isVisible())

        self.page.cmb_projection.setCurrentText("3D Globe")
        _sync_projection_parameter_panel(self.window)
        self.assertEqual(
            visible_projection_params("3D Globe"),
            ["central_longitude", "central_latitude", "azimuth", "elevation", "zoom"],
        )
        self.assertTrue(self.page.projection_param_widgets["azimuth"]["field"].isVisible())
        self.assertFalse(self.page.projection_param_widgets["extent"]["field"].isVisible())

    def test_projection_scope_rules_protect_regional_projections(self):
        self.assertFalse(projection_supports_global_extent("Albers Equal Area"))
        self.assertTrue(is_global_extent([-180.0, 180.0, -90.0, 90.0]))
        self.assertEqual(projection_default_extent("North Polar Stereographic"), [-180.0, 180.0, 50.0, 90.0])
        self.assertEqual(projection_default_extent("South Polar Stereographic"), [-180.0, 180.0, -90.0, -50.0])
        self.assertEqual(projection_default_extent("Gnomonic"), [-90.0, 90.0, -60.0, 60.0])

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

    def test_full_gui_language_modes_do_not_mix_core_ui_terms(self):
        window = start_gui([])
        self.addCleanup(lambda: window.exit_application())
        self.app.processEvents()

        def visible_texts_for(page_key: str) -> list[str]:
            window.set_active_page(page_key)
            window.refresh_translations()
            self.app.processEvents()
            texts: list[str] = []
            for widget in window.findChildren(QWidget):
                if not hasattr(widget, "text") or not hasattr(widget, "isVisibleTo"):
                    continue
                try:
                    if widget.isVisibleTo(window):
                        text = str(widget.text()).strip()
                        if text:
                            texts.append(text)
                except RuntimeError:
                    continue
            return texts

        window.apply_ui_preferences(UIPreferences(theme="violet", language="en"), persist=False)
        english_texts: list[str] = []
        for page in ("dashboard", "processing", "leakage"):
            english_texts.extend(visible_texts_for(page))
        english_visible = "\n".join(english_texts)
        for forbidden in (
            "系统与项目状态",
            "数据与输出",
            "输出结构",
            "配置名称",
            "数据下载",
            "选择下载文件夹",
            "待校正数据",
            "官方尺度/增益因子",
            "正演建模",
        ):
            self.assertNotIn(forbidden, english_visible)

        window.apply_ui_preferences(UIPreferences(theme="green", language="zh"), persist=False)
        chinese_texts: list[str] = []
        for page in ("dashboard", "processing", "leakage"):
            chinese_texts.extend(visible_texts_for(page))
        chinese_visible = "\n".join(chinese_texts)
        for forbidden in (
            "Dashboard",
            "Filter Processing",
            "Leakage Correction",
            "Appearance",
            "CONFIG READY",
            "System and project status",
            "Current run",
            "Load Config",
            "Save Config",
            "Validate Paths",
            "Run Filters",
            "FILTER INPUT PATHS",
            "GFC INPUT DIRECTORY",
            "DETECTED RANGE",
            "AUXILIARY FILTER FILES",
            "C20 REPLACEMENT FILE",
            "DEGREE-1 FILE",
            "GIA MODEL PATH",
            "FILTER OUTPUT PATHS",
            "REMOTE SYNC",
            "MAIN OUTPUT ROOT",
            "Open Logs",
            "Browse",
            "Folder...",
            "File...",
            "Ready to Process",
            "Input not loaded",
            "Basin scale factor",
        ):
            self.assertNotIn(forbidden, chinese_visible)

        self.assertEqual(translate_text("下载 GFC", "en"), "Download GFC")
        self.assertEqual(translate_text("系统与项目状态", "en"), "System and project status")
        self.assertEqual(
            translate_text("Preview basin: first boundary feature", "zh"),
            "预览流域：第一个边界要素",
        )

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
        self.page.cmb_projection.setCurrentText("Robinson")
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

    def test_3d_globe_renders_visible_graticule_layer(self):
        window = start_gui([])
        self.addCleanup(lambda: window.exit_application())
        self.app.processEvents()
        window.set_active_page("preview")
        page = window.page_preview
        sample_stack = self._create_sample_stack()
        page.edit_dataset_source.setText(str(sample_stack))
        page.cmb_projection.setCurrentText("3D Globe")

        window.controller.on_load_stack_info()
        window.controller.on_render_preview()
        self.app.processEvents()

        self.assertEqual(getattr(window.controller._ax, "name", ""), "3d")
        self.assertGreater(len(getattr(window.controller._ax, "lines", [])), 20)
        self.assertEqual(len(window.controller._figure.axes), 2)
        page.plot_toolbar_host.setVisible(True)
        window.controller._sync_preview_toolbar_mode()
        self.assertTrue(window.controller._nav_toolbar.isVisible())
        self.assertTrue(window.controller.preview_3d_controls.isVisible())
        self.assertTrue(window.controller.btn_preview_3d_view.isVisible())
        self.assertIn("3D View", window.controller.btn_preview_3d_view.text())
        before_limits = [
            tuple(round(v, 6) for v in window.controller._ax.get_xlim3d()),
            tuple(round(v, 6) for v in window.controller._ax.get_ylim3d()),
            tuple(round(v, 6) for v in window.controller._ax.get_zlim3d()),
        ]
        self.assertEqual(before_limits[0], before_limits[1])
        self.assertEqual(before_limits[1], before_limits[2])

        window.controller._set_preview_3d_zoom(1.6, rerender=False)
        self.app.processEvents()
        after_limits = [
            tuple(round(v, 6) for v in window.controller._ax.get_xlim3d()),
            tuple(round(v, 6) for v in window.controller._ax.get_ylim3d()),
            tuple(round(v, 6) for v in window.controller._ax.get_zlim3d()),
        ]
        self.assertEqual(after_limits[0], after_limits[1])
        self.assertEqual(after_limits[1], after_limits[2])
        self.assertLess(after_limits[0][1] - after_limits[0][0], before_limits[0][1] - before_limits[0][0])

    def test_responsive_layout_respects_small_available_geometry(self):
        self.window._current_screen_metrics = lambda: (1100, 700, 1.0)
        self.window._layout_bucket = None
        self.window._apply_responsive_layout(force=True)
        self.assertLessEqual(self.window.minimumWidth(), 1100)
        self.assertLessEqual(self.window.minimumHeight(), 700)


if __name__ == "__main__":
    unittest.main()
