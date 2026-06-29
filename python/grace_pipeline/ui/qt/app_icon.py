"""Application icon helpers for the Qt shell."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def app_icon_path() -> Path | None:
    root = _repo_root()
    candidates = [
        root / "installer" / "grace-l2.ico",
        root / "resources" / "grace-l2.ico",
        root / "grace-l2.ico",
    ]
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        bundle_dir = Path(getattr(sys, "_MEIPASS", exe_dir))
        candidates.extend(
            [
                bundle_dir / "resources" / "grace-l2.ico",
                bundle_dir / "grace-l2.ico",
                exe_dir / "resources" / "grace-l2.ico",
                exe_dir / "grace-l2.ico",
                exe_dir.parent / "resources" / "grace-l2.ico",
            ]
        )
    for path in candidates:
        if path.exists():
            return path
    return None


def load_app_icon() -> QIcon:
    path = app_icon_path()
    if path is None:
        return QIcon()
    return QIcon(str(path))


def install_app_icon(window=None) -> QIcon:
    icon = load_app_icon()
    if icon.isNull():
        return icon
    if window is not None:
        window.setWindowIcon(icon)
    app = QApplication.instance()
    if app is not None:
        app.setWindowIcon(icon)
    return icon
