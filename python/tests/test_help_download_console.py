import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "Agg")

ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
os.environ["GRACE_L2_HOME"] = str(ROOT)
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QPushButton

import grace_pipeline.ui.qt.controller as qt_controller
from grace_pipeline.ui.qt.data_sources import OFFICIAL_DATA_PORTALS, official_data_url
from grace_pipeline.ui.qt.global_monitor import configure_global_run_monitor
from grace_pipeline.ui.qt.help_docs import EARTHDATA_REGISTER_URL, HELP_TOPICS, HelpDocsDialog
from grace_pipeline.ui.qt.main_window import MainWindow
from grace_pipeline.ui.qt.preferences import UIPreferences
from grace_pipeline.ui.qt.theme import palette_for_theme


class _FakeMessageBox:
    Icon = QMessageBox.Icon
    ButtonRole = QMessageBox.ButtonRole

    last = None

    def __init__(self, _parent=None):
        type(self).last = self
        self.title = ""
        self.text = ""
        self.info = ""
        self.details = ""
        self.buttons = []
        self.default_button = None
        self.escape_button = None
        self._clicked = None

    def setIcon(self, _icon):
        return None

    def setObjectName(self, name):
        self.object_name = name

    def setWindowTitle(self, title):
        self.title = title

    def setText(self, text):
        self.text = text

    def setInformativeText(self, text):
        self.info = text

    def setDetailedText(self, text):
        self.details = text

    def addButton(self, text, role):
        button = object()
        self.buttons.append((button, str(text), role))
        if self._clicked is None:
            self._clicked = button
        return button

    def setDefaultButton(self, button):
        self.default_button = button

    def setEscapeButton(self, button):
        self.escape_button = button

    def exec(self):
        return 0

    def clickedButton(self):
        return self._clicked


class HelpDownloadConsoleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.window = MainWindow(load_persisted=False)
        cls.window.resize(1500, 900)
        cls.window.show()
        cls.app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.window.close()
        cls.app.processEvents()

    def setUp(self):
        self.window.apply_ui_preferences(UIPreferences(theme="blue", language="en"), persist=False)
        self.window.set_active_page("dashboard")
        self.app.processEvents()

    def tearDown(self):
        self.app.processEvents()

    def test_console_is_named_localized_and_routes_categories(self):
        self.assertEqual(self.window.btn_console.text(), "Console & Log Management")
        self.assertEqual(
            [
                self.window.console_tabs.tabText(index)
                for index in range(self.window.console_tabs.count())
            ],
            ["Console", "Workflow Logs", "Data & I/O", "Warnings & Errors"],
        )

        for output in (
            self.window.console_text,
            self.window.filters_text,
            self.window.data_io_text,
            self.window.alerts_text,
        ):
            output.clear()
        self.window._append_console_line("[PIPELINE] started", "stdout")
        self.window._append_console_line("[GFC] downloaded one file", "stdout")
        self.window._append_console_line("[ERROR] invalid input", "stderr")

        self.assertIn("[PIPELINE] started", self.window.filters_text.toPlainText())
        self.assertNotIn("[GFC]", self.window.filters_text.toPlainText())
        self.assertIn("[GFC] downloaded", self.window.data_io_text.toPlainText())
        self.assertIn("[ERROR] invalid input", self.window.alerts_text.toPlainText())
        self.assertEqual(self.window.console_text.toPlainText().count("\n"), 2)

        self.window.apply_ui_preferences(UIPreferences(theme="blue", language="zh"), persist=False)
        self.app.processEvents()
        self.assertEqual(self.window.btn_console.text(), "控制台与日志管理")
        self.assertEqual(
            [
                self.window.console_tabs.tabText(index)
                for index in range(self.window.console_tabs.count())
            ],
            ["控制台", "工作流日志", "数据与输入输出", "警告与错误"],
        )

    def test_official_source_menu_exposes_all_supported_providers(self):
        self.window.set_active_page("data_paths")
        page = self.window.page_data_paths
        self.assertTrue(page.btn_open_download_site.isVisible())
        self.assertEqual(len(OFFICIAL_DATA_PORTALS), 8)
        self.assertTrue(all(portal.url.startswith("https://") for portal in OFFICIAL_DATA_PORTALS))
        self.assertNotIn("umm_json", official_data_url("GSM", "CSR"))

        menu = page.btn_open_download_site.menu()
        self.assertIsNotNone(menu)
        portal_actions = [
            action for action in menu.actions() if action.toolTip().startswith("https://")
        ]
        self.assertGreaterEqual(len(portal_actions), len(OFFICIAL_DATA_PORTALS) + 1)

    def test_download_confirmation_uses_active_language_and_button_roles(self):
        self.window.apply_ui_preferences(UIPreferences(theme="blue", language="zh"), persist=False)
        with patch.object(qt_controller, "QMessageBox", _FakeMessageBox):
            result = self.window.controller._confirm_download_request(
                product_type="GSM",
                center="HUST",
                start_ym="2024-01",
                end_ym="2024-03",
                download_dir=str(ROOT / "output" / "local"),
                needs_auth=False,
            )

        box = _FakeMessageBox.last
        self.assertEqual(result, "start")
        self.assertEqual(box.title, "下载确认")
        self.assertIn("数据提供方", box.info)
        self.assertIn("月份范围: 2024-01 – 2024-03", box.info)
        self.assertIn("Earthdata 授权: 不需要", box.info)
        self.assertEqual(box.details, "")
        labels = [label for _button, label, _role in box.buttons]
        self.assertEqual(labels, ["开始下载", "打开官方数据页面", "取消"])
        self.assertEqual(box.buttons[0][2], QMessageBox.ButtonRole.AcceptRole)
        self.assertEqual(box.buttons[-1][2], QMessageBox.ButtonRole.RejectRole)
        self.assertIsNotNone(box.default_button)
        self.assertIsNotNone(box.escape_button)

    def test_earthdata_dialog_follows_active_language(self):
        self.window.apply_ui_preferences(UIPreferences(theme="blue", language="zh"), persist=False)
        captured = []

        def reject_dialog(dialog):
            captured.append(dialog)
            return QDialog.DialogCode.Rejected

        with patch.object(qt_controller.QDialog, "exec", reject_dialog):
            self.assertFalse(self.window.controller.on_earthdata_auth(require_credentials=False))

        dialog = captured[0]
        self.assertEqual(dialog.windowTitle(), "Earthdata 授权")
        button_texts = [button.text() for button in dialog.findChildren(QPushButton)]
        self.assertIn("打开 Earthdata 令牌指南", button_texts)
        self.assertIn("保存授权", button_texts)
        self.assertIn("取消", button_texts)
        buttons_by_text = {
            button.text(): button for button in dialog.findChildren(QPushButton)
        }
        self.assertEqual(buttons_by_text["打开 Earthdata 令牌指南"].objectName(), "SoftButton")
        self.assertEqual(buttons_by_text["保存授权"].objectName(), "PrimaryButton")
        self.assertEqual(buttons_by_text["取消"].objectName(), "GhostButton")
        dialog.reject()
        dialog.deleteLater()
        self.app.processEvents()

    def test_production_download_patch_keeps_confirmation_step(self):
        configure_global_run_monitor(self.window)
        controller = self.window.controller
        calls = []
        controller._gfc_download_range = lambda: ("2024-01", "2024-02")
        controller._confirm_download_request = lambda **kwargs: calls.append(kwargs) or "cancel"
        controller._run_in_thread = lambda *_args, **_kwargs: self.fail(
            "cancelled download must not start"
        )
        self.window.page_data_paths.edit_download_dir.setText(str(ROOT / "output" / "local"))

        controller.on_download_gfc_range()

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["start_ym"], "2024-01")
        self.assertIn("needs_auth", calls[0])

    def test_help_links_content_and_dark_theme_are_current(self):
        self.window.apply_ui_preferences(
            UIPreferences(theme="graphite", language="en"), persist=False
        )
        dialog = HelpDocsDialog(self.window)
        external = next(topic for topic in HELP_TOPICS if topic.key == "external_links")
        data_paths = next(topic for topic in HELP_TOPICS if topic.key == "data_paths")

        self.assertIn(EARTHDATA_REGISTER_URL, external.html_en)
        for portal in OFFICIAL_DATA_PORTALS:
            self.assertIn(portal.url, external.html_en)
        self.assertIn("CSR, JPL, GFZ, HUST, and ITSG", data_paths.html_en)
        expected_surface = palette_for_theme("graphite", app=self.app)["surface"]
        self.assertEqual(dialog.colors["surface"], expected_surface)
        self.assertIn(f"background: {expected_surface}", dialog._wrap_html(external))
        dialog.close()
        dialog.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
