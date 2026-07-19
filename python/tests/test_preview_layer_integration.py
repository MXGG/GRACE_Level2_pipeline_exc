import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "Agg")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QLabel,
    QLineEdit,
    QSpinBox,
)
import numpy as np
from scipy.io import savemat


ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from grace_pipeline.ui.qt.main_window import MainWindow


class PreviewLayerIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow(load_persisted=False)
        self.controller = self.window.controller
        # Layer-order tests do not need to redraw the Matplotlib canvas.
        self.controller._refresh_preview_after_layer_change = lambda: None

    def tearDown(self):
        self.window.close()
        self.app.processEvents()

    def test_layer_panel_is_top_first_and_renderer_is_bottom_first(self):
        model_resets = []
        self.controller.preview_layer_model.modelReset.connect(
            lambda: model_resets.append(True)
        )
        self.controller._render_preview_layer_table()
        self.assertEqual(model_resets, [True])

        render_ids = [layer.id for layer in self.controller._preview_render_layers()]
        display_ids = [layer.id for layer in self.controller._preview_display_layers()]

        self.assertEqual(render_ids, list(reversed(display_ids)))
        self.assertEqual(render_ids[0], "data")
        self.assertEqual(display_ids[0], "colorbar")

        self.controller._add_preview_overlay_layer(
            str(ROOT / "data" / "secondary.mat"),
            metadata={"active_var": "ewh"},
        )
        self.controller._top_preview_layer("data")

        data_layers = [
            layer
            for layer in self.controller._preview_display_layers()
            if layer.type == "raster"
        ]
        self.assertEqual(data_layers[0].id, "data")
        self.assertEqual(
            [layer.id for layer in self.controller._preview_render_layers()],
            list(reversed([layer.id for layer in self.controller._preview_display_layers()])),
        )

    def test_move_up_changes_actual_render_order(self):
        self.controller._add_preview_overlay_layer(
            str(ROOT / "data" / "secondary.mat"),
            metadata={"active_var": "ewh"},
        )
        before = [layer.id for layer in self.controller._preview_display_layers()]
        data_index = before.index("data")

        self.controller._move_preview_layer("data", -1)

        after = [layer.id for layer in self.controller._preview_display_layers()]
        self.assertEqual(after.index("data"), data_index - 1)
        self.assertEqual(
            [layer.id for layer in self.controller._preview_render_layers()],
            list(reversed(after)),
        )

    def test_same_file_can_be_added_as_multiple_variable_layers(self):
        path = str(ROOT / "data" / "same-source.mat")
        self.controller._add_preview_overlay_layer(path, metadata={"active_var": "ewh"})
        self.controller._add_preview_overlay_layer(path, metadata={"active_var": "uncertainty"})

        matching = [layer for layer in self.controller.preview_layers if layer.path == path]
        self.assertEqual(len(matching), 2)
        self.assertEqual({layer.metadata["active_var"] for layer in matching}, {"ewh", "uncertainty"})
        self.assertEqual(len({layer.id for layer in matching}), 2)

    def test_duplicate_layer_keeps_a_stable_instance_and_selection(self):
        model = self.controller.preview_layer_model
        original = next(item for item in model.draw_order() if item.layer_id == "data")

        self.controller._duplicate_preview_layer_instance(original.instance_id)

        copies = [item for item in model.draw_order() if item.name.endswith("(copy)")]
        self.assertEqual(len(copies), 1)
        self.assertEqual(
            self.controller._selected_preview_layer_instance_id,
            copies[0].instance_id,
        )
        self.assertEqual(
            len({layer.instance_id for layer in self.controller.preview_layers}),
            len(self.controller.preview_layers),
        )

    def test_imported_layer_context_menu_actions_are_enabled_and_mutate_model(self):
        first_path = str(ROOT / "data" / "first-overlay.mat")
        second_path = str(ROOT / "data" / "second-overlay.mat")
        self.controller._add_preview_overlay_layer(first_path, metadata={"active_var": "ewh"})
        self.controller._add_preview_overlay_layer(second_path, metadata={"active_var": "ewh"})
        model = self.controller.preview_layer_model
        view = self.window.page_preview.layer_tree_view
        first = next(item for item in model.draw_order() if item.path == first_path)

        def actions_for(instance_id):
            menu = view.build_context_menu(model.index_for_instance(instance_id))
            return menu, {
                action.data(): action
                for action in menu.actions()
                if action.data()
            }

        menu, actions = actions_for(first.instance_id)
        self.addCleanup(menu.deleteLater)
        self.assertEqual(
            set(actions),
            {"properties", "rename", "duplicate", "move_up", "move_down", "move_top", "zoom", "remove"},
        )
        self.assertTrue(actions["remove"].isEnabled())
        self.assertTrue(actions["properties"].isEnabled())

        before_row = model.index_for_instance(first.instance_id).row()
        actions["move_up"].trigger()
        self.assertEqual(model.index_for_instance(first.instance_id).row(), before_row - 1)

        menu, actions = actions_for(first.instance_id)
        self.addCleanup(menu.deleteLater)
        count_before = len(model.draw_order())
        actions["duplicate"].trigger()
        self.assertEqual(len(model.draw_order()), count_before + 1)

        menu, actions = actions_for(first.instance_id)
        self.addCleanup(menu.deleteLater)
        with patch.object(QDialog, "exec", return_value=QDialog.Rejected) as dialog_exec:
            actions["properties"].trigger()
        dialog_exec.assert_called_once()

        menu, actions = actions_for(first.instance_id)
        self.addCleanup(menu.deleteLater)
        actions["remove"].trigger()
        self.assertIsNone(model.layer_record(first.instance_id))

        built_in = next(item for item in model.draw_order() if item.layer_id == "data")
        menu, actions = actions_for(built_in.instance_id)
        self.addCleanup(menu.deleteLater)
        self.assertFalse(actions["remove"].isEnabled())

    def test_layer_properties_dialog_applies_settings_without_month_tolerance(self):
        path = str(ROOT / "data" / "properties-overlay.mat")
        self.controller._add_preview_overlay_layer(
            path,
            metadata={"active_var": "ewh", "time_tolerance_months": 4},
            opacity=0.7,
        )
        model = self.controller.preview_layer_model
        record = next(item for item in model.draw_order() if item.path == path)
        self.assertNotIn("time_tolerance_months", record.metadata)

        dialog = self.controller._create_preview_layer_properties_dialog(record.instance_id)
        self.assertIsNotNone(dialog)
        self.addCleanup(dialog.deleteLater)
        self.assertEqual(dialog.objectName(), "PreviewLayerPropertiesDialog")
        self.assertNotIn("Month Match Tolerance", " ".join(label.text() for label in dialog.findChildren(QLabel)))

        name_edit = dialog.findChild(QLineEdit, "LayerPropertyNameEdit")
        visible_check = dialog.findChild(QCheckBox, "LayerPropertyVisibleCheck")
        opacity_spin = dialog.findChild(QSpinBox, "LayerPropertyOpacitySpin")
        variable_combo = dialog.findChild(QComboBox, "LayerPropertyVariableCombo")
        name_edit.setText("Comparison EWH")
        visible_check.setChecked(False)
        opacity_spin.setValue(55)
        variable_combo.setCurrentText("ewh")
        dialog.accept()

        updated = model.layer_record(record.instance_id)
        self.assertEqual(updated.name, "Comparison EWH")
        self.assertFalse(updated.visible)
        self.assertAlmostEqual(updated.opacity, 0.55)
        self.assertEqual(updated.metadata["active_var"], "ewh")
        self.assertNotIn("time_tolerance_months", updated.metadata)
        self.assertNotIn("month_tolerance", updated.metadata)

    def test_imported_raster_does_not_reenable_hidden_base_raster(self):
        base = next(layer for layer in self.controller.preview_layers if layer.id == "data")
        base.visible = False
        self.controller._add_preview_overlay_layer(
            str(ROOT / "data" / "overlay.mat"),
            metadata={"active_var": "ewh"},
        )

        self.assertFalse(self.controller._preview_layer_visible("raster", path=None))
        self.assertTrue(self.controller._preview_layer_visible("raster"))

    def test_zoom_to_layer_supports_base_raster_and_vector_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stack_path = root / "grid.mat"
            savemat(
                stack_path,
                {
                    "lon": np.array([-12.0, 28.0]),
                    "lat": np.array([-6.0, 14.0]),
                    "ewh": np.zeros((2, 2, 1)),
                },
            )
            page = self.window.page_preview
            page.edit_dataset_source.setText(str(stack_path))
            model = self.controller.preview_layer_model
            base = next(item for item in model.draw_order() if item.layer_id == "data")

            self.controller._zoom_to_preview_layer_instance(base.instance_id)

            self.assertEqual(page.edit_region_lon_min.text(), "-12")
            self.assertEqual(page.edit_region_lon_max.text(), "28")
            self.assertEqual(page.edit_region_lat_min.text(), "-6")
            self.assertEqual(page.edit_region_lat_max.text(), "14")

            txt_grid_path = root / "overlay_grid.txt"
            np.savetxt(
                txt_grid_path,
                np.array(
                    [
                        [10.0, 30.0, 1.0],
                        [10.0, 40.0, 2.0],
                        [20.0, 30.0, 3.0],
                        [20.0, 40.0, 4.0],
                    ]
                ),
                delimiter=",",
                header="lon,lat,value",
                comments="",
            )
            self.assertEqual(
                self.controller._preview_layer_type_for_path(str(txt_grid_path)),
                "raster",
            )
            self.controller._add_preview_overlay_layer(str(txt_grid_path))
            txt_grid = next(
                item for item in model.draw_order() if item.path == str(txt_grid_path)
            )
            self.assertEqual(txt_grid.layer_type, "raster")

            boundary_path = root / "boundary.txt"
            np.savetxt(
                boundary_path,
                np.array([[101.0, 21.0], [109.0, 21.0], [109.0, 27.0], [101.0, 21.0]]),
            )
            self.controller._add_preview_overlay_layer(str(boundary_path))
            boundary = next(
                item for item in model.draw_order() if item.path == str(boundary_path)
            )
            self.assertEqual(boundary.layer_type, "boundary")

            self.controller._zoom_to_preview_layer_instance(boundary.instance_id)

            self.assertEqual(page.edit_region_lon_min.text(), "101")
            self.assertEqual(page.edit_region_lon_max.text(), "109")
            self.assertEqual(page.edit_region_lat_min.text(), "21")
            self.assertEqual(page.edit_region_lat_max.text(), "27")

    def test_preview_fields_have_accessible_names_from_visible_labels(self):
        page = self.window.page_preview

        self.assertEqual(page.edit_dataset_source.accessibleName(), "Data Source")
        self.assertEqual(page.cmb_data_var.accessibleName(), "Data Variable")
        self.assertEqual(page.slider_time_index.accessibleName(), "Time Slice")
        self.assertEqual(page.cmb_projection.accessibleName(), "Map Projection")
        self.assertEqual(page.edit_cmin.accessibleName(), "Minimum")
        self.assertEqual(page.edit_cmax.accessibleName(), "Maximum")

        self.window.ui_preferences.language = "zh"
        self.window.refresh_translations()
        model = self.controller.preview_layer_model
        coast = next(item for item in model.draw_order() if item.layer_id == "coastline")
        coast_index = model.index_for_instance(coast.instance_id)

        self.assertEqual(page.layer_tree_view.accessibleName(), "预览图层")
        self.assertEqual(model.data(coast_index), "海岸线")
        self.assertEqual(model.data(coast_index, Qt.ItemDataRole.EditRole), "Coastlines")
        card_title = next(
            label for label in page.card_layers.findChildren(QLabel)
            if label.objectName() == "CardTitle"
        )
        self.assertEqual(card_title.text(), "图层管理")
        self.assertEqual(page.btn_overlay_add.text(), "导入栅格 / 矢量图层")
        self.assertFalse(hasattr(page, "card_layer_properties"))
        self.assertFalse(hasattr(page, "spin_layer_time_tolerance"))

        self.window.ui_preferences.language = "en"
        self.window.refresh_translations()
        self.assertEqual(model.data(coast_index), "Coastlines")


if __name__ == "__main__":
    unittest.main()
