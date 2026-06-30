"""Theme primitives for the PySide6 desktop shell."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication


LIGHT_COLOR = {
    "background": "#f7f9fc",
    "surface": "#ffffff",
    "surface_low": "#f0f4f8",
    "surface_mid": "#e8eff4",
    "surface_high": "#d9e4ec",
    "nav_surface": "#eef3f8",
    "nav_footer": "#edf2f8",
    "top_surface": "#fbfcfe",
    "border": "#d7e1e8",
    "border_strong": "#a8b3bb",
    "text": "#29343a",
    "text_muted": "#566168",
    "primary": "#005db5",
    "primary_dim": "#0052a0",
    "primary_soft": "#d6e3ff",
    "success": "#4caf50",
    "warning": "#f2a100",
    "danger": "#c44f4f",
    "console_bg": "#121b2f",
    "console_tab_bg": "#17233c",
    "console_text": "#91f1c4",
    "console_muted": "#9fb2ce",
    "console_warn": "#f4d98a",
    "progress_panel_bg": "#fff7e1",
    "progress_panel_border": "#f3ddb0",
    "toolbar_bg": "rgba(255, 255, 255, 0.82)",
    "danger_surface": "#fff5f5",
    "danger_surface_hover": "#ffecec",
    "danger_border": "#f4d0d0",
    "success_bg": "#dbf5de",
    "success_text": "#23773e",
    "warning_bg": "#fff0cf",
    "warning_text": "#9b6a00",
    "danger_bg": "#ffe4e4",
    "danger_text": "#a33434",
    "disabled_bg": "#b9cde5",
    "disabled_text": "#f5f8fc",
    "disabled_border": "#b9cde5",
    "ghost_disabled_text": "#95a0a7",
    "ghost_disabled_border": "#dde5eb",
    "placeholder_bg": "#eef4f8",
    "input_bg": "#FFFFFF",
    "input_border": "#D5DEE0",
    "text_disabled": "#9CA3AF",
}


DARK_COLOR = {
    "background": "#0d1726",
    "surface": "#142235",
    "surface_low": "#1a2b42",
    "surface_mid": "#223750",
    "surface_high": "#2b4664",
    "nav_surface": "#111d2d",
    "nav_footer": "#101a29",
    "top_surface": "#101b2b",
    "border": "#2d4663",
    "border_strong": "#577393",
    "text": "#e8f0fb",
    "text_muted": "#a8bdd5",
    "primary": "#59a4ff",
    "primary_dim": "#458fdf",
    "primary_soft": "#173660",
    "success": "#6bd68c",
    "warning": "#ffb347",
    "danger": "#ff8b8b",
    "console_bg": "#08101b",
    "console_tab_bg": "#101b2c",
    "console_text": "#8ff0c0",
    "console_muted": "#8ea4bf",
    "console_warn": "#f4d98a",
    "progress_panel_bg": "#2b2515",
    "progress_panel_border": "#6d5930",
    "toolbar_bg": "rgba(20, 34, 53, 0.92)",
    "danger_surface": "#351a20",
    "danger_surface_hover": "#452028",
    "danger_border": "#71424c",
    "success_bg": "#193726",
    "success_text": "#84f0a5",
    "warning_bg": "#3b2c13",
    "warning_text": "#ffc86f",
    "danger_bg": "#402128",
    "danger_text": "#ffb1b1",
    "disabled_bg": "#41556f",
    "disabled_text": "#cad6e3",
    "disabled_border": "#41556f",
    "ghost_disabled_text": "#71859e",
    "ghost_disabled_border": "#39516d",
    "placeholder_bg": "#1b2a40",
    "input_bg": "#0F172A",
    "input_border": "#334155",
    "text_disabled": "#64748B",
}


COLOR = dict(LIGHT_COLOR)
_FONT_BOOTSTRAPPED = False


def ensure_application_font(app=None) -> str:
    """Load a readable CJK-capable UI font when Qt starts without a font database."""

    global _FONT_BOOTSTRAPPED
    app = app or QGuiApplication.instance()
    if app is None:
        return ""
    preferred = (
        "Microsoft YaHei UI",
        "Microsoft YaHei",
        "Noto Sans SC",
        "SimHei",
        "SimSun",
        "Segoe UI",
        "Arial",
    )
    families = set(QFontDatabase.families())
    if not families and not _FONT_BOOTSTRAPPED:
        font_dir = Path("C:/Windows/Fonts")
        for name in (
            "msyh.ttc",
            "NotoSansSC-VF.ttf",
            "Noto Sans SC (TrueType).otf",
            "simhei.ttf",
            "simsun.ttc",
            "SegUIVar.ttf",
            "arial.ttf",
        ):
            path = font_dir / name
            if path.exists():
                QFontDatabase.addApplicationFont(str(path))
        _FONT_BOOTSTRAPPED = True
        families = set(QFontDatabase.families())

    chosen = next((family for family in preferred if family in families), "")
    if chosen and app is not None:
        app.setFont(QFont(chosen, 10))
    return chosen


def resolve_system_theme(app=None) -> str:
    hints = getattr(app or QGuiApplication.instance(), "styleHints", lambda: None)()
    if hints is not None and hasattr(hints, "colorScheme"):
        with_value = hints.colorScheme()
        if with_value == Qt.ColorScheme.Dark:
            return "dark"
    return "light"


def resolve_theme_mode(theme_mode: str = "system", app=None) -> str:
    theme_mode = str(theme_mode or "system").strip().lower()
    if theme_mode == "system":
        return resolve_system_theme(app=app)
    if theme_mode in {"light", "blue", "green", "sepia", "violet"}:
        return "light"
    if theme_mode in {"dark", "graphite"}:
        return "dark"
    return "light"


def palette_for_theme(theme_mode: str = "system", app=None) -> dict[str, str]:
    theme_mode = str(theme_mode or "system").strip().lower()
    resolved = resolve_theme_mode(theme_mode=theme_mode, app=app)
    colors = dict(DARK_COLOR if resolved == "dark" else LIGHT_COLOR)
    if theme_mode == "blue":
        colors.update(
            {
                "background": "#f3f8ff",
                "surface_low": "#eaf3fc",
                "nav_surface": "#e8f1fb",
                "nav_footer": "#e2edf8",
                "top_surface": "#f8fbff",
                "primary": "#0068b7",
                "primary_dim": "#005799",
                "primary_soft": "#d7eaff",
            }
        )
    elif theme_mode == "green":
        colors.update(
            {
                "background": "#f4faf6",
                "surface_low": "#EEF7F1",
                "nav_surface": "#F0F7F2",
                "nav_footer": "#E2F0E8",
                "top_surface": "#FFFFFF",
                "border": "#D6E5DC",
                "primary": "#1F7A4D",
                "primary_dim": "#16653F",
                "primary_soft": "#DDF3E5",
            }
        )
    elif theme_mode == "sepia":
        colors.update(
            {
                "background": "#faf6ef",
                "surface_low": "#f3eadf",
                "surface_mid": "#eadcc9",
                "nav_surface": "#f1e6d8",
                "nav_footer": "#eadcc9",
                "top_surface": "#fffaf2",
                "border": "#d9c6ad",
                "primary": "#8a5a24",
                "primary_dim": "#744819",
                "primary_soft": "#f1dfc4",
            }
        )
    elif theme_mode == "violet":
        colors.update(
            {
                "background": "#f8f6ff",
                "surface_low": "#f0ebfb",
                "nav_surface": "#eee8fa",
                "nav_footer": "#e7dff5",
                "top_surface": "#fbfaff",
                "primary": "#6d4db8",
                "primary_dim": "#583b9b",
                "primary_soft": "#e5dcff",
            }
        )
    elif theme_mode == "graphite":
        colors.update(
            {
                "background": "#101214",
                "surface": "#1a1f24",
                "surface_low": "#22282e",
                "surface_mid": "#2b333a",
                "surface_high": "#36404a",
                "nav_surface": "#15191d",
                "nav_footer": "#12161a",
                "top_surface": "#171b20",
                "border": "#333c45",
                "primary": "#8fb8ff",
                "primary_dim": "#72a2ef",
                "primary_soft": "#24364f",
            }
        )
    return colors


def set_active_palette(colors: dict[str, str]) -> None:
    COLOR.clear()
    COLOR.update(colors)


def _font_stack(ui_font: str | None = None) -> str:
    preferred = str(ui_font or "default").strip()
    if not preferred or preferred == "default":
        preferred = "Microsoft YaHei UI"
    if preferred == "Microsoft YaHei UI":
        return '"Microsoft YaHei UI", "Segoe UI", sans-serif'
    if preferred == "Segoe UI":
        return '"Segoe UI", "Microsoft YaHei UI", sans-serif'
    return f'"{preferred}", "Microsoft YaHei UI", "Segoe UI", sans-serif'


def _mono_stack(mono_font: str | None = None) -> str:
    preferred = str(mono_font or "default").strip()
    if not preferred or preferred == "default":
        preferred = "Consolas"
    if preferred == "Consolas":
        return '"Consolas", "JetBrains Mono", monospace'
    return f'"{preferred}", "Consolas", "JetBrains Mono", monospace'


def build_stylesheet(colors: dict[str, str], ui_font: str | None = None, mono_font: str | None = None) -> str:
    ui_stack = _font_stack(ui_font)
    mono_stack = _mono_stack(mono_font)
    return f"""
QWidget {{
    background: {colors["background"]};
    color: {colors["text"]};
    font-family: {ui_stack};
    font-size: 13px;
}}

QLabel,
QCheckBox,
QRadioButton {{
    background: transparent;
}}

QCheckBox,
QRadioButton {{
    spacing: 8px;
    padding: 2px 0;
}}

QCheckBox::indicator,
QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {colors["border_strong"]};
    border-radius: 4px;
    background: {colors["surface"]};
}}

QRadioButton::indicator {{
    border-radius: 8px;
}}

QCheckBox::indicator:hover,
QRadioButton::indicator:hover {{
    border-color: {colors["primary"]};
}}

QCheckBox::indicator:checked,
QRadioButton::indicator:checked {{
    background: {colors["primary"]};
    border: 1px solid {colors["primary"]};
}}

QCheckBox::indicator:checked:disabled,
QRadioButton::indicator:checked:disabled {{
    background: {colors["disabled_bg"]};
    border-color: {colors["disabled_border"]};
}}

QCheckBox::indicator:disabled,
QRadioButton::indicator:disabled {{
    background: {colors["surface_low"]};
    border-color: {colors["ghost_disabled_border"]};
}}

QMainWindow {{
    background: {colors["background"]};
}}

QFrame#NavigationRail {{
    background: {colors["nav_surface"]};
    border-right: 1px solid {colors["border"]};
}}

QFrame#NavFooter {{
    background: {colors["nav_footer"]};
    border-top: 1px solid {colors["border"]};
}}

QPushButton#NavButton {{
    background: transparent;
    border: none;
    border-left: 2px solid transparent;
    border-radius: 0px;
    color: {colors["text_muted"]};
    padding: 14px 18px;
    text-align: left;
    font-size: 14px;
    font-weight: 500;
}}

QPushButton#NavButton:hover {{
    background: {colors["placeholder_bg"]};
    color: {colors["text"]};
}}

QPushButton#NavButton:checked {{
    background: {colors["primary_soft"]};
    border-left: 3px solid {colors["primary"]};
    color: {colors["primary"]};
    font-weight: 600;
}}

QFrame#TopBar {{
    background: {colors["top_surface"]};
    border-bottom: 1px solid {colors["border"]};
}}

QLabel#AppTitle {{
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}

QLabel#Breadcrumb {{
    color: {colors["primary"]};
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}

QPushButton#PrimaryButton {{
    background: {colors["primary"]};
    color: white;
    border: 1px solid {colors["primary"]};
    border-radius: 3px;
    padding: 8px 16px;
    font-weight: 600;
}}

QPushButton#PrimaryButton:hover {{
    background: {colors["primary_dim"]};
}}

QPushButton#PrimaryButton:disabled {{
    background: {colors["disabled_bg"]};
    color: {colors["text"]};
    border-color: {colors["border_strong"]};
}}

QPushButton#GhostButton {{
    background: transparent;
    color: {colors["text_muted"]};
    border: 1px solid {colors["border"]};
    border-radius: 3px;
    padding: 8px 14px;
    font-weight: 600;
}}

QPushButton#GhostButton:hover {{
    background: {colors["surface_low"]};
    color: {colors["text"]};
}}

QPushButton#GhostButton:checked {{
    background: {colors["surface_low"]};
    color: {colors["text"]};
    border-color: {colors["border_strong"]};
}}

QPushButton#GhostButton:disabled {{
    background: {colors["surface_low"]};
    color: {colors["text_muted"]};
    border-color: {colors["border"]};
}}

QPushButton#SoftButton {{
    background: {colors["primary_soft"]};
    color: {colors["primary"]};
    border: 1px solid {colors["primary_soft"]};
    border-radius: 3px;
    padding: 8px 14px;
    font-weight: 600;
}}

QPushButton#SoftButton:hover {{
    background: {colors["placeholder_bg"]};
    border-color: {colors["primary_soft"]};
}}

QPushButton#PathButton {{
    background: {colors["surface"]};
    color: {colors["text"]};
    border: 1px solid {colors["border"]};
    border-radius: 3px;
    padding: 8px 13px;
    font-weight: 600;
}}

QPushButton#PathButton:hover {{
    background: {colors["surface_low"]};
    border-color: {colors["border_strong"]};
}}

QPushButton#PathButton:disabled {{
    background: {colors["surface_low"]};
    color: {colors["text_muted"]};
    border-color: {colors["border"]};
}}

QToolButton#IconButton {{
    background: transparent;
    color: {colors["text_muted"]};
    border: 1px solid {colors["border"]};
    border-radius: 4px;
    padding: 6px 9px;
    font-size: 18px;
    font-weight: 700;
}}

QToolButton#IconButton:hover,
QToolButton#IconButton:checked {{
    background: {colors["surface_low"]};
    color: {colors["primary"]};
    border-color: {colors["border_strong"]};
}}

QPushButton#DangerGhostButton {{
    background: {colors["danger_surface"]};
    color: {colors["danger"]};
    border: 1px solid {colors["danger_border"]};
    border-radius: 3px;
    padding: 8px 14px;
    font-weight: 600;
}}

QPushButton#DangerGhostButton:hover {{
    background: {colors["danger_surface_hover"]};
}}

QPushButton#DangerGhostButton:disabled {{
    background: {colors["surface_low"]};
    color: {colors["text_muted"]};
    border-color: {colors["border"]};
}}

QFrame#PageRoot {{
    background: {colors["background"]};
}}

QFrame#PageCard {{
    background: {colors["surface"]};
    border: 1px solid {colors["border"]};
    border-radius: 4px;
}}

QFrame#ActionZone {{
    background: {colors["surface"]};
    border: 1px solid {colors["border"]};
    border-radius: 4px;
}}

QFrame#WorkflowStep {{
    background: {colors["surface_low"]};
    border: 1px solid {colors["border"]};
    border-radius: 4px;
}}

QFrame#FilterMethodList {{
    background: {colors["surface_low"]};
    border: 1px solid {colors["border"]};
    border-radius: 4px;
}}

QFrame#FilterParameterPanel {{
    background: {colors["surface"]};
    border: 1px solid {colors["border"]};
    border-radius: 4px;
}}

QLabel#FilterParameterTitle {{
    color: {colors["text"]};
    font-size: 14px;
    font-weight: 700;
}}

QCheckBox[filterMethod="true"] {{
    padding: 8px 8px;
    border-radius: 4px;
    color: {colors["text"]};
}}

QCheckBox[filterMethod="true"]:hover {{
    background: {colors["surface_mid"]};
}}

QCheckBox[filterActive="true"] {{
    background: {colors["primary_soft"]};
    color: {colors["primary"]};
    font-weight: 700;
}}

QLabel#WorkflowStepNumber {{
    background: {colors["primary"]};
    color: white;
    border-radius: 10px;
    padding: 2px 7px;
    font-size: 11px;
    font-weight: 700;
}}

QFrame#CardHeader {{
    background: {colors["surface_low"]};
    border-bottom: 1px solid {colors["border"]};
}}

QLabel#CardTitle {{
    font-size: 13px;
    font-weight: 600;
    color: {colors["text_muted"]};
    letter-spacing: 0;
}}

QLabel#PageTitle {{
    font-size: 24px;
    font-weight: 600;
}}

QLabel#PageSubtitle {{
    color: {colors["text_muted"]};
    font-size: 14px;
}}

QLabel#TopProgressLabel {{
    color: {colors["text"]};
    font-size: 12px;
    font-weight: 700;
}}

QLabel#TopProgressDetail {{
    color: {colors["text_muted"]};
    font-family: {mono_stack};
    font-size: 11px;
}}

QLabel#TopProgressValue {{
    color: {colors["warning_text"]};
    font-size: 12px;
    font-weight: 700;
}}

QWidget#PageHeader,
QWidget#PageHeader QLabel,
QWidget#CardBody,
QFrame#CardHeader QLabel,
QWidget#ActionZoneBody,
QFrame#ActionZone QLabel {{
    background: transparent;
}}

QLabel#StatusBadge {{
    border-radius: 10px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0;
}}

QLabel#StatusBadge[variant="primary"] {{
    background: {colors["primary_soft"]};
    color: {colors["primary"]};
}}

QLabel#StatusBadge[variant="success"] {{
    background: {colors["success_bg"]};
    color: {colors["success_text"]};
}}

QLabel#StatusBadge[variant="warning"] {{
    background: {colors["warning_bg"]};
    color: {colors["warning_text"]};
}}

QLabel#StatusBadge[variant="danger"] {{
    background: {colors["danger_bg"]};
    color: {colors["danger_text"]};
}}

QLabel#LabelCaps {{
    color: {colors["text_muted"]};
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0;
}}

QLabel#ValueText {{
    color: {colors["text"]};
    font-size: 13px;
}}

QLabel#PreviewStatusValue {{
    color: {colors["text"]};
    font-size: 13px;
}}

QLabel#MonoText {{
    font-family: {mono_stack};
    color: {colors["text_muted"]};
    font-size: 13px;
}}

QLabel#MetricValue {{
    font-size: 30px;
    font-weight: 700;
}}

QProgressBar {{
    border: 1px solid {colors["border"]};
    background: {colors["surface_low"]};
    border-radius: 5px;
    min-height: 10px;
    max-height: 10px;
}}

QProgressBar::chunk {{
    background: {colors["primary"]};
    border-radius: 4px;
}}

QProgressBar[active="false"]::chunk {{
    background: transparent;
}}

QProgressBar#TopProgressBar {{
    min-height: 16px;
    max-height: 16px;
    background: {colors["surface_mid"]};
    border-radius: 8px;
}}

QProgressBar#TopProgressBar::chunk {{
    background: {colors["warning"]};
    border-radius: 8px;
}}

QFrame#TopProgressPanel {{
    background: {colors["progress_panel_bg"]};
    border: 1px solid {colors["progress_panel_border"]};
    border-radius: 18px;
}}

QTableWidget {{
    background: {colors["surface"]};
    alternate-background-color: {colors["surface_low"]};
    gridline-color: {colors["border"]};
    border: none;
}}

QHeaderView::section {{
    background: {colors["surface_low"]};
    color: {colors["text_muted"]};
    border: none;
    border-bottom: 1px solid {colors["border"]};
    padding: 8px;
    font-size: 11px;
    font-weight: 700;
}}

QLineEdit, QComboBox, QPlainTextEdit, QTextEdit {{
    background: {colors.get("input_bg", colors["surface"])};
    border: 1px solid {colors.get("input_border", colors["border"])};
    border-radius: 3px;
    padding: 8px;
}}

QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border-color: {colors["primary"]};
}}

QComboBox QAbstractItemView {{
    background: {colors["surface"]};
    color: {colors["text"]};
    border: 1px solid {colors["border"]};
    selection-background-color: {colors["primary_soft"]};
    selection-color: {colors["text"]};
}}

QComboBox QAbstractItemView::item {{
    background: {colors["surface"]};
    color: {colors["text"]};
    min-height: 24px;
    padding: 4px 8px;
}}

QComboBox QAbstractItemView::item:selected {{
    background: {colors["primary_soft"]};
    color: {colors["text"]};
}}

QFrame#PreviewSidebar {{
    background: {colors["surface"]};
    border-right: 1px solid {colors["border"]};
}}

QFrame#PreviewSidebarFooter {{
    background: {colors["surface"]};
    border-top: 1px solid {colors["border"]};
}}

QFrame#PreviewToolbarHost {{
    background: {colors["toolbar_bg"]};
    border: 1px solid {colors["border"]};
    border-radius: 4px;
}}

QFrame#PreviewToolbarHost QToolButton {{
    background: transparent;
    color: {colors["text_muted"]};
    border: none;
    padding: 4px 6px;
}}

QFrame#PreviewToolbarHost QToolButton:hover {{
    background: {colors["surface_low"]};
    color: {colors["text"]};
}}

QFrame#ConsolePanel {{
    background: {colors["console_bg"]};
    border-top: 1px solid {colors["border"]};
}}

QFrame#ConsoleHeader {{
    background: {colors["console_bg"]};
    border: 1px solid {colors["console_tab_bg"]};
    border-radius: 4px;
}}

QLabel#ConsoleHeaderTitle {{
    color: {colors["console_muted"]};
    font-size: 13px;
    font-weight: 600;
}}

QPushButton#ConsoleButton {{
    background: {colors["console_tab_bg"]};
    color: {colors["console_text"]};
    border: 1px solid {colors["border_strong"]};
    border-radius: 3px;
    padding: 7px 14px;
    font-weight: 600;
}}

QPushButton#ConsoleButton:hover {{
    background: {colors["surface_mid"]};
    color: {colors["console_text"]};
}}

QWidget#DownloadControlStrip {{
    background: {colors["surface_low"]};
    border-radius: 3px;
}}

QFrame#FilterExportPanel {{
    background: {colors["surface_low"]};
    border: 1px solid {colors["border"]};
    border-radius: 3px;
}}

QFrame#PreviewSidebar QWidget,
QWidget#FieldRow,
QWidget#FieldBlock,
QWidget#InlineField,
QScrollArea {{
    background: transparent;
}}

QFrame#PreviewSidebarFooter QPushButton#PrimaryButton {{
    background: {colors["primary"]};
    color: white;
    border: 1px solid {colors["primary"]};
    border-radius: 3px;
    padding: 8px 16px;
    font-weight: 600;
}}

QFrame#PreviewSidebarFooter QPushButton#PrimaryButton:hover {{
    background: {colors["primary_dim"]};
    color: white;
}}

QFrame#PreviewSidebarFooter QPushButton#GhostButton {{
    background: transparent;
    color: {colors["text_muted"]};
    border: 1px solid {colors["border"]};
    border-radius: 3px;
    padding: 8px 14px;
    font-weight: 600;
}}

QFrame#PreviewSidebarFooter QPushButton#GhostButton:hover {{
    background: {colors["surface_low"]};
    color: {colors["text"]};
}}

QFrame#PreviewSidebar QCheckBox {{
    background: transparent;
    spacing: 8px;
    padding: 3px 0;
}}

QFrame#PreviewSidebar QCheckBox::indicator {{
    width: 16px;
    height: 16px;
}}

QFrame#PreviewSidebar QComboBox QAbstractItemView,
QFrame#PreviewSidebar QComboBox QAbstractItemView::item {{
    background: {colors["surface"]};
    color: {colors["text"]};
}}

QDockWidget {{
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}}

QDockWidget::title {{
    background: {colors["console_bg"]};
    color: {colors["console_text"]};
    padding: 10px;
    text-align: left;
    font-family: {mono_stack};
    letter-spacing: 1px;
}}

QTabWidget::pane {{
    border: none;
}}

QTabWidget#ConsoleTabs::pane {{
    background: {colors["console_bg"]};
    border: none;
}}

QTabWidget#ConsoleTabs QTabBar {{
    background: {colors["console_tab_bg"]};
}}

QTabWidget#ConsoleTabs QStackedWidget {{
    background: {colors["console_bg"]};
}}

QTabBar::tab {{
    background: {colors["console_tab_bg"]};
    color: {colors["console_muted"]};
    padding: 8px 14px;
}}

QTabBar::tab:selected {{
    background: {colors["console_bg"]};
    color: {colors["console_text"]};
}}
"""


def app_stylesheet(theme_mode: str = "system", app=None, ui_font: str | None = None, mono_font: str | None = None) -> str:
    ensure_application_font(app=app)
    colors = palette_for_theme(theme_mode=theme_mode, app=app)
    set_active_palette(colors)
    return build_stylesheet(colors, ui_font=ui_font, mono_font=mono_font)


APP_STYLESHEET = app_stylesheet("light")
