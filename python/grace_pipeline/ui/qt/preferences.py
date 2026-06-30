"""Persistent UI preferences for the desktop shell."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSettings


ORG_NAME = "GRACE-L2"
APP_NAME = "GRACE Level-2 Pipeline"
THEME_ITEMS = [
    ("System", "system"),
    ("Light", "light"),
    ("Dark", "dark"),
    ("Blue", "blue"),
    ("Green", "green"),
    ("Graphite", "graphite"),
    ("Sepia", "sepia"),
    ("Violet", "violet"),
]
THEME_MODES = {value for _label, value in THEME_ITEMS}
LANGUAGE_MODES = {"en", "zh"}
UI_FONT_ITEMS = [
    ("Default UI font", "default"),
    ("Microsoft YaHei UI", "Microsoft YaHei UI"),
    ("Segoe UI", "Segoe UI"),
    ("Microsoft YaHei", "Microsoft YaHei"),
    ("Arial", "Arial"),
]
MONO_FONT_ITEMS = [
    ("Default mono font", "default"),
    ("Consolas", "Consolas"),
    ("JetBrains Mono", "JetBrains Mono"),
    ("Cascadia Mono", "Cascadia Mono"),
    ("Courier New", "Courier New"),
]
UI_FONT_VALUES = {value for _label, value in UI_FONT_ITEMS}
MONO_FONT_VALUES = {value for _label, value in MONO_FONT_ITEMS}


@dataclass(slots=True)
class UIPreferences:
    theme: str = "blue"
    language: str = "en"
    ui_font: str = "default"
    mono_font: str = "default"


def _normalize_theme(value: str | None) -> str:
    value = str(value or "blue").strip().lower()
    return value if value in THEME_MODES else "blue"


def _normalize_language(value: str | None) -> str:
    value = str(value or "en").strip().lower()
    return value if value in LANGUAGE_MODES else "en"


def _normalize_font(value: str | None, allowed: set[str]) -> str:
    value = str(value or "default").strip()
    return value if value in allowed else "default"


def make_settings_store() -> QSettings:
    return QSettings(ORG_NAME, APP_NAME)


def load_ui_preferences(settings: QSettings | None = None) -> UIPreferences:
    store = settings or make_settings_store()
    return UIPreferences(
        theme=_normalize_theme(store.value("ui/theme", "blue", type=str)),
        language=_normalize_language(store.value("ui/language", "zh", type=str)),
        ui_font=_normalize_font(store.value("ui/font", "default", type=str), UI_FONT_VALUES),
        mono_font=_normalize_font(store.value("ui/monoFont", "default", type=str), MONO_FONT_VALUES),
    )


def save_ui_preferences(preferences: UIPreferences, settings: QSettings | None = None) -> UIPreferences:
    store = settings or make_settings_store()
    normalized = UIPreferences(
        theme=_normalize_theme(preferences.theme),
        language=_normalize_language(preferences.language),
        ui_font=_normalize_font(getattr(preferences, "ui_font", "default"), UI_FONT_VALUES),
        mono_font=_normalize_font(getattr(preferences, "mono_font", "default"), MONO_FONT_VALUES),
    )
    store.setValue("ui/theme", normalized.theme)
    store.setValue("ui/language", normalized.language)
    store.setValue("ui/font", normalized.ui_font)
    store.setValue("ui/monoFont", normalized.mono_font)
    store.sync()
    return normalized
