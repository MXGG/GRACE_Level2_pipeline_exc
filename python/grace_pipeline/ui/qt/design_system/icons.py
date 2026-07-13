"""Theme-aware icon loading for the Qt desktop interface.

Navigation icons are packaged SVG assets.  They are recolored at render time so
the same source artwork follows every application theme.  A small QPainter
fallback keeps controls usable if an asset is missing from an unusual package.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

try:
    from PySide6.QtSvg import QSvgRenderer
except ImportError:  # pragma: no cover - QtSvg is included by normal GUI installs.
    QSvgRenderer = None


class IconRegistry:
    """Resolve, recolor, and cache packaged UI icons by semantic name."""

    _ALIASES = {
        "menu": "panel-left-close",
        "dashboard": "layout-dashboard",
        "processing": "sliders-horizontal",
        "filter": "sliders-horizontal",
        "leakage": "droplets",
        "basin": "map-pinned",
        "preview": "scan-eye",
    }

    def __init__(self, asset_dir: str | Path | None = None):
        default_dir = Path(__file__).resolve().parents[1] / "assets" / "icons" / "navigation"
        self.asset_dir = Path(asset_dir).resolve() if asset_dir is not None else default_dir
        self._cache: dict[tuple[str, str, int], QIcon] = {}

    def canonical_name(self, name: str) -> str:
        key = str(name or "").strip().lower().replace("_", "-")
        return self._ALIASES.get(key, key)

    def asset_path(self, name: str) -> Path | None:
        """Return the packaged SVG path for *name*, if it exists."""

        path = self.asset_dir / f"{self.canonical_name(name)}.svg"
        return path if path.is_file() else None

    def available(self, name: str) -> bool:
        return self.asset_path(name) is not None

    def clear_cache(self) -> None:
        self._cache.clear()

    def icon(self, name: str, color: str | QColor = "#566168", size: int = 24) -> QIcon:
        """Return a theme-colored icon, using QPainter only when SVG loading fails."""

        canonical = self.canonical_name(name)
        resolved_color = QColor(color)
        if not resolved_color.isValid():
            resolved_color = QColor("#566168")
        logical_size = max(12, int(size))
        cache_key = (canonical, resolved_color.name(QColor.NameFormat.HexArgb), logical_size)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return QIcon(cached)

        icon = self._svg_icon(canonical, resolved_color, logical_size)
        if icon.isNull():
            icon = self._fallback_icon(canonical, resolved_color, logical_size)
        self._cache[cache_key] = QIcon(icon)
        return icon

    def _svg_icon(self, canonical: str, color: QColor, size: int) -> QIcon:
        path = self.asset_path(canonical)
        if path is None or QSvgRenderer is None:
            return QIcon()
        try:
            svg = path.read_text(encoding="utf-8").replace("currentColor", color.name())
        except OSError:
            return QIcon()
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        if not renderer.isValid():
            return QIcon()

        pixmap = QPixmap(QSize(size, size))
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        return QIcon(pixmap)

    @staticmethod
    def _fallback_icon(name: str, color: QColor, size: int) -> QIcon:
        """Draw a neutral line glyph when an SVG was not packaged correctly."""

        pixmap = QPixmap(QSize(size, size))
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.scale(size / 24.0, size / 24.0)
        painter.setPen(QPen(color, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if name.startswith("panel-left"):
            painter.drawRoundedRect(QRectF(3.5, 3.5, 17, 17), 2, 2)
            painter.drawLine(9, 4, 9, 20)
            direction = -1 if name.endswith("close") else 1
            painter.drawLine(15 - direction * 2, 9, 15 + direction, 12)
            painter.drawLine(15 + direction, 12, 15 - direction * 2, 15)
        else:
            painter.drawRoundedRect(QRectF(4.5, 4.5, 15, 15), 3, 3)
            painter.drawEllipse(QPointF(12, 12), 2.25, 2.25)
        painter.end()
        return QIcon(pixmap)


ICON_REGISTRY = IconRegistry()
