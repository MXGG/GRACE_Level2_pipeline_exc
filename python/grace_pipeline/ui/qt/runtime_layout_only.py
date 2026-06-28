"""Runtime layout and button-role fixes."""
import contextlib
from grace_pipeline.ui.qt.runtime_terms_min import canonical


def _take_after(layout, keep):
    while layout.count() > keep:
        item = layout.takeAt(keep); widget = item.widget(); child = item.layout()
        if widget is not None: widget.setParent(None)
        elif child is not None: _take_after(child, 0)


def compact_processing(window):
    from PySide6.QtWidgets import QGridLayout, QSizePolicy, QWidget
    page = getattr(window, "page_processing", None)
    if page is None or getattr(page, "_runtime_compact", False): return
    _take_after(page.body, 1); wrapper = QWidget(); grid = QGridLayout(wrapper)
    grid.setContentsMargins(0, 0, 0, 0); grid.setHorizontalSpacing(18); grid.setVerticalSpacing(18)
    for card in (page.card_time_range, page.card_inversion, page.card_grid_settings, page.card_filters, page.card_sh_tools):
        card.setParent(wrapper); card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
    page.card_filters.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    grid.addWidget(page.card_time_range, 0, 0); grid.addWidget(page.card_inversion, 1, 0); grid.addWidget(page.card_grid_settings, 2, 0)
    grid.addWidget(page.card_filters, 0, 1, 2, 1); grid.addWidget(page.card_sh_tools, 2, 1)
    grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 1); grid.setRowStretch(1, 1)
    page.body.addWidget(wrapper); page.body.addStretch(1); page._runtime_compact = True


def button_roles(window):
    from PySide6.QtWidgets import QPushButton
    primary = ("run", "download", "validate", "render", "export", "generate", "运行", "下载", "校验", "导出")
    danger = ("stop", "abort", "delete", "clear", "停止", "中止", "删除", "清除")
    browse = ("browse", "folder", "file", "选择文件", "选择文件夹")
    for button in window.findChildren(QPushButton):
        text = canonical(button.text()).lower()
        if any(word in text for word in danger): button.setObjectName("DangerGhostButton")
        elif any(word in text for word in primary): button.setObjectName("PrimaryButton")
        elif any(word in text for word in browse): button.setObjectName("GhostButton")
        button.style().unpolish(button); button.style().polish(button)


def wire_data_page(window):
    page = getattr(window, "page_data_paths", None); ctrl = getattr(window, "controller", None)
    if page is None or ctrl is None: return
    for child in page.findChildren(type(page.btn_download_gfc_range)):
        if "数据网页" in child.text() or "Data Website" in canonical(child.text()):
            with contextlib.suppress(Exception): child.clicked.disconnect()
            child.clicked.connect(ctrl.on_open_data_page)


def apply(window):
    compact_processing(window); button_roles(window); wire_data_page(window)
