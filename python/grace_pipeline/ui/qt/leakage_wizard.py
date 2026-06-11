"""Simplified leakage-correction wizard for the Qt GUI.

The original page exposed too many algorithm families at once. This module
keeps the backend compatibility attributes but rebuilds the visible page into a
three-step workflow:

1. read an input stack and display only its data shape;
2. select one of three user-facing correction methods;
3. choose output location and run.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from types import MethodType

import numpy as np
from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
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
    "edit_coastal_buffer_cells",
    "edit_coastal_attenuation_gain",
    "edit_regularized_lambda",
    "edit_regularized_step_size",
    "edit_regularized_sigma",
    "edit_regularized_iter",
    "edit_fm_iteration_count",
    "edit_fm_convergence_threshold",
    "edit_fm_acceleration",
    "edit_fm_patience",
    "edit_fm_min_improve",
    "edit_lrc_edge_buffer",
    "cmb_lrc_format",
    "cmb_scope",
    "cmb_strategy_family",
    "cmb_correction_strategy",
    "cmb_scene_override",
    "cmb_reference_mode",
    "cmb_official_mode",
    "cmb_preview_layer",
    "cmb_preview_figure",
    "cmb_preview_region",
    "cmb_preview_time",
    "lbl_leakage_info",
    "lbl_dataset_shape_value",
    "lbl_product_type_value",
    "lbl_linkage_status",
    "lbl_operator_value",
    "lbl_scene_value",
    "lbl_recommendation_value",
    "lbl_boundary_status",
    "lbl_preview_status",
    "lbl_scientific_note",
    "lbl_method_hint",
    "txt_leakage_notes",
    "badge_product",
    "badge_operator",
    "badge_scene",
    "badge_strategy",
    "card_note",
)


def _detach_reused_widgets(page) -> None:
    """Detach widgets before rebuilding the page to avoid PySide deleting them.

    Qt destroys child C++ objects when their parent container is destroyed. The
    simplified wizard reuses many controls that were originally mounted inside
    the legacy leakage page, so they must be reparented to None before the old
    layout tree is cleared.
    """

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
        operator = str(getattr(page, "cmb_lrc_filter_operator", None).currentData() or "Auto") if getattr(page, "cmb_lrc_filter_operator", None) is not None else "Auto"
        page.edit_operator_autodetect.setText(operator)


def _set_method_panels(page) -> None:
    mode = _current_leakage_mode(page)
    is_official = mode == "official_gain"
    is_basin = mode == "basin_scale_factor"
    is_fm = mode == "forward_modeling"

    page.panel_reference_input.setVisible(True)
    page.panel_boundary_input.setVisible(is_basin or is_fm)
    page.panel_basin_scale_options.setVisible(is_basin)
    page.panel_forward_modeling_options.setVisible(is_fm)
    page.lbl_lrc_method_hint.setText(
        {
            "official_gain": "Use when an official scaling/gain grid is available on the same or compatible grid. The correction is applied as a grid-wise gain factor.",
            "basin_scale_factor": "Use for basin, lake, or regional statistics. Provide a boundary and either a reference model stack or keep the synthetic-unit option.",
            "forward_modeling": "Advanced regional correction. Provide boundary, filtering operator, Lmax, and a reference/trend field so the program can simulate leakage response.",
        }[mode]
    )
    page.lbl_lrc_reference_label.setText(
        "Scaling/Gain Grid" if is_official else ("Reference Model Stack" if is_basin else "Reference / Trend Field")
    )
    page.edit_reference_input.setPlaceholderText(
        "Official scaling/gain grid" if is_official else "Optional reference model stack; leave blank for synthetic-unit workflow"
    )
    for btn in (page.rb_lrc_official_gain, page.rb_lrc_basin_scale, page.rb_lrc_forward_modeling):
        btn.setObjectName("PrimaryButton" if btn.isChecked() else "GhostButton")
        btn.style().unpolish(btn)
        btn.style().polish(btn)
    _sync_hidden_leakage_strategy(page)


def _shape_text(shape) -> str:
    try:
        vals = [int(v) for v in tuple(shape)]
    except Exception:
        return "-"
    return " x ".join(str(v) for v in vals) if vals else "-"


def _time_text(host, t_arr, nt: int, meta: dict) -> str:
    try:
        _years, labels = host._resolve_time(t_arr, int(nt), meta=meta or {})
        if labels:
            return f"{labels[0]} / {labels[-1]} ({len(labels)} epochs)"
    except Exception:
        pass
    return f"{int(nt)} epochs"


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
            page.lbl_leakage_info.setText("Input loaded")
            page.lbl_dataset_shape_value.setText(_shape_text(shape))
            page.lbl_lrc_variable_value.setText(active_var)
            page.lbl_lrc_time_value.setText(_time_text(controller.host, info.get("t"), nt, meta))
            if lon.size and lat.size:
                page.lbl_lrc_grid_extent_value.setText(
                    f"lon {float(np.nanmin(lon)):.3g}–{float(np.nanmax(lon)):.3g}, "
                    f"lat {float(np.nanmin(lat)):.3g}–{float(np.nanmax(lat)):.3g}"
                )
            else:
                page.lbl_lrc_grid_extent_value.setText("-")
            page.lbl_linkage_status.setText("Input metadata loaded. Select a correction method and provide the required method-specific files.")
            controller.on_log(f"[LEAKAGE] Input metadata loaded: {page.edit_lrc_input.text().strip()}", "stdout")
        except Exception as exc:
            page.lbl_leakage_info.setText(f"Load failed: {exc}")
            page.lbl_linkage_status.setText("Input loading failed. Check the file path and stack structure.")
            with contextlib.suppress(Exception):
                controller._show_error("Leakage correction", str(exc))

    def read_reference_info() -> None:
        path = page.edit_reference_input.text().strip()
        if not path:
            page.lbl_lrc_reference_info.setText("Reference file is not set.")
            return
        p = Path(path)
        if not p.exists():
            page.lbl_lrc_reference_info.setText("Reference file does not exist.")
            return
        try:
            info = controller.host.load_stack_info(str(p))
            shape = _shape_text(info.get("shape"))
            meta = info.get("meta", {}) or {}
            page.lbl_lrc_reference_info.setText(f"Loaded: {shape} | variable={meta.get('active_var', 'auto')}")
        except Exception as exc:
            page.lbl_lrc_reference_info.setText(f"Read failed: {exc}")

    def read_boundary_info() -> None:
        path = page.edit_regional_boundary.text().strip()
        if not path:
            page.lbl_lrc_boundary_info.setText("Boundary file is not set.")
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
            page.lbl_lrc_boundary_info.setText(f"Loaded {len(names)} boundary feature(s){bbox_text}")
        except Exception as exc:
            page.lbl_lrc_boundary_info.setText(f"Boundary read failed: {exc}")

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
    _detach_reused_widgets(page)
    _clear_layout(page.body)
    page.add_header("Leakage Correction")

    # Keep compatibility controls alive but hidden for existing controller/service code.
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

    page.btn_run_leakage.setText("Run Leakage Correction")
    page.btn_pause_leakage.setText("Pause")
    page.btn_stop_leakage.setText("Stop")

    # Step 1: input stack.
    card_input = CardFrame("1. Input grid stack")
    card_input.body.addWidget(_make_field_row("Input Stack", _make_edit_browse_widget(page.edit_lrc_input, page.btn_lrc_input_browse)))
    page.lbl_lrc_variable_value = QLabel("-")
    page.lbl_lrc_time_value = QLabel("-")
    page.lbl_lrc_grid_extent_value = QLabel("-")
    for label in (page.lbl_leakage_info, page.lbl_dataset_shape_value, page.lbl_lrc_variable_value, page.lbl_lrc_time_value, page.lbl_lrc_grid_extent_value):
        label.setWordWrap(True)
    card_input.body.addWidget(
        _make_compact_field_grid(
            [
                ("Input Status", page.lbl_leakage_info),
                ("Grid Shape", page.lbl_dataset_shape_value),
                ("Data Variable", page.lbl_lrc_variable_value),
                ("Time Coverage", page.lbl_lrc_time_value),
                ("Grid Extent", page.lbl_lrc_grid_extent_value),
            ],
            columns=2,
        )
    )
    input_actions = QWidget()
    input_actions_layout = QHBoxLayout(input_actions)
    input_actions_layout.setContentsMargins(0, 0, 0, 0)
    input_actions_layout.addWidget(page.btn_load_leakage_info)
    input_actions_layout.addStretch(1)
    card_input.body.addWidget(input_actions)
    page.lbl_linkage_status.setText("Read the input stack first. The page only reports data structure and does not guess product type or filter chain.")
    card_input.body.addWidget(page.lbl_linkage_status)

    # Step 2: method selection.
    card_method = CardFrame("2. Correction method")
    page.rb_lrc_official_gain = QRadioButton("Official scaling/gain factor")
    page.rb_lrc_basin_scale = QRadioButton("Regional scale factor")
    page.rb_lrc_forward_modeling = QRadioButton("Forward modeling")
    page.rb_lrc_official_gain.setChecked(True)
    page.lrc_method_group = QButtonGroup(page)
    for idx, rb in enumerate((page.rb_lrc_official_gain, page.rb_lrc_basin_scale, page.rb_lrc_forward_modeling)):
        rb.setCheckable(True)
        page.lrc_method_group.addButton(rb, idx)
        rb.setToolTip(
            [
                "Apply an official scaling/gain grid to the input stack.",
                "Use a boundary and reference/synthetic field to estimate a basin-scale factor.",
                "Advanced regional correction using boundary, filter operator, Lmax, and reference/trend field.",
            ][idx]
        )
    method_row = QWidget()
    method_row_layout = QHBoxLayout(method_row)
    method_row_layout.setContentsMargins(0, 0, 0, 0)
    method_row_layout.setSpacing(10)
    method_row_layout.addWidget(page.rb_lrc_official_gain)
    method_row_layout.addWidget(page.rb_lrc_basin_scale)
    method_row_layout.addWidget(page.rb_lrc_forward_modeling)
    method_row_layout.addStretch(1)
    card_method.body.addWidget(method_row)
    page.lbl_lrc_method_hint = QLabel("")
    page.lbl_lrc_method_hint.setWordWrap(True)
    card_method.body.addWidget(page.lbl_lrc_method_hint)

    # Shared method-specific reference input.
    page.panel_reference_input = QWidget()
    ref_layout = QVBoxLayout(page.panel_reference_input)
    ref_layout.setContentsMargins(0, 0, 0, 0)
    ref_layout.setSpacing(8)
    page.lbl_lrc_reference_label = QLabel("Scaling/Gain Grid")
    page.btn_lrc_read_reference = QPushButton("Read Reference")
    page.btn_lrc_read_reference.setObjectName("GhostButton")
    page.lbl_lrc_reference_info = QLabel("Reference not loaded.")
    page.lbl_lrc_reference_info.setWordWrap(True)
    ref_layout.addWidget(_make_stacked_field("Method Input", _make_edit_browse_widget(page.edit_reference_input, page.btn_reference_input_browse), page.lbl_lrc_reference_label))
    ref_actions = QWidget()
    ref_actions_layout = QHBoxLayout(ref_actions)
    ref_actions_layout.setContentsMargins(0, 0, 0, 0)
    ref_actions_layout.addWidget(page.btn_lrc_read_reference)
    ref_actions_layout.addStretch(1)
    ref_layout.addWidget(ref_actions)
    ref_layout.addWidget(page.lbl_lrc_reference_info)
    card_method.body.addWidget(page.panel_reference_input)

    # Boundary panel shared by regional scale factor and forward modeling.
    page.panel_boundary_input = QWidget()
    boundary_layout = QVBoxLayout(page.panel_boundary_input)
    boundary_layout.setContentsMargins(0, 0, 0, 0)
    boundary_layout.setSpacing(8)
    page.cmb_lrc_boundary_name_field = QComboBox()
    page.cmb_lrc_boundary_name_field.setEditable(True)
    page.cmb_lrc_boundary_name_field.addItems(["Name", "NAME", "Basin", "BASIN", "ID"])
    page.cmb_lrc_boundary_feature = QComboBox()
    page.cmb_lrc_boundary_feature.addItem("Load boundary to list features", "")
    page.btn_lrc_read_boundary = QPushButton("Read Boundary")
    page.btn_lrc_read_boundary.setObjectName("GhostButton")
    page.lbl_lrc_boundary_info = QLabel("Boundary not loaded.")
    page.lbl_lrc_boundary_info.setWordWrap(True)
    boundary_layout.addWidget(_make_field_row("Regional Boundary", _make_edit_browse_widget(page.edit_regional_boundary, page.btn_regional_boundary_browse)))
    boundary_layout.addWidget(
        _make_compact_field_grid(
            [("Name Field", page.cmb_lrc_boundary_name_field), ("Boundary Feature", page.cmb_lrc_boundary_feature)],
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
        [("Initial / manual scale factor", page.edit_lrc_sf_factor)],
        columns=1,
    )
    card_method.body.addWidget(page.panel_basin_scale_options)

    page.panel_forward_modeling_options = QWidget()
    fm_layout = QVBoxLayout(page.panel_forward_modeling_options)
    fm_layout.setContentsMargins(0, 0, 0, 0)
    fm_layout.setSpacing(10)
    page.cmb_lrc_filter_operator = _make_choice_combo(
        [
            ("Auto / from processing setup", "Auto"),
            ("Gaussian", "GAUSSIAN"),
            ("DDK", "DDK4"),
            ("Fan", "FAN"),
            ("PnMm / P4M6", "P4M6"),
            ("HSAF / Hankel", "HSAF"),
        ],
        "Auto",
    )
    page.edit_lrc_lmax = _make_line_edit("60", "Maximum spherical harmonic degree")
    fm_layout.addWidget(
        _make_compact_field_grid(
            [
                ("Filter operator", page.cmb_lrc_filter_operator),
                ("Lmax", page.edit_lrc_lmax),
                ("Gaussian radius / km", page.edit_lrc_gaussian_km),
                ("DDK type", page.edit_ddk_type),
            ],
            columns=2,
        )
    )
    fm_advanced = CollapsibleSection("Forward-modeling iteration settings", expanded=False)
    fm_advanced.body.addWidget(
        _make_compact_field_grid(
            [
                ("Maximum iterations", page.edit_fm_iteration_count),
                ("Convergence threshold", page.edit_fm_convergence_threshold),
                ("Acceleration", page.edit_fm_acceleration),
                ("Patience", page.edit_fm_patience),
                ("Minimum improvement", page.edit_fm_min_improve),
            ],
            columns=2,
        )
    )
    fm_layout.addWidget(fm_advanced)
    card_method.body.addWidget(page.panel_forward_modeling_options)

    # Keep unsupported/experimental controls accessible but not prominent.
    page.developer_section = CollapsibleSection("Developer / experimental options", expanded=False)
    page.developer_section.body.addWidget(_make_field_row("Legacy strategy", page.cmb_correction_strategy))
    page.developer_section.body.addWidget(
        _make_compact_field_grid(
            [("Reference mode", page.cmb_reference_mode), ("Official mode", page.cmb_official_mode), ("Output format", page.cmb_lrc_format)],
            columns=3,
        )
    )
    card_method.body.addWidget(page.developer_section)

    # Step 3: output and execution.
    card_output = CardFrame("3. Output and run")
    page.lbl_lrc_output_hint = QLabel("Recommended outputs: corrected_stack, difference_stack, summary.json, diagnostics, and preview_manifest.json.")
    page.lbl_lrc_output_hint.setWordWrap(True)
    card_output.body.addWidget(_make_field_row("Output Location", _make_edit_browse_widget(page.edit_lrc_output, page.btn_lrc_output_browse)))
    card_output.body.addWidget(_make_field_row("Output Format", page.cmb_lrc_format))
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
    card_output.body.addWidget(page.lbl_preview_status)

    page.txt_leakage_notes.setPlaceholderText("Runtime notes and method diagnostics will appear here after loading or running.")
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
