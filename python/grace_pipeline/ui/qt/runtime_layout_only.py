"""Runtime layout and button-role fixes.

This module must be conservative: it is applied after the WIP shell has
already built and polished the Qt object tree. Do not remove or reparent
existing card widgets here, because parent layout teardown can invalidate
PySide/Shiboken wrapper objects on some startup paths.
"""
from __future__ import annotations

import contextlib
from grace_pipeline.ui.qt.runtime_terms_min import canonical


def _alive(widget) -> bool:
    if widget is None:
        return False
    try:
        widget.objectName()
        return True
    except RuntimeError:
        return False


def compact_processing(window):
    """Apply non-destructive compact sizing to the processing page.

    The previous implementation rebuilt the page body by taking items out of
    the existing layout. On the current WIP GUI this may delete CardFrame C++
    objects before they are reparented, causing libshiboken runtime errors at
    startup. This version keeps the existing object tree intact and only adjusts
    sizing and spacing hints.
    """
    from PySide6.QtWidgets import QSizePolicy

    page = getattr(window, "page_processing", None)
    if page is None or getattr(page, "_runtime_compact", False):
        return

    body = getattr(page, "body", None)
    if body is not None:
        with contextlib.suppress(Exception):
            body.setContentsMargins(0, 0, 0, 0)
        with contextlib.suppress(Exception):
            body.setSpacing(14)

    for name in ("card_time_range", "card_inversion", "card_grid_settings", "card_sh_tools"):
        card = getattr(page, name, None)
        if _alive(card):
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

    filters = getattr(page, "card_filters", None)
    if _alive(filters):
        filters.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    page._runtime_compact = True


def button_roles(window):
    from PySide6.QtWidgets import QPushButton
    primary = ("run", "download", "validate", "render", "export", "generate", "运行", "下载", "校验", "导出")
    danger = ("stop", "abort", "delete", "clear", "停止", "中止", "删除", "清除")
    browse = ("browse", "folder", "file", "选择文件", "选择文件夹")
    for button in window.findChildren(QPushButton):
        text = canonical(button.text()).lower()
        if any(word in text for word in danger):
            button.setObjectName("DangerGhostButton")
        elif any(word in text for word in primary):
            button.setObjectName("PrimaryButton")
        elif any(word in text for word in browse):
            button.setObjectName("GhostButton")
        button.style().unpolish(button)
        button.style().polish(button)


def wire_data_page(window):
    page = getattr(window, "page_data_paths", None)
    ctrl = getattr(window, "controller", None)
    if page is None or ctrl is None:
        return
    for child in page.findChildren(type(page.btn_download_gfc_range)):
        if "数据网页" in child.text() or "Data Website" in canonical(child.text()):
            with contextlib.suppress(Exception):
                child.clicked.disconnect()
            child.clicked.connect(ctrl.on_open_data_page)


def apply(window):
    compact_processing(window)
    button_roles(window)
    wire_data_page(window)
