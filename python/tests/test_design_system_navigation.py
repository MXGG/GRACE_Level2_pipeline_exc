import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "Agg")

ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from PySide6.QtWidgets import QApplication

from grace_pipeline.ui.qt.design_system.icons import ICON_REGISTRY, IconRegistry
from grace_pipeline.ui.qt.main_window import MainWindow, NAV_RAIL_COLLAPSED_WIDTH
from grace_pipeline.ui.qt.theme import build_stylesheet, palette_for_theme, set_active_palette
from grace_pipeline.ui.qt.widgets import CollapsibleSection, NavigationButton


class DesignSystemNavigationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_registry_resolves_packaged_semantic_icons_and_has_safe_fallback(self):
        expected = {
            "dashboard": "layout-dashboard.svg",
            "processing": "sliders-horizontal.svg",
            "leakage": "droplets.svg",
            "basin": "map-pinned.svg",
            "preview": "scan-eye.svg",
            "panel-left-open": "panel-left-open.svg",
            "panel-left-close": "panel-left-close.svg",
        }
        for semantic_name, filename in expected.items():
            path = ICON_REGISTRY.asset_path(semantic_name)
            self.assertIsNotNone(path, semantic_name)
            self.assertEqual(path.name, filename)
            self.assertFalse(ICON_REGISTRY.icon(semantic_name, "#005db5", 22).isNull())

        with tempfile.TemporaryDirectory() as td:
            fallback_registry = IconRegistry(td)
            self.assertFalse(fallback_registry.available("not-packaged"))
            self.assertFalse(fallback_registry.icon("not-packaged", "#005db5", 22).isNull())

    def test_navigation_button_compact_mode_retains_accessible_label(self):
        set_active_palette(palette_for_theme("light", app=self.app))
        button = NavigationButton("Preview", "preview")
        self.assertEqual(button.text(), "Preview")
        self.assertEqual(button.accessibleName(), "Preview")
        self.assertEqual(button.toolTip(), "Preview")
        self.assertFalse(button.icon().isNull())

        button.set_compact(True)
        self.assertEqual(button.text(), "")
        self.assertEqual(button.width(), 44)
        self.assertEqual(button.accessibleName(), "Preview")
        self.assertIn("navigation", button.accessibleDescription())
        self.assertEqual(button.toolTip(), "Preview")

        button.apply_language(lambda text: "预览" if text == "Preview" else text)
        self.assertEqual(button.text(), "")
        self.assertEqual(button.accessibleName(), "预览")
        self.assertEqual(button.toolTip(), "预览")

        button.set_compact(False)
        self.assertEqual(button.text(), "预览")

    def test_control_states_are_derived_from_each_theme_palette(self):
        for theme in ("light", "dark", "blue", "green", "graphite", "sepia", "violet"):
            colors = palette_for_theme(theme, app=self.app)
            self.assertEqual(colors["control_checked"], colors["primary"])
            self.assertEqual(colors["focus_ring"], colors["primary"])
            self.assertEqual(colors["disabled_bg"], colors["surface_mid"])
            self.assertEqual(colors["button_secondary_bg"], colors["surface"])
            self.assertEqual(colors["button_secondary_border"], colors["border_strong"])
            stylesheet = build_stylesheet(colors)
            self.assertIn(f'background: {colors["control_checked"]};', stylesheet)
            self.assertIn(f'border-color: {colors["focus_ring"]};', stylesheet)
            self.assertIn("QPushButton {", stylesheet)
            self.assertIn("QMenu {", stylesheet)
            self.assertNotIn("QFrame#PreviewSidebar QWidget,", stylesheet)
            self.assertNotIn("#A46A2A", stylesheet)
            self.assertNotIn("radio_dot_brown.svg", stylesheet)
            self.assertNotIn("switch_on.svg", stylesheet)
            self.assertNotIn("switch_off.svg", stylesheet)

    def test_explicit_button_hierarchy_is_not_overridden_by_label_keywords(self):
        window = MainWindow(load_persisted=False)
        try:
            window._apply_button_roles()
            self.assertEqual(window.page_data_paths.btn_load_config.objectName(), "GhostButton")
            self.assertEqual(window.page_data_paths.btn_save_config.objectName(), "GhostButton")
            self.assertEqual(
                window.page_data_paths.btn_validate_paths.objectName(), "SoftButton"
            )
            # Layer editing now lives in the tree's Properties dialog; keeping an
            # always-visible Apply button would reintroduce the redundant card.
            self.assertFalse(hasattr(window.page_preview, "btn_layer_apply"))
            self.assertEqual(window.page_preview.btn_plot.objectName(), "PrimaryButton")
            self.assertEqual(window.page_preview.btn_export_figure.objectName(), "SoftButton")
            self.assertEqual(window.page_leakage.btn_stop_leakage.objectName(), "DangerGhostButton")
            self.assertEqual(window.console_text.objectName(), "ConsoleOutput")
            self.assertEqual(window.filters_text.property("stream"), "filter")
            self.assertEqual(window.alerts_text.property("stream"), "alert")
            self.assertFalse(window.console_text.styleSheet())
        finally:
            window.close()
            self.app.processEvents()

        section = CollapsibleSection("Advanced Parameters")
        self.assertEqual(section.toggle.objectName(), "SectionToggle")
        self.assertFalse(section.toggle.styleSheet())

    def test_collapsed_navigation_keeps_icon_rail_and_page_keys(self):
        window = MainWindow(load_persisted=False)
        window._current_screen_metrics = lambda: (1920, 1040, 1.0)
        window.resize(1600, 980)
        window.show()
        self.app.processEvents()
        try:
            expected_keys = {"dashboard", "processing", "leakage", "basin", "preview"}
            self.assertEqual(set(window._nav_buttons), expected_keys)

            window.set_nav_collapsed(True)
            self.app.processEvents()
            self.assertTrue(window.nav_rail.isVisible())
            self.assertEqual(window.nav_rail.width(), NAV_RAIL_COLLAPSED_WIDTH)
            self.assertTrue(window.nav_brand_mark.isVisible())
            self.assertFalse(window.nav_brand_title.isVisible())
            self.assertIn("Expand", window.btn_nav_toggle.accessibleName())
            for button in window._nav_buttons.values():
                self.assertEqual(button.text(), "")
                self.assertTrue(button.accessibleName())
                self.assertEqual(button.toolTip(), button.accessibleName())
                self.assertFalse(button.icon().isNull())

            window.set_active_page("preview")
            self.app.processEvents()
            self.assertTrue(window._nav_buttons["preview"].isChecked())

            window.set_nav_collapsed(False)
            self.app.processEvents()
            self.assertGreaterEqual(window.nav_rail.width(), 200)
            self.assertTrue(window.nav_brand_title.isVisible())
            self.assertFalse(window.nav_brand_mark.isVisible())
            self.assertEqual(window._nav_buttons["preview"].text(), "Preview")
        finally:
            window.close()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
