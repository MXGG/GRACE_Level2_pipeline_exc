"""Reusable PySide6 widgets for the desktop shell."""

from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from grace_pipeline.ui.qt.theme import COLOR


class YearMonthEdit(QLineEdit):
    """Compact YYYY-MM field backed by a month picker dialog."""

    def __init__(self, value: str = "", placeholder: str = "YYYY-MM", *, allow_when_readonly: bool = True):
        super().__init__(value)
        self._allow_when_readonly = bool(allow_when_readonly)
        self.setPlaceholderText(placeholder)
        self.setMaxLength(7)

    def mousePressEvent(self, event):  # noqa: N802 - Qt override
        if self.isEnabled() and (self._allow_when_readonly or not self.isReadOnly()):
            self.open_month_picker()
            event.accept()
            return
        super().mousePressEvent(event)

    def open_month_picker(self) -> None:
        text = self.text().strip()
        year = 2002
        month = 4
        if len(text) >= 7 and text[4] == "-":
            try:
                year = int(text[:4])
                month = max(1, min(12, int(text[5:7])))
            except ValueError:
                pass

        dialog = QDialog(self)
        translator = getattr(self.window(), "translate_text", None)
        dialog.setWindowTitle(translator("Select Month") if callable(translator) else "Select Month")
        layout = QVBoxLayout(dialog)
        row = QHBoxLayout()
        year_spin = QSpinBox()
        year_spin.setRange(1900, 2100)
        year_spin.setValue(year)
        month_combo = QComboBox()
        for value in range(1, 13):
            month_combo.addItem(f"{value:02d}", value)
        month_combo.setCurrentIndex(month - 1)
        row.addWidget(year_spin, 1)
        row.addWidget(month_combo, 1)
        layout.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.setText(f"{year_spin.value():04d}-{int(month_combo.currentData()):02d}")


def build_line_icon(icon_key: str, color: str | None = None, size: int = 22) -> QIcon:
    """Return a compact line icon for shell controls and navigation."""

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.scale(size / 24.0, size / 24.0)
    pen = QPen(QColor(color or COLOR["text_muted"]), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    key = str(icon_key or "").strip().lower()
    if key == "menu":
        painter.drawLine(5, 7, 19, 7)
        painter.drawLine(5, 12, 19, 12)
        painter.drawLine(5, 17, 19, 17)
    elif key == "dashboard":
        for rect in (
            QRectF(4, 4, 6.5, 6.5),
            QRectF(13.5, 4, 6.5, 4.5),
            QRectF(4, 13.5, 6.5, 6.5),
            QRectF(13.5, 11.5, 6.5, 8.5),
        ):
            painter.drawRoundedRect(rect, 1.2, 1.2)
    elif key in {"processing", "filter"}:
        for y, knob_x in ((6, 9), (12, 15), (18, 11)):
            painter.drawLine(4, y, 20, y)
            painter.setBrush(QColor(color))
            painter.drawEllipse(QPointF(knob_x, y), 2.2, 2.2)
            painter.setBrush(Qt.NoBrush)
    elif key == "leakage":
        path = QPainterPath()
        path.moveTo(12, 3.5)
        path.cubicTo(8.2, 8.2, 6.2, 11.0, 6.2, 14.2)
        path.cubicTo(6.2, 18.2, 8.7, 20.8, 12.0, 20.8)
        path.cubicTo(15.3, 20.8, 17.8, 18.2, 17.8, 14.2)
        path.cubicTo(17.8, 11.0, 15.8, 8.2, 12, 3.5)
        painter.drawPath(path)
        painter.drawLine(9.0, 15.0, 15.0, 15.0)
    elif key == "basin":
        painter.drawRoundedRect(QRectF(4, 5, 16, 14), 2.0, 2.0)
        path = QPainterPath()
        path.moveTo(5.5, 16.5)
        path.cubicTo(8.0, 12.0, 10.2, 13.8, 12.0, 10.5)
        path.cubicTo(14.0, 14.0, 16.2, 11.8, 18.5, 16.5)
        painter.drawPath(path)
        painter.drawLine(6.0, 8.0, 10.5, 8.0)
    elif key == "preview":
        path = QPainterPath()
        path.moveTo(3.5, 12.0)
        path.cubicTo(6.5, 7.5, 9.2, 5.8, 12.0, 5.8)
        path.cubicTo(14.8, 5.8, 17.5, 7.5, 20.5, 12.0)
        path.cubicTo(17.5, 16.5, 14.8, 18.2, 12.0, 18.2)
        path.cubicTo(9.2, 18.2, 6.5, 16.5, 3.5, 12.0)
        painter.drawPath(path)
        painter.drawEllipse(QPointF(12.0, 12.0), 3.0, 3.0)
    else:
        painter.drawRoundedRect(QRectF(5, 5, 14, 14), 3.0, 3.0)
        painter.drawLine(8, 12, 16, 12)
    painter.end()
    return QIcon(pixmap)


class NavigationButton(QPushButton):
    """Left-rail navigation button with a stable object name for styling."""

    def __init__(self, label: str, icon_text: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._nav_label = str(label or "")
        self._nav_icon = str(icon_text or "")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("NavButton")
        self.setProperty("skipTextTranslation", True)
        self.setIconSize(QSize(20, 20))
        self.refresh_icon()
        self.apply_language(lambda value: value)

    def apply_language(self, translator) -> None:
        label = translator(self._nav_label)
        self.refresh_icon()
        self.setText(label)

    def refresh_icon(self) -> None:
        color = COLOR["primary"] if self.isChecked() else COLOR["text_muted"]
        self.setIcon(build_line_icon(self._nav_icon, color))

    def nextCheckState(self) -> None:  # noqa: N802
        super().nextCheckState()
        self.refresh_icon()

    def setChecked(self, checked: bool) -> None:  # type: ignore[override]
        super().setChecked(checked)
        self.refresh_icon()


class ElidedLabel(QLabel):
    """QLabel that keeps the full text and elides visually on resize."""

    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._full_text = ""
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setText(text)

    def setText(self, text: str) -> None:  # type: ignore[override]
        self._full_text = str(text or "")
        self._refresh_elided_text()

    def full_text(self) -> str:
        return self._full_text

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._refresh_elided_text()

    def _refresh_elided_text(self) -> None:
        width = max(0, self.contentsRect().width())
        display = self.fontMetrics().elidedText(self._full_text, Qt.ElideRight, width) if width else self._full_text
        super().setText(display)
        self.setToolTip(self._full_text if display != self._full_text else "")


class CardFrame(QFrame):
    """Reusable card container with optional header row."""

    def __init__(self, title: str | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("PageCard")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.body: QVBoxLayout | None = None

        if title:
            header = QFrame(self)
            header.setObjectName("CardHeader")
            header.setFixedHeight(56)
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(16, 0, 16, 0)
            header_layout.setSpacing(8)
            title_label = QLabel(title, header)
            title_label.setObjectName("CardTitle")
            title_label.setWordWrap(False)
            header_layout.addWidget(title_label)
            header_layout.addStretch(1)
            self.layout.addWidget(header)

        body = QWidget(self)
        body.setObjectName("CardBody")
        self.body = QVBoxLayout(body)
        self.body.setContentsMargins(16, 14, 16, 16)
        self.body.setSpacing(12)
        self.layout.addWidget(body)


class CollapsibleSection(QFrame):
    """Simple collapsible section for advanced settings."""

    def __init__(self, title: str, *, expanded: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("PageCard")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame(self)
        header.setObjectName("CardHeader")
        header.setFixedHeight(44)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 12, 0)
        header_layout.setSpacing(8)

        self.toggle = QToolButton(header)
        self.toggle.setText(title)
        self.toggle.setCheckable(True)
        self.toggle.setChecked(bool(expanded))
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.toggle.setCursor(Qt.PointingHandCursor)
        self.toggle.setStyleSheet("QToolButton { border: none; font-weight: 700; text-align: left; padding: 0; }")
        header_layout.addWidget(self.toggle)
        header_layout.addStretch(1)
        root.addWidget(header)

        self.content = QWidget(self)
        self.body = QVBoxLayout(self.content)
        self.body.setContentsMargins(16, 12, 16, 16)
        self.body.setSpacing(12)
        self.content.setVisible(bool(expanded))
        root.addWidget(self.content)

        self.toggle.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool) -> None:
        self.toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        self.content.setVisible(bool(checked))


class PlaceholderCanvas(QFrame):
    """Stylized placeholder for previews, maps, or diagnostic charts."""

    def __init__(self, title: str, subtitle: str = "", accent: str = "#005db5", height: int = 280):
        super().__init__()
        self.title = title
        self.subtitle = subtitle
        self.accent = QColor(accent)
        self.setMinimumHeight(height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setObjectName("PageCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)

        top = QHBoxLayout()
        label_wrap = QVBoxLayout()
        overline = QLabel("VISUAL PLACEHOLDER")
        overline.setObjectName("LabelCaps")
        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        title_label.setStyleSheet("font-size: 24px;")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("PageSubtitle")
        label_wrap.addWidget(overline)
        label_wrap.addWidget(title_label)
        if subtitle:
            label_wrap.addWidget(subtitle_label)
        top.addLayout(label_wrap)
        top.addStretch(1)
        layout.addLayout(top)
        layout.addStretch(1)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(20, 72, -20, -20)

        painter.fillRect(rect, QColor(COLOR["placeholder_bg"]))

        pen = QPen(QColor(COLOR["border"]))
        pen.setWidth(1)
        painter.setPen(pen)
        step = max(32, rect.width() // 12)
        x = rect.left()
        while x < rect.right():
            painter.drawLine(x, rect.top(), x, rect.bottom())
            x += step
        y = rect.top()
        while y < rect.bottom():
            painter.drawLine(rect.left(), y, rect.right(), y)
            y += step

        accent_pen = QPen(self.accent)
        accent_pen.setWidth(4)
        painter.setPen(accent_pen)
        painter.drawRoundedRect(
            rect.adjusted(rect.width() // 5, rect.height() // 6, -rect.width() // 5, -rect.height() // 6),
            10,
            10,
        )
        painter.drawEllipse(rect.center(), 6, 6)


def build_page_header(title: str, subtitle: str, action_text: str | None = None) -> QWidget:
    widget = QWidget()
    widget.setObjectName("PageHeader")
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(16)

    label_wrap = QVBoxLayout()
    label_wrap.setContentsMargins(0, 0, 0, 0)
    label_wrap.setSpacing(4)
    title_label = QLabel(title)
    title_label.setObjectName("PageTitle")
    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("PageSubtitle")
    label_wrap.addWidget(title_label)
    label_wrap.addWidget(subtitle_label)

    layout.addLayout(label_wrap)
    layout.addStretch(1)

    if action_text:
        btn = QPushButton(action_text)
        btn.setObjectName("PrimaryButton")
        layout.addWidget(btn)

    return widget


def build_badge(text: str, variant: str = "primary") -> QLabel:
    label = QLabel(text)
    label.setObjectName("StatusBadge")
    label.setProperty("variant", variant)
    label.style().unpolish(label)
    label.style().polish(label)
    return label


def build_labeled_value(label: str, value: str) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    top = QLabel(label)
    top.setObjectName("LabelCaps")
    bottom = QLabel(value)
    bottom.setObjectName("ValueText")
    bottom.setWordWrap(True)
    layout.addWidget(top)
    layout.addWidget(bottom)
    return widget


def build_metric_card(label: str, value: str, footer: str = "", accent: str | None = None) -> CardFrame:
    card = CardFrame(label)
    if accent:
        card.setStyleSheet(f"QFrame#PageCard {{ border-left: 3px solid {accent}; }}")
    value_label = QLabel(value)
    value_label.setObjectName("MetricValue")
    card.body.addWidget(value_label)
    if footer:
        footer_label = QLabel(footer)
        footer_label.setObjectName("CardBodyText")
        footer_label.setWordWrap(True)
        card.body.addWidget(footer_label)
    card.body.addStretch(1)
    return card


def build_progress_card(title: str, value_text: str, task_text: str, progress: int) -> CardFrame:
    card = CardFrame(title)
    title_value = QLabel(value_text)
    title_value.setObjectName("ValueText")
    title_value.setStyleSheet(f"color: {COLOR['primary']}; font-weight: 700;")
    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(progress)
    task = QLabel(task_text)
    task.setObjectName("MonoText")
    card.body.addWidget(title_value)
    card.body.addWidget(bar)
    card.body.addWidget(task)
    return card


def populate_table(table: QTableWidget, headers: Iterable[str], rows: Iterable[Iterable[str]]) -> None:
    headers = list(headers)
    rows = [list(row) for row in rows]
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            item = QTableWidgetItem(str(value))
            if c == 0:
                item.setForeground(QColor(COLOR["primary"]))
            table.setItem(r, c, item)
    table.horizontalHeader().setStretchLastSection(True)
    table.verticalHeader().setVisible(False)
    table.setAlternatingRowColors(True)
    table.setSelectionMode(QTableWidget.NoSelection)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.setShowGrid(False)


def build_form_grid(rows: Iterable[tuple[str, str, str | None]]) -> QWidget:
    widget = QWidget()
    grid = QGridLayout(widget)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(18)
    grid.setVerticalSpacing(14)
    for idx, (label, value, status) in enumerate(rows):
        grid.addWidget(build_labeled_value(label, value), idx, 0)
        if status:
            grid.addWidget(build_badge(status, _status_variant(status)), idx, 1, alignment=Qt.AlignRight | Qt.AlignTop)
    grid.setColumnStretch(0, 1)
    return widget


def _status_variant(text: str) -> str:
    norm = text.lower()
    if "success" in norm or "verified" in norm or "ready" in norm or "active" in norm:
        return "success"
    if "warning" in norm:
        return "warning"
    if "fail" in norm or "invalid" in norm or "critical" in norm:
        return "danger"
    return "primary"
