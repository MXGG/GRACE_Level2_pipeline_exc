"""Simplified leakage-correction wizard for the Qt GUI."""

from __future__ import annotations

import contextlib
from pathlib import Path
from types import MethodType

import numpy as np
from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from grace_pipeline.ui.plotting.boundaries import boundary_bbox, read_boundary_file
from grace_pipeline.ui.qt.pages import (
    _make_choice_combo,
    _make_compact_field_grid,
    _make_edit_browse_widget,
    _make_field_row,
    _make_line_edit,
    _make_stacked_field,
)
from grace_pipeline.ui.qt.widgets import CardFrame, CollapsibleSection


_REUSED_WIDGET_ATTRS = (
    "chk_leakage_enable",
    "rb_method_fm",
    "rb_method_sf",
    "btn_run_leakage",
    "btn_pause_leakage",
    "btn_stop_leakage",
    "btn_lrc_input_browse",
    "btn_reference_input_browse",
    "btn_regional_boundary_browse",
    "btn_lrc_output_browse",
    "btn_load_leakage_info",
    "btn_open_preview_asset",
    "btn_open_preview_corrected",
    "edit_lrc_input",
    "edit_reference_input",
    "edit_regional_boundary",
    "edit_lrc_output",
    "edit_lrc_sf_factor",
    "edit_operator_autodetect",
    "edit_lrc_gaussian_km",
    "edit_ddk_type",
    "edit_fm_iteration_count",
    "edit_fm_convergence_threshold",
    "edit_fm_acceleration",
    "edit_fm_patience",
    "edit_fm_min_improve",
    "cmb_lrc_format",
    "cmb_scope",
    "cmb_strategy_family",
    "cmb_correction_strategy",
    "cmb_scene_override",
    "cmb_reference_mode",
    "cmb_official_mode",
    "lbl_leakage_info",
    "lbl_dataset_shape_value",
    "lbl_product_type_value",
    "lbl_linkage_status",
    "lbl_operator_value",
    "lbl_scene_value",
    "lbl_recommendation_value",
    "lbl_boundary_status",
    "lbl_preview_status",
    "txt_leakage_notes",
    "badge_product",
    "badge_operator",
    "badge_scene",
    "badge_strategy",
    "card_note",
)


def _is_zh(window) -> bool:
    return getattr(getattr(window, "ui_preferences", None), "language", "en") == "zh"


def _tr(window, en: str, zh: str) -> str:
    return zh if _is_zh(window) else en


def _detach_reused_widgets(page) -> None:
    """Detach reused widgets before clearing the legacy page tree."""

    for attr in _REUSED_WIDGET_ATTRS:
        widget = getattr(page, attr, None)
        if widget is None:
            continue
        with contextlib.suppress(RuntimeError):
            widget.setParent(None)


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.setParent(None)
        elif child_layout is not None:
            _clear_layout(child_layout)


def _combo_set(combo, data_value: str) -> None:
    if combo is None:
        return
    idx = combo.findData(data_value)
    if idx >= 0:
        with QSignalBlocker(combo):
            combo.setCurrentIndex(idx)


def _current_leakage_mode(page) -> str:
    if getattr(page, "rb_lrc_forward_modeling", None) is not None and page.rb_lrc_forward_modeling.isChecked():
        return "forward_modeling"
    if getattr(page, "rb_lrc_basin_scale", None) is not None and page.rb_lrc_basin_scale.isChecked():
        return "basin_scale_factor"
    return "official_gain"


def _sync_hidden_leakage_strategy(page) -> None:
    """Map the simplified radio buttons back to legacy backend controls."""

    mode = _current_leakage_mode(page)
    if mode == "official_gain":
        _combo_set(page.cmb_scope, "global")
        _combo_set(page.cmb_strategy_family, "official")
        _combo_set(page.cmb_correction_strategy, "official_land_scaling")
        _combo_set(page.cmb_official_mode, "land_scaling")
        page.edit_operator_autodetect.setText("Auto")
    elif mode == "basin_scale_factor":
        _combo_set(page.cmb_scope, "regional")
        _combo_set(page.cmb_strategy_family, "regional")
        _combo_set(page.cmb_correction_strategy, "basin_scale_factor")
        _combo_set(page.cmb_reference_mode, "trend")
        page.edit_operator_autodetect.setText("Auto")
    else:
        _combo_set(page.cmb_scope, "regional")
        _combo_set(page.cmb_strategy_family, "regional")
        _combo_set(page.cmb_correction_strategy, "forward_modeling")
        _combo_set(page.cmb_reference_mode, "trend")
        operator_combo = getattr(page, "cmb_lrc_filter_operator", None)
        operator = str(operator_combo.currentData() or "Auto") if operator_combo is not None else "Auto"
        page.edit_operator_autodetect.setText(operator)


def _method_hint(window, mode: str) -> str:
    hints = {
        "official_gain": (
            "Use when an official scaling/gain grid is available on the same or compatible grid. The correction is applied as a grid-wise gain factor.",
            "适用于已经获得官方 scaling/gain grid 的情形。程序按同格网增益因子逐格作用于输入栈。",
        ),
        "basin_scale_factor": (
            "Use for basin, lake, or regional statistics. Provide a boundary and either a reference model stack or a synthetic-unit setup.",
            "适用于流域、湖泊或区域统计。需要提供区域边界，并可输入参考模型栈；若无参考模型，可采用 synthetic unit field 思路计算区域尺度因子。",
        ),
        "forward_modeling": (
            "Advanced regional correction. Provide boundary, filtering operator, Lmax, and a reference or trend field so the program can simulate leakage response.",
            "高级区域校正方法。需要提供区域边界、滤波算子、Lmax 以及参考场或趋势场，用于模拟滤波前后的泄漏响应。",
        ),
    }
    en, zh = hints[mode]
    return _tr(window, en, zh)


def _set_method_panels(page) -> None:
    window = getattr(page, "_leakage_window", None)
    mode = _current_leakage_mode(page)
    is_official = mode == "official_gain"
    is_basin = mode == "basin_scale_factor"
    is_fm = mode == "forward_modeling"

    page.panel_reference_input.setVisible(True)
    page.panel_boundary_input.setVisible(is_basin or is_fm)
    page.panel_basin_scale_options.setVisible(is_basin)
    page.panel_forward_modeling_options.setVisible(is_fm)
    page.lbl_lrc_method_hint.setText(_method_hint(window, mode) if window is not None else _method_hint(page, mode))
    page.lbl_lrc_reference_label.setText(
        _tr(window, "Scaling/Gain Grid", "Scaling/Gain 网格")
        if is_official
        else (_tr(window, "Reference Model Stack", "参考模型栈") if is_basin else _tr(window, "Reference / Trend Field", "参考场 / 趋势场"))
    )
    page.edit_reference_input.setPlaceholderText(
        _tr(window, "Official scaling/gain grid", "官方 scaling/gain 网格")
        if is_official
        else _tr(window, "Optional reference model stack; leave blank for synthetic-unit workflow", "可选参考模型栈；留空时按 synthetic unit field 思路处理")
    )
    _sync_hidden_leakage_strategy(page)


def _shape_text(shape) -> str:
    try:
        vals = [int(v) for v in tuple(shape)]
    except Exception:
        return "-"
    return " x ".join(str(v) for v in vals) if vals else "-"


def _time_text(host, t_arr, nt: int, meta: dict, window=None) -> str:
    try:
        _years, labels = host._resolve_time(t_arr, int(nt), meta=meta or {})
        if labels:
            suffix = _tr(window, "epochs", "期")
            return f"{labels[0]} / {labels[-1]} ({len(labels)} {suffix})"
    except Exception:
        pass
    suffix = _tr(window, "epochs", "期")
    return f"{int(nt)} {suffix}"


def _make_method_card(title: str, desc: str, radio: QRadioButton) -> QFrame:
    card = QFrame()
    card.setObjectName("PageCard")
    card.setMinimumHeight(112)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(8)
    radio.setText(title)
    radio.setCursor(Qt.PointingHandCursor)
    title_font = radio.font()
    title_font.setBold(True)
    radio.setFont(title_font)
    desc_label = QLabel(desc)
    desc_label.setObjectName("PageSubtitle")
    desc_label.setWordWrap(True)
    layout.addWidget(radio)
    layout.addWidget(desc_label)
    layout.addStretch(1)
    return card


def _install_simple_load_handlers(window) -> None:
    page = window.page_leakage
    controller = window.controller

    def load_input_info() -> None:
        try:
            controller.pull_ui_to_host()
            info = controller.host.load_leakage_info()
            shape = tuple(info.get("shape") or ())
            meta = info.get("meta", {}) or {}
            active_var = str(meta.get("active_var") or "ewh")
            nt = int(shape[2]) if len(shape) >= 3 else 1
            lon = np.asarray(info.get("lon"), dtype=float).squeeze()
            lat = np.asarray(info.get("lat"), dtype=float).squeeze()
            page.lbl_leakage_info.setText(_tr(window, "Input loaded", "输入已读取"))
            page.lbl_dataset_shape_value.setText(_shape_text(shape))
            page.lbl_lrc_variable_value.setText(active_var)
            page.lbl_lrc_time_value.setText(_time_text(controller.host, info.get("t"), nt, meta, window))
            if lon.size and lat.size:
                page.lbl_lrc_grid_extent_value.setText(
                    f"lon {float(np.nanmin(lon)):.3g}–{float(np.nanmax(lon)):.3g}, "
                    f"lat {float(np.nanmin(lat)):.3g}–{float(np.nanmax(lat)):.3g}"
                )
            else:
                page.lbl_lrc_grid_extent_value.setText("-")
            page.lbl_linkage_status.setText(
                _tr(
                    window,
                    "Input metadata loaded. Select a correction method and provide the required method-specific files.",
                    "输入元数据已读取。请选择校正方法，并补充该方法所需的数据文件。",
                )
            )
            controller.on_log(f"[LEAKAGE] Input metadata loaded: {page.edit_lrc_input.text().strip()}", "stdout")
        except Exception as exc:
            page.lbl_leakage_info.setText(_tr(window, "Load failed", "读取失败") + f": {exc}")
            page.lbl_linkage_status.setText(_tr(window, "Input loading failed. Check the file path and stack structure.", "输入读取失败，请检查文件路径和栈数据结构。"))
            with contextlib.suppress(Exception):
                controller._show_error(_tr(window, "Leakage correction", "泄漏校正"), str(exc))

    def read_reference_info() -> None:
        path = page.edit_reference_input.text().strip()
        if not path:
            page.lbl_lrc_reference_info.setText(_tr(window, "Reference file is not set.", "尚未设置参考文件。"))
            return
        p = Path(path)
        if not p.exists():
            page.lbl_lrc_reference_info.setText(_tr(window, "Reference file does not exist.", "参考文件不存在。"))
            return
        try:
            info = controller.host.load_stack_info(str(p))
            shape = _shape_text(info.get("shape"))
            meta = info.get("meta", {}) or {}
            page.lbl_lrc_reference_info.setText(_tr(window, "Loaded", "已读取") + f": {shape} | variable={meta.get('active_var', 'auto')}")
        except Exception as exc:
            page.lbl_lrc_reference_info.setText(_tr(window, "Read failed", "读取失败") + f": {exc}")

    def read_boundary_info() -> None:
        path = page.edit_regional_boundary.text().strip()
        if not path:
            page.lbl_lrc_boundary_info.setText(_tr(window, "Boundary file is not set.", "尚未设置边界文件。"))
            return
        try:
            name_field = page.cmb_lrc_boundary_name_field.currentText().strip() or "Name"
            basins = read_boundary_file(path, name_field=name_field)
            page.cmb_lrc_boundary_feature.clear()
            names = []
            for idx, basin in enumerate(basins or []):
                name = str(getattr(basin, "name", "") or f"Feature {idx + 1}").strip()
                names.append(name)
                page.cmb_lrc_boundary_feature.addItem(name, name)
            bbox = boundary_bbox(basins or [])
            bbox_text = ""
            if bbox is not None:
                bbox_text = f" | bbox=({bbox[0]:.3g}, {bbox[1]:.3g}, {bbox[2]:.3g}, {bbox[3]:.3g})"
            page.lbl_lrc_boundary_info.setText(_tr(window, "Loaded", "已读取") + f" {len(names)} " + _tr(window, "boundary feature(s)", "个边界要素") + bbox_text)
        except Exception as exc:
            page.lbl_lrc_boundary_info.setText(_tr(window, "Boundary read failed", "边界读取失败") + f": {exc}")

    with contextlib.suppress(Exception):
        page.btn_load_leakage_info.clicked.disconnect()
    page.btn_load_leakage_info.clicked.connect(load_input_info)
    page.btn_lrc_read_reference.clicked.connect(read_reference_info)
    page.btn_lrc_read_boundary.clicked.connect(read_boundary_info)


def _patch_controller_pull(window) -> None:
    controller = window.controller
    if getattr(controller, "_leakage_wizard_pull_patched", False):
        return
    original_pull = controller.pull_ui_to_host

    def patched_pull_ui_to_host(self):
        page = self.window.page_leakage
        _sync_hidden_leakage_strategy(page)
        original_pull()
        mode = _current_leakage_mode(page)
        self.host.var_lrc_enable.set(True)
        self.host.var_lrc_input.set(page.edit_lrc_input.text().strip())
        self.host.var_lrc_output.set(page.edit_lrc_output.text().strip())
        self.host.var_lrc_fmt.set(str(page.cmb_lrc_format.currentData() or "mat"))
        self.host.var_lrc_boundary.set(page.edit_regional_boundary.text().strip() if mode in {"basin_scale_factor", "forward_modeling"} else "")
        self.host.var_lrc_scope.set("regional" if mode in {"basin_scale_factor", "forward_modeling"} else "global")
        self.host.var_lrc_method.set("FM" if mode == "forward_modeling" else "SF")
        self.host.var_lrc_sf.set(self._safe_float(page.edit_lrc_sf_factor.text(), 1.0))
        self.host.var_lrc_sf_method.set(str(page.cmb_lrc_filter_operator.currentData() or "Auto"))
        self.host.var_lrc_sf_gauss.set(self._safe_float(page.edit_lrc_gaussian_km.text(), 300.0))
        self.host.var_lrc_sf_ddk.set(page.edit_ddk_type.text().strip() or "DDK4")
        self.host.var_lrc_fm_max_iter.set(max(1, int(round(self._safe_float(page.edit_fm_iteration_count.text(), 40.0)))))
        self.host.var_lrc_fm_tol.set(self._safe_float(page.edit_fm_convergence_threshold.text(), 0.01))
        self.host.var_lrc_fm_accel.set(self._safe_float(page.edit_fm_acceleration.text(), 1.1))
        self.host.var_lrc_fm_patience.set(max(0, int(round(self._safe_float(page.edit_fm_patience.text(), 8.0)))))
        self.host.var_lrc_fm_min_improve.set(self._safe_float(page.edit_fm_min_improve.text(), 1.0e-4))
        with contextlib.suppress(Exception):
            lmax = int(round(self._safe_float(page.edit_lrc_lmax.text(), float(self.host.cfg.inversion.Lmax))))
            self.host.cfg.inversion.Lmax = max(2, lmax)
            if isinstance(getattr(self.host.cfg, "_raw", None), dict):
                self.host.cfg._raw.setdefault("inversion", {})["Lmax"] = max(2, lmax)

    controller.pull_ui_to_host = MethodType(patched_pull_ui_to_host, controller)
    controller._leakage_wizard_pull_patched = True


def install_leakage_wizard(window) -> None:
    """Rebuild the visible leakage page into a simpler guided workflow."""

    page = window.page_leakage
    page._leakage_window = window
    _detach_reused_widgets(page)
    _clear_layout(page.body)
    page.add_header(_tr(window, "Leakage Correction", "泄漏校正"))

    for widget in (
        page.chk_leakage_enable,
        page.rb_method_fm,
        page.rb_method_sf,
        page.cmb_scope,
        page.cmb_strategy_family,
        page.cmb_correction_strategy,
        page.cmb_scene_override,
        page.cmb_reference_mode,
        page.cmb_official_mode,
        page.edit_operator_autodetect,
        page.lbl_operator_value,
        page.lbl_scene_value,
        page.lbl_recommendation_value,
        page.lbl_boundary_status,
        page.badge_product,
        page.badge_operator,
        page.badge_scene,
        page.badge_strategy,
    ):
        with contextlib.suppress(Exception):
            widget.hide()

    page.btn_run_leakage.setText(_tr(window, "Run Leakage Correction", "运行泄漏校正"))
    page.btn_pause_leakage.setText(_tr(window, "Pause", "暂停"))
    page.btn_stop_leakage.setText(_tr(window, "Stop", "停止"))
    page.btn_load_leakage_info.setText(_tr(window, "Read Input Metadata", "读取输入信息"))
    page.btn_lrc_input_browse.setText(_tr(window, "Browse", "浏览"))
    page.btn_reference_input_browse.setText(_tr(window, "Browse", "浏览"))
    page.btn_regional_boundary_browse.setText(_tr(window, "Browse", "浏览"))
    page.btn_lrc_output_browse.setText(_tr(window, "Browse", "浏览"))
    page.btn_open_preview_asset.setText(_tr(window, "Open Current Result", "打开当前结果"))
    page.btn_open_preview_corrected.setText(_tr(window, "View Corrected Stack in Preview", "在预览页查看校正栈"))

    card_input = CardFrame(_tr(window, "1. Input grid stack", "1. 输入格网栈"))
    page.edit_lrc_input.setPlaceholderText(_tr(window, "Stack to correct, supports MAT / NC / HDF / TXT", "待校正栈，支持 MAT / NC / HDF / TXT"))
    card_input.body.addWidget(_make_field_row(_tr(window, "Input Stack", "输入栈"), _make_edit_browse_widget(page.edit_lrc_input, page.btn_lrc_input_browse)))
    page.lbl_lrc_variable_value = QLabel("-")
    page.lbl_lrc_time_value = QLabel("-")
    page.lbl_lrc_grid_extent_value = QLabel("-")
    for label in (page.lbl_leakage_info, page.lbl_dataset_shape_value, page.lbl_lrc_variable_value, page.lbl_lrc_time_value, page.lbl_lrc_grid_extent_value):
        label.setWordWrap(True)
    page.lbl_leakage_info.setText(_tr(window, "Input not loaded", "输入未读取"))
    card_input.body.addWidget(
        _make_compact_field_grid(
            [
                (_tr(window, "Input Status", "输入状态"), page.lbl_leakage_info),
                (_tr(window, "Grid Shape", "网格尺寸"), page.lbl_dataset_shape_value),
                (_tr(window, "Data Variable", "数据变量"), page.lbl_lrc_variable_value),
                (_tr(window, "Time Coverage", "时间范围"), page.lbl_lrc_time_value),
                (_tr(window, "Grid Extent", "经纬度范围"), page.lbl_lrc_grid_extent_value),
            ],
            columns=3,
        )
    )
    input_actions = QWidget()
    input_actions_layout = QHBoxLayout(input_actions)
    input_actions_layout.setContentsMargins(0, 0, 0, 0)
    input_actions_layout.addWidget(page.btn_load_leakage_info)
    input_actions_layout.addStretch(1)
    card_input.body.addWidget(input_actions)
    page.lbl_linkage_status.setText(_tr(window, "Read the input stack first. This step only reports data structure and does not guess product type or filter chain.", "请先读取输入栈。本步骤只显示数据结构，不自动猜测产品类型或滤波链。"))
    card_input.body.addWidget(page.lbl_linkage_status)

    card_method = CardFrame(_tr(window, "2. Correction method", "2. 选择校正方法"))
    page.rb_lrc_official_gain = QRadioButton()
    page.rb_lrc_basin_scale = QRadioButton()
    page.rb_lrc_forward_modeling = QRadioButton()
    page.rb_lrc_official_gain.setChecked(True)
    page.lrc_method_group = QButtonGroup(page)
    page.lrc_method_group.addButton(page.rb_lrc_official_gain, 0)
    page.lrc_method_group.addButton(page.rb_lrc_basin_scale, 1)
    page.lrc_method_group.addButton(page.rb_lrc_forward_modeling, 2)
    methods_row = QWidget()
    methods_layout = QHBoxLayout(methods_row)
    methods_layout.setContentsMargins(0, 0, 0, 0)
    methods_layout.setSpacing(12)
    methods_layout.addWidget(
        _make_method_card(
            _tr(window, "Official scaling/gain factor", "官方 scaling/gain 因子"),
            _tr(window, "Apply an official gain grid directly to the input stack.", "读取官方增益网格并直接作用于输入栈。"),
            page.rb_lrc_official_gain,
        ),
        1,
    )
    methods_layout.addWidget(
        _make_method_card(
            _tr(window, "Regional scale factor", "区域尺度因子"),
            _tr(window, "Boundary + reference/synthetic field for basin-scale correction.", "边界 + 参考/合成场，用于区域尺度校正。"),
            page.rb_lrc_basin_scale,
        ),
        1,
    )
    methods_layout.addWidget(
        _make_method_card(
            _tr(window, "Forward modeling", "前向建模"),
            _tr(window, "Advanced correction using boundary, operator, Lmax, and reference/trend field.", "高级方法，需要边界、算子、Lmax 和参考/趋势场。"),
            page.rb_lrc_forward_modeling,
        ),
        1,
    )
    card_method.body.addWidget(methods_row)
    page.lbl_lrc_method_hint = QLabel("")
    page.lbl_lrc_method_hint.setObjectName("PageSubtitle")
    page.lbl_lrc_method_hint.setWordWrap(True)
    card_method.body.addWidget(page.lbl_lrc_method_hint)

    page.panel_reference_input = QWidget()
    ref_layout = QVBoxLayout(page.panel_reference_input)
    ref_layout.setContentsMargins(0, 0, 0, 0)
    ref_layout.setSpacing(8)
    page.lbl_lrc_reference_label = QLabel(_tr(window, "Scaling/Gain Grid", "Scaling/Gain 网格"))
    page.lbl_lrc_reference_label.setObjectName("LabelCaps")
    page.btn_lrc_read_reference = QPushButton(_tr(window, "Read Reference", "读取参考数据"))
    page.btn_lrc_read_reference.setObjectName("GhostButton")
    page.lbl_lrc_reference_info = QLabel(_tr(window, "Reference not loaded.", "参考数据未读取。"))
    page.lbl_lrc_reference_info.setWordWrap(True)
    ref_layout.addWidget(page.lbl_lrc_reference_label)
    ref_layout.addWidget(_make_edit_browse_widget(page.edit_reference_input, page.btn_reference_input_browse))
    ref_actions = QWidget()
    ref_actions_layout = QHBoxLayout(ref_actions)
    ref_actions_layout.setContentsMargins(0, 0, 0, 0)
    ref_actions_layout.addWidget(page.btn_lrc_read_reference)
    ref_actions_layout.addStretch(1)
    ref_layout.addWidget(ref_actions)
    ref_layout.addWidget(page.lbl_lrc_reference_info)
    card_method.body.addWidget(page.panel_reference_input)

    page.panel_boundary_input = QWidget()
    boundary_layout = QVBoxLayout(page.panel_boundary_input)
    boundary_layout.setContentsMargins(0, 0, 0, 0)
    boundary_layout.setSpacing(8)
    page.cmb_lrc_boundary_name_field = QComboBox()
    page.cmb_lrc_boundary_name_field.setEditable(True)
    page.cmb_lrc_boundary_name_field.addItems(["Name", "NAME", "Basin", "BASIN", "ID"])
    page.cmb_lrc_boundary_feature = QComboBox()
    page.cmb_lrc_boundary_feature.addItem(_tr(window, "Load boundary to list features", "读取边界后显示要素列表"), "")
    page.btn_lrc_read_boundary = QPushButton(_tr(window, "Read Boundary", "读取边界"))
    page.btn_lrc_read_boundary.setObjectName("GhostButton")
    page.lbl_lrc_boundary_info = QLabel(_tr(window, "Boundary not loaded.", "边界未读取。"))
    page.lbl_lrc_boundary_info.setWordWrap(True)
    boundary_layout.addWidget(_make_field_row(_tr(window, "Regional Boundary", "区域边界"), _make_edit_browse_widget(page.edit_regional_boundary, page.btn_regional_boundary_browse)))
    boundary_layout.addWidget(
        _make_compact_field_grid(
            [(_tr(window, "Name Field", "名称字段"), page.cmb_lrc_boundary_name_field), (_tr(window, "Boundary Feature", "边界要素"), page.cmb_lrc_boundary_feature)],
            columns=2,
        )
    )
    boundary_actions = QWidget()
    boundary_actions_layout = QHBoxLayout(boundary_actions)
    boundary_actions_layout.setContentsMargins(0, 0, 0, 0)
    boundary_actions_layout.addWidget(page.btn_lrc_read_boundary)
    boundary_actions_layout.addStretch(1)
    boundary_layout.addWidget(boundary_actions)
    boundary_layout.addWidget(page.lbl_lrc_boundary_info)
    card_method.body.addWidget(page.panel_boundary_input)

    page.panel_basin_scale_options = _make_compact_field_grid(
        [(_tr(window, "Initial / manual scale factor", "初始 / 手动尺度因子"), page.edit_lrc_sf_factor)],
        columns=1,
    )
    card_method.body.addWidget(page.panel_basin_scale_options)

    page.panel_forward_modeling_options = QWidget()
    fm_layout = QVBoxLayout(page.panel_forward_modeling_options)
    fm_layout.setContentsMargins(0, 0, 0, 0)
    fm_layout.setSpacing(10)
    page.cmb_lrc_filter_operator = _make_choice_combo(
        [
            (_tr(window, "Auto / from processing setup", "自动 / 使用处理设置"), "Auto"),
            ("Gaussian", "GAUSSIAN"),
            ("DDK", "DDK4"),
            ("Fan", "FAN"),
            ("PnMm / P4M6", "P4M6"),
            (_tr(window, "HSAF / Hankel", "HSAF / Hankel"), "HSAF"),
        ],
        "Auto",
    )
    page.edit_lrc_lmax = _make_line_edit("60", _tr(window, "Maximum spherical harmonic degree", "最大球谐阶次"))
    fm_layout.addWidget(
        _make_compact_field_grid(
            [
                (_tr(window, "Filter operator", "滤波算子"), page.cmb_lrc_filter_operator),
                ("Lmax", page.edit_lrc_lmax),
                (_tr(window, "Gaussian radius / km", "Gaussian 半径 / km"), page.edit_lrc_gaussian_km),
                (_tr(window, "DDK type", "DDK 类型"), page.edit_ddk_type),
            ],
            columns=2,
        )
    )
    fm_advanced = CollapsibleSection(_tr(window, "Forward-modeling iteration settings", "前向建模迭代设置"), expanded=False)
    fm_advanced.body.addWidget(
        _make_compact_field_grid(
            [
                (_tr(window, "Maximum iterations", "最大迭代次数"), page.edit_fm_iteration_count),
                (_tr(window, "Convergence threshold", "收敛阈值"), page.edit_fm_convergence_threshold),
                (_tr(window, "Acceleration", "加速因子"), page.edit_fm_acceleration),
                (_tr(window, "Patience", "容忍轮数"), page.edit_fm_patience),
                (_tr(window, "Minimum improvement", "最小改进量"), page.edit_fm_min_improve),
            ],
            columns=2,
        )
    )
    fm_layout.addWidget(fm_advanced)
    card_method.body.addWidget(page.panel_forward_modeling_options)

    page.developer_section = CollapsibleSection(_tr(window, "Developer / experimental options", "开发者 / 实验选项"), expanded=False)
    page.developer_section.body.addWidget(_make_field_row(_tr(window, "Legacy strategy", "旧版策略"), page.cmb_correction_strategy))
    page.developer_section.body.addWidget(
        _make_compact_field_grid(
            [(_tr(window, "Reference mode", "参考模式"), page.cmb_reference_mode), (_tr(window, "Official mode", "官方模式"), page.cmb_official_mode), (_tr(window, "Output format", "输出格式"), page.cmb_lrc_format)],
            columns=3,
        )
    )
    card_method.body.addWidget(page.developer_section)

    card_output = CardFrame(_tr(window, "3. Output and run", "3. 输出与运行"))
    page.lbl_lrc_output_hint = QLabel(_tr(window, "Recommended outputs: corrected_stack, difference_stack, summary.json, diagnostics, and preview_manifest.json.", "推荐输出：corrected_stack、difference_stack、summary.json、diagnostics 和 preview_manifest.json。"))
    page.lbl_lrc_output_hint.setWordWrap(True)
    card_output.body.addWidget(_make_field_row(_tr(window, "Output Location", "输出位置"), _make_edit_browse_widget(page.edit_lrc_output, page.btn_lrc_output_browse)))
    card_output.body.addWidget(_make_field_row(_tr(window, "Output Format", "输出格式"), page.cmb_lrc_format))
    card_output.body.addWidget(page.lbl_lrc_output_hint)
    action_row = QWidget()
    action_layout = QHBoxLayout(action_row)
    action_layout.setContentsMargins(0, 0, 0, 0)
    action_layout.addWidget(page.btn_open_preview_asset)
    action_layout.addWidget(page.btn_open_preview_corrected)
    action_layout.addStretch(1)
    action_layout.addWidget(page.btn_pause_leakage)
    action_layout.addWidget(page.btn_stop_leakage)
    action_layout.addWidget(page.btn_run_leakage)
    card_output.body.addWidget(action_row)
    page.lbl_preview_status.setText(_tr(window, "After the run finishes, open the corrected stack in Preview to inspect maps and series.", "运行完成后，可在预览页打开校正栈并检查地图和时间序列。"))
    card_output.body.addWidget(page.lbl_preview_status)

    page.txt_leakage_notes.setPlaceholderText(_tr(window, "Runtime notes and method diagnostics will appear here after loading or running.", "读取或运行后的方法诊断与日志说明将在此显示。"))
    page.txt_leakage_notes.setMinimumHeight(110)
    with contextlib.suppress(Exception):
        page.card_note.body.addWidget(page.txt_leakage_notes)

    wrapper = QWidget()
    wrapper_layout = QVBoxLayout(wrapper)
    wrapper_layout.setContentsMargins(0, 0, 0, 0)
    wrapper_layout.setSpacing(18)
    wrapper_layout.addWidget(card_input)
    wrapper_layout.addWidget(card_method)
    wrapper_layout.addWidget(card_output)
    wrapper_layout.addWidget(page.card_note)
    page.body.addWidget(wrapper)
    page.body.addStretch(1)

    for rb in (page.rb_lrc_official_gain, page.rb_lrc_basin_scale, page.rb_lrc_forward_modeling):
        rb.toggled.connect(lambda _checked=False: _set_method_panels(page))
    page.cmb_lrc_filter_operator.currentIndexChanged.connect(lambda _idx=0: _sync_hidden_leakage_strategy(page))
    _set_method_panels(page)
    _install_simple_load_handlers(window)
    _patch_controller_pull(window)
