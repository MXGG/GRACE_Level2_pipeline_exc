"""Theme primitives for the PySide6 desktop shell."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication

SEMANTIC_COLOR_TOKENS = (
    "app_bg",
    "sidebar_bg",
    "content_bg",
    "card_bg",
    "card_header_bg",
    "card_border",
    "field_bg",
    "field_border",
    "field_focus_border",
    "status_bg",
    "primary",
    "primary_soft",
    "hover_bg",
    "selected_bg",
    "read_only_bg",
    "table_header_bg",
)


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
    "success": "#2f855a",
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
    "success_bg": "#eef8f1",
    "success_text": "#20613f",
    "warning_bg": "#fff7e5",
    "warning_text": "#9b6a00",
    "danger_bg": "#fff0f0",
    "danger_text": "#a33434",
    "disabled_bg": "#e8eff4",
    "disabled_text": "#7d898f",
    "disabled_border": "#d7e1e8",
    "ghost_disabled_text": "#95a0a7",
    "ghost_disabled_border": "#dde5eb",
    "placeholder_bg": "#eef4f8",
    "input_bg": "#FFFFFF",
    "input_border": "#D5DEE0",
    "text_disabled": "#9CA3AF",
    "control_bg": "#FFFFFF",
    "control_hover_bg": "#eef4f8",
    "control_border": "#a8b3bb",
    "control_checked": "#005db5",
    "control_checked_hover": "#0052a0",
    "control_disabled_bg": "#f0f4f8",
    "control_disabled_border": "#d7e1e8",
    "focus_ring": "#005db5",
    # Semantic visual-hierarchy tokens.  Keep these names stable: pages and
    # components should describe their role rather than borrow an unrelated
    # surface colour.
    "app_bg": "#edf2f7",
    "sidebar_bg": "#f3f6f9",
    "content_bg": "#f7f9fc",
    "card_bg": "#ffffff",
    "card_header_bg": "#f5f8fb",
    "card_border": "#d7e1e8",
    "field_bg": "#ffffff",
    "field_border": "#cbd5df",
    "field_focus_border": "#005db5",
    "status_bg": "#f8fafc",
    "primary_soft": "#d6e3ff",
    "hover_bg": "#f1f5f9",
    "selected_bg": "#e5eefb",
    "read_only_bg": "#f6f8fa",
    "table_header_bg": "#f5f8fb",
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
    "control_bg": "#142235",
    "control_hover_bg": "#1a2b42",
    "control_border": "#577393",
    "control_checked": "#59a4ff",
    "control_checked_hover": "#458fdf",
    "control_disabled_bg": "#1a2b42",
    "control_disabled_border": "#2d4663",
    "focus_ring": "#59a4ff",
    "app_bg": "#091321",
    "sidebar_bg": "#111d2d",
    "content_bg": "#0d1726",
    "card_bg": "#142235",
    "card_header_bg": "#182940",
    "card_border": "#2d4663",
    "field_bg": "#0f172a",
    "field_border": "#3c526b",
    "field_focus_border": "#59a4ff",
    "status_bg": "#101b2b",
    "primary_soft": "#173660",
    "hover_bg": "#1a2b42",
    "selected_bg": "#173660",
    "read_only_bg": "#111d2d",
    "table_header_bg": "#182940",
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
                "app_bg": "#edf4fb",
                "sidebar_bg": "#f1f6fb",
                "content_bg": "#f6f9fd",
                "card_bg": "#ffffff",
                "card_header_bg": "#f2f7fc",
                "card_border": "#cedbe7",
                "field_bg": "#ffffff",
                "field_border": "#c7d6e5",
                "field_focus_border": "#0068b7",
                "status_bg": "#f8fafc",
                "hover_bg": "#edf5fc",
                "selected_bg": "#dfedfb",
                "read_only_bg": "#f7f9fb",
                "table_header_bg": "#f2f7fc",
            }
        )
    elif theme_mode == "green":
        colors.update(
            {
                "background": "#f3f7f5",
                "surface": "#ffffff",
                "surface_low": "#f6f9f7",
                "surface_mid": "#eaf1ed",
                "surface_high": "#dce9e2",
                "nav_surface": "#f5f8f6",
                "nav_footer": "#e8f1ec",
                "top_surface": "#ffffff",
                "border": "#d5e1da",
                "border_strong": "#9fb5a9",
                "text": "#223129",
                "text_muted": "#58685f",
                "primary": "#176b45",
                "primary_dim": "#0f5636",
                "primary_soft": "#e1f0e8",
                "success": "#2f855a",
                "success_bg": "#edf7f0",
                "success_text": "#20613f",
                "placeholder_bg": "#f0f5f2",
                "input_border": "#cad8d0",
                "app_bg": "#edf3ef",
                "sidebar_bg": "#f3f7f4",
                "content_bg": "#f7f9f8",
                "card_bg": "#ffffff",
                "card_header_bg": "#f3f8f5",
                "card_border": "#d5e1da",
                "field_bg": "#ffffff",
                "field_border": "#cad8d0",
                "field_focus_border": "#176b45",
                "status_bg": "#f8faf9",
                "hover_bg": "#f0f6f2",
                "selected_bg": "#e2f1e8",
                "read_only_bg": "#f7f9f8",
                "table_header_bg": "#f3f8f5",
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
                "app_bg": "#f2eee8",
                "sidebar_bg": "#f8f5f0",
                "content_bg": "#fbf9f6",
                "card_bg": "#ffffff",
                "card_header_bg": "#fbf5ec",
                "card_border": "#dfd1c1",
                "field_bg": "#ffffff",
                "field_border": "#d5c7b8",
                "field_focus_border": "#8a5a24",
                "status_bg": "#faf9f7",
                "hover_bg": "#f8f3ed",
                "selected_bg": "#f4e6d2",
                "read_only_bg": "#f8f7f5",
                "table_header_bg": "#fbf5ec",
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
                "app_bg": "#f1eef8",
                "sidebar_bg": "#f6f3fb",
                "content_bg": "#f9f8fc",
                "card_bg": "#ffffff",
                "card_header_bg": "#f6f3fb",
                "card_border": "#ddd5ec",
                "field_bg": "#ffffff",
                "field_border": "#d3cbe2",
                "field_focus_border": "#6d4db8",
                "status_bg": "#f9f9fb",
                "hover_bg": "#f3effa",
                "selected_bg": "#e9e2f8",
                "read_only_bg": "#f8f8fa",
                "table_header_bg": "#f6f3fb",
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
                "app_bg": "#0d1013",
                "sidebar_bg": "#15191d",
                "content_bg": "#111519",
                "card_bg": "#1a1f24",
                "card_header_bg": "#20262c",
                "card_border": "#333c45",
                "field_bg": "#111418",
                "field_border": "#46515c",
                "field_focus_border": "#8fb8ff",
                "status_bg": "#171b20",
                "hover_bg": "#22282e",
                "selected_bg": "#24364f",
                "read_only_bg": "#15191d",
                "table_header_bg": "#20262c",
            }
        )
    colors.update(
        {
            "input_bg": colors["field_bg"],
            "input_border": colors["field_border"],
            "control_bg": colors["field_bg"],
            "control_hover_bg": colors["hover_bg"],
            "control_border": colors["field_border"],
            "control_checked": colors["primary"],
            "control_checked_hover": colors["primary_dim"],
            "control_disabled_bg": colors["read_only_bg"],
            "control_disabled_border": colors["field_border"],
            "focus_ring": colors["field_focus_border"],
            "disabled_bg": colors["surface_mid"],
            "disabled_text": colors["text_disabled"],
            "disabled_border": colors["border"],
            "ghost_disabled_text": colors["text_disabled"],
            "ghost_disabled_border": colors["border"],
            "button_secondary_bg": colors["card_bg"],
            "button_secondary_hover": colors["hover_bg"],
            "button_secondary_border": colors["border_strong"],
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


def build_stylesheet(
    colors: dict[str, str], ui_font: str | None = None, mono_font: str | None = None
) -> str:
    ui_stack = _font_stack(ui_font)
    mono_stack = _mono_stack(mono_font)
    icon_dir = (Path(__file__).with_name("assets") / "icons").as_posix()
    check_icon = f"{icon_dir}/check_white.svg"
    return f"""
QWidget {{
    color: {colors["text"]};
    font-family: {ui_stack};
    font-size: 13px;
}}

QMainWindow,
QDialog,
QMessageBox {{
    background: {colors["app_bg"]};
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
    color: {colors["text"]};
    font-size: 13px;
}}

QPushButton {{
    background: {colors["button_secondary_bg"]};
    color: {colors["text"]};
    border: 1px solid {colors["button_secondary_border"]};
    border-radius: 5px;
    padding: 8px 14px;
    font-weight: 600;
}}

QPushButton:hover {{
    background: {colors["button_secondary_hover"]};
    color: {colors["primary"]};
    border-color: {colors["primary"]};
}}

QPushButton:pressed {{
    background: {colors["surface_mid"]};
    border-color: {colors["primary_dim"]};
}}

QPushButton:disabled {{
    background: {colors["disabled_bg"]};
    color: {colors["disabled_text"]};
    border-color: {colors["disabled_border"]};
}}

QToolButton {{
    background: {colors["button_secondary_bg"]};
    color: {colors["text"]};
    border: 1px solid {colors["button_secondary_border"]};
    border-radius: 5px;
    padding: 5px 8px;
}}

QToolButton:hover {{
    background: {colors["button_secondary_hover"]};
    color: {colors["primary"]};
    border-color: {colors["primary"]};
}}

QToolButton:disabled {{
    background: {colors["disabled_bg"]};
    color: {colors["disabled_text"]};
    border-color: {colors["disabled_border"]};
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {colors["control_border"]};
    border-radius: 3px;
    background: {colors["control_bg"]};
}}

QCheckBox::indicator:hover {{
    border-color: {colors["control_checked"]};
    background: {colors["control_hover_bg"]};
}}

QCheckBox::indicator:checked {{
    background: {colors["control_checked"]};
    border-color: {colors["control_checked"]};
    image: url("{check_icon}");
}}

QCheckBox::indicator:disabled {{
    background: {colors["control_disabled_bg"]};
    border-color: {colors["control_disabled_border"]};
    image: none;
}}

QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {colors["control_border"]};
    border-radius: 8px;
    background: {colors["control_bg"]};
}}

QRadioButton::indicator:hover {{
    border-color: {colors["control_checked"]};
    background: {colors["control_hover_bg"]};
}}

QRadioButton::indicator:checked {{
    width: 8px;
    height: 8px;
    border: 5px solid {colors["control_checked"]};
    border-radius: 9px;
    background: {colors["control_bg"]};
}}

QRadioButton::indicator:disabled {{
    background: {colors["control_disabled_bg"]};
    border-color: {colors["control_disabled_border"]};
}}

QCheckBox[switchRole="true"] {{
    spacing: 12px;
    min-height: 30px;
}}

QCheckBox[switchRole="true"]::indicator {{
    width: 46px;
    height: 24px;
    min-width: 46px;
    max-width: 46px;
    min-height: 24px;
    max-height: 24px;
    border: 1px solid {colors["control_border"]};
    border-radius: 12px;
    background: {colors["control_disabled_bg"]};
    image: none;
}}

QCheckBox[switchRole="true"]::indicator:hover {{
    border-color: {colors["control_checked"]};
    background: {colors["control_hover_bg"]};
}}

QCheckBox[switchRole="true"]::indicator:checked {{
    border-color: {colors["control_checked"]};
    background: {colors["control_checked"]};
    image: url("{check_icon}");
}}

QCheckBox[switchRole="true"]::indicator:checked:hover {{
    border-color: {colors["control_checked_hover"]};
    background: {colors["control_checked_hover"]};
}}

QCheckBox[switchRole="true"]::indicator:disabled {{
    border-color: {colors["control_disabled_border"]};
    background: {colors["control_disabled_bg"]};
    image: none;
}}

QCheckBox::indicator:focus,
QRadioButton::indicator:focus {{
    border-color: {colors["focus_ring"]};
}}

QMainWindow {{
    background: {colors["app_bg"]};
}}

QFrame#NavigationRail {{
    background: {colors["sidebar_bg"]};
    border-right: 1px solid {colors["card_border"]};
}}

QWidget#NavBrand,
QWidget#NavItems {{
    background: transparent;
}}

QLabel#NavBrandTitle {{
    color: {colors["text"]};
    font-size: 28px;
    font-weight: 700;
}}

QLabel#NavBrandMark {{
    background: {colors["primary_soft"]};
    color: {colors["primary"]};
    border: 1px solid {colors["border"]};
    border-radius: 8px;
    font-size: 15px;
    font-weight: 800;
}}

QFrame#NavFooter {{
    background: {colors["nav_footer"]};
    border-top: 1px solid {colors["border"]};
}}

QLabel#NavAvatar {{
    background: {colors["primary"]};
    color: white;
    border-radius: 15px;
    font-weight: 700;
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

QPushButton#NavButton[compact="true"] {{
    padding: 12px 0px;
    text-align: center;
}}

QPushButton#NavButton:hover {{
    background: {colors["hover_bg"]};
    color: {colors["text"]};
}}

QPushButton#NavButton:checked {{
    background: {colors["selected_bg"]};
    border-left: 3px solid {colors["primary"]};
    color: {colors["primary"]};
    font-weight: 600;
}}

QPushButton#NavButton:focus {{
    background: {colors["control_hover_bg"]};
    border-right: 2px solid {colors["focus_ring"]};
}}

QPushButton#NavButton:disabled {{
    background: transparent;
    color: {colors["text_disabled"]};
    border-left-color: transparent;
}}

QFrame#TopBar {{
    background: {colors["card_bg"]};
    border-bottom: 1px solid {colors["card_border"]};
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
    border-radius: 5px;
    padding: 8px 16px;
    font-weight: 600;
}}

QPushButton#PrimaryButton:hover {{
    background: {colors["primary_dim"]};
    color: white;
    border-color: {colors["primary_dim"]};
}}

QPushButton#PrimaryButton:disabled {{
    background: {colors["disabled_bg"]};
    color: {colors["disabled_text"]};
    border-color: {colors["disabled_border"]};
}}

QPushButton#GhostButton {{
    background: {colors["button_secondary_bg"]};
    color: {colors["text"]};
    border: 1px solid {colors["button_secondary_border"]};
    border-radius: 5px;
    padding: 8px 14px;
    font-weight: 600;
}}

QPushButton#GhostButton:hover {{
    background: {colors["button_secondary_hover"]};
    color: {colors["primary"]};
    border-color: {colors["primary"]};
}}

QPushButton#GhostButton:checked {{
    background: {colors["primary_soft"]};
    color: {colors["primary"]};
    border-color: {colors["primary"]};
}}

QPushButton#GhostButton:disabled {{
    background: {colors["disabled_bg"]};
    color: {colors["disabled_text"]};
    border-color: {colors["disabled_border"]};
}}

QPushButton#SoftButton {{
    background: {colors["surface"]};
    color: {colors["primary"]};
    border: 1px solid {colors["primary"]};
    border-radius: 5px;
    padding: 8px 14px;
    font-weight: 600;
}}

QPushButton#SoftButton:hover {{
    background: {colors["primary_soft"]};
    color: {colors["primary_dim"]};
    border-color: {colors["primary_dim"]};
}}

QPushButton#SoftButton:disabled {{
    background: {colors["disabled_bg"]};
    color: {colors["disabled_text"]};
    border-color: {colors["disabled_border"]};
}}

QPushButton#PathButton {{
    background: {colors["surface"]};
    color: {colors["text"]};
    border: 1px solid {colors["button_secondary_border"]};
    border-radius: 5px;
    padding: 8px 13px;
    font-weight: 600;
}}

QPushButton#PathButton:hover {{
    background: {colors["button_secondary_hover"]};
    color: {colors["primary"]};
    border-color: {colors["primary"]};
}}

QPushButton#PathButton:disabled {{
    background: {colors["disabled_bg"]};
    color: {colors["disabled_text"]};
    border-color: {colors["disabled_border"]};
}}

QToolButton#IconButton {{
    background: {colors["surface"]};
    color: {colors["text_muted"]};
    border: 1px solid {colors["border"]};
    border-radius: 5px;
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

QToolButton#IconButton:focus {{
    border-color: {colors["focus_ring"]};
    background: {colors["control_hover_bg"]};
}}

QToolButton#IconButton:disabled {{
    background: {colors["control_disabled_bg"]};
    color: {colors["text_disabled"]};
    border-color: {colors["control_disabled_border"]};
}}

QPushButton#DangerGhostButton {{
    background: {colors["danger_surface"]};
    color: {colors["danger"]};
    border: 1px solid {colors["danger_border"]};
    border-radius: 5px;
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

QPushButton#LayerIconButton {{
    background: {colors["surface"]};
    color: {colors["text_muted"]};
    border: 1px solid {colors["border"]};
    border-radius: 5px;
    padding: 0px;
    font-size: 13px;
    font-weight: 700;
}}

QPushButton#LayerIconButton:hover {{
    background: {colors["primary_soft"]};
    color: {colors["primary"]};
    border-color: {colors["border_strong"]};
}}

QPushButton#LayerIconButton:disabled {{
    background: {colors["surface_low"]};
    color: {colors["ghost_disabled_text"]};
    border-color: {colors["ghost_disabled_border"]};
}}

QFrame#PageRoot {{
    background: {colors["content_bg"]};
}}

QWidget#PreviewPage {{
    background: {colors["app_bg"]};
}}

QFrame#PreviewContent {{
    background: {colors["content_bg"]};
}}

QFrame#PreviewMapCard {{
    background: {colors["card_bg"]};
    border: 1px solid {colors["card_border"]};
    border-radius: 6px;
}}

QFrame#PreviewCanvasHost {{
    background: {colors["field_bg"]};
    border: none;
    border-radius: 4px;
}}

QFrame#EmbeddedSection {{
    background: transparent;
    border: 1px solid {colors["card_border"]};
    border-radius: 4px;
}}

QFrame#EmbeddedSectionHeader {{
    background: {colors["read_only_bg"]};
    border: none;
    border-bottom: 1px solid {colors["card_border"]};
}}

QWidget#EmbeddedSectionContent,
QFrame#EmbeddedSectionContent {{
    background: transparent;
    border: none;
}}

QFrame#PageCard {{
    background: {colors["card_bg"]};
    border: 1px solid {colors["card_border"]};
    border-radius: 6px;
}}

QFrame#ActionZone {{
    background: {colors["card_bg"]};
    border: 1px solid {colors["card_border"]};
    border-radius: 6px;
}}

QFrame#WorkflowStep {{
    background: {colors["read_only_bg"]};
    border: 1px solid {colors["card_border"]};
    border-radius: 6px;
}}

QFrame#WorkflowStep[variant="success"] {{
    border-color: {colors["success"]};
    background: {colors["success_bg"]};
}}

QFrame#WorkflowStep[variant="warning"] {{
    border-color: {colors["warning"]};
    background: {colors["warning_bg"]};
}}

QFrame#DashboardStatCard {{
    background: {colors["card_bg"]};
    border: 1px solid {colors["card_border"]};
    border-radius: 6px;
}}

QLabel#DashboardStatValue {{
    color: {colors["text"]};
    font-size: 19px;
    font-weight: 700;
}}

QLabel#DashboardRunStatus {{
    color: {colors["text"]};
    font-size: 18px;
    font-weight: 700;
}}

QLabel#DashboardPath {{
    color: {colors["text"]};
    font-size: 14px;
    font-weight: 700;
}}

QLabel#DashboardCountValue {{
    color: {colors["primary"]};
    font-size: 17px;
    font-weight: 700;
}}

QLabel#WorkflowStepTitle {{
    color: {colors["text"]};
    font-size: 13px;
    font-weight: 700;
}}

QTreeWidget#OutputTree {{
    background: {colors["card_bg"]};
    border: 1px solid {colors["card_border"]};
    border-radius: 4px;
    alternate-background-color: {colors["surface_low"]};
    color: {colors["text"]};
}}

QTreeWidget#OutputTree::item {{
    min-height: 23px;
    padding: 2px 4px;
}}

QTreeWidget#OutputTree::item:selected {{
    background: {colors["primary_soft"]};
    color: {colors["primary"]};
}}

QTreeWidget#OutputTree QHeaderView::section {{
    background: {colors["table_header_bg"]};
    color: {colors["text_muted"]};
    border: 0px;
    border-bottom: 1px solid {colors["border"]};
    padding: 5px 6px;
    font-weight: 700;
}}

QFrame#FilterMethodList {{
    background: {colors["read_only_bg"]};
    border: 1px solid {colors["card_border"]};
    border-radius: 4px;
}}

QFrame#FilterParameterPanel {{
    background: {colors["card_bg"]};
    border: 1px solid {colors["card_border"]};
    border-radius: 4px;
}}

QWidget#DownloadControlStrip {{
    background: transparent;
    border: none;
    border-radius: 0px;
}}

QWidget#DownloadControlStrip QLineEdit,
QWidget#DownloadControlStrip QComboBox {{
    background: {colors["field_bg"]};
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

QPushButton#PlotToolButton {{
    background: {colors["surface"]};
    color: {colors["text"]};
    border: 1px solid {colors["border_strong"]};
    border-radius: 4px;
    padding: 0px;
    font-size: 16px;
    font-weight: 700;
}}

QPushButton#PlotToolButton:hover {{
    background: {colors["primary_soft"]};
    color: {colors["primary"]};
    border-color: {colors["primary"]};
}}

QFrame#CardHeader {{
    background: {colors["card_header_bg"]};
    border-bottom: 1px solid {colors["card_border"]};
}}

QToolButton#SectionToggle {{
    background: transparent;
    color: {colors["text"]};
    border: none;
    border-radius: 4px;
    padding: 2px 4px;
    font-weight: 700;
    text-align: left;
}}

QToolButton#SectionToggle:hover,
QToolButton#SectionToggle:checked {{
    background: {colors["primary_soft"]};
    color: {colors["primary"]};
    border: none;
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

QLabel#ProgressValue {{
    color: {colors["primary"]};
    font-weight: 700;
}}

QLabel#PreviewStatusValue {{
    color: {colors["text_muted"]};
    font-size: 12px;
}}

QFrame#PreviewStatusBar,
QFrame#StatusBar,
QFrame[statusRole="true"] {{
    background: {colors["status_bg"]};
    border: none;
    border-top: 1px solid {colors["card_border"]};
    border-radius: 0px;
}}

QFrame#StatusBarHeader {{
    background: transparent;
    border: none;
    border-bottom: 0px;
}}

QLabel#StatusBarTitle {{
    background: transparent;
    color: {colors["text_muted"]};
    font-size: 11px;
    font-weight: 600;
}}

QFrame#PreviewStatusBar QWidget,
QFrame#PreviewStatusBar QLabel,
QFrame#StatusBar QWidget,
QFrame#StatusBar QLabel,
QFrame[statusRole="true"] QWidget,
QFrame[statusRole="true"] QLabel {{
    background: transparent;
}}

QFrame#PreviewStatusBar QLabel#LabelCaps,
QFrame#StatusBar QLabel#LabelCaps,
QFrame[statusRole="true"] QLabel#LabelCaps {{
    color: {colors["text_muted"]};
    font-size: 11px;
    font-weight: 600;
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
    background: {colors["card_bg"]};
    alternate-background-color: {colors["read_only_bg"]};
    gridline-color: {colors["card_border"]};
    border: none;
}}

QHeaderView::section {{
    background: {colors["table_header_bg"]};
    color: {colors["text_muted"]};
    border: none;
    border-bottom: 1px solid {colors["card_border"]};
    padding: 8px;
    font-size: 11px;
    font-weight: 700;
}}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background: {colors["field_bg"]};
    border: 1px solid {colors["field_border"]};
    border-radius: 3px;
    padding: 8px;
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QPlainTextEdit:focus, QTextEdit:focus {{
    border-color: {colors["field_focus_border"]};
}}

QLineEdit:read-only,
QPlainTextEdit:read-only,
QTextEdit:read-only,
QLineEdit[readOnly="true"],
QPlainTextEdit[readOnly="true"],
QTextEdit[readOnly="true"] {{
    background: {colors["read_only_bg"]};
    color: {colors["text_muted"]};
    border-color: {colors["field_border"]};
}}

QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
QPlainTextEdit:disabled, QTextEdit:disabled {{
    background: {colors["read_only_bg"]};
    color: {colors["text_disabled"]};
    border-color: {colors["field_border"]};
}}

QPushButton#PrimaryButton:focus,
QPushButton#GhostButton:focus,
QPushButton#SoftButton:focus,
QPushButton#PathButton:focus,
QPushButton#DangerGhostButton:focus,
QPushButton#LayerIconButton:focus,
QPushButton#PlotToolButton:focus {{
    border-color: {colors["field_focus_border"]};
}}

QComboBox QAbstractItemView {{
    background: {colors["field_bg"]};
    color: {colors["text"]};
    border: 1px solid {colors["field_border"]};
    selection-background-color: {colors["selected_bg"]};
    selection-color: {colors["text"]};
}}

QComboBox QAbstractItemView::item {{
    background: {colors["field_bg"]};
    color: {colors["text"]};
    min-height: 24px;
    padding: 4px 8px;
}}

QComboBox QAbstractItemView::item:selected {{
    background: {colors["selected_bg"]};
    color: {colors["primary"]};
}}

QMenu {{
    background: {colors["card_bg"]};
    color: {colors["text"]};
    border: 1px solid {colors["border_strong"]};
    border-radius: 6px;
    padding: 6px;
}}

QMenu::item {{
    background: transparent;
    color: {colors["text"]};
    border-radius: 4px;
    padding: 7px 28px 7px 10px;
}}

QMenu::item:selected {{
    background: {colors["selected_bg"]};
    color: {colors["primary"]};
}}

QMenu::item:disabled {{
    color: {colors["text_disabled"]};
}}

QMenu::separator {{
    height: 1px;
    background: {colors["border"]};
    margin: 5px 8px;
}}

QFrame#PreviewSidebar {{
    background: {colors["sidebar_bg"]};
    border-right: 1px solid {colors["card_border"]};
}}

QWidget#PreviewSidebarContent {{
    background: {colors["sidebar_bg"]};
}}

QFrame#PreviewSidebarFooter {{
    background: {colors["sidebar_bg"]};
    border-top: 1px solid {colors["card_border"]};
}}

QFrame#PreviewToolbarHost {{
    background: {colors["toolbar_bg"]};
    border: 1px solid {colors["card_border"]};
    border-radius: 4px;
}}

QFrame#PreviewToolbarHost QToolButton {{
    background: transparent;
    color: {colors["text_muted"]};
    border: none;
    padding: 4px 6px;
}}

QFrame#PreviewToolbarHost QToolButton:hover {{
    background: {colors["hover_bg"]};
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

QTextEdit#ConsoleOutput {{
    background: {colors["console_bg"]};
    color: {colors["console_text"]};
    border: none;
    border-radius: 0px;
    padding: 8px;
    font-family: {mono_stack};
}}

QTextEdit#ConsoleOutput[stream="filter"] {{
    color: {colors["console_muted"]};
}}

QTextEdit#ConsoleOutput[stream="alert"] {{
    color: {colors["console_warn"]};
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
    background: transparent;
    border: none;
    border-radius: 0px;
}}

QFrame#FilterExportPanel {{
    background: {colors["read_only_bg"]};
    border: 1px solid {colors["card_border"]};
    border-radius: 3px;
}}

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
    background: {colors["card_bg"]};
    color: {colors["text"]};
    border: 1px solid {colors["border_strong"]};
    border-radius: 5px;
    padding: 8px 14px;
    font-weight: 600;
}}

QFrame#PreviewSidebarFooter QPushButton#GhostButton:hover {{
    background: {colors["primary_soft"]};
    color: {colors["primary"]};
    border-color: {colors["primary"]};
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

QLabel#SidebarTitle {{
    color: {colors["text"]};
    font-size: 16px;
    font-weight: 700;
}}

QWidget#InlineStatusField {{
    background: transparent;
    border: none;
    border-left: 2px solid {colors["card_border"]};
    border-radius: 0px;
    padding: 5px 8px;
}}

QLabel#InlineStatusValue {{
    color: {colors["text"]};
    font-weight: 600;
}}

QTableWidget#OverlayLayerTable {{
    background: {colors["card_bg"]};
    border: 1px solid {colors["card_border"]};
    border-radius: 4px;
    gridline-color: {colors["border"]};
    selection-background-color: {colors["selected_bg"]};
    selection-color: {colors["text"]};
}}

QTableWidget#OverlayLayerTable QHeaderView::section {{
    background: {colors["table_header_bg"]};
    color: {colors["text_muted"]};
    border: none;
    border-bottom: 1px solid {colors["card_border"]};
    padding: 6px 4px;
    font-weight: 600;
}}

QTableWidget#OverlayLayerTable::item {{
    padding: 4px 6px;
}}

QTreeView#PreviewLayerTree {{
    background: {colors["card_bg"]};
    alternate-background-color: {colors["read_only_bg"]};
    color: {colors["text"]};
    border: 1px solid {colors["card_border"]};
    border-radius: 6px;
    padding: 4px;
    outline: none;
    selection-background-color: {colors["selected_bg"]};
    selection-color: {colors["text"]};
}}

QTreeView#PreviewLayerTree::item {{
    min-height: 28px;
    padding: 3px 5px;
    border-radius: 4px;
}}

QTreeView#PreviewLayerTree::item:hover:!selected {{
    background: {colors["hover_bg"]};
}}

QTreeView#PreviewLayerTree::item:selected,
QTreeView#PreviewLayerTree::item:selected:active {{
    background: {colors["selected_bg"]};
    color: {colors["text"]};
}}

QTreeView#PreviewLayerTree::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {colors["border_strong"]};
    border-radius: 3px;
    background: {colors["field_bg"]};
}}

QTreeView#PreviewLayerTree::indicator:hover {{
    border-color: {colors["primary"]};
}}

QTreeView#PreviewLayerTree::indicator:checked {{
    background: {colors["primary"]};
    border-color: {colors["primary"]};
    image: url({check_icon});
}}

QTreeView#PreviewLayerTree::indicator:indeterminate {{
    background: {colors["primary_soft"]};
    border: 2px solid {colors["primary"]};
}}

QWidget#LayerActionCell {{
    background: transparent;
}}

QFrame#PreviewSidebar QComboBox QAbstractItemView,
QFrame#PreviewSidebar QComboBox QAbstractItemView::item {{
    background: {colors["field_bg"]};
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


def app_stylesheet(
    theme_mode: str = "system", app=None, ui_font: str | None = None, mono_font: str | None = None
) -> str:
    ensure_application_font(app=app)
    colors = palette_for_theme(theme_mode=theme_mode, app=app)
    set_active_palette(colors)
    return build_stylesheet(colors, ui_font=ui_font, mono_font=mono_font)


APP_STYLESHEET = app_stylesheet("light")
