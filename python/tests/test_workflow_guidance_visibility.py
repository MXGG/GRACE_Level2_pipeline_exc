import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "Agg")

ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from PySide6.QtWidgets import QApplication, QLabel, QRadioButton, QWidget

from grace_pipeline.ui.qt.leakage_wizard import _make_method_card
from grace_pipeline.ui.qt.ui_compact_polish import (
    _compact_leakage_page,
    _hide_long_explanatory_labels,
)


class WorkflowGuidanceVisibilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_leakage_method_guidance_survives_compact_layout(self):
        radio = QRadioButton()
        card = _make_method_card(
            "Official scale/gain factor",
            "Use the official grid to restore amplitudes at every grid cell.",
            radio,
        )
        _hide_long_explanatory_labels(card, min_len=10)
        description = next(
            label for label in card.findChildren(QLabel) if "restore amplitudes" in label.text()
        )
        self.assertTrue(bool(description.property("keepCompact")))
        self.assertFalse(description.isHidden())

        page = QWidget()
        for name, text in (
            ("lbl_lrc_method_hint", "Task-critical method guidance"),
            ("lbl_lrc_output_hint", "Expected corrected products"),
            ("lbl_preview_status", "Preview hand-off guidance"),
            ("lbl_lrc_reference_info", "Reference data status"),
            ("lbl_lrc_filter_hint", "Filter parameter guidance"),
        ):
            label = QLabel(text, page)
            label.hide()
            setattr(page, name, label)
        window = SimpleNamespace(
            page_leakage=page,
            ui_preferences=SimpleNamespace(language="en"),
        )
        _compact_leakage_page(window)
        for name in (
            "lbl_lrc_method_hint",
            "lbl_lrc_output_hint",
            "lbl_preview_status",
            "lbl_lrc_reference_info",
            "lbl_lrc_filter_hint",
        ):
            label = getattr(page, name)
            self.assertTrue(bool(label.property("keepCompact")))
            self.assertFalse(label.isHidden())


if __name__ == "__main__":
    unittest.main()
