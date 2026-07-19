"""Patch MainWindow preference application for runtime theme modes."""

def install():
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication
    from grace_pipeline.ui.qt import main_window, preferences, theme
    from grace_pipeline.ui.qt.runtime_theme_simple import norm_theme
    def apply(self, pref, persist=True):
        pref = preferences.UIPreferences(norm_theme(getattr(pref, "theme", "system")), preferences._normalize_language(getattr(pref, "language", "zh")))
        self.ui_preferences = pref
        if persist:
            preferences.save_ui_preferences(pref, settings=self._settings_store)
        app = QApplication.instance() or QGuiApplication.instance()
        if app is not None:
            self._apply_font_scale_to_app(app)
            app.setStyleSheet(theme.app_stylesheet(pref.theme, app=app) + self._font_scale_stylesheet())
        self._resolved_theme = theme.resolve_theme_mode(pref.theme, app=app)
        self.setWindowTitle(self.translate_text(self._window_title_base))
        self.refresh_translations()
        if getattr(self, "controller", None) is not None:
            self.controller.refresh_plot_theme()
        QTimer.singleShot(0, lambda: self._apply_responsive_layout(force=True))
    main_window.MainWindow.apply_ui_preferences = apply
