"""Startup splash screen support for the Qt GUI application."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen


class PipelineSplashScreen(QSplashScreen):
    """Pixmap splash screen with a real progress overlay."""

    def __init__(self, pixmap: QPixmap):
        super().__init__(pixmap)
        self._progress = 0
        self._status = "Initializing application..."
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowTitle("GRACE Level-2 Pipeline")

    def set_progress(self, value: int, status: str | None = None) -> None:
        self._progress = max(0, min(100, int(value)))
        if status:
            self._status = status
        self.repaint()
        QApplication.processEvents()

    def drawContents(self, painter: QPainter) -> None:
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        pixmap = self.pixmap()
        width = float(pixmap.width())
        height = float(pixmap.height())
        status_rect = QRectF(0.112 * width, 0.735 * height, 0.64 * width, 0.055 * height)
        bar_rect = QRectF(0.112 * width, 0.795 * height, 0.72 * width, 0.010 * height)

        status_bg = QPainterPath()
        status_bg.addRoundedRect(status_rect.adjusted(-8, -4, 8, 4), 8, 8)
        painter.fillPath(status_bg, QColor(248, 252, 255, 218))

        font = QFont("Segoe UI", max(10, int(height * 0.024)))
        font.setWeight(QFont.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor("#0b254f"))
        painter.drawText(status_rect, Qt.AlignVCenter | Qt.AlignLeft, self._status)

        radius = max(2.0, bar_rect.height() / 2.0)
        track = QPainterPath()
        track.addRoundedRect(bar_rect, radius, radius)
        painter.fillPath(track, QColor("#d6dee9"))
        if self._progress > 0:
            fill_rect = QRectF(bar_rect)
            fill_rect.setWidth(bar_rect.width() * self._progress / 100.0)
            fill = QPainterPath()
            fill.addRoundedRect(fill_rect, radius, radius)
            painter.fillPath(fill, QColor("#04bce8"))


def _candidate_splash_paths() -> list[Path]:
    module_dir = Path(__file__).resolve().parent
    candidates = [module_dir / "assets" / "splash.png"]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        root = Path(meipass)
        candidates.append(root / "grace_pipeline" / "ui" / "qt" / "assets" / "splash.png")
        candidates.append(root / "resources" / "splash.png")
    home_dir = os.environ.get("GRACE_L2_HOME")
    if home_dir:
        candidates.append(Path(home_dir) / "resources" / "splash.png")
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "resources" / "splash.png")
        candidates.append(exe_dir.parent / "resources" / "splash.png")
    return candidates


def load_splash_pixmap() -> QPixmap | None:
    for path in _candidate_splash_paths():
        if path.exists():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                return pixmap
    return None


def create_splash_screen() -> PipelineSplashScreen | None:
    pixmap = load_splash_pixmap()
    if pixmap is None:
        return None
    screen = QApplication.primaryScreen()
    if screen is not None:
        available = screen.availableGeometry()
        max_width = int(available.width() * 0.72)
        max_height = int(available.height() * 0.72)
        if pixmap.width() > max_width or pixmap.height() > max_height:
            pixmap = pixmap.scaled(max_width, max_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    splash = PipelineSplashScreen(pixmap)
    splash.show()
    splash.set_progress(3, "Initializing application...")
    QApplication.processEvents()
    return splash
