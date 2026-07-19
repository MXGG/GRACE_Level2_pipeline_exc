import math
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from grace_pipeline.ui.qt.theme import (  # noqa: E402
    SEMANTIC_COLOR_TOKENS,
    build_stylesheet,
    palette_for_theme,
)

THEMES = ("light", "dark", "blue", "green", "graphite", "sepia", "violet", "system")
LIGHT_THEMES = ("light", "blue", "green", "sepia", "violet", "system")


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def _distance(left: str, right: str) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(_rgb(left), _rgb(right))))


def _luminance(value: str) -> float:
    channels = []
    for raw in _rgb(value):
        channel = raw / 255.0
        channels.append(
            channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


class ThemeVisualHierarchyTest(unittest.TestCase):
    def test_every_supported_theme_exposes_complete_semantic_tokens(self):
        for theme in THEMES:
            with self.subTest(theme=theme):
                colors = palette_for_theme(theme)
                self.assertTrue(set(SEMANTIC_COLOR_TOKENS).issubset(colors))
                for token in SEMANTIC_COLOR_TOKENS:
                    self.assertRegex(colors[token], r"^#[0-9A-Fa-f]{6}$", (theme, token))
                self.assertEqual(colors["input_bg"], colors["field_bg"])
                self.assertEqual(colors["input_border"], colors["field_border"])
                self.assertEqual(colors["focus_ring"], colors["field_focus_border"])
                self.assertEqual(colors["control_bg"], colors["field_bg"])

    def test_light_themes_keep_forms_white_and_separate_from_tinted_containers(self):
        for theme in LIGHT_THEMES:
            with self.subTest(theme=theme):
                colors = palette_for_theme(theme)
                self.assertGreaterEqual(_luminance(colors["field_bg"]), 0.97)
                self.assertGreaterEqual(_luminance(colors["card_bg"]), 0.97)
                self.assertNotEqual(colors["field_bg"], colors["card_header_bg"])
                self.assertNotEqual(colors["field_bg"], colors["content_bg"])
                self.assertNotEqual(colors["field_bg"], colors["status_bg"])
                self.assertNotEqual(colors["card_header_bg"], colors["status_bg"])
                self.assertNotEqual(colors["app_bg"], colors["content_bg"])
                self.assertGreater(_distance(colors["field_border"], colors["field_bg"]), 20)

    def test_dark_themes_preserve_the_same_semantic_separation(self):
        for theme in ("dark", "graphite"):
            with self.subTest(theme=theme):
                colors = palette_for_theme(theme)
                self.assertNotEqual(colors["field_bg"], colors["card_bg"])
                self.assertNotEqual(colors["field_bg"], colors["card_header_bg"])
                self.assertNotEqual(colors["status_bg"], colors["card_header_bg"])
                self.assertNotEqual(colors["app_bg"], colors["content_bg"])
                self.assertGreater(_distance(colors["field_border"], colors["field_bg"]), 20)

    def test_card_headers_are_subtle_tints_not_primary_colour_blocks(self):
        for theme in THEMES:
            with self.subTest(theme=theme):
                colors = palette_for_theme(theme)
                header_delta = _distance(colors["card_header_bg"], colors["card_bg"])
                self.assertGreater(header_delta, 2)
                self.assertLess(header_delta, 45)
                self.assertNotEqual(colors["card_header_bg"], colors["primary"])

    def test_qss_assigns_semantic_roles_to_distinct_widget_selectors(self):
        colors = palette_for_theme("sepia")
        qss = build_stylesheet(colors)

        expected_fragments = (
            f'QMainWindow,\nQDialog,\nQMessageBox {{\n    background: {colors["app_bg"]};',
            f'QFrame#NavigationRail {{\n    background: {colors["sidebar_bg"]};',
            f'QFrame#PageRoot {{\n    background: {colors["content_bg"]};',
            f'QWidget#PreviewPage {{\n    background: {colors["app_bg"]};',
            f'QFrame#PreviewContent {{\n    background: {colors["content_bg"]};',
            f'QFrame#PreviewMapCard {{\n    background: {colors["card_bg"]};',
            f'QFrame#PreviewCanvasHost {{\n    background: {colors["field_bg"]};',
            f'QFrame#PreviewSidebar {{\n    background: {colors["sidebar_bg"]};',
            f'QWidget#PreviewSidebarContent {{\n    background: {colors["sidebar_bg"]};',
            f'QFrame#PreviewSidebarFooter {{\n    background: {colors["sidebar_bg"]};',
            "QFrame#EmbeddedSection {\n    background: transparent;",
            f'QFrame#EmbeddedSectionHeader {{\n    background: {colors["read_only_bg"]};',
            f'QFrame#PageCard {{\n    background: {colors["card_bg"]};',
            f'QFrame#CardHeader {{\n    background: {colors["card_header_bg"]};',
            (
                "QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, "
                "QPlainTextEdit, QTextEdit {\n"
                f'    background: {colors["field_bg"]};'
            ),
            (
                "QFrame#PreviewStatusBar,\nQFrame#StatusBar,\n"
                'QFrame[statusRole="true"] {\n'
                f'    background: {colors["status_bg"]};'
            ),
            f'QHeaderView::section {{\n    background: {colors["table_header_bg"]};',
            "QLineEdit:read-only,\nQPlainTextEdit:read-only,\nQTextEdit:read-only,",
            f'    background: {colors["read_only_bg"]};',
            f'QPushButton#NavButton:checked {{\n    background: {colors["selected_bg"]};',
        )
        for fragment in expected_fragments:
            self.assertIn(fragment, qss)

        self.assertIn("QWidget#DownloadControlStrip {\n    background: transparent;", qss)
        self.assertIn("QWidget#InlineStatusField {\n    background: transparent;", qss)
        widget_rule = qss.split("QWidget {", 1)[1].split("}", 1)[0]
        self.assertNotIn("background:", widget_rule)


if __name__ == "__main__":
    unittest.main()
