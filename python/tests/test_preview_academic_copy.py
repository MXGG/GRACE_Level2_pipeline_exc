import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from grace_pipeline.ui.qt.i18n import canonical_text, translate_text
from grace_pipeline.ui.qt.main_window import MainWindow


class PreviewAcademicCopyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_scientific_and_gis_terms_are_canonical_in_both_languages(self):
        expected = {
            "Equivalent water height (EWH)": "等效水高（EWH）",
            "Map Projection": "地图投影",
            "Spatial Extent & Graticule": "空间范围与经纬网",
            "Mass Anomaly Raster": "质量变化栅格",
            "Import Raster / Vector Layer": "导入栅格 / 矢量图层",
            "Cursor Position": "光标位置",
            "Grid Value": "格网值",
            "Render Time": "渲染耗时",
        }
        for english, chinese in expected.items():
            with self.subTest(term=english):
                self.assertEqual(translate_text(english, "zh"), chinese)
                self.assertEqual(translate_text(chinese, "en"), english)

        self.assertEqual(canonical_text("Load Stack Info"), "Read Dataset Metadata")
        self.assertEqual(canonical_text("Projection"), "Map Projection")

    def test_dynamic_dataset_summary_switches_language_without_losing_values(self):
        english = (
            "Dimensions: 360 × 180 × 158 | "
            "Time coverage: 2002-04–2017-05 | 117.8 KB"
        )
        chinese = (
            "维度：360 × 180 × 158 | "
            "时间范围：2002-04–2017-05 | 117.8 KB"
        )
        self.assertEqual(translate_text(english, "zh"), chinese)
        self.assertEqual(translate_text(chinese, "en"), english)

    def test_preview_initial_state_is_truthful_and_uses_approved_labels(self):
        window = MainWindow(load_persisted=False)
        try:
            page = window.page_preview
            self.assertEqual(page.edit_dataset_source.text(), "")
            self.assertEqual(
                page.edit_dataset_source.placeholderText(),
                "Select a gridded MAT, NetCDF, or HDF5 dataset",
            )
            self.assertEqual(page.btn_load_stack.text(), "Read Dataset Metadata")
            self.assertEqual(page.lbl_stack_info.text(), "Dataset not loaded.")
            self.assertEqual(page.cmb_data_var.accessibleName(), "Data Variable")
            self.assertEqual(page.cmb_projection.accessibleName(), "Map Projection")
            self.assertEqual(page.lbl_dataset.text(), "No dataset loaded")
            self.assertEqual(page.lbl_cursor_position.text(), "—")
            self.assertEqual(page.lbl_grid_value.text(), "—")
            self.assertEqual(page.lbl_engine_latency.text(), "—")
        finally:
            window.close()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
