from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QModelIndex, Qt  # noqa: E402

from grace_pipeline.ui.qt.preview_layer_tree import (  # noqa: E402
    GROUP_DATA,
    GROUP_DECORATIONS,
    GROUP_SPECS,
    GROUP_VECTORS,
    PreviewLayerTreeModel,
)


@dataclass
class ExistingPreviewLayer:
    id: str
    name: str
    type: str
    path: str | None = None
    visible: bool = True
    zorder: int = 0
    opacity: float = 1.0
    removable: bool = True
    metadata: dict = field(default_factory=dict)


def _sample_layers() -> list[ExistingPreviewLayer]:
    return [
        ExistingPreviewLayer("data-low", "Low data", "raster", zorder=10, removable=False),
        ExistingPreviewLayer("coast", "Coastline", "coastline", zorder=20, removable=False),
        ExistingPreviewLayer("grid", "Graticule", "graticule", zorder=30, removable=False),
        ExistingPreviewLayer("data-high", "High data", "raster", zorder=80),
        ExistingPreviewLayer("bar", "Color scale", "colorbar", zorder=100, removable=False),
    ]


def test_fixed_groups_and_top_item_has_higher_draw_order() -> None:
    model = PreviewLayerTreeModel(_sample_layers())

    labels = [model.data(model.index(row, 0)) for row in range(model.rowCount())]
    assert labels == [spec.label for spec in GROUP_SPECS]
    assert labels == ["Map Decorations", "Vector Overlays", "Data Layers"]

    assert [item.name for item in model.draw_order(GROUP_DATA)] == ["High data", "Low data"]
    emitted = model.to_preview_layers()
    emitted_by_id = {item.id: item for item in emitted}
    assert emitted_by_id["data-high"].zorder > emitted_by_id["data-low"].zorder
    assert [item.name for item in model.render_order()][-1] == "Color scale"


def test_visibility_checkboxes_include_group_tristate_and_accessible_labels() -> None:
    layers = [
        ExistingPreviewLayer("a", "Visible raster", "raster", visible=True, zorder=20),
        ExistingPreviewLayer("b", "Hidden raster", "raster", visible=False, zorder=10),
    ]
    model = PreviewLayerTreeModel(layers)
    group_index = model.group_index(GROUP_DATA)
    first = model.index(0, 0, group_index)

    assert model.flags(first) & Qt.ItemFlag.ItemIsUserCheckable
    assert model.flags(first) & Qt.ItemFlag.ItemIsDragEnabled
    assert model.flags(first) & Qt.ItemFlag.ItemIsEditable
    assert model.data(group_index, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.PartiallyChecked
    assert "Visible raster" in model.data(first, Qt.ItemDataRole.AccessibleTextRole)
    assert "status ready" in model.data(first, Qt.ItemDataRole.AccessibleTextRole)

    individual_changes: list[tuple[str, bool]] = []
    group_changes: list[tuple[str, bool]] = []
    model.layerVisibilityChanged.connect(
        lambda instance_id, visible: individual_changes.append((instance_id, visible))
    )
    model.groupVisibilityChanged.connect(
        lambda group, visible: group_changes.append((group, visible))
    )
    assert model.setData(
        group_index,
        Qt.CheckState.Unchecked,
        Qt.ItemDataRole.CheckStateRole,
    )
    assert individual_changes == []
    assert group_changes == [(GROUP_DATA, False)]

    assert all(not item.visible for item in model.draw_order(GROUP_DATA))
    assert model.data(group_index, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Unchecked

    assert model.setData(first, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
    assert model.layer_record(model.data(first, model.InstanceIdRole)).visible is True
    assert model.data(group_index, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.PartiallyChecked


def test_drag_drop_reorders_with_top_is_higher_semantics() -> None:
    model = PreviewLayerTreeModel(
        [
            ExistingPreviewLayer("top", "Top", "raster", zorder=30),
            ExistingPreviewLayer("middle", "Middle", "raster", zorder=20),
            ExistingPreviewLayer("bottom", "Bottom", "raster", zorder=10),
        ]
    )
    group_index = model.group_index(GROUP_DATA)
    bottom_index = model.index(2, 0, group_index)
    mime = model.mimeData([bottom_index])

    assert model.canDropMimeData(mime, Qt.DropAction.MoveAction, 0, 0, group_index)
    assert model.dropMimeData(mime, Qt.DropAction.MoveAction, 0, 0, group_index)
    assert [item.name for item in model.draw_order(GROUP_DATA)] == ["Bottom", "Top", "Middle"]

    emitted = {item.name: item.zorder for item in model.to_preview_layers()}
    assert emitted["Bottom"] > emitted["Top"] > emitted["Middle"]
    # Semantic groups are fixed: a raster cannot be dragged into vectors.
    assert not model.canDropMimeData(
        mime,
        Qt.DropAction.MoveAction,
        0,
        0,
        model.group_index(GROUP_VECTORS),
    )

    # The convenience API accepts a final visual row rather than Qt's
    # insertion-before coordinate.
    middle_id = next(
        item.instance_id for item in model.draw_order(GROUP_DATA) if item.name == "Middle"
    )
    assert model.move_layer(middle_id, 0)
    assert [item.name for item in model.draw_order(GROUP_DATA)] == ["Middle", "Bottom", "Top"]


def test_serialization_round_trip_is_json_compatible_and_preserves_metadata() -> None:
    layer = ExistingPreviewLayer(
        "monthly",
        "Monthly EWH",
        "raster",
        path="C:/science/monthly.mat",
        zorder=15,
        opacity=0.65,
        metadata={
            "status": "warning",
            "legend": {"kind": "ramp", "stops": ((0, "#2166ac"), (1, "#b2182b"))},
            "months": ("2002-04", "2002-05"),
        },
    )
    model = PreviewLayerTreeModel([layer])
    payload = model.to_dict()

    serialized = json.dumps(payload, ensure_ascii=False)
    restored = PreviewLayerTreeModel.from_dict(json.loads(serialized))
    record = restored.draw_order(GROUP_DATA)[0]

    assert payload["order_semantics"] == "top-is-higher"
    assert record.layer_id == "monthly"
    assert record.path == "C:/science/monthly.mat"
    assert record.opacity == 0.65
    assert record.status == "warning"
    assert record.legend["kind"] == "ramp"
    assert record.metadata["months"] == ["2002-04", "2002-05"]
    assert restored.to_dict() == payload


def test_retired_preview_month_tolerance_metadata_is_not_serialized() -> None:
    layer = ExistingPreviewLayer(
        "legacy",
        "Legacy overlay",
        "raster",
        metadata={
            "active_var": "ewh",
            "time_tolerance_months": 3,
            "month_tolerance": 2,
        },
    )
    model = PreviewLayerTreeModel([layer])
    record = model.draw_order(GROUP_DATA)[0]

    assert record.metadata == {"active_var": "ewh"}
    assert not model.update_layer_metadata(
        record.instance_id,
        {"time_tolerance_months": 5},
    )
    assert "time_tolerance_months" not in model.to_dict()["groups"][2]["layers"][0]["metadata"]


def test_same_path_instances_are_not_deduplicated_and_duplicate_gets_unique_ids() -> None:
    shared = "C:/science/shared.mat"
    model = PreviewLayerTreeModel(
        [
            ExistingPreviewLayer(
                "filtered", "DDK4", "raster", path=shared, zorder=20, removable=False
            ),
            ExistingPreviewLayer("unfiltered", "Unfiltered", "raster", path=shared, zorder=10),
        ]
    )
    before = model.draw_order(GROUP_DATA)
    assert len(before) == 2
    assert {item.path for item in before} == {shared}
    assert len({item.instance_id for item in before}) == 2

    duplicate_id = model.duplicate_layer(before[0].instance_id)
    after = model.draw_order(GROUP_DATA)
    assert duplicate_id is not None
    assert len(after) == 3
    assert [item.path for item in after].count(shared) == 3
    assert len({item.instance_id for item in after}) == 3
    assert len({item.layer_id for item in after}) == 3
    assert model.layer_record(duplicate_id).removable is True


def test_adapter_accepts_mappings_and_emits_existing_preview_layer_factory() -> None:
    model = PreviewLayerTreeModel.from_preview_layers(
        [
            {
                "id": "basin",
                "name": "Yangtze basin",
                "type": "shapefile",
                "path": "C:/science/yangtze.shp",
                "visible": True,
                "zorder": 50,
                "opacity": 0.8,
                "removable": True,
                "metadata": {"field": "NAME"},
            }
        ]
    )
    record = model.draw_order(GROUP_VECTORS)[0]
    assert record.name == "Yangtze basin"
    assert model.draw_order(GROUP_DECORATIONS) == []

    emitted = model.to_preview_layers(ExistingPreviewLayer)
    assert len(emitted) == 1
    assert isinstance(emitted[0], ExistingPreviewLayer)
    assert emitted[0].path == "C:/science/yangtze.shp"
    assert emitted[0].metadata["layer_tree_group"] == GROUP_VECTORS


def test_context_action_api_rejects_groups_and_nonremovable_layers() -> None:
    model = PreviewLayerTreeModel(
        [ExistingPreviewLayer("locked", "Locked", "raster", removable=False)]
    )
    record = model.draw_order(GROUP_DATA)[0]
    assert model.request_rename(record.instance_id)
    assert model.request_duplicate(record.instance_id)
    assert model.request_zoom(record.instance_id)
    assert model.request_properties(record.instance_id)
    assert model.request_context_action("move_up", record.instance_id)
    assert model.request_context_action("move_down", record.instance_id)
    assert model.request_context_action("move_top", record.instance_id)
    assert not model.request_remove(record.instance_id)
    assert not model.request_rename(QModelIndex())
