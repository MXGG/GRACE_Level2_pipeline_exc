"""Stable entry point for the simplified leakage wizard."""

from __future__ import annotations

import contextlib

from PySide6.QtWidgets import QLabel, QToolButton

from grace_pipeline.ui.qt import leakage_wizard as base

EXTRA_REUSED_WIDGET_ATTRS = (
    "edit_coastal_buffer_cells",
    "edit_coastal_attenuation_gain",
    "edit_regularized_lambda",
    "edit_regularized_step_size",
    "edit_regularized_sigma",
    "edit_regularized_iter",
    "edit_lrc_edge_buffer",
    "edit_lrc_sf_fan_r1",
    "edit_lrc_sf_fan_r2",
    "edit_lrc_sf_hsa_ts",
    "edit_lrc_sf_p4_deg",
    "edit_lrc_sf_p4_m",
    "edit_lrc_sf_grid",
    "edit_lrc_sf_hsa_window",
    "edit_lrc_sf_hsa_p",
    "edit_lrc_sf_hsa_order",
    "edit_lrc_sf_hsa_buffer",
    "edit_lrc_toolbox",
    "edit_lrc_aux_global",
    "edit_lrc_aux_region",
    "edit_lrc_matlab",
)

_TEXT_REPLACEMENTS_ZH = {
    "1. 输入格网栈": "1. 待校正数据",
    "输入栈": "待校正数据",
    "请先读取输入栈。本步骤只显示数据结构，不自动猜测产品类型或滤波链。": "请先读取待校正数据。本步骤用于确认数据维度、变量名称、时间范围和经纬度范围。",
    "官方 scaling/gain 因子": "官方尺度/增益因子",
    "读取官方增益网格并直接作用于输入栈。": "读取官方尺度/增益因子网格，并按格网位置应用于待校正数据。",
    "边界 + 参考/合成场，用于区域尺度校正。": "基于区域边界与参考模型或合成场估计区域尺度因子。",
    "前向建模": "正演建模",
    "高级方法，需要边界、算子、Lmax 和参考/趋势场。": "基于区域边界、滤波方法、Lmax 和参考场模拟泄漏响应。",
    "滤波算子": "滤波方法",
    "前向建模迭代设置": "正演建模迭代设置",
    "推荐输出：corrected_stack、difference_stack、summary.json、diagnostics 和 preview_manifest.json。": "输出文件：corrected_stack、difference_stack、summary.json、diagnostics 和 preview_manifest.json。",
    "运行完成后，可在预览页打开校正栈并检查地图和时间序列。": "运行完成后，可在预览页检查校正结果的空间分布和时间序列。",
    "Scaling/Gain 网格": "尺度/增益因子网格",
    "官方 scaling/gain 网格": "官方尺度/增益因子网格",
}

_TEXT_REPLACEMENTS_EN = {
    "1. Input grid stack": "1. Correction dataset",
    "Input Stack": "Correction Dataset",
    "Read the input stack first. This step only reports data structure and does not guess product type or filter chain.": "Read the correction dataset first. This step reports dimensions, variable name, time coverage, and grid extent.",
    "Forward modeling": "Forward modelling",
    "Filter operator": "Filter method",
    "Forward-modeling iteration settings": "Forward-modelling iteration settings",
    "Recommended outputs: corrected_stack, difference_stack, summary.json, diagnostics, and preview_manifest.json.": "Output files: corrected_stack, difference_stack, summary.json, diagnostics, and preview_manifest.json.",
}


def _is_zh(window) -> bool:
    return getattr(getattr(window, "ui_preferences", None), "language", "en") == "zh"


def _tr(window, en: str, zh: str) -> str:
    return zh if _is_zh(window) else en


def _replace_widget_texts(page, window) -> None:
    replacements = _TEXT_REPLACEMENTS_ZH if _is_zh(window) else _TEXT_REPLACEMENTS_EN
    for label in page.findChildren(QLabel):
        text = label.text()
        if text in replacements:
            label.setText(replacements[text])
    for tool in page.findChildren(QToolButton):
        text = tool.text()
        if text in replacements:
            tool.setText(replacements[text])


def _method_mode(page) -> str:
    if getattr(page, "rb_lrc_forward_modeling", None) is not None and page.rb_lrc_forward_modeling.isChecked():
        return "forward_modeling"
    if getattr(page, "rb_lrc_basin_scale", None) is not None and page.rb_lrc_basin_scale.isChecked():
        return "basin_scale_factor"
    return "official_gain"


def _set_method_language(page, window) -> None:
    if hasattr(page, "rb_lrc_official_gain"):
        page.rb_lrc_official_gain.setText(_tr(window, "Official scale/gain factor", "官方尺度/增益因子"))
    if hasattr(page, "rb_lrc_basin_scale"):
        page.rb_lrc_basin_scale.setText(_tr(window, "Regional scale factor", "区域尺度因子"))
    if hasattr(page, "rb_lrc_forward_modeling"):
        page.rb_lrc_forward_modeling.setText(_tr(window, "Forward modelling", "正演建模"))

    mode = _method_mode(page)
    hint = {
        "official_gain": _tr(
            window,
            "Use an official scale/gain grid to apply grid-wise amplitude restoration to the correction dataset.",
            "适用于已获得官方尺度/增益因子网格的情形。程序按格网位置对待校正数据进行幅值恢复。",
        ),
        "basin_scale_factor": _tr(
            window,
            "Use a regional boundary and a reference model or synthetic field to estimate a scale factor for basin-scale analysis.",
            "适用于流域、湖泊等区域统计。程序基于区域边界及参考模型或合成场估计区域尺度因子。",
        ),
        "forward_modeling": _tr(
            window,
            "Use a regional boundary, filter method, Lmax, and reference or trend field to simulate the leakage response before correction.",
            "适用于高级区域校正。程序基于区域边界、滤波方法、Lmax 及参考场或趋势场模拟滤波前后的泄漏响应。",
        ),
    }[mode]
    with contextlib.suppress(Exception):
        page.lbl_lrc_method_hint.setText(hint)

    with contextlib.suppress(Exception):
        page.lbl_lrc_reference_label.setText(
            {
                "official_gain": _tr(window, "Scale/Gain Factor Grid", "尺度/增益因子网格"),
                "basin_scale_factor": _tr(window, "Reference Model or Synthetic Field", "参考模型或合成场"),
                "forward_modeling": _tr(window, "Reference or Trend Field", "参考场或趋势场"),
            }[mode]
        )
    with contextlib.suppress(Exception):
        page.edit_reference_input.setPlaceholderText(
            {
                "official_gain": _tr(window, "Official scale/gain factor grid", "官方尺度/增益因子网格"),
                "basin_scale_factor": _tr(window, "Reference model stack; leave blank to use the synthetic-field workflow", "参考模型栈；留空时采用合成场方案"),
                "forward_modeling": _tr(window, "Reference field, model field, or trend field", "参考场、模型场或趋势场"),
            }[mode]
        )


def _set_filter_parameter_visibility(page, window) -> None:
    combo = getattr(page, "cmb_lrc_filter_operator", None)
    if combo is None:
        return
    method = str(combo.currentData() or "Auto").upper()
    show_gaussian = method == "GAUSSIAN"
    show_ddk = method.startswith("DDK")

    for label in page.findChildren(QLabel):
        text = label.text().strip().lower()
        if text in {"gaussian 半径 / km", "gaussian radius / km"}:
            label.setVisible(show_gaussian)
        elif text in {"ddk 类型", "ddk type"}:
            label.setVisible(show_ddk)
    with contextlib.suppress(Exception):
        page.edit_lrc_gaussian_km.setVisible(show_gaussian)
    with contextlib.suppress(Exception):
        page.edit_ddk_type.setVisible(show_ddk)

    if hasattr(page, "lbl_lrc_filter_hint"):
        page.lbl_lrc_filter_hint.setText(
            {
                "GAUSSIAN": _tr(window, "Gaussian filtering requires a smoothing radius.", "选择 Gaussian 时需设置平滑半径。"),
                "DDK4": _tr(window, "DDK filtering requires the DDK kernel type.", "选择 DDK 时需设置 DDK 类型。"),
                "FAN": _tr(window, "Fan filtering uses the parameters from the processing setup.", "Fan 滤波参数沿用滤波处理页设置。"),
                "P4M6": _tr(window, "PnMm/P4M6 parameters are taken from the processing setup.", "PnMm/P4M6 参数沿用滤波处理页设置。"),
                "HSAF": _tr(window, "HSAF parameters are taken from the processing setup.", "HSAF 参数沿用滤波处理页设置。"),
                "AUTO": _tr(window, "The filter method follows the processing setup.", "滤波方法沿用滤波处理页设置。"),
            }.get(method, _tr(window, "The selected filter method uses the processing setup.", "所选滤波方法沿用滤波处理页设置。"))
        )


def _refresh_polish(page, window) -> None:
    _replace_widget_texts(page, window)
    _set_method_language(page, window)
    _set_filter_parameter_visibility(page, window)


def _install_polish_hooks(window) -> None:
    page = window.page_leakage
    _refresh_polish(page, window)
    for radio_name in ("rb_lrc_official_gain", "rb_lrc_basin_scale", "rb_lrc_forward_modeling"):
        radio = getattr(page, radio_name, None)
        if radio is not None:
            radio.toggled.connect(lambda _checked=False, p=page, w=window: _refresh_polish(p, w))
    combo = getattr(page, "cmb_lrc_filter_operator", None)
    if combo is not None:
        combo.currentIndexChanged.connect(lambda _idx=0, p=page, w=window: _refresh_polish(p, w))


def install_leakage_wizard(window) -> None:
    existing = tuple(getattr(base, "_REUSED_WIDGET_ATTRS", ()))
    base._REUSED_WIDGET_ATTRS = tuple(dict.fromkeys(existing + EXTRA_REUSED_WIDGET_ATTRS))
    base.install_leakage_wizard(window)
    page = window.page_leakage

    with contextlib.suppress(Exception):
        page.cmb_lrc_filter_operator.setItemText(0, _tr(window, "Use Processing Setup", "沿用滤波处理设置"))
    with contextlib.suppress(Exception):
        page.lbl_lrc_filter_hint = QLabel(page)
        page.lbl_lrc_filter_hint.setObjectName("PageSubtitle")
        page.lbl_lrc_filter_hint.setWordWrap(True)
        page.panel_forward_modeling_options.layout().insertWidget(1, page.lbl_lrc_filter_hint)

    _install_polish_hooks(window)
