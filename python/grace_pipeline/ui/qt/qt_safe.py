"""Small Qt lifetime helpers shared by runtime UI patches."""

from __future__ import annotations

import contextlib

try:
    from shiboken6 import isValid as _shiboken_is_valid
except Exception:  # pragma: no cover - PySide6 always ships shiboken6.
    def _shiboken_is_valid(_obj) -> bool:
        return True


def qt_object_is_alive(obj) -> bool:
    try:
        return obj is not None and _shiboken_is_valid(obj)
    except RuntimeError:
        return False


def is_deleted_qt_object_error(exc: BaseException) -> bool:
    return "already deleted" in str(exc).lower()


def safe_set_text(widget, text: str) -> None:
    if not qt_object_is_alive(widget):
        return
    with contextlib.suppress(RuntimeError):
        widget.setText(text)
