"""Main application window for the PySide6 shell."""

from __future__ import annotations

import contextlib

from PySide6.QtCore import Qt, QSignalBlocker, QTimer
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from grace_pipeline.ui.qt.mock_data import CONSOLE_LINES, NAV_ITEMS, PAGE_TITLES
from grace_pipeline.ui.qt.i18n import translate_text
from grace_pipeline.ui.qt.pages import (
    BasinPage,
    DashboardPage,
    DataPathsPage,
    LeakagePage,
    PreviewPage,
    ProcessingSetupPage,
    RunMonitorPage,
)
from grace_pipeline.ui.qt.preferences import UIPreferences, load_ui_preferences, save_ui_preferences
from grace_pipeline.ui.qt.theme import app_stylesheet, resolve_theme_mode
from grace_pipeline.ui.qt.widgets import ElidedLabel, NavigationButton, build_badge


class MainWindow(QMainWindow):
    """Stitch-inspired desktop shell with left rail, top bar, pages, and console."""

    def __init__(self, load_persisted: bool = True, settings_store=None):
        super().__init__()
        self._window_title_base = "GRACE Level-2 Pipeline"
        self._settings_store = settings_store
        self.ui_preferences = load_ui_preferences(settings_store) if load_persisted else UIPreferences()
        self._resolved_theme = resolve_theme_mode(self.ui_preferences.theme)
        self._style_hints_bound = False
        self.setWindowTitle(self.translate_text(self._window_title_base))
        self.resize(1600, 980)
        self.setMinimumSize(1320, 820)
        self._initial_fit_done = False
        self._layout_bucket: tuple[int, int, int] | None = None
        self._nav_buttons: dict[str, NavigationButton] = {}
        self._pages: dict[str, QWidget] = {}
        self._tracked_screen = None
        self._screen_changed_bound = False
        self._last_console_height = 220
        self._nav_collapsed = False
        self._font_scale_delta = 1

        self._build_shell()
        self._bind_system_theme_changes()
        self.apply_ui_preferences(self.ui_preferences, persist=False)
        self.set_active_page("dashboard")

        from grace_pipeline.ui.qt.controller import MainWindowController

        self.controller = MainWindowController(self)

    def _build_shell(self):
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.nav_rail = self._build_nav_rail()
        root.addWidget(self.nav_rail)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        content_layout.addWidget(self._build_top_bar())

        self.content_splitter = QSplitter(Qt.Vertical)
        self.content_splitter.setChildrenCollapsible(False)

        self.stack = QStackedWidget()
        self.page_dashboard = DashboardPage()
        self.page_data_paths = DataPathsPage()
        self.page_processing = ProcessingSetupPage()
        self.page_leakage = LeakagePage()
        self.page_basin = BasinPage()
        self.page_preview = PreviewPage()
        self.page_monitor = RunMonitorPage()
        self.btn_run = self.page_dashboard.btn_run_full
        self.btn_pause = self.page_dashboard.btn_pause_run
        self.btn_stop = self.page_dashboard.btn_stop_run
        self.btn_console_dashboard = self.page_dashboard.btn_console_run
        self.btn_console_dashboard.setCheckable(True)
        self.btn_console_dashboard.toggled.connect(self._toggle_console)
        self.stack.addWidget(self._register_page("dashboard", self.page_dashboard))
        self.stack.addWidget(self._register_page("data_paths", self.page_data_paths))
        self.stack.addWidget(self._register_page("processing", self.page_processing))
        self.stack.addWidget(self._register_page("leakage", self.page_leakage))
        self.stack.addWidget(self._register_page("basin", self.page_basin))
        self.stack.addWidget(self._register_page("preview", self.page_preview))
        self.stack.addWidget(self._register_page("monitor", self.page_monitor))
        self.content_splitter.addWidget(self.stack)
        self.console_panel = self._build_console_panel()
        self.content_splitter.addWidget(self.console_panel)
        self.content_splitter.setStretchFactor(0, 10)
        self.content_splitter.setStretchFactor(1, 3)
        self.content_splitter.setSizes([900, 0])
        content_layout.addWidget(self.content_splitter, 1)
        self._set_run_button_state(False)

        root.addWidget(content, 1)
        self.setCentralWidget(central)

    def _build_nav_rail(self) -> QWidget:
        rail = QFrame()
        rail.setObjectName("NavigationRail")
        rail.setFixedWidth(240)

        layout = QVBoxLayout(rail)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        brand = QWidget()
        brand_layout = QVBoxLayout(brand)
        brand_layout.setContentsMargins(24, 22, 24, 24)
        brand_layout.setSpacing(4)

        title = QLabel("GRACE-L2")
        title.setStyleSheet("font-size: 28px; font-weight: 700;")
        subtitle = QLabel("PRECISION PIPELINE")
        subtitle.setObjectName("LabelCaps")
        brand_layout.addWidget(title)
        brand_layout.addWidget(subtitle)
        layout.addWidget(brand)

        nav_wrap = QWidget()
        nav_layout = QVBoxLayout(nav_wrap)
        nav_layout.setContentsMargins(0, 12, 0, 12)
        nav_layout.setSpacing(2)
        for key, label in NAV_ITEMS:
            btn = NavigationButton(label)
            btn.clicked.connect(lambda checked=False, page_key=key: self.set_active_page(page_key))
            nav_layout.addWidget(btn)
            self._nav_buttons[key] = btn
        nav_layout.addStretch(1)
        layout.addWidget(nav_wrap, 1)

        footer = QFrame()
        footer.setObjectName("NavFooter")
        foot_layout = QVBoxLayout(footer)
        foot_layout.setContentsMargins(18, 14, 18, 14)
        foot_layout.setSpacing(6)
        user = QLabel("L2")
        user.setFixedSize(30, 30)
        user.setAlignment(Qt.AlignCenter)
        user.setStyleSheet("background: #005db5; color: white; border-radius: 15px; font-weight: 700;")
        foot_layout.addWidget(user, alignment=Qt.AlignLeft)
        foot_layout.addWidget(QLabel("Local Workspace"))
        role = QLabel("Python / MATLAB")
        role.setObjectName("MonoText")
        foot_layout.addWidget(role)
        layout.addWidget(footer)
        return rail

    def _build_top_bar(self) -> QWidget:
        top = QFrame()
        top.setObjectName("TopBar")
        layout = QHBoxLayout(top)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(18)

        left = QHBoxLayout()
        left.setSpacing(12)
        self.btn_nav_toggle = QToolButton()
        self.btn_nav_toggle.setObjectName("IconButton")
        self.btn_nav_toggle.setText("☰")
        self.btn_nav_toggle.setCheckable(True)
        self.btn_nav_toggle.setToolTip("Collapse or expand the left navigation")
        self.btn_nav_toggle.clicked.connect(self._toggle_nav_rail)
        left.addWidget(self.btn_nav_toggle)
        self.app_title = QLabel("GRACE LEVEL-2 PIPELINE")
        self.app_title.setObjectName("AppTitle")
        divider = QLabel("/")
        divider.setObjectName("LabelCaps")
        self.breadcrumb = QLabel(PAGE_TITLES["dashboard"])
        self.breadcrumb.setObjectName("Breadcrumb")
        left.addWidget(self.app_title)
        left.addWidget(divider)
        left.addWidget(self.breadcrumb)
        left.addStretch(1)
        layout.addLayout(left, 1)

        self.pipeline_status = build_badge("CONFIG READY", "success")
        layout.addWidget(self.pipeline_status)

        self.top_progress_wrap = QFrame()
        self.top_progress_wrap.setObjectName("TopProgressPanel")
        self.top_progress_wrap.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        progress_layout = QHBoxLayout(self.top_progress_wrap)
        progress_layout.setContentsMargins(12, 8, 12, 8)
        progress_layout.setSpacing(10)
        self.top_progress_label = ElidedLabel("Preparing run")
        self.top_progress_label.setObjectName("TopProgressLabel")
        self.top_progress_detail = QLabel("0 / 0")
        self.top_progress_detail.setObjectName("TopProgressDetail")
        self.top_progress_detail.setMinimumWidth(72)
        self.top_progress_percent = QLabel("0%")
        self.top_progress_percent.setObjectName("TopProgressValue")
        self.top_progress_percent.setMinimumWidth(36)
        self.top_progress_bar = QProgressBar()
        self.top_progress_bar.setObjectName("TopProgressBar")
        self.top_progress_bar.setMinimumWidth(220)
        self.top_progress_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.top_progress_bar.setFixedHeight(16)
        self.top_progress_bar.setRange(0, 100)
        self.top_progress_bar.setValue(0)
        self.top_progress_bar.setTextVisible(False)
        progress_layout.addWidget(self.top_progress_label, 2)
        progress_layout.addWidget(self.top_progress_detail, 0)
        progress_layout.addWidget(self.top_progress_percent, 0)
        progress_layout.addWidget(self.top_progress_bar, 3)
        self.top_progress_wrap.setVisible(False)
        layout.addWidget(self.top_progress_wrap, 2)

        self.btn_console = QPushButton("Console")
        self.btn_console.setObjectName("GhostButton")
        self.btn_console.setCheckable(True)
        self.btn_console.setToolTip("Show or hide process logs")
        self.btn_help = QPushButton("Help")
        self.btn_help.setObjectName("GhostButton")
        self.btn_help.setToolTip("Open the desktop workflow guide")
        self.btn_settings = QPushButton("Settings")
        self.btn_settings.setObjectName("GhostButton")
        self.btn_settings.setToolTip("Theme and language preferences")
        self.btn_console.toggled.connect(self._toggle_console)
        for btn in (self.btn_help, self.btn_console, self.btn_settings):
            layout.addWidget(btn)

        return top

    def _build_console_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("ConsolePanel")
        panel.setMinimumHeight(180)
        panel.setMaximumHeight(300)
        layout = QVBoxLayout(panel)
        # Align console body with page cards (same horizontal gutter as content pages).
        layout.setContentsMargins(24, 8, 24, 8)
        layout.setSpacing(0)

        tabs = QTabWidget()
        tabs.setObjectName("ConsoleTabs")
        self.console_tabs = tabs

        self.console_text = QTextEdit()
        self.console_text.setReadOnly(True)
        self.console_text.setStyleSheet("background: #121b2f; color: #91f1c4; border: none; font-family: 'JetBrains Mono', Consolas, monospace;")
        self.console_text.setPlainText("\n".join(CONSOLE_LINES))
        tabs.addTab(self.console_text, "Console")

        self.filters_text = QTextEdit()
        self.filters_text.setReadOnly(True)
        self.filters_text.setStyleSheet("background: #121b2f; color: #9fb2ce; border: none; font-family: 'JetBrains Mono', Consolas, monospace;")
        self.filters_text.setPlainText("[OK] Filter chain controls are linked to the active configuration.")
        tabs.addTab(self.filters_text, "Filters")

        self.alerts_text = QTextEdit()
        self.alerts_text.setReadOnly(True)
        self.alerts_text.setStyleSheet("background: #121b2f; color: #f4d98a; border: none; font-family: 'JetBrains Mono', Consolas, monospace;")
        self.alerts_text.setPlainText("SYSTEM: Desktop shell is connected to the Python workflow controller.")
        tabs.addTab(self.alerts_text, "Alerts")

        layout.addWidget(tabs)
        self.console_dock = panel
        self.console_dock.hide()
        self.btn_console.setChecked(False)
        return panel

    def _register_page(self, key: str, widget: QWidget) -> QWidget:
        self._pages[key] = widget
        return widget

    def set_active_page(self, key: str):
        if key == "monitor":
            key = "dashboard"
        if key not in self._pages:
            return
        self.stack.setCurrentWidget(self._pages[key])
        self.breadcrumb.setText(PAGE_TITLES[key])
        for btn_key, btn in self._nav_buttons.items():
            btn.setChecked(btn_key == key)
        self._apply_responsive_layout(force=(key == "preview"))
        self.refresh_translations()

    def set_top_status(self, text: str, variant: str = "primary"):
        self.pipeline_status.setText(text)
        self.pipeline_status.setProperty("variant", variant)
        self.pipeline_status.style().unpolish(self.pipeline_status)
        self.pipeline_status.style().polish(self.pipeline_status)
        self.refresh_translations()

    def _append_console_line(self, text: str, tag: str = "stdout"):
        self.console_text.append(text)
        if tag == "stderr":
            self.alerts_text.append(text)
        else:
            self.filters_text.append(text)

    def _toggle_console(self, checked: bool):
        self.set_console_visible(checked)

    def _sync_console_button(self, visible: bool):
        self.btn_console.blockSignals(True)
        self.btn_console.setChecked(visible)
        self.btn_console.blockSignals(False)
        if hasattr(self, "btn_console_dashboard"):
            self.btn_console_dashboard.blockSignals(True)
            self.btn_console_dashboard.setChecked(visible)
            self.btn_console_dashboard.blockSignals(False)

    def _set_run_button_state(self, active: bool):
        run_button = getattr(self, "btn_run", None)
        pause_buttons = [btn for btn in (getattr(self, "btn_pause", None), self.page_monitor.btn_pause_run) if btn is not None]
        stop_buttons = [btn for btn in (getattr(self, "btn_stop", None), self.page_monitor.btn_abort_pipeline) if btn is not None]
        if run_button is not None:
            run_button.setEnabled(not active)
        for btn in pause_buttons:
            btn.setEnabled(active)
            if not active:
                btn.setText("Pause")
        for btn in stop_buttons:
            btn.setEnabled(active)

    def set_pause_action_paused(self, paused: bool):
        text = "Resume" if paused else "Pause"
        for btn in (getattr(self, "btn_pause", None), self.page_monitor.btn_pause_run):
            if btn is not None:
                btn.setText(text)

    def set_console_visible(self, visible: bool):
        if visible:
            self.console_dock.show()
            total = max(360, self.content_splitter.height())
            panel_h = min(self._last_console_height, max(180, total // 2))
            self.content_splitter.setSizes([max(320, total - panel_h), panel_h])
        else:
            sizes = self.content_splitter.sizes()
            if len(sizes) > 1 and sizes[1] > 0:
                self._last_console_height = sizes[1]
            total = sum(sizes) if sizes else max(360, self.content_splitter.height())
            self.content_splitter.setSizes([total, 0])
            self.console_dock.hide()
        self._sync_console_button(visible)

    def _toggle_nav_rail(self):
        self.set_nav_collapsed(not self._nav_collapsed)

    def set_nav_collapsed(self, collapsed: bool):
        self._nav_collapsed = bool(collapsed)
        self.nav_rail.setVisible(not self._nav_collapsed)
        self.nav_rail.setFixedWidth(0 if self._nav_collapsed else 240)
        self.btn_nav_toggle.setChecked(self._nav_collapsed)
        self._layout_bucket = None
        self._apply_responsive_layout(force=True)

    def set_run_active(self, active: bool, text: str = "", indeterminate: bool = False):
        self._set_run_button_state(active)
        if active:
            self.top_progress_wrap.setVisible(True)
        elif text == "Idle":
            self.top_progress_wrap.setVisible(False)
        if text:
            self.top_progress_label.setText(text)
        if not active and text == "Idle":
            self.top_progress_detail.setText("0 / 0")
            self.top_progress_percent.setText("0%")
        if indeterminate:
            self.top_progress_bar.setRange(0, 0)
        elif self.top_progress_bar.minimum() == 0 and self.top_progress_bar.maximum() == 0:
            self.top_progress_bar.setRange(0, 100)
        self.refresh_translations()

    def set_run_progress(self, pct: float, detail: str = "", stage: str = ""):
        self.top_progress_wrap.setVisible(True)
        if pct < 0:
            self.top_progress_bar.setRange(0, 0)
            self.top_progress_percent.setText("...")
        else:
            self.top_progress_bar.setRange(0, 100)
            clamped = int(round(max(0.0, min(100.0, pct))))
            self.top_progress_bar.setValue(clamped)
            self.top_progress_percent.setText(f"{clamped}%")
        if detail:
            self.top_progress_detail.setText(detail.replace("/", " / "))
        if stage:
            self.top_progress_label.setText(stage)
        self.refresh_translations()

    def showEvent(self, event):
        super().showEvent(event)
        self._bind_screen_signals()
        if not self._initial_fit_done:
            screen = self._current_screen()
            if screen is not None:
                geo = screen.availableGeometry()
                target_w = self._clamp(int(geo.width() * 0.97), min(1280, geo.width()), geo.width())
                target_h = self._clamp(int(geo.height() * 0.96), min(820, geo.height()), geo.height())
                self.resize(target_w, target_h)
                self.move(geo.x() + max(0, (geo.width() - target_w) // 2), geo.y() + max(0, (geo.height() - target_h) // 2))
            self._initial_fit_done = True
        self._apply_responsive_layout(force=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._bind_screen_signals()
        self._apply_responsive_layout()

    def _current_screen(self):
        screen = None
        handle = self.windowHandle()
        if handle is not None:
            screen = handle.screen()
        if screen is None:
            screen = self.screen()
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        return screen

    def _current_screen_metrics(self) -> tuple[int, int, float]:
        screen = self._current_screen()
        if screen is None:
            return (1600, 980, 1.0)
        geo = screen.availableGeometry()
        dpi_scale = float(screen.logicalDotsPerInch() / 96.0)
        dpi_scale = max(1.0, min(2.0, dpi_scale))
        return (int(geo.width()), int(geo.height()), dpi_scale)

    def _bind_screen_signals(self):
        handle = self.windowHandle()
        if handle is not None and not self._screen_changed_bound:
            handle.screenChanged.connect(self._on_screen_changed)
            self._screen_changed_bound = True
        screen = self._current_screen()
        if screen is self._tracked_screen:
            return
        if self._tracked_screen is not None:
            with contextlib.suppress(Exception):
                self._tracked_screen.availableGeometryChanged.disconnect(self._on_screen_metrics_changed)
            with contextlib.suppress(Exception):
                self._tracked_screen.geometryChanged.disconnect(self._on_screen_metrics_changed)
        self._tracked_screen = screen
        if screen is not None:
            screen.availableGeometryChanged.connect(self._on_screen_metrics_changed)
            screen.geometryChanged.connect(self._on_screen_metrics_changed)

    def _bind_system_theme_changes(self):
        app = QApplication.instance() or QGuiApplication.instance()
        hints = getattr(app, "styleHints", lambda: None)()
        if hints is None or self._style_hints_bound or not hasattr(hints, "colorSchemeChanged"):
            return
        hints.colorSchemeChanged.connect(self._on_system_color_scheme_changed)
        self._style_hints_bound = True

    def _on_system_color_scheme_changed(self, *_args):
        if self.ui_preferences.theme == "system":
            self.apply_ui_preferences(self.ui_preferences, persist=False)

    def translate_text(self, text: str) -> str:
        return translate_text(text, self.ui_preferences.language)

    def apply_ui_preferences(self, preferences: UIPreferences, persist: bool = True):
        theme = str(preferences.theme or "system").strip().lower()
        language = str(preferences.language or "en").strip().lower()
        if theme not in {"system", "light", "dark"}:
            theme = "system"
        if language not in {"en", "zh"}:
            language = "en"
        self.ui_preferences = UIPreferences(theme=theme, language=language)
        if persist:
            save_ui_preferences(self.ui_preferences, settings=self._settings_store)
        app = QApplication.instance() or QGuiApplication.instance()
        if app is not None:
            stylesheet = app_stylesheet(self.ui_preferences.theme, app=app)
            self._apply_font_scale_to_app(app)
            app.setStyleSheet(stylesheet + self._font_scale_stylesheet())
        self._resolved_theme = resolve_theme_mode(self.ui_preferences.theme, app=app)
        self.setWindowTitle(self.translate_text(self._window_title_base))
        self.refresh_translations()
        if getattr(self, "controller", None) is not None:
            self.controller.refresh_plot_theme()

    def _apply_font_scale_to_app(self, app) -> None:
        font = QFont(app.font())
        font.setPointSize(max(9, min(16, 10 + int(self._font_scale_delta))))
        app.setFont(font)

    def _font_scale_stylesheet(self) -> str:
        base = max(12, min(18, 13 + int(self._font_scale_delta)))
        small = max(11, base - 1)
        micro = max(10, base - 2)
        title = base + 13
        metric = base + 17
        return f"""
QWidget {{
    font-size: {base}px;
}}
QPushButton#NavButton {{
    font-size: {base}px;
}}
QLabel#AppTitle,
QLabel#Breadcrumb,
QLabel#TopProgressLabel,
QLabel#TopProgressValue {{
    font-size: {small}px;
}}
QLabel#CardTitle,
QLabel#LabelCaps,
QLabel#StatusBadge,
QLabel#TopProgressDetail {{
    font-size: {micro}px;
}}
QLabel#PageTitle {{
    font-size: {title}px;
}}
QLabel#PageSubtitle,
QLabel#ValueText,
QLabel#PreviewStatusValue {{
    font-size: {base}px;
}}
QLabel#MetricValue {{
    font-size: {metric}px;
}}
QCheckBox::indicator,
QRadioButton::indicator {{
    width: {base + 4}px;
    height: {base + 4}px;
}}
"""

    def _set_font_scale_delta(self, value: int) -> None:
        self._font_scale_delta = max(-2, min(5, int(value)))
        self.apply_ui_preferences(self.ui_preferences, persist=False)
        self._layout_bucket = None
        self._apply_responsive_layout(force=True)

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            key = event.key()
            if key in (Qt.Key_Plus, Qt.Key_Equal):
                self._set_font_scale_delta(self._font_scale_delta + 1)
                event.accept()
                return
            if key == Qt.Key_Minus:
                self._set_font_scale_delta(self._font_scale_delta - 1)
                event.accept()
                return
            if key == Qt.Key_0:
                self._set_font_scale_delta(1)
                event.accept()
                return
        super().keyPressEvent(event)

    def refresh_translations(self):
        self.setWindowTitle(self.translate_text(self._window_title_base))
        widgets = [self] + self.findChildren(QWidget)
        for widget in widgets:
            self._translate_widget_text(widget)
            self._translate_widget_placeholder(widget)
            if isinstance(widget, QComboBox):
                self._translate_combo_items(widget)
            if isinstance(widget, QTabWidget):
                self._translate_tab_widget(widget)
            if isinstance(widget, QTableWidget):
                self._translate_table_headers(widget)
                self._translate_table_items(widget)

    def _translate_widget_text(self, widget: QWidget):
        if bool(widget.property("skipTextTranslation")):
            return
        if not isinstance(widget, (QLabel, QPushButton, QCheckBox, QRadioButton, QToolButton)):
            return
        if not hasattr(widget, "text"):
            return
        current = widget.text()
        base = getattr(widget, "_tr_base_text", None)
        last = getattr(widget, "_tr_last_text", None)
        if base is None:
            base = current
        elif current not in {base, last} and current.strip():
            base = current
        widget._tr_base_text = base
        translated = self.translate_text(base)
        if current != translated:
            widget.setText(translated)
        widget._tr_last_text = translated

    def _translate_widget_placeholder(self, widget: QWidget):
        if not isinstance(widget, QLineEdit):
            return
        current = widget.placeholderText()
        if not current:
            return
        base = getattr(widget, "_tr_base_placeholder", None)
        last = getattr(widget, "_tr_last_placeholder", None)
        if base is None:
            base = current
        elif current not in {base, last} and current.strip():
            base = current
        widget._tr_base_placeholder = base
        translated = self.translate_text(base)
        if current != translated:
            widget.setPlaceholderText(translated)
        widget._tr_last_placeholder = translated

    def _translate_combo_items(self, widget: QComboBox):
        current_items = [widget.itemText(index) for index in range(widget.count())]
        base_items = getattr(widget, "_tr_base_items", None)
        last_items = getattr(widget, "_tr_last_items", None)
        if base_items is None or len(base_items) != widget.count():
            base_items = list(current_items)
        elif current_items != last_items and current_items != base_items:
            base_items = list(current_items)
        widget._tr_base_items = list(base_items)
        translated_items = [self.translate_text(text) for text in base_items]
        blocker = QSignalBlocker(widget)
        try:
            for index, text in enumerate(translated_items):
                if widget.itemText(index) != text:
                    widget.setItemText(index, text)
        finally:
            del blocker
        widget._tr_last_items = translated_items

    def _translate_tab_widget(self, widget: QTabWidget):
        current_tabs = [widget.tabText(index) for index in range(widget.count())]
        base_tabs = getattr(widget, "_tr_base_tabs", None)
        last_tabs = getattr(widget, "_tr_last_tabs", None)
        if base_tabs is None:
            base_tabs = list(current_tabs)
        elif current_tabs != last_tabs and current_tabs != base_tabs:
            base_tabs = list(current_tabs)
        widget._tr_base_tabs = list(base_tabs)
        translated_tabs = [self.translate_text(text) for text in base_tabs]
        for index, text in enumerate(translated_tabs):
            if widget.tabText(index) != text:
                widget.setTabText(index, text)
        widget._tr_last_tabs = translated_tabs

    def _translate_table_headers(self, widget: QTableWidget):
        current_headers = []
        for index in range(widget.columnCount()):
            item = widget.horizontalHeaderItem(index)
            current_headers.append(item.text() if item is not None else "")
        base_headers = getattr(widget, "_tr_base_headers", None)
        last_headers = getattr(widget, "_tr_last_headers", None)
        if base_headers is None or len(base_headers) != widget.columnCount():
            base_headers = list(current_headers)
        elif current_headers != last_headers and current_headers != base_headers:
            base_headers = list(current_headers)
        widget._tr_base_headers = list(base_headers)
        translated_headers = [self.translate_text(text) for text in base_headers]
        for index, text in enumerate(translated_headers):
            item = widget.horizontalHeaderItem(index)
            if item is not None and item.text() != text:
                item.setText(text)
        widget._tr_last_headers = translated_headers

    def _translate_table_items(self, widget: QTableWidget):
        for row in range(widget.rowCount()):
            for col in range(widget.columnCount()):
                item = widget.item(row, col)
                if item is None:
                    continue
                current = item.text()
                base = getattr(item, "_tr_base_text", None)
                last = getattr(item, "_tr_last_text", None)
                if base is None:
                    base = current
                elif current not in {base, last} and current.strip():
                    base = current
                item._tr_base_text = base
                translated = self.translate_text(base)
                if current != translated:
                    item.setText(translated)
                item._tr_last_text = translated

    def _on_screen_changed(self, *_args):
        self._bind_screen_signals()
        self._on_screen_metrics_changed()

    def _ensure_window_fits_available_geometry(self):
        if self.isMaximized() or self.isFullScreen():
            return
        screen = self._current_screen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        target_w = min(self.width(), geo.width())
        target_h = min(self.height(), geo.height())
        target_x = min(max(self.x(), geo.x()), geo.x() + max(0, geo.width() - target_w))
        target_y = min(max(self.y(), geo.y()), geo.y() + max(0, geo.height() - target_h))
        if target_w != self.width() or target_h != self.height():
            self.resize(target_w, target_h)
        if target_x != self.x() or target_y != self.y():
            self.move(target_x, target_y)

    def _on_screen_metrics_changed(self, *_args):
        self._ensure_window_fits_available_geometry()
        self._layout_bucket = None
        self._apply_responsive_layout(force=True)
        if self.stack.currentWidget() is getattr(self, "page_preview", None) and getattr(self, "controller", None) is not None:
            QTimer.singleShot(0, self.controller.on_preview_home)

    @staticmethod
    def _clamp(value: int, low: int, high: int) -> int:
        return max(low, min(high, value))

    def _apply_responsive_layout(self, force: bool = False):
        screen_w, screen_h, dpi_scale = self._current_screen_metrics()
        bucket = (
            screen_w // 120,
            screen_h // 90,
            self.width() // 120,
            self.height() // 90,
            int(round(dpi_scale * 10)),
        )
        if not force and bucket == self._layout_bucket:
            return
        self._layout_bucket = bucket

        nav_width = self._clamp(int(screen_w * 0.16 / dpi_scale), 200, 250)
        if self._nav_collapsed:
            self.nav_rail.setFixedWidth(0)
            nav_width = 0
        else:
            self.nav_rail.setFixedWidth(nav_width)

        min_w_floor = min(1100, screen_w)
        min_h_floor = min(720, screen_h)
        min_w = self._clamp(int(screen_w * 0.70), min_w_floor, max(min_w_floor, min(1600, screen_w)))
        min_h = self._clamp(int(screen_h * 0.74), min_h_floor, max(min_h_floor, min(980, screen_h)))
        self.setMinimumSize(min_w, min_h)

        page = getattr(self, "page_preview", None)
        if page is None:
            return

        content_w = max(720, self.width() - nav_width)
        content_h = max(560, self.height() - 90)

        sidebar_w = self._clamp(int(content_w * (0.19 if dpi_scale <= 1.1 else 0.21)), 240, 340)
        if page.sidebar_panel.isVisible():
            page.sidebar_panel.setMinimumWidth(self._clamp(sidebar_w - 18, 220, 320))
            page.sidebar_panel.setMaximumWidth(self._clamp(sidebar_w + 18, 280, 380))
            page.page_splitter.setSizes([sidebar_w, max(860, content_w - sidebar_w)])
        else:
            page.page_splitter.setSizes([0, max(860, content_w)])

        if page.card_status.isVisible():
            status_h = self._clamp(int(content_h * 0.11), 64, 96)
            plot_h = max(460, content_h - status_h - 54)
            page.main_splitter.setSizes([plot_h, status_h])
        else:
            page.main_splitter.setSizes([max(500, content_h - 24), 0])
