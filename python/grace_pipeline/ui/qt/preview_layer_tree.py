"""Reusable, GIS-style layer tree for the preview canvas.

The module deliberately has no dependency on :mod:`controller`.  It accepts
any ``PreviewLayer``-like object exposing the usual attributes and can emit
objects through a caller supplied factory.  This keeps the model usable while
the current preview controller is incrementally migrated from its table-based
layer list.

Layer order follows the convention used by QGIS and ArcGIS: an item nearer the
top of the tree has a higher draw order.  Fixed semantic groups are displayed
from foreground to background (decorations, vector overlays, data layers).
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence
from uuid import uuid4

from PySide6.QtCore import (
    QAbstractItemModel,
    QByteArray,
    QMimeData,
    QModelIndex,
    QObject,
    Qt,
    Signal,
)
from PySide6.QtGui import QAction, QFont, QKeySequence, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QMenu,
    QTreeView,
    QWidget,
)

from grace_pipeline.ui.qt.design_system import ICON_REGISTRY

SCHEMA_VERSION = 1
MIME_TYPE = "application/x-grace-preview-layer-instance-ids"

GROUP_DECORATIONS = "decorations"
GROUP_VECTORS = "vectors"
GROUP_DATA = "data"


@dataclass(frozen=True)
class LayerGroupSpec:
    """Definition for one fixed, semantic layer group."""

    key: str
    label: str
    description: str


# Foreground first: the top group and top child always have the higher draw
# order.  The public group labels are intentionally stable serialization/UI
# contracts rather than translated strings.
GROUP_SPECS: tuple[LayerGroupSpec, ...] = (
    LayerGroupSpec(
        GROUP_DECORATIONS,
        "Map Decorations",
        "Legends, color scales, graticules, annotations, and map furniture",
    ),
    LayerGroupSpec(
        GROUP_VECTORS,
        "Vector Overlays",
        "Coastlines, boundaries, points, lines, and polygons",
    ),
    LayerGroupSpec(
        GROUP_DATA,
        "Data Layers",
        "GRACE grids and other raster data",
    ),
)

_GROUP_BY_KEY = {spec.key: spec for spec in GROUP_SPECS}

_DECORATION_TYPES = {
    "annotation",
    "colorbar",
    "compass",
    "decoration",
    "graticule",
    "grid",
    "legend",
    "north_arrow",
    "scalebar",
    "scale_bar",
    "title",
}
_VECTOR_TYPES = {
    "boundary",
    "coastline",
    "feature",
    "line",
    "mask",
    "point",
    "polygon",
    "shapefile",
    "vector",
}


def group_for_layer_type(layer_type: str) -> str:
    """Return the semantic group for a layer type.

    Unknown types are treated as data rather than decorations so scientific
    content never silently acquires foreground/map-furniture semantics.
    """

    normalized = str(layer_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in _DECORATION_TYPES:
        return GROUP_DECORATIONS
    if normalized in _VECTOR_TYPES:
        return GROUP_VECTORS
    return GROUP_DATA


def _json_safe(value: Any) -> Any:
    """Recursively convert common Python values to JSON-compatible values."""

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    # Metadata should remain inspectable even when a plugin supplied an enum or
    # another small value object.  String fallback also guarantees json.dumps.
    return str(value)


def _read_attr(source: Any, name: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(name, default)
    return getattr(source, name, default)


_LEGACY_PREVIEW_TIME_METADATA_KEYS = {
    "time_tolerance_months",
    "month_tolerance",
}


def _preview_metadata(value: Any) -> dict[str, Any]:
    """Drop retired preview-only month tolerance keys during every import."""

    metadata = dict(value or {})
    for key in _LEGACY_PREVIEW_TIME_METADATA_KEYS:
        metadata.pop(key, None)
    return metadata


@dataclass
class PreviewLayerAdapter:
    """Controller-compatible value returned when no output factory is given."""

    id: str
    name: str
    type: str
    path: Optional[str] = None
    visible: bool = True
    zorder: int = 0
    opacity: float = 1.0
    removable: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LayerTreeRecord:
    """Qt-independent state for one layer instance in the tree."""

    instance_id: str
    layer_id: str
    name: str
    layer_type: str
    group: str
    path: Optional[str] = None
    visible: bool = True
    opacity: float = 1.0
    removable: bool = True
    status: str = "ready"
    legend: Any = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    zorder_hint: int = 0

    @classmethod
    def from_preview_layer(
        cls,
        source: Any,
        *,
        group: Optional[str] = None,
        instance_id: Optional[str] = None,
    ) -> "LayerTreeRecord":
        metadata = _preview_metadata(_read_attr(source, "metadata", {}))
        layer_type = str(_read_attr(source, "type", _read_attr(source, "layer_type", "raster")))
        requested_group = (
            group
            or _read_attr(source, "group", None)
            or metadata.get("layer_tree_group")
            or metadata.get("_layer_tree_group")
        )
        resolved_group = (
            str(requested_group)
            if str(requested_group or "") in _GROUP_BY_KEY
            else group_for_layer_type(layer_type)
        )
        raw_id = _read_attr(source, "id", _read_attr(source, "layer_id", "layer"))
        name = str(_read_attr(source, "name", raw_id or "Layer") or "Layer")
        raw_path = _read_attr(source, "path", None)
        status = _read_attr(source, "status", metadata.get("status", "ready"))
        legend = _read_attr(source, "legend", metadata.get("legend", {}))
        return cls(
            instance_id=str(instance_id or _read_attr(source, "instance_id", "") or uuid4()),
            layer_id=str(raw_id or "layer"),
            name=name,
            layer_type=layer_type,
            group=resolved_group,
            path=None if raw_path in (None, "") else str(raw_path),
            visible=bool(_read_attr(source, "visible", True)),
            opacity=max(0.0, min(1.0, float(_read_attr(source, "opacity", 1.0) or 0.0))),
            removable=bool(_read_attr(source, "removable", True)),
            status=str(status or "ready"),
            legend=copy.deepcopy(legend),
            metadata=copy.deepcopy(metadata),
            zorder_hint=int(
                _read_attr(source, "zorder", _read_attr(source, "zorder_hint", 0)) or 0
            ),
        )

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, Any], *, default_group: Optional[str] = None
    ) -> "LayerTreeRecord":
        layer_type = str(payload.get("type", payload.get("layer_type", "raster")))
        requested_group = str(payload.get("group", default_group or ""))
        group = (
            requested_group
            if requested_group in _GROUP_BY_KEY
            else group_for_layer_type(layer_type)
        )
        layer_id = str(payload.get("id", payload.get("layer_id", "layer")) or "layer")
        raw_path = payload.get("path")
        return cls(
            instance_id=str(payload.get("instance_id") or uuid4()),
            layer_id=layer_id,
            name=str(payload.get("name") or layer_id or "Layer"),
            layer_type=layer_type,
            group=group,
            path=None if raw_path in (None, "") else str(raw_path),
            visible=bool(payload.get("visible", True)),
            opacity=max(0.0, min(1.0, float(payload.get("opacity", 1.0) or 0.0))),
            removable=bool(payload.get("removable", True)),
            status=str(payload.get("status") or "ready"),
            legend=copy.deepcopy(payload.get("legend", {})),
            metadata=copy.deepcopy(_preview_metadata(payload.get("metadata", {}))),
            zorder_hint=int(payload.get("zorder", payload.get("zorder_hint", 0)) or 0),
        )

    def to_dict(self, *, zorder: int) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "id": self.layer_id,
            "name": self.name,
            "type": self.layer_type,
            "group": self.group,
            "path": self.path,
            "visible": self.visible,
            "zorder": int(zorder),
            "opacity": float(self.opacity),
            "removable": self.removable,
            "status": self.status,
            "legend": _json_safe(self.legend),
            "metadata": _json_safe(self.metadata),
        }


class _Node:
    def __init__(
        self,
        *,
        parent: Optional["_Node"] = None,
        group_spec: Optional[LayerGroupSpec] = None,
        record: Optional[LayerTreeRecord] = None,
    ) -> None:
        self.parent = parent
        self.group_spec = group_spec
        self.record = record
        self.children: list[_Node] = []

    @property
    def is_group(self) -> bool:
        return self.group_spec is not None

    def row(self) -> int:
        if self.parent is None:
            return 0
        try:
            return self.parent.children.index(self)
        except ValueError:
            return 0


class PreviewLayerTreeModel(QAbstractItemModel):
    """Single-column semantic layer tree with explicit draw-order behavior."""

    InstanceIdRole = int(Qt.ItemDataRole.UserRole) + 1
    LayerIdRole = int(Qt.ItemDataRole.UserRole) + 2
    GroupRole = int(Qt.ItemDataRole.UserRole) + 3
    LayerTypeRole = int(Qt.ItemDataRole.UserRole) + 4
    PathRole = int(Qt.ItemDataRole.UserRole) + 5
    StatusRole = int(Qt.ItemDataRole.UserRole) + 6
    LegendRole = int(Qt.ItemDataRole.UserRole) + 7
    MetadataRole = int(Qt.ItemDataRole.UserRole) + 8
    OpacityRole = int(Qt.ItemDataRole.UserRole) + 9
    RemovableRole = int(Qt.ItemDataRole.UserRole) + 10
    IsGroupRole = int(Qt.ItemDataRole.UserRole) + 11

    layerVisibilityChanged = Signal(str, bool)
    groupVisibilityChanged = Signal(str, bool)
    layerRenamed = Signal(str, str)
    layerAdded = Signal(str)
    layerRemoved = Signal(str)
    layerDuplicated = Signal(str, str)
    layerOrderChanged = Signal()
    layerStatusChanged = Signal(str, str)
    layerLegendChanged = Signal(str)
    layerOpacityChanged = Signal(str, float)
    layerMetadataChanged = Signal(str)

    contextActionRequested = Signal(str, str)
    renameRequested = Signal(str)
    removeRequested = Signal(str)
    duplicateRequested = Signal(str)
    zoomRequested = Signal(str)
    propertiesRequested = Signal(str)
    moveUpRequested = Signal(str)
    moveDownRequested = Signal(str)
    moveTopRequested = Signal(str)

    _ACTION_SIGNALS = {
        "rename": "renameRequested",
        "remove": "removeRequested",
        "duplicate": "duplicateRequested",
        "zoom": "zoomRequested",
        "properties": "propertiesRequested",
        "move_up": "moveUpRequested",
        "move_down": "moveDownRequested",
        "move_top": "moveTopRequested",
    }

    def __init__(
        self,
        layers: Optional[Iterable[Any]] = None,
        parent: Optional[QObject] = None,
        *,
        translator: Optional[Callable[[str], str]] = None,
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self._root = _Node()
        self._groups: dict[str, _Node] = {}
        self._instances: dict[str, _Node] = {}
        for spec in GROUP_SPECS:
            node = _Node(parent=self._root, group_spec=spec)
            self._root.children.append(node)
            self._groups[spec.key] = node
        if layers is not None:
            self.replace_from_preview_layers(layers)

    # -- QAbstractItemModel implementation ---------------------------------
    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 1

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid() and parent.column() != 0:
            return 0
        node = self._node(parent)
        return len(node.children)

    def index(
        self,
        row: int,
        column: int,
        parent: QModelIndex = QModelIndex(),
    ) -> QModelIndex:
        if column != 0 or row < 0:
            return QModelIndex()
        parent_node = self._node(parent)
        if row >= len(parent_node.children):
            return QModelIndex()
        return self.createIndex(row, column, parent_node.children[row])

    def parent(self, child: QModelIndex = QModelIndex()) -> QModelIndex:
        if not child.isValid():
            return QModelIndex()
        node = self._node(child)
        parent_node = node.parent
        if parent_node is None or parent_node is self._root:
            return QModelIndex()
        return self.createIndex(parent_node.row(), 0, parent_node)

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)) -> Any:
        if not index.isValid():
            return None
        node = self._node(index)
        if node.is_group:
            return self._group_data(node, role)
        return self._layer_data(node, role)

    def setData(
        self, index: QModelIndex, value: Any, role: int = int(Qt.ItemDataRole.EditRole)
    ) -> bool:  # noqa: N802
        if not index.isValid():
            return False
        node = self._node(index)
        if role == int(Qt.ItemDataRole.CheckStateRole):
            visible = value in (Qt.CheckState.Checked, Qt.CheckState.Checked.value)
            if node.is_group:
                return self._set_group_visibility(node, visible)
            record = node.record
            return (
                False if record is None else self.set_layer_visibility(record.instance_id, visible)
            )
        if (
            role in (int(Qt.ItemDataRole.EditRole), int(Qt.ItemDataRole.DisplayRole))
            and not node.is_group
        ):
            record = node.record
            return False if record is None else self.rename_layer(record.instance_id, str(value))
        return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        node = self._node(index)
        if node.is_group:
            return (
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsDropEnabled
            )
        return (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEditable
            | Qt.ItemFlag.ItemIsUserCheckable
            | Qt.ItemFlag.ItemIsDragEnabled
            | Qt.ItemFlag.ItemNeverHasChildren
        )

    def roleNames(self) -> dict[int, QByteArray]:  # noqa: N802
        roles = dict(super().roleNames())
        roles.update(
            {
                self.InstanceIdRole: QByteArray(b"instanceId"),
                self.LayerIdRole: QByteArray(b"layerId"),
                self.GroupRole: QByteArray(b"group"),
                self.LayerTypeRole: QByteArray(b"layerType"),
                self.PathRole: QByteArray(b"path"),
                self.StatusRole: QByteArray(b"status"),
                self.LegendRole: QByteArray(b"legend"),
                self.MetadataRole: QByteArray(b"metadata"),
                self.OpacityRole: QByteArray(b"opacity"),
                self.RemovableRole: QByteArray(b"removable"),
                self.IsGroupRole: QByteArray(b"isGroup"),
            }
        )
        return roles

    def mimeTypes(self) -> list[str]:  # noqa: N802
        return [MIME_TYPE]

    def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:  # noqa: N802
        mime = QMimeData()
        ordered: list[str] = []
        for index in indexes:
            if not index.isValid() or index.column() != 0:
                continue
            node = self._node(index)
            if node.is_group or node.record.instance_id in ordered:  # type: ignore[union-attr]
                continue
            ordered.append(node.record.instance_id)  # type: ignore[union-attr]
        mime.setData(MIME_TYPE, QByteArray(json.dumps(ordered).encode("utf-8")))
        return mime

    def canDropMimeData(  # noqa: N802
        self,
        data: QMimeData,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex,
    ) -> bool:
        if action == Qt.DropAction.IgnoreAction:
            return True
        if action != Qt.DropAction.MoveAction or column not in (-1, 0):
            return False
        target = self._node(parent)
        if not parent.isValid() or not target.is_group:
            return False
        instance_ids = self._decode_mime(data)
        if not instance_ids:
            return False
        return all(
            instance_id in self._instances and self._instances[instance_id].parent is target
            for instance_id in instance_ids
        )

    def dropMimeData(  # noqa: N802
        self,
        data: QMimeData,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex,
    ) -> bool:
        if action == Qt.DropAction.IgnoreAction:
            return True
        if not self.canDropMimeData(data, action, row, column, parent):
            return False
        target = self._node(parent)
        instance_ids = self._decode_mime(data)
        nodes = [self._instances[item] for item in instance_ids]
        current_rows = sorted(node.row() for node in nodes)
        destination = len(target.children) if row < 0 else max(0, min(row, len(target.children)))

        # Qt can move a contiguous selection with one beginMoveRows operation.
        if current_rows == list(range(current_rows[0], current_rows[0] + len(current_rows))):
            return self.moveRows(parent, current_rows[0], len(current_rows), parent, destination)

        # Non-contiguous selections are uncommon for this single-selection
        # view, but keeping them deterministic makes the model reusable.
        self.beginResetModel()
        selected = [node for node in target.children if node in nodes]
        before_destination = sum(1 for node in selected if node.row() < destination)
        target.children = [node for node in target.children if node not in nodes]
        destination = max(0, min(destination - before_destination, len(target.children)))
        for offset, node in enumerate(selected):
            target.children.insert(destination + offset, node)
        self.endResetModel()
        self.layerOrderChanged.emit()
        return True

    def moveRows(  # noqa: N802
        self,
        source_parent: QModelIndex,
        source_row: int,
        count: int,
        destination_parent: QModelIndex,
        destination_child: int,
    ) -> bool:
        source = self._node(source_parent)
        destination = self._node(destination_parent)
        if (
            not source_parent.isValid()
            or not destination_parent.isValid()
            or not source.is_group
            or source is not destination
            or count <= 0
            or source_row < 0
            or source_row + count > len(source.children)
            or destination_child < 0
            or destination_child > len(source.children)
            or source_row <= destination_child <= source_row + count
        ):
            return False
        if not self.beginMoveRows(
            source_parent,
            source_row,
            source_row + count - 1,
            destination_parent,
            destination_child,
        ):
            return False
        moving = source.children[source_row : source_row + count]
        del source.children[source_row : source_row + count]
        insertion = (
            destination_child - count if destination_child > source_row else destination_child
        )
        for offset, node in enumerate(moving):
            source.children.insert(insertion + offset, node)
        self.endMoveRows()
        self.layerOrderChanged.emit()
        return True

    def supportedDropActions(self) -> Qt.DropAction:  # noqa: N802
        return Qt.DropAction.MoveAction

    def supportedDragActions(self) -> Qt.DropAction:  # noqa: N802
        return Qt.DropAction.MoveAction

    # -- Layer access and modification APIs --------------------------------
    def group_index(self, group: str) -> QModelIndex:
        node = self._groups.get(group)
        if node is None:
            return QModelIndex()
        return self.createIndex(node.row(), 0, node)

    def index_for_instance(self, instance_id: str) -> QModelIndex:
        node = self._instances.get(str(instance_id))
        if node is None:
            return QModelIndex()
        return self.createIndex(node.row(), 0, node)

    def layer_record(self, instance_id: str) -> Optional[LayerTreeRecord]:
        node = self._instances.get(str(instance_id))
        return node.record if node is not None else None

    def draw_order(
        self, group: Optional[str] = None, *, visible_only: bool = False
    ) -> list[LayerTreeRecord]:
        """Return records from highest to lowest draw order (tree top first)."""

        groups = [self._groups[group]] if group in self._groups else self._root.children
        records = [node.record for group_node in groups for node in group_node.children]
        if visible_only:
            records = [record for record in records if record.visible]
        return records

    def render_order(self, *, visible_only: bool = False) -> list[LayerTreeRecord]:
        """Return records in painter order (lowest first, foreground last)."""

        return list(reversed(self.draw_order(visible_only=visible_only)))

    def replace_from_preview_layers(self, layers: Iterable[Any]) -> None:
        """Replace contents from controller-compatible objects or mappings."""

        records: list[tuple[int, LayerTreeRecord]] = []
        for position, layer in enumerate(layers):
            records.append((position, LayerTreeRecord.from_preview_layer(layer)))
        self.beginResetModel()
        for group in self._groups.values():
            group.children.clear()
        self._instances.clear()
        used_layer_ids: set[str] = set()
        used_instance_ids: set[str] = set()
        for group_key, group_node in self._groups.items():
            matching = [
                (position, record) for position, record in records if record.group == group_key
            ]
            matching.sort(key=lambda item: (-item[1].zorder_hint, item[0]))
            for _, record in matching:
                record.instance_id = self._unique_instance_id(record.instance_id, used_instance_ids)
                record.layer_id = self._unique_layer_id(record.layer_id, used_layer_ids)
                used_instance_ids.add(record.instance_id)
                used_layer_ids.add(record.layer_id)
                node = _Node(parent=group_node, record=record)
                group_node.children.append(node)
                self._instances[record.instance_id] = node
        self.endResetModel()

    @classmethod
    def from_preview_layers(
        cls,
        layers: Iterable[Any],
        parent: Optional[QObject] = None,
        *,
        translator: Optional[Callable[[str], str]] = None,
    ) -> "PreviewLayerTreeModel":
        return cls(layers, parent, translator=translator)

    def set_translator(self, translator: Optional[Callable[[str], str]]) -> None:
        """Update translated presentation without mutating serialized names."""

        self._translator = translator
        self.layoutChanged.emit()

    def _tr(self, text: str) -> str:
        if self._translator is None:
            return text
        try:
            return str(self._translator(text))
        except Exception:
            return text

    @staticmethod
    def _icon(name: str):
        application = QApplication.instance()
        color = "#566168"
        if application is not None:
            color = application.palette().color(QPalette.ColorRole.Text).name()
        return ICON_REGISTRY.icon(name, color=color, size=18)

    def add_preview_layer(self, layer: Any, *, group: Optional[str] = None, row: int = 0) -> str:
        record = LayerTreeRecord.from_preview_layer(layer, group=group)
        return self.add_record(record, row=row)

    def add_record(self, record: LayerTreeRecord, *, row: int = 0) -> str:
        group_key = (
            record.group
            if record.group in self._groups
            else group_for_layer_type(record.layer_type)
        )
        record.group = group_key
        record.instance_id = self._unique_instance_id(record.instance_id, set(self._instances))
        record.layer_id = self._unique_layer_id(
            record.layer_id,
            {node.record.layer_id for node in self._instances.values()},
        )
        group_node = self._groups[group_key]
        insertion = max(0, min(int(row), len(group_node.children)))
        parent_index = self.group_index(group_key)
        self.beginInsertRows(parent_index, insertion, insertion)
        node = _Node(parent=group_node, record=record)
        group_node.children.insert(insertion, node)
        self._instances[record.instance_id] = node
        self.endInsertRows()
        self.layerAdded.emit(record.instance_id)
        return record.instance_id

    def rename_layer(self, instance_id: str, name: str) -> bool:
        node = self._instances.get(str(instance_id))
        normalized = str(name).strip()
        if node is None or not normalized or node.record.name == normalized:
            return False
        node.record.name = normalized
        index = self.index_for_instance(instance_id)
        self.dataChanged.emit(
            index,
            index,
            [
                int(Qt.ItemDataRole.DisplayRole),
                int(Qt.ItemDataRole.EditRole),
                int(Qt.ItemDataRole.AccessibleTextRole),
            ],
        )
        self.layerRenamed.emit(node.record.instance_id, normalized)
        return True

    def set_layer_visibility(self, instance_id: str, visible: bool) -> bool:
        node = self._instances.get(str(instance_id))
        if node is None or node.record.visible == bool(visible):
            return False
        node.record.visible = bool(visible)
        index = self.index_for_instance(instance_id)
        self.dataChanged.emit(
            index,
            index,
            [int(Qt.ItemDataRole.CheckStateRole), int(Qt.ItemDataRole.AccessibleTextRole)],
        )
        parent_index = self.group_index(node.record.group)
        self.dataChanged.emit(parent_index, parent_index, [int(Qt.ItemDataRole.CheckStateRole)])
        self.layerVisibilityChanged.emit(node.record.instance_id, node.record.visible)
        return True

    def set_layer_status(self, instance_id: str, status: str) -> bool:
        node = self._instances.get(str(instance_id))
        normalized = str(status or "ready")
        if node is None or node.record.status == normalized:
            return False
        node.record.status = normalized
        index = self.index_for_instance(instance_id)
        self.dataChanged.emit(
            index,
            index,
            [
                self.StatusRole,
                int(Qt.ItemDataRole.ToolTipRole),
                int(Qt.ItemDataRole.AccessibleTextRole),
            ],
        )
        self.layerStatusChanged.emit(node.record.instance_id, normalized)
        return True

    def set_layer_legend(self, instance_id: str, legend: Any) -> bool:
        node = self._instances.get(str(instance_id))
        if node is None or node.record.legend == legend:
            return False
        node.record.legend = copy.deepcopy(legend)
        index = self.index_for_instance(instance_id)
        self.dataChanged.emit(index, index, [self.LegendRole])
        self.layerLegendChanged.emit(node.record.instance_id)
        return True

    def set_layer_opacity(self, instance_id: str, opacity: float) -> bool:
        node = self._instances.get(str(instance_id))
        if node is None:
            return False
        normalized = max(0.0, min(1.0, float(opacity)))
        if abs(node.record.opacity - normalized) < 1e-12:
            return False
        node.record.opacity = normalized
        index = self.index_for_instance(instance_id)
        self.dataChanged.emit(
            index,
            index,
            [self.OpacityRole, int(Qt.ItemDataRole.ToolTipRole)],
        )
        self.layerOpacityChanged.emit(node.record.instance_id, normalized)
        return True

    def update_layer_metadata(self, instance_id: str, values: Mapping[str, Any]) -> bool:
        node = self._instances.get(str(instance_id))
        if node is None:
            return False
        updates = copy.deepcopy(_preview_metadata(values))
        if not updates:
            return False
        changed = any(node.record.metadata.get(key) != value for key, value in updates.items())
        if not changed:
            return False
        node.record.metadata.update(updates)
        index = self.index_for_instance(instance_id)
        self.dataChanged.emit(index, index, [self.MetadataRole, int(Qt.ItemDataRole.ToolTipRole)])
        self.layerMetadataChanged.emit(node.record.instance_id)
        return True

    def remove_layer(self, instance_id: str, *, force: bool = False) -> bool:
        node = self._instances.get(str(instance_id))
        if node is None or (not node.record.removable and not force):
            return False
        parent = node.parent
        row = node.row()
        parent_index = self.group_index(node.record.group)
        self.beginRemoveRows(parent_index, row, row)
        parent.children.pop(row)
        del self._instances[node.record.instance_id]
        self.endRemoveRows()
        self.layerRemoved.emit(node.record.instance_id)
        return True

    def duplicate_layer(self, instance_id: str, *, name: Optional[str] = None) -> Optional[str]:
        node = self._instances.get(str(instance_id))
        if node is None:
            return None
        original = node.record
        duplicate = copy.deepcopy(original)
        duplicate.instance_id = str(uuid4())
        duplicate.layer_id = self._unique_layer_id(
            f"{original.layer_id}-copy",
            {item.record.layer_id for item in self._instances.values()},
        )
        duplicate.name = str(name or f"{original.name} (copy)")
        # A protected built-in source may be duplicated for comparison, but
        # the user-created copy must always remain removable.
        duplicate.removable = True
        new_id = self.add_record(duplicate, row=node.row() + 1)
        self.layerDuplicated.emit(original.instance_id, new_id)
        return new_id

    def move_layer(self, instance_id: str, destination_row: int) -> bool:
        """Move a layer to a zero-based final row within its semantic group."""

        node = self._instances.get(str(instance_id))
        if node is None:
            return False
        source_row = node.row()
        final_row = max(0, min(int(destination_row), len(node.parent.children) - 1))
        if source_row == final_row:
            return False
        group_index = self.group_index(node.record.group)
        qt_destination = final_row + 1 if final_row > source_row else final_row
        return self.moveRows(group_index, source_row, 1, group_index, qt_destination)

    # -- Context-action contract -------------------------------------------
    def request_context_action(self, action: str, target: Any) -> bool:
        """Emit a typed context request for an index or instance id.

        Rename/remove/duplicate are requests so a controller may confirm or
        augment them.  Direct mutation APIs with matching names are provided
        above for consumers that do not need confirmation.
        """

        normalized = str(action).strip().lower()
        if normalized not in self._ACTION_SIGNALS:
            return False
        instance_id = self._instance_id_from_target(target)
        node = self._instances.get(instance_id)
        if node is None or (normalized == "remove" and not node.record.removable):
            return False
        self.contextActionRequested.emit(normalized, instance_id)
        getattr(self, self._ACTION_SIGNALS[normalized]).emit(instance_id)
        return True

    def request_rename(self, target: Any) -> bool:
        return self.request_context_action("rename", target)

    def request_remove(self, target: Any) -> bool:
        return self.request_context_action("remove", target)

    def request_duplicate(self, target: Any) -> bool:
        return self.request_context_action("duplicate", target)

    def request_zoom(self, target: Any) -> bool:
        return self.request_context_action("zoom", target)

    def request_properties(self, target: Any) -> bool:
        return self.request_context_action("properties", target)

    # -- Serialization and adapter APIs ------------------------------------
    def to_dict(self) -> dict[str, Any]:
        zorders = self._zorders()
        return {
            "schema": "grace-preview-layer-tree",
            "schema_version": SCHEMA_VERSION,
            "order_semantics": "top-is-higher",
            "groups": [
                {
                    "id": group.group_spec.key,
                    "name": group.group_spec.label,
                    "layers": [
                        node.record.to_dict(zorder=zorders[node.record.instance_id])
                        for node in group.children
                    ],
                }
                for group in self._root.children
            ],
        }

    def load_dict(self, payload: Mapping[str, Any]) -> None:
        if not isinstance(payload, Mapping):
            raise TypeError("Layer tree payload must be a mapping")
        version = int(payload.get("schema_version", SCHEMA_VERSION))
        if version != SCHEMA_VERSION:
            raise ValueError(f"Unsupported layer tree schema version: {version}")
        raw_groups = payload.get("groups", [])
        if not isinstance(raw_groups, Sequence) or isinstance(raw_groups, (str, bytes, bytearray)):
            raise ValueError("Layer tree 'groups' must be a sequence")
        records: list[LayerTreeRecord] = []
        for raw_group in raw_groups:
            if not isinstance(raw_group, Mapping):
                continue
            group_key = str(raw_group.get("id", ""))
            raw_layers = raw_group.get("layers", [])
            if not isinstance(raw_layers, Sequence) or isinstance(
                raw_layers, (str, bytes, bytearray)
            ):
                continue
            for raw_layer in raw_layers:
                if isinstance(raw_layer, Mapping):
                    records.append(LayerTreeRecord.from_dict(raw_layer, default_group=group_key))
        self.replace_from_preview_layers(records)

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
        parent: Optional[QObject] = None,
    ) -> "PreviewLayerTreeModel":
        model = cls(parent=parent)
        model.load_dict(payload)
        return model

    def to_preview_layers(
        self,
        factory: Optional[Callable[..., Any]] = None,
        *,
        visible_only: bool = False,
    ) -> list[Any]:
        """Emit controller-compatible layers in tree order (top first).

        ``factory`` may be the current controller's ``PreviewLayer`` class.
        It is called only with that legacy class's established keyword fields.
        Assigned z-orders are global and monotonic, so sorting them ascending
        yields the correct painter order while the top tree item remains the
        highest value.
        """

        target = factory or PreviewLayerAdapter
        records = self.draw_order(visible_only=visible_only)
        zorders = self._zorders()
        emitted: list[Any] = []
        for record in records:
            metadata = copy.deepcopy(record.metadata)
            metadata["layer_tree_group"] = record.group
            metadata["_layer_tree_instance_id"] = record.instance_id
            metadata["status"] = record.status
            metadata["legend"] = copy.deepcopy(record.legend)
            emitted.append(
                target(
                    id=record.layer_id,
                    name=record.name,
                    type=record.layer_type,
                    path=record.path,
                    visible=record.visible,
                    zorder=zorders[record.instance_id],
                    opacity=record.opacity,
                    removable=record.removable,
                    metadata=metadata,
                )
            )
        return emitted

    # -- Internal helpers ---------------------------------------------------
    def _node(self, index: QModelIndex) -> _Node:
        if index.isValid():
            pointer = index.internalPointer()
            if isinstance(pointer, _Node):
                return pointer
        return self._root

    def _group_data(self, node: _Node, role: int) -> Any:
        spec = node.group_spec
        if role in (int(Qt.ItemDataRole.DisplayRole), int(Qt.ItemDataRole.EditRole)):
            return self._tr(spec.label)
        if role == int(Qt.ItemDataRole.DecorationRole):
            return self._icon(
                {
                    GROUP_DECORATIONS: "scan-eye",
                    GROUP_VECTORS: "map-pinned",
                    GROUP_DATA: "layout-dashboard",
                }.get(spec.key, "layout-dashboard")
            )
        if role == int(Qt.ItemDataRole.FontRole):
            font = QFont()
            font.setBold(True)
            return font
        if role == int(Qt.ItemDataRole.CheckStateRole):
            visible = sum(1 for child in node.children if child.record.visible)
            if visible == 0:
                return Qt.CheckState.Unchecked
            if visible == len(node.children):
                return Qt.CheckState.Checked
            return Qt.CheckState.PartiallyChecked
        if role == int(Qt.ItemDataRole.ToolTipRole):
            return (
                f"{self._tr(spec.description)}\n"
                f"{len(node.children)} {self._tr('layer(s)')}"
            )
        if role == int(Qt.ItemDataRole.AccessibleTextRole):
            return (
                f"{self._tr(spec.label)}, {self._tr('group')}, "
                f"{len(node.children)} {self._tr('layers')}"
            )
        if role == int(Qt.ItemDataRole.AccessibleDescriptionRole):
            return self._tr(spec.description)
        if role == self.GroupRole:
            return spec.key
        if role == self.IsGroupRole:
            return True
        return None

    def _layer_data(self, node: _Node, role: int) -> Any:
        record = node.record
        if role == int(Qt.ItemDataRole.DisplayRole):
            return self._tr(record.name)
        if role == int(Qt.ItemDataRole.EditRole):
            # Editing always exposes the canonical stored name.  Returning a
            # translated label here would persist Chinese display text into
            # project state merely by opening and accepting the editor.
            return record.name
        if role == int(Qt.ItemDataRole.DecorationRole):
            icon_name = {
                "boundary": "map-pinned",
                "coastline": "map-pinned",
                "shapefile": "map-pinned",
                "graticule": "layout-dashboard",
                "grid": "layout-dashboard",
                "colorbar": "sliders-horizontal",
                "raster": "scan-eye",
            }.get(record.layer_type.lower(), "scan-eye")
            return self._icon(icon_name)
        if role == int(Qt.ItemDataRole.CheckStateRole):
            return Qt.CheckState.Checked if record.visible else Qt.CheckState.Unchecked
        if role == int(Qt.ItemDataRole.ToolTipRole):
            parts = [
                self._tr(record.name),
                f"{self._tr('Type')}: {self._tr(record.layer_type.title())}",
                f"{self._tr('Status')}: {self._tr(record.status.title())}",
            ]
            if record.path:
                parts.append(f"{self._tr('Source')}: {record.path}")
            return "\n".join(parts)
        if role == int(Qt.ItemDataRole.StatusTipRole):
            return record.status
        if role == int(Qt.ItemDataRole.AccessibleTextRole):
            if self._translator is None:
                visibility = "visible" if record.visible else "hidden"
                return (
                    f"{record.name}, {record.layer_type}, {visibility}, "
                    f"status {record.status}"
                )
            visibility = self._tr("Visible") if record.visible else self._tr("Hidden")
            return (
                f"{self._tr(record.name)}, {self._tr(record.layer_type.title())}, "
                f"{visibility}, {self._tr('Status')} {self._tr(record.status.title())}"
            )
        if role == int(Qt.ItemDataRole.AccessibleDescriptionRole):
            return record.path or f"{self._tr(record.layer_type.title())} {self._tr('layer')}"
        if role == self.InstanceIdRole:
            return record.instance_id
        if role == self.LayerIdRole:
            return record.layer_id
        if role == self.GroupRole:
            return record.group
        if role == self.LayerTypeRole:
            return record.layer_type
        if role == self.PathRole:
            return record.path
        if role == self.StatusRole:
            return record.status
        if role == self.LegendRole:
            return copy.deepcopy(record.legend)
        if role == self.MetadataRole:
            return copy.deepcopy(record.metadata)
        if role == self.OpacityRole:
            return record.opacity
        if role == self.RemovableRole:
            return record.removable
        if role == self.IsGroupRole:
            return False
        return None

    def _set_group_visibility(self, group: _Node, visible: bool) -> bool:
        changed = [child for child in group.children if child.record.visible != visible]
        if not changed:
            return False
        for child in changed:
            child.record.visible = visible
        if group.children:
            parent_index = self.group_index(group.group_spec.key)
            first = self.index(0, 0, parent_index)
            last = self.index(len(group.children) - 1, 0, parent_index)
            self.dataChanged.emit(
                first,
                last,
                [int(Qt.ItemDataRole.CheckStateRole), int(Qt.ItemDataRole.AccessibleTextRole)],
            )
        group_index = self.group_index(group.group_spec.key)
        self.dataChanged.emit(group_index, group_index, [int(Qt.ItemDataRole.CheckStateRole)])
        # One group operation must not trigger one expensive map render per
        # child.  Consumers receive a single batch notification after all
        # records and accessibility states are consistent.
        self.groupVisibilityChanged.emit(group.group_spec.key, visible)
        return True

    def _decode_mime(self, mime: QMimeData) -> list[str]:
        if not mime.hasFormat(MIME_TYPE):
            return []
        try:
            parsed = json.loads(bytes(mime.data(MIME_TYPE)).decode("utf-8"))
        except (TypeError, ValueError, UnicodeDecodeError):
            return []
        if not isinstance(parsed, list):
            return []
        return [str(item) for item in parsed]

    def _instance_id_from_target(self, target: Any) -> str:
        if isinstance(target, QModelIndex):
            value = self.data(target, self.InstanceIdRole)
            return str(value or "")
        return str(target or "")

    def _zorders(self) -> dict[str, int]:
        records = self.draw_order()
        total = len(records)
        return {
            record.instance_id: (total - index - 1) * 10 for index, record in enumerate(records)
        }

    @staticmethod
    def _unique_instance_id(candidate: str, used: set[str]) -> str:
        normalized = str(candidate or "")
        if normalized and normalized not in used:
            return normalized
        value = str(uuid4())
        while value in used:
            value = str(uuid4())
        return value

    @staticmethod
    def _unique_layer_id(candidate: str, used: set[str]) -> str:
        base = str(candidate or "layer").strip() or "layer"
        if base not in used:
            return base
        number = 2
        while f"{base}-{number}" in used:
            number += 1
        return f"{base}-{number}"


class PreviewLayerTreeView(QTreeView):
    """Keyboard- and screen-reader-friendly view for the layer tree model."""

    actionRequested = Signal(str, str)
    renameRequested = Signal(str)
    removeRequested = Signal(str)
    duplicateRequested = Signal(str)
    zoomRequested = Signal(str)
    propertiesRequested = Signal(str)
    moveUpRequested = Signal(str)
    moveDownRequested = Signal(str)
    moveTopRequested = Signal(str)

    _ACTION_SIGNALS = {
        "rename": "renameRequested",
        "remove": "removeRequested",
        "duplicate": "duplicateRequested",
        "zoom": "zoomRequested",
        "properties": "propertiesRequested",
        "move_up": "moveUpRequested",
        "move_down": "moveDownRequested",
        "move_top": "moveTopRequested",
    }

    def __init__(
        self,
        model: Optional[PreviewLayerTreeModel] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        if model is not None:
            self.setModel(model)
        self.setObjectName("PreviewLayerTree")
        self.setAccessibleName("Preview layers")
        self.setAccessibleDescription(
            "Map layers grouped by type. Layers nearer the top draw above layers below them."
        )
        self.setHeaderHidden(True)
        self.setRootIsDecorated(True)
        self.setItemsExpandable(True)
        self.setUniformRowHeights(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._translator: Optional[Callable[[str], str]] = None

    def set_translator(self, translator: Optional[Callable[[str], str]]) -> None:
        self._translator = translator
        model = self.model()
        if isinstance(model, PreviewLayerTreeModel):
            model.set_translator(translator)
        self.setAccessibleName(self._tr("Preview layers"))
        self.setAccessibleDescription(
            self._tr(
                "Map layers grouped by type. Layers nearer the top draw above layers below them."
            )
        )
        self.viewport().update()

    def _tr(self, text: str) -> str:
        if self._translator is None:
            return text
        try:
            return str(self._translator(text))
        except Exception:
            return text

    def request_action(self, action: str, index: Optional[QModelIndex] = None) -> bool:
        normalized = str(action).strip().lower()
        if normalized not in self._ACTION_SIGNALS:
            return False
        target = index if index is not None and index.isValid() else self.currentIndex()
        model = self.model()
        if not target.isValid() or not isinstance(model, PreviewLayerTreeModel):
            return False
        instance_id = str(model.data(target, model.InstanceIdRole) or "")
        if not instance_id:
            return False
        if not self._action_enabled(normalized, target, model):
            return False
        self.actionRequested.emit(normalized, instance_id)
        getattr(self, self._ACTION_SIGNALS[normalized]).emit(instance_id)
        model.request_context_action(normalized, instance_id)
        if normalized == "rename":
            self.edit(target)
        return True

    @staticmethod
    def _action_enabled(
        action: str,
        index: QModelIndex,
        model: PreviewLayerTreeModel,
    ) -> bool:
        if action == "remove":
            return bool(model.data(index, model.RemovableRole))
        if action in {"move_up", "move_top"}:
            return index.row() > 0
        if action == "move_down":
            return index.row() < model.rowCount(index.parent()) - 1
        return True

    def build_context_menu(self, index: QModelIndex) -> QMenu:
        """Build the layer menu separately so behavior is testable without UI automation."""

        menu = QMenu(self)
        menu.setObjectName("PreviewLayerContextMenu")
        groups = (
            (
                ("properties", "Properties", QKeySequence("Alt+Return")),
                ("rename", "Rename", QKeySequence(Qt.Key.Key_F2)),
                ("duplicate", "Duplicate", QKeySequence("Ctrl+D")),
            ),
            (
                ("move_up", "Move up", QKeySequence("Alt+Up")),
                ("move_down", "Move down", QKeySequence("Alt+Down")),
                ("move_top", "Move to top", QKeySequence("Ctrl+Shift+Up")),
            ),
            (
                ("zoom", "Zoom to Layer", QKeySequence("Z")),
                ("remove", "Delete", QKeySequence(Qt.Key.Key_Delete)),
            ),
        )
        model = self.model()
        if not isinstance(model, PreviewLayerTreeModel):
            return menu
        for group_number, actions in enumerate(groups):
            if group_number:
                menu.addSeparator()
            for action_name, label, shortcut in actions:
                action = QAction(self._tr(label), menu)
                action.setShortcut(shortcut)
                action.setData(action_name)
                action.setEnabled(self._action_enabled(action_name, index, model))
                action.triggered.connect(
                    lambda checked=False, name=action_name, target=index: self.request_action(
                        name, target
                    )
                )
                menu.addAction(action)
        return menu

    def contextMenuEvent(self, event: Any) -> None:  # noqa: N802
        index = self.indexAt(event.pos())
        model = self.model()
        if not index.isValid() or not isinstance(model, PreviewLayerTreeModel):
            return
        if not model.data(index, model.InstanceIdRole):
            return
        self.setCurrentIndex(index)
        menu = self.build_context_menu(index)
        menu.exec(event.globalPos())

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802
        index = self.currentIndex()
        model = self.model()
        key = event.key()
        modifiers = event.modifiers()
        if isinstance(model, PreviewLayerTreeModel) and index.isValid():
            if key == Qt.Key.Key_Space:
                current = model.data(index, int(Qt.ItemDataRole.CheckStateRole))
                next_state = (
                    Qt.CheckState.Unchecked
                    if current in (Qt.CheckState.Checked, Qt.CheckState.Checked.value)
                    else Qt.CheckState.Checked
                )
                if model.setData(index, next_state, int(Qt.ItemDataRole.CheckStateRole)):
                    event.accept()
                    return
            if key == Qt.Key.Key_F2 and self.request_action("rename", index):
                event.accept()
                return
            if key == Qt.Key.Key_Delete and self.request_action("remove", index):
                event.accept()
                return
            if key == Qt.Key.Key_D and modifiers & Qt.KeyboardModifier.ControlModifier:
                if self.request_action("duplicate", index):
                    event.accept()
                    return
            if (
                key in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and modifiers & Qt.KeyboardModifier.AltModifier
            ):
                if self.request_action("properties", index):
                    event.accept()
                    return
            if key == Qt.Key.Key_Z and modifiers == Qt.KeyboardModifier.NoModifier:
                if self.request_action("zoom", index):
                    event.accept()
                    return
            if key == Qt.Key.Key_Up and modifiers & Qt.KeyboardModifier.AltModifier:
                if self.request_action("move_up", index):
                    event.accept()
                    return
            if key == Qt.Key.Key_Down and modifiers & Qt.KeyboardModifier.AltModifier:
                if self.request_action("move_down", index):
                    event.accept()
                    return
            if (
                key == Qt.Key.Key_Up
                and modifiers & Qt.KeyboardModifier.ControlModifier
                and modifiers & Qt.KeyboardModifier.ShiftModifier
            ):
                if self.request_action("move_top", index):
                    event.accept()
                    return
        super().keyPressEvent(event)


__all__ = [
    "GROUP_DATA",
    "GROUP_DECORATIONS",
    "GROUP_SPECS",
    "GROUP_VECTORS",
    "LayerGroupSpec",
    "LayerTreeRecord",
    "MIME_TYPE",
    "PreviewLayerAdapter",
    "PreviewLayerTreeModel",
    "PreviewLayerTreeView",
    "SCHEMA_VERSION",
    "group_for_layer_type",
]
