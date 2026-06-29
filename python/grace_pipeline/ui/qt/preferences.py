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


@dataclass(slots=True)
class UIPreferences:
    theme: str = "system"
    language: str = "en"


def _normalize_theme(value: str | None) -> str:
    value = str(value or "system").strip().lower()
    return value if value in THEME_MODES else "system"


def _normalize_language(value: str | None) -> str:
    value = str(value or "en").strip().lower()
    return value if value in LANGUAGE_MODES else "en"


def make_settings_store() -> QSettings:
    return QSettings(ORG_NAME, APP_NAME)


def load_ui_preferences(settings: QSettings | None = None) -> UIPreferences:
    store = settings or make_settings_store()
    return UIPreferences(
        theme=_normalize_theme(store.value("ui/theme", "system", type=str)),
        language=_normalize_language(store.value("ui/language", "zh", type=str)),
    )


def save_ui_preferences(preferences: UIPreferences, settings: QSettings | None = None) -> UIPreferences:
    store = settings or make_settings_store()
    normalized = UIPreferences(
        theme=_normalize_theme(preferences.theme),
        language=_normalize_language(preferences.language),
    )
    store.setValue("ui/theme", normalized.theme)
    store.setValue("ui/language", normalized.language)
    store.sync()
    return normalized
