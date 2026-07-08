"""Runtime shell enhancements for the Qt desktop application."""

from __future__ import annotations

import contextlib
import getpass
import os
import platform
import sys
from datetime import datetime
from types import MethodType

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

try:
    from shiboken6 import isValid as _shiboken_is_valid
except Exception:  # pragma: no cover - PySide6 always ships shiboken6.
    def _shiboken_is_valid(_obj) -> bool:
        return True

from grace_pipeline.ui.qt.app_icon import app_icon_path, install_app_icon
from grace_pipeline.ui.qt.pages import _make_compact_field_grid, _make_field_row
from grace_pipeline.ui.qt.widgets import CardFrame

APP_VERSION = "0.1"


class WindowsTaskbarProgress:
    """Best-effort Windows taskbar progress integration.

    The implementation deliberately avoids mandatory third-party dependencies.
    If COM taskbar integration is unavailable, all methods become no-ops.
    """

    TBPF_NOPROGRESS = 0
    TBPF_INDETERMINATE = 0x1
    TBPF_NORMAL = 0x2
    TBPF_ERROR = 0x4
    TBPF_PAUSED = 0x8

    def __init__(self, window) -> None:
        self.window = window
        self._taskbar = None
        self._hwnd = 0
        if sys.platform != "win32":
            return
        with contextlib.suppress(Exception):
            import ctypes
            from ctypes import POINTER, HRESULT, c_int, c_uint, c_ulonglong, c_void_p
            from ctypes.wintypes import HWND
            import comtypes
            from comtypes import COMMETHOD, GUID, IUnknown

            class ITaskbarList3(IUnknown):
                _iid_ = GUID("{EA1AFB91-9E28-4B86-90E9-9E9F8A5EEB8B}")
                _methods_ = [
                    COMMETHOD([], HRESULT, "HrInit"),
                    COMMETHOD([], HRESULT, "AddTab", (['in'], HWND, 'hwnd')),
                    COMMETHOD([], HRESULT, "DeleteTab", (['in'], HWND, 'hwnd')),
                    COMMETHOD([], HRESULT, "ActivateTab", (['in'], HWND, 'hwnd')),
                    COMMETHOD([], HRESULT, "SetActiveAlt", (['in'], HWND, 'hwnd')),
                    COMMETHOD([], HRESULT, "MarkFullscreenWindow", (['in'], HWND, 'hwnd'), (['in'], c_int, 'fFullscreen')),
                    COMMETHOD([], HRESULT, "SetProgressValue", (['in'], HWND, 'hwnd'), (['in'], c_ulonglong, 'ullCompleted'), (['in'], c_ulonglong, 'ullTotal')),
                    COMMETHOD([], HRESULT, "SetProgressState", (['in'], HWND, 'hwnd'), (['in'], c_uint, 'tbpFlags')),
                ]

            clsid = GUID("{56FDF344-FD6D-11d0-958A-006097C9A090}")
            self._taskbar = comtypes.CoCreateInstance(clsid, interface=ITaskbarList3)
            self._taskbar.HrInit()
            self._hwnd = int(window.winId())

    def set_progress(self, percent: float | int | None) -> None:
        if self._taskbar is None or not self._hwnd:
            return
        with contextlib.suppress(Exception):
            if percent is None or float(percent) < 0:
                self._taskbar.SetProgressState(self._hwnd, self.TBPF_INDETERMINATE)
            else:
                value = max(0, min(100, int(round(float(percent)))))
                self._taskbar.SetProgressState(self._hwnd, self.TBPF_NORMAL)
                self._taskbar.SetProgressValue(self._hwnd, value, 100)

    def clear(self) -> None:
        if self._taskbar is None or not self._hwnd:
            return
        with contextlib.suppress(Exception):
            self._taskbar.SetProgressState(self._hwnd, self.TBPF_NOPROGRESS)


def _tr(window, en: str, zh: str) -> str:
    return zh if getattr(getattr(window, "ui_preferences", None), "language", "en") == "zh" else en


def _qt_object_is_alive(obj) -> bool:
    try:
        return obj is not None and _shiboken_is_valid(obj)
    except RuntimeError:
        return False


def _memory_text() -> str:
    with contextlib.suppress(Exception):
        import psutil

        vm = psutil.virtual_memory()
        return f"{vm.used / 1024**3:.1f} / {vm.total / 1024**3:.1f} GB ({vm.percent:.0f}%)"
    if sys.platform == "win32":
        with contextlib.suppress(Exception):
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            used = stat.ullTotalPhys - stat.ullAvailPhys
            return f"{used / 1024**3:.1f} / {stat.ullTotalPhys / 1024**3:.1f} GB ({stat.dwMemoryLoad:.0f}%)"
    return "-"


def _detach(widget) -> None:
    with contextlib.suppress(Exception):
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


def _detach_dashboard_widgets(page) -> None:
    for attr in (
        "btn_run_full", "btn_pause_run", "btn_stop_run", "btn_load_config", "btn_save_config", "btn_validate_paths",
        "btn_open_data_paths", "btn_open_processing", "btn_open_preview", "btn_console_run",
        "lbl_project_name", "lbl_last_edited", "lbl_uid", "badge_summary_state", "lbl_output_root", "lbl_output_hint",
        "lbl_data_count", "lbl_time_span", "lbl_dashboard_status", "lbl_dashboard_stage", "lbl_dashboard_counts",
        "lbl_active_filters", "lbl_active_io", "bar_active_run", "lbl_preview_artifact", "lbl_preview_root",
        "lbl_preview_output", "lbl_preview_stacks", "lbl_preview_monthly", "lbl_preview_plots", "lbl_preview_logs",
    ):
        widget = getattr(page, attr, None)
        if widget is not None:
            _detach(widget)


def _compact_metric(title: str, value_widget: QWidget, hint_widget: QWidget | None = None) -> QFrame:
    frame = QFrame()
    frame.setObjectName("PageCard")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(6)
    title_label = QLabel(title)
    title_label.setObjectName("LabelCaps")
    layout.addWidget(title_label)
    layout.addWidget(value_widget)
    if hint_widget is not None:
        layout.addWidget(hint_widget)
    layout.addStretch(1)
    return frame


def install_dashboard_overview(window) -> None:
    page = window.page_dashboard
    # DashboardPage now owns the workflow overview layout. Older shell
    # enhancement code rebuilt the page into the legacy system-status view.
    if hasattr(page, "workflow_steps") and hasattr(page, "output_tree"):
        return
    if getattr(page, "_enhanced_dashboard_installed", False):
        return
    _detach_dashboard_widgets(page)
    _clear_layout(page.body)
    page.add_header(_tr(window, "Dashboard", "总览"))

    page.lbl_system_time = QLabel("-")
    page.lbl_system_memory = QLabel("-")
    page.lbl_system_runtime = QLabel("-")
    page.lbl_system_user = QLabel(getpass.getuser())
    for label in (page.lbl_system_time, page.lbl_system_memory, page.lbl_system_runtime, page.lbl_system_user):
        label.setWordWrap(True)

    top = CardFrame(_tr(window, "System and project status", "系统与项目状态"))
    project_grid = _make_compact_field_grid(
        [
            (_tr(window, "Configuration", "配置名称"), page.lbl_project_name),
            (_tr(window, "Last updated", "最近更新"), page.lbl_last_edited),
            (_tr(window, "Configuration ID", "配置指纹"), page.lbl_uid),
            (_tr(window, "State", "状态"), page.badge_summary_state),
            (_tr(window, "User", "当前用户"), page.lbl_system_user),
            (_tr(window, "Version", "程序版本"), QLabel(f"v{APP_VERSION}")),
            (_tr(window, "Time", "系统时间"), page.lbl_system_time),
            (_tr(window, "Memory", "内存占用"), page.lbl_system_memory),
        ],
        columns=4,
    )
    top.body.addWidget(project_grid)

    control_row = QWidget()
    control_layout = QHBoxLayout(control_row)
    control_layout.setContentsMargins(0, 0, 0, 0)
    control_layout.setSpacing(8)
    for button in (page.btn_open_data_paths, page.btn_validate_paths, page.btn_open_processing):
        control_layout.addWidget(button)
    control_layout.addStretch(1)
    for button in (page.btn_load_config, page.btn_save_config):
        control_layout.addWidget(button)
    top.body.addWidget(control_row)

    run_card = CardFrame(_tr(window, "Current run", "当前运行"))
    run_card.body.addWidget(_make_field_row(_tr(window, "Status", "状态"), page.lbl_dashboard_status, label_width=76))
    run_card.body.addWidget(page.bar_active_run)
    run_card.body.addWidget(_make_compact_field_grid(
        [
            (_tr(window, "Progress", "进度"), page.lbl_dashboard_counts),
            (_tr(window, "Stage", "阶段"), page.lbl_dashboard_stage),
            (_tr(window, "Filter chain", "滤波链"), page.lbl_active_filters),
        ],
        columns=1,
    ))
    run_buttons = QWidget()
    run_buttons_layout = QHBoxLayout(run_buttons)
    run_buttons_layout.setContentsMargins(0, 0, 0, 0)
    run_buttons_layout.setSpacing(8)
    run_buttons_layout.addWidget(page.btn_run_full, 2)
    run_buttons_layout.addWidget(page.btn_pause_run, 1)
    run_buttons_layout.addWidget(page.btn_stop_run, 1)
    run_buttons_layout.addWidget(page.btn_console_run, 1)
    run_buttons_layout.addWidget(page.btn_open_preview, 1)
    run_card.body.addWidget(run_buttons)

    data_card = CardFrame(_tr(window, "Data and outputs", "数据与输出"))
    data_row = QGridLayout()
    data_row.setContentsMargins(0, 0, 0, 0)
    data_row.setHorizontalSpacing(12)
    data_row.setVerticalSpacing(12)
    data_row.addWidget(_compact_metric(_tr(window, "Available months", "可用月份"), page.lbl_data_count, page.lbl_time_span), 0, 0)
    data_row.addWidget(_compact_metric(_tr(window, "Output root", "输出根目录"), page.lbl_output_root, page.lbl_output_hint), 0, 1)
    data_row.setColumnStretch(0, 1)
    data_row.setColumnStretch(1, 2)
    data_card.body.addLayout(data_row)

    output_card = CardFrame(_tr(window, "Output structure", "输出结构"))
    output_grid = _make_compact_field_grid(
        [
            (_tr(window, "Latest artifact", "最近产物"), page.lbl_preview_artifact),
            (_tr(window, "Root", "根目录"), page.lbl_preview_root),
            (_tr(window, "Local", "本地输出"), page.lbl_preview_output),
            (_tr(window, "Stacks", "栈文件"), page.lbl_preview_stacks),
            (_tr(window, "Monthly", "月度产品"), page.lbl_preview_monthly),
            (_tr(window, "Figures", "图件"), page.lbl_preview_plots),
            (_tr(window, "Logs", "日志"), page.lbl_preview_logs),
            (_tr(window, "Runtime", "运行环境"), page.lbl_system_runtime),
        ],
        columns=2,
    )
    output_card.body.addWidget(output_grid)

    grid = QGridLayout()
    grid.setHorizontalSpacing(18)
    grid.setVerticalSpacing(18)
    grid.addWidget(top, 0, 0, 1, 2)
    grid.addWidget(run_card, 1, 0)
    grid.addWidget(data_card, 1, 1)
    grid.addWidget(output_card, 2, 0, 1, 2)
    grid.setColumnStretch(0, 1)
    grid.setColumnStretch(1, 1)
    wrapper = QWidget()
    wrapper.setLayout(grid)
    page.body.addWidget(wrapper)
    page.body.addStretch(1)
    page._enhanced_dashboard_installed = True

    def update_system_info() -> None:
        page.lbl_system_time.setText(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        page.lbl_system_memory.setText(_memory_text())
        page.lbl_system_runtime.setText(f"Python {platform.python_version()} | {platform.system()} {platform.release()}")

    page._system_timer = QTimer(window)
    page._system_timer.timeout.connect(update_system_info)
    page._system_timer.start(1000)
    update_system_info()


def install_nav_footer_identity(window) -> None:
    footer = getattr(window, "nav_rail", None).findChild(QFrame, "NavFooter") if getattr(window, "nav_rail", None) is not None else None
    if footer is None:
        return
    labels = footer.findChildren(QLabel)
    if len(labels) >= 3:
        labels[0].setText("L2")
        labels[1].setText(_tr(window, "Version / User", "版本 / 用户"))
        labels[2].setText(f"v{APP_VERSION} · {getpass.getuser()}")


def install_shell_app_icon(window) -> QIcon | None:
    path = app_icon_path()
    if path is None:
        return None
    icon = install_app_icon(window)
    if icon.isNull():
        return None
    return icon


def install_tray(window, icon: QIcon | None = None) -> None:
    existing = getattr(window, "tray_icon", None)
    if _qt_object_is_alive(existing):
        if icon is not None and not icon.isNull():
            existing.setIcon(icon)
        window._tray_installed = True
        return
    if getattr(window, "_tray_installed", False):
        return
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return
    icon = icon or install_shell_app_icon(window) or window.windowIcon()
    tray = QSystemTrayIcon(icon, window)
    tray.setToolTip("GRACE Level-2 Pipeline")
    menu = QMenu()
    action_open = QAction(_tr(window, "Open", "打开"), tray)
    action_exit = QAction(_tr(window, "Exit", "退出"), tray)
    menu.addAction(action_open)
    menu.addSeparator()
    menu.addAction(action_exit)
    tray.setContextMenu(menu)

    def open_window() -> None:
        window.showNormal()
        window.raise_()
        window.activateWindow()

    def exit_app() -> None:
        window._force_exit = True
        tray.hide()
        QApplication.quit()

    action_open.triggered.connect(open_window)
    action_exit.triggered.connect(exit_app)
    tray.activated.connect(lambda reason: open_window() if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick) else None)
    tray.show()
    window.tray_icon = tray
    window._tray_installed = True

    original_close_event = window.closeEvent

    def close_event(self, event: QCloseEvent) -> None:
        if getattr(self, "_force_exit", False):
            original_close_event(event)
            return
        event.ignore()
        self.hide()
        if _qt_object_is_alive(getattr(self, "tray_icon", None)):
            self.tray_icon.showMessage(
                "GRACE-L2",
                _tr(self, "The program is still running in the system tray. Right-click the tray icon to open or exit.", "程序已最小化到系统托盘。右键托盘图标可打开或退出。"),
                QSystemTrayIcon.Information,
                2500,
            )

    window.closeEvent = MethodType(close_event, window)


def install_taskbar_progress(window) -> None:
    if getattr(window, "_taskbar_progress_installed", False):
        return
    taskbar = WindowsTaskbarProgress(window)
    window.taskbar_progress = taskbar

    original_set_run_active = window.set_run_active
    original_set_run_progress = window.set_run_progress

    def set_run_active(self, active: bool, text: str = "", indeterminate: bool = False):
        original_set_run_active(active, text, indeterminate)
        if active:
            self.taskbar_progress.set_progress(None if indeterminate else 0)
        else:
            self.taskbar_progress.clear()

    def set_run_progress(self, pct: float, detail: str = "", stage: str = ""):
        original_set_run_progress(pct, detail, stage)
        self.taskbar_progress.set_progress(None if pct < 0 else pct)

    window.set_run_active = MethodType(set_run_active, window)
    window.set_run_progress = MethodType(set_run_progress, window)
    window._taskbar_progress_installed = True


def install_shell_enhancements(window) -> None:
    icon = install_shell_app_icon(window)
    install_dashboard_overview(window)
    install_nav_footer_identity(window)
    install_tray(window, icon)
    install_taskbar_progress(window)
