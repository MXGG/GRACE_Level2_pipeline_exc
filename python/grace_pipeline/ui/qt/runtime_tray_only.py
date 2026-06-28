"""Runtime tray close behavior."""

def apply(window, app=None):
    from PySide6.QtCore import QEvent, QObject
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon
    app = app or QApplication.instance()
    if app is None or getattr(window, "_runtime_tray", False):
        return
    app.setQuitOnLastWindowClosed(False)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return
    icon = window.windowIcon()
    if icon.isNull():
        icon = app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
    tray = QSystemTrayIcon(icon, window)
    menu = QMenu()
    open_action = QAction(window.translate_text("Open GRACE-L2"), menu)
    exit_action = QAction(window.translate_text("Exit"), menu)
    menu.addAction(open_action)
    menu.addAction(exit_action)
    tray.setContextMenu(menu)
    def show_window():
        window.showNormal(); window.raise_(); window.activateWindow()
    open_action.triggered.connect(show_window)
    exit_action.triggered.connect(lambda: (setattr(window, "_force_exit", True), tray.hide(), app.quit()))
    class CloseFilter(QObject):
        def eventFilter(self, obj, event):
            if obj is window and event.type() == QEvent.Type.Close and not getattr(window, "_force_exit", False):
                event.ignore(); window.hide(); return True
            return False
    close_filter = CloseFilter(window)
    window.installEventFilter(close_filter)
    tray.show()
    window._runtime_tray = True
    window._runtime_tray_icon = tray
    window._runtime_tray_filter = close_filter
