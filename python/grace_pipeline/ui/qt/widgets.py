"""Reusable PySide6 widgets for the desktop shell."""

from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen
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

from grace_pipeline.ui.qt.design_system.icons import ICON_REGISTRY
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
    """Compatibility wrapper around the shared packaged-icon registry."""

    return ICON_REGISTRY.icon(icon_key, color or COLOR["text_muted"], size=size)


class NavigationButton(QPushButton):
    """Left-rail navigation button with a stable object name for styling."""

    def __init__(self, label: str, icon_text: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._nav_label = str(label or "")
        self._nav_icon = str(icon_text or "")
        self._display_label = self._nav_label
        self._compact = False
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("NavButton")
        self.setProperty("skipTextTranslation", True)
        self.setProperty("compact", False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setIconSize(QSize(22, 22))
        self.setMinimumHeight(48)
        self.refresh_icon()
        self.apply_language(lambda value: value)

    def apply_language(self, translator) -> None:
        label = translator(self._nav_label)
        self._display_label = str(label or self._nav_label)
        self.refresh_icon()
        self.setText("" if self._compact else self._display_label)
        self.setToolTip(self._display_label)
        self.setAccessibleName(self._display_label)
        self.setAccessibleDescription(f"{self._display_label} navigation page")

    def set_compact(self, compact: bool) -> None:
        """Show only the icon while retaining tooltip and accessible text."""

        compact = bool(compact)
        if self._compact == compact:
            return
        self._compact = compact
        self.setProperty("compact", compact)
        if compact:
            self.setFixedWidth(44)
            self.setText("")
        else:
            self.setMinimumWidth(0)
            self.setMaximumWidth(16777215)
            self.setText(self._display_label)
        self.style().unpolish(self)
        self.style().polish(self)
        self.updateGeometry()

    def refresh_icon(self) -> None:
        if not self.isEnabled():
            color = COLOR.get("text_disabled", COLOR["text_muted"])
        else:
            color = COLOR["primary"] if self.isChecked() else COLOR["text_muted"]
        self.setIcon(build_line_icon(self._nav_icon, color))

    def changeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().changeEvent(event)
        if event.type() == QEvent.Type.EnabledChange:
            self.refresh_icon()

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
        self.header: QFrame | None = None
        self.title_label: QLabel | None = None
        self.body_widget: QWidget | None = None

        if title:
            header = QFrame(self)
            header.setObjectName("CardHeader")
            header.setFixedHeight(44)
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(16, 0, 16, 0)
            header_layout.setSpacing(8)
            title_label = QLabel(title, header)
            title_label.setObjectName("CardTitle")
            title_label.setWordWrap(False)
            header_layout.addWidget(title_label)
            header_layout.addStretch(1)
            self.layout.addWidget(header)
            self.header = header
            self.title_label = title_label

        body = QWidget(self)
        body.setObjectName("CardBody")
        self.body_widget = body
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
        header.setFixedHeight(40)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 12, 0)
        header_layout.setSpacing(8)

        self.toggle = QToolButton(header)
        self.toggle.setObjectName("SectionToggle")
        self.toggle.setText(title)
        self.toggle.setCheckable(True)
        self.toggle.setChecked(bool(expanded))
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.toggle.setCursor(Qt.PointingHandCursor)
        header_layout.addWidget(self.toggle)
        header_layout.addStretch(1)
        root.addWidget(header)

        self.content = QWidget(self)
        self.header = header
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

    def __init__(self, title: str, subtitle: str = "", accent: str | None = None, height: int = 280):
        super().__init__()
        self.title = title
        self.subtitle = subtitle
        self._accent_override = accent
        self.accent = QColor(accent or COLOR["primary"])
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

    def changeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().changeEvent(event)
        if self._accent_override is None and event.type() in {
            QEvent.Type.PaletteChange,
            QEvent.Type.StyleChange,
        }:
            self.accent = QColor(COLOR["primary"])
            self.update()

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
    title_value.setObjectName("ProgressValue")
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
