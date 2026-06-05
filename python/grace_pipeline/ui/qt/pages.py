"""Interactive PySide6 pages for the Stitch-inspired shell."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from grace_pipeline.ui.qt.mock_data import BASIN_ROWS, PAGE_SUBTITLES
from grace_pipeline.ui.qt.path_defaults import DEFAULT_DATA_PATHS
from grace_pipeline.ui.qt.widgets import CardFrame, CollapsibleSection, PlaceholderCanvas, build_badge, build_page_header, populate_table


PATH_FIELD_LABEL_WIDTH = 220


def _make_row_label(text: str, width: int | None = None) -> QLabel:
    label = QLabel(text)
    label.setObjectName("LabelCaps")
    if width is not None:
        label.setFixedWidth(width)
    return label


def _make_line_edit(value: str = "", placeholder: str = "") -> QLineEdit:
    edit = QLineEdit(value)
    if placeholder:
        edit.setPlaceholderText(placeholder)
    return edit


def _make_combo(values: list[str], current: str | None = None) -> QComboBox:
    combo = QComboBox()
    for value in values:
        combo.addItem(value, value)
    if current and current in values:
        combo.setCurrentText(current)
    return combo


def _make_choice_combo(items: list[tuple[str, str]], current_data: str | None = None) -> QComboBox:
    combo = QComboBox()
    for label, value in items:
        combo.addItem(label, value)
    if current_data is not None:
        idx = combo.findData(current_data)
        if idx >= 0:
            combo.setCurrentIndex(idx)
    return combo


def _make_field_row(label: str, widget: QWidget, status: QLabel | None = None, label_width: int | None = None) -> QWidget:
    row = QWidget()
    row.setObjectName("FieldRow")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    layout.addWidget(_make_row_label(label, label_width))
    layout.addWidget(widget, 1)
    if status is not None:
        layout.addWidget(status, 0, alignment=Qt.AlignRight | Qt.AlignVCenter)
    return row


def _make_stacked_field(label: str, widget: QWidget, status: QLabel | None = None) -> QWidget:
    row = QWidget()
    row.setObjectName("FieldBlock")
    layout = QVBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    top = QHBoxLayout()
    top.setContentsMargins(0, 0, 0, 0)
    top.setSpacing(8)
    top.addWidget(_make_row_label(label))
    top.addStretch(1)
    if status is not None:
        top.addWidget(status)
    layout.addLayout(top)
    layout.addWidget(widget)
    return row


def _make_edit_browse_widget(edit: QLineEdit, browse: QPushButton) -> QWidget:
    row = QWidget()
    row.setObjectName("InlineField")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    layout.addWidget(edit, 1)
    layout.addWidget(browse)
    return row


def _make_dual_field(
    left_label: str,
    left_widget: QWidget,
    right_label: str,
    right_widget: QWidget,
) -> QWidget:
    row = QWidget()
    row.setObjectName("FieldRow")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    layout.addWidget(_make_stacked_field(left_label, left_widget), 1)
    layout.addWidget(_make_stacked_field(right_label, right_widget), 1)
    return row


def _make_compact_field_grid(fields: list[tuple[str, QWidget]], columns: int = 2) -> QWidget:
    row = QWidget()
    row.setObjectName("FieldRow")
    layout = QGridLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setHorizontalSpacing(10)
    layout.setVerticalSpacing(10)
    columns = max(1, int(columns))
    for idx, (label, widget) in enumerate(fields):
        layout.addWidget(_make_stacked_field(label, widget), idx // columns, idx % columns)
    for col in range(columns):
        layout.setColumnStretch(col, 1)
    return row


def _table_item(text: str):
    from PySide6.QtWidgets import QTableWidgetItem

    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
    return item


class ScrollPage(QWidget):
    """Base page with a scrollable body."""

    def __init__(self, key: str):
        super().__init__()
        self.key = key

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        root.addWidget(scroll)

        container = QFrame()
        container.setObjectName("PageRoot")
        self.body = QVBoxLayout(container)
        self.body.setContentsMargins(28, 24, 28, 24)
        self.body.setSpacing(24)
        scroll.setWidget(container)

    def add_header(self, title: str, action_text: str | None = None):
        self.body.addWidget(build_page_header(title, PAGE_SUBTITLES[self.key], action_text))


class DashboardPage(ScrollPage):
    def __init__(self):
        super().__init__("dashboard")
        self.add_header("Dashboard")

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(18)

        self.card_summary = CardFrame("Project Configuration Summary")
        summary_row = QHBoxLayout()
        self.lbl_project_name = QLabel("Unsaved configuration")
        self.lbl_last_edited = QLabel("Not saved")
        self.lbl_uid = QLabel("pending")
        self.badge_summary_state = build_badge("Idle", "muted")
        summary_row.addWidget(self._value_box("Project Name", self.lbl_project_name))
        summary_row.addWidget(self._value_box("Last Edited", self.lbl_last_edited))
        summary_row.addWidget(self._value_box("UID", self.lbl_uid))
        summary_row.addWidget(self.badge_summary_state)
        self.card_summary.body.addLayout(summary_row)

        self.card_commands = CardFrame("Pipeline Controls")
        self.btn_run_full = QPushButton("Run Filters")
        self.btn_run_full.setObjectName("PrimaryButton")
        self.btn_pause_run = QPushButton("Pause")
        self.btn_pause_run.setObjectName("GhostButton")
        self.btn_stop_run = QPushButton("Stop")
        self.btn_stop_run.setObjectName("DangerGhostButton")
        self.btn_load_config = QPushButton("Load Config")
        self.btn_load_config.setObjectName("GhostButton")
        self.btn_save_config = QPushButton("Save Config")
        self.btn_save_config.setObjectName("GhostButton")
        self.btn_validate_paths = QPushButton("Validate Paths")
        self.btn_validate_paths.setObjectName("GhostButton")
        self.btn_open_data_paths = QPushButton("Data Paths")
        self.btn_open_data_paths.setObjectName("GhostButton")
        self.btn_open_processing = QPushButton("Processing Setup")
        self.btn_open_processing.setObjectName("GhostButton")
        self.btn_open_preview = QPushButton("Preview Results")
        self.btn_open_preview.setObjectName("GhostButton")
        self.btn_console_run = QPushButton("Console")
        self.btn_console_run.setObjectName("GhostButton")
        for button in (
            self.btn_run_full,
            self.btn_pause_run,
            self.btn_stop_run,
            self.btn_load_config,
            self.btn_save_config,
            self.btn_validate_paths,
            self.btn_open_data_paths,
            self.btn_open_processing,
            self.btn_open_preview,
            self.btn_console_run,
        ):
            button.setMinimumHeight(36)
        control_layout = QVBoxLayout()
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(10)
        setup_row = QHBoxLayout()
        setup_row.setContentsMargins(0, 0, 0, 0)
        setup_row.setSpacing(8)
        setup_row.addWidget(self.btn_open_data_paths)
        setup_row.addWidget(self.btn_validate_paths)
        setup_row.addWidget(self.btn_open_processing)
        setup_row.addStretch(1)
        run_row = QHBoxLayout()
        run_row.setContentsMargins(0, 0, 0, 0)
        run_row.setSpacing(8)
        run_row.addWidget(self.btn_run_full, 2)
        run_row.addWidget(self.btn_pause_run, 1)
        run_row.addWidget(self.btn_stop_run, 1)
        run_row.addWidget(self.btn_console_run, 1)
        run_row.addWidget(self.btn_open_preview, 1)
        control_layout.addLayout(setup_row)
        control_layout.addLayout(run_row)
        self.card_commands.body.addLayout(control_layout)
        self.card_commands.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        self.card_output_root = CardFrame("Output Root")
        self.lbl_output_root = QLabel("Output root: not resolved")
        self.lbl_output_root.setObjectName("MetricValue")
        self.lbl_output_root.setWordWrap(True)
        self.lbl_output_root.setStyleSheet("font-size: 22px; font-weight: 700;")
        self.card_output_root.body.addWidget(self.lbl_output_root)
        self.lbl_output_hint = QLabel("Local execution | Output directories resolved from active config.")
        self.lbl_output_hint.setWordWrap(True)
        self.card_output_root.body.addWidget(self.lbl_output_hint)

        self.card_data_availability = CardFrame("Data Availability")
        self.lbl_data_count = QLabel("0")
        self.lbl_data_count.setObjectName("MetricValue")
        self.lbl_time_span = QLabel("GFC data files | not scanned")
        self.card_data_availability.body.addWidget(self.lbl_data_count)
        self.card_data_availability.body.addWidget(self.lbl_time_span)

        self.card_active_run = CardFrame("Current Run")
        self.card_active_run.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.lbl_dashboard_status = QLabel("Ready")
        self.lbl_dashboard_status.setObjectName("ValueText")
        self.lbl_dashboard_status.setStyleSheet("font-size: 18px; font-weight: 700;")
        self.lbl_dashboard_stage = QLabel("No pipeline activity yet.")
        self.lbl_dashboard_stage.setWordWrap(True)
        self.lbl_dashboard_counts = QLabel("0 / 0")
        self.lbl_dashboard_counts.setObjectName("MonoText")
        self.lbl_active_run_name = self.lbl_dashboard_status
        self.lbl_active_task = self.lbl_dashboard_stage
        self.lbl_active_counts = self.lbl_dashboard_counts
        self.lbl_active_filters = QLabel("Filters: not evaluated yet.")
        self.lbl_active_filters.setWordWrap(True)
        self.lbl_active_io = QLabel("I/O: waiting for the first run.")
        self.lbl_active_io.setWordWrap(True)
        self.bar_active_run = QProgressBar()
        self.bar_active_run.setRange(0, 100)
        self.bar_active_run.setValue(0)
        self.bar_active_run.setFormat("%p%")
        self.bar_active_run.setTextVisible(False)
        self.bar_active_run.setProperty("active", False)
        self.card_active_run.body.addWidget(_make_field_row("Status", self.lbl_dashboard_status, label_width=72))
        self.card_active_run.body.addWidget(self.bar_active_run)
        self.card_active_run.body.addWidget(_make_field_row("Progress", self.lbl_dashboard_counts, label_width=72))
        self.card_active_run.body.addWidget(_make_field_row("Stage", self.lbl_dashboard_stage, label_width=72))
        self.card_active_run.body.addWidget(_make_field_row("Filters", self.lbl_active_filters, label_width=72))

        self.card_output_preview = CardFrame("Run Output Preview")
        self.lbl_preview_artifact = QLabel("Latest Artifact: waiting for pipeline outputs.")
        self.lbl_preview_artifact.setWordWrap(True)
        self.lbl_preview_root = QLabel("Output Root: not resolved yet.")
        self.lbl_preview_root.setWordWrap(True)
        self.lbl_preview_output = QLabel("Local Output: not resolved yet.")
        self.lbl_preview_output.setWordWrap(True)
        self.lbl_preview_stacks = QLabel("Stacks: not resolved yet.")
        self.lbl_preview_stacks.setWordWrap(True)
        self.lbl_preview_monthly = QLabel("Monthly MAT: not resolved yet.")
        self.lbl_preview_monthly.setWordWrap(True)
        self.lbl_preview_plots = QLabel("Plots: not resolved yet.")
        self.lbl_preview_plots.setWordWrap(True)
        self.lbl_preview_logs = QLabel("Logs: not resolved yet.")
        self.lbl_preview_logs.setWordWrap(True)
        self.card_output_preview.body.addWidget(self.lbl_preview_artifact)
        self.card_output_preview.body.addWidget(self.lbl_preview_root)
        self.card_output_preview.body.addWidget(self.lbl_preview_output)
        self.card_output_preview.body.addWidget(self.lbl_preview_stacks)
        self.card_output_preview.body.addWidget(self.lbl_preview_monthly)
        self.card_output_preview.body.addWidget(self.lbl_preview_plots)
        self.card_output_preview.body.addWidget(self.lbl_preview_logs)

        grid.addWidget(self.card_summary, 0, 0, 1, 2)
        grid.addWidget(self.card_commands, 1, 0)
        grid.addWidget(self.card_active_run, 1, 1, alignment=Qt.AlignTop)
        grid.addWidget(self.card_output_root, 2, 0)
        grid.addWidget(self.card_data_availability, 2, 1)
        grid.addWidget(self.card_output_preview, 3, 0, 1, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        wrapper = QWidget()
        wrapper.setLayout(grid)
        self.body.addWidget(wrapper)
        self.body.addStretch(1)

    @staticmethod
    def _value_box(label_text: str, value_widget: QWidget) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(_make_row_label(label_text))
        layout.addWidget(value_widget)
        return box

    @staticmethod
    def _action_zone(title: str, detail: str, buttons: list[QPushButton]) -> QWidget:
        frame = QFrame()
        frame.setObjectName("ActionZone")
        frame.setToolTip(detail)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        title_label = _make_row_label(title)
        row = QWidget()
        row.setObjectName("ActionZoneBody")
        row_layout = QGridLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setHorizontalSpacing(6)
        row_layout.setVerticalSpacing(6)
        full_width = len(buttons) == 3
        for idx, button in enumerate(buttons):
            if full_width and idx == 0:
                row_layout.addWidget(button, 0, 0, 1, 2)
            elif full_width:
                row_layout.addWidget(button, 1, idx - 1)
            else:
                row_layout.addWidget(button, idx // 2, idx % 2)
            button.setToolTip(detail)
        for col in range(2):
            row_layout.setColumnStretch(col, 1)
        layout.addWidget(title_label)
        layout.addWidget(row)
        return frame


class DataPathsPage(ScrollPage):
    def __init__(self):
        super().__init__("data_paths")
        self.add_header("Data Paths Configuration")

        top_grid = QGridLayout()
        top_grid.setHorizontalSpacing(18)
        top_grid.setVerticalSpacing(18)

        self.btn_load_config = QPushButton("Load Config")
        self.btn_load_config.setObjectName("GhostButton")
        self.btn_save_config = QPushButton("Save Config")
        self.btn_save_config.setObjectName("GhostButton")
        self.btn_validate_paths = QPushButton("Validate All Paths")
        self.btn_validate_paths.setObjectName("PrimaryButton")

        self.card_input_dirs = CardFrame("Input Directories")
        self.card_output_dirs = CardFrame("Output Directories")
        self.card_reference_paths = CardFrame("Reference Paths")

        self.cmb_download_product = _make_combo(["GSM 文件", "Mascon NC"], "GSM 文件")
        self.cmb_gfc_center = _make_combo(["自动", "CSR", "JPL", "GFZ", "HUST", "ITSG"], "自动")
        self.cmb_mascon_resolution = _make_combo(["0.25°", "0.5°", "1°"], "0.5°")
        self.edit_download_start_ym = _make_line_edit("", "YYYY-MM")
        self.edit_download_end_ym = _make_line_edit("", "YYYY-MM")
        self.edit_download_dir = _make_line_edit(str(DEFAULT_DATA_PATHS["GFC"]))
        self.btn_download_dir_browse = QPushButton("选择文件夹...")
        self.btn_download_dir_browse.setObjectName("GhostButton")
        self.btn_download_gfc_range = QPushButton("下载")
        self.btn_download_gfc_range.setObjectName("PrimaryButton")
        self.btn_download_gfc_range.setMinimumWidth(148)
        gfc_action_row = QWidget()
        gfc_action_layout = QHBoxLayout(gfc_action_row)
        gfc_action_layout.setContentsMargins(0, 0, 0, 0)
        gfc_action_layout.setSpacing(8)
        gfc_action_layout.addWidget(self.cmb_download_product, 0)
        gfc_action_layout.addWidget(self.cmb_gfc_center, 0)
        gfc_action_layout.addWidget(self.cmb_mascon_resolution, 0)
        gfc_action_layout.addWidget(self.edit_download_start_ym, 0)
        gfc_action_layout.addWidget(self.edit_download_end_ym, 0)
        gfc_action_layout.addWidget(self.edit_download_dir, 1)
        gfc_action_layout.addWidget(self.btn_download_dir_browse, 0)
        gfc_action_layout.addWidget(self.btn_download_gfc_range, 0)
        self.lbl_gfc_download_status = QLabel("GFC download: idle.")
        self.lbl_gfc_download_status.setWordWrap(True)
        self.card_input_dirs.body.addWidget(_make_field_row("数据下载", gfc_action_row, label_width=PATH_FIELD_LABEL_WIDTH))

        self.edit_gfc_input_dir = _make_line_edit(str(DEFAULT_DATA_PATHS["GFC"]))
        self.btn_gfc_browse = QPushButton("Folder...")
        self.btn_gfc_browse.setObjectName("GhostButton")
        self.badge_gfc_input = build_badge("Pending", "primary")
        self.card_input_dirs.body.addWidget(
            _make_field_row(
                "GFC 输入目录",
                _make_edit_browse_widget(self.edit_gfc_input_dir, self.btn_gfc_browse),
                self.badge_gfc_input,
                label_width=PATH_FIELD_LABEL_WIDTH,
            )
        )
        self.lbl_gfc_detected_range = QLabel("Detected Range: waiting for GFC scan.")
        self.lbl_gfc_detected_range.setWordWrap(True)
        self.card_input_dirs.body.addWidget(
            _make_field_row(
                "检测范围",
                self.lbl_gfc_detected_range,
                label_width=PATH_FIELD_LABEL_WIDTH,
            )
        )

        self.edit_ddk_data_dir = _make_line_edit(str(DEFAULT_DATA_PATHS["DDK"]))
        self.btn_ddk_browse = QPushButton("Folder...")
        self.btn_ddk_browse.setObjectName("GhostButton")
        self.badge_ddk_data = build_badge("Pending", "primary")
        self.card_input_dirs.body.addWidget(
            _make_field_row(
                "DDK 数据目录",
                _make_edit_browse_widget(self.edit_ddk_data_dir, self.btn_ddk_browse),
                self.badge_ddk_data,
                label_width=PATH_FIELD_LABEL_WIDTH,
            )
        )

        self.chk_remote_sync = QCheckBox("Enabled")
        self.chk_remote_sync.setChecked(True)
        self.card_output_dirs.body.addWidget(_make_field_row("Remote Sync", self.chk_remote_sync, label_width=PATH_FIELD_LABEL_WIDTH))
        self.edit_main_output_root = _make_line_edit(str(DEFAULT_DATA_PATHS["OUTPUT"]))
        self.btn_output_browse = QPushButton("Folder...")
        self.btn_output_browse.setObjectName("GhostButton")
        self.badge_output_root = build_badge("Pending", "primary")
        self.card_output_dirs.body.addWidget(
            _make_field_row(
                "Main Output Root",
                _make_edit_browse_widget(self.edit_main_output_root, self.btn_output_browse),
                self.badge_output_root,
                label_width=PATH_FIELD_LABEL_WIDTH,
            )
        )
        self.edit_logs_dir = _make_line_edit(str(DEFAULT_DATA_PATHS["LOGS"]))
        self.badge_logs_dir = build_badge("Pending", "primary")
        self.card_output_dirs.body.addWidget(_make_field_row("Logs Directory", self.edit_logs_dir, self.badge_logs_dir, label_width=PATH_FIELD_LABEL_WIDTH))
        self.card_input_dirs.body.addStretch(1)
        self.card_output_dirs.body.addStretch(1)

        self.edit_aux_path = _make_line_edit(str(DEFAULT_DATA_PATHS["AUX"]))
        self.edit_boundary_root = _make_line_edit(str(DEFAULT_DATA_PATHS["BOUNDARY"]))
        self.edit_boundary_path = _make_line_edit(str(DEFAULT_DATA_PATHS["BOUNDARY_SHP"]))
        self.edit_low_degree_path = _make_line_edit(str(DEFAULT_DATA_PATHS["LOW_DEGREE_C20"]))
        self.edit_degree1_path = _make_line_edit(str(DEFAULT_DATA_PATHS["LOW_DEGREE_DEGREE1"]))
        self.edit_gia_path = _make_line_edit(str(DEFAULT_DATA_PATHS["GIA"]))
        self.edit_mascon_root = _make_line_edit(str(DEFAULT_DATA_PATHS["MASCON_DIR"]))
        self.edit_mascon_reference = _make_line_edit(str(DEFAULT_DATA_PATHS["MASCON_REFERENCE_FILE"]))
        self.edit_mascon_gad = _make_line_edit(str(DEFAULT_DATA_PATHS["MASCON_GAD"]))
        self.edit_mascon_gia = _make_line_edit(str(DEFAULT_DATA_PATHS["MASCON_GIA"]))
        self.btn_aux_browse = QPushButton("Folder...")
        self.btn_boundary_root_browse = QPushButton("Folder...")
        self.btn_boundary_browse = QPushButton("File...")
        self.btn_low_degree_browse = QPushButton("File...")
        self.btn_degree1_browse = QPushButton("File...")
        self.btn_gia_browse = QPushButton("File...")
        self.btn_mascon_root_browse = QPushButton("Folder...")
        self.btn_mascon_reference_browse = QPushButton("File...")
        self.btn_mascon_gad_browse = QPushButton("File...")
        self.btn_mascon_gia_browse = QPushButton("File...")
        for btn in (
            self.btn_aux_browse,
            self.btn_boundary_root_browse,
            self.btn_boundary_browse,
            self.btn_low_degree_browse,
            self.btn_degree1_browse,
            self.btn_gia_browse,
            self.btn_mascon_root_browse,
            self.btn_mascon_reference_browse,
            self.btn_mascon_gad_browse,
            self.btn_mascon_gia_browse,
        ):
            btn.setObjectName("GhostButton")

        self.btn_toggle_reference_roots = QPushButton("Show Root Paths")
        self.btn_toggle_reference_roots.setObjectName("GhostButton")
        self.btn_toggle_reference_roots.setCheckable(True)
        self.reference_roots_panel = QFrame()
        self.reference_roots_panel.setObjectName("PageCard")
        self.reference_roots_panel.setVisible(False)
        roots_layout = QVBoxLayout(self.reference_roots_panel)
        roots_layout.setContentsMargins(14, 14, 14, 14)
        roots_layout.setSpacing(10)
        roots_layout.addWidget(
            _make_field_row("Aux Root", _make_edit_browse_widget(self.edit_aux_path, self.btn_aux_browse), self._make_path_badge("badge_aux_path"), label_width=PATH_FIELD_LABEL_WIDTH)
        )
        roots_layout.addWidget(
            _make_field_row(
                "Boundary Folder",
                _make_edit_browse_widget(self.edit_boundary_root, self.btn_boundary_root_browse),
                self._make_path_badge("badge_boundary_root"),
                label_width=PATH_FIELD_LABEL_WIDTH,
            )
        )
        roots_layout.addWidget(
            _make_field_row(
                "Mascon Folder",
                _make_edit_browse_widget(self.edit_mascon_root, self.btn_mascon_root_browse),
                self._make_path_badge("badge_mascon_root"),
                label_width=PATH_FIELD_LABEL_WIDTH,
            )
        )

        self.card_reference_paths.body.addWidget(self.btn_toggle_reference_roots)
        self.card_reference_paths.body.addWidget(self.reference_roots_panel)
        self.card_reference_paths.body.addWidget(
            _make_field_row("Boundary Shapefile", _make_edit_browse_widget(self.edit_boundary_path, self.btn_boundary_browse), self._make_path_badge("badge_boundary_path"), label_width=PATH_FIELD_LABEL_WIDTH)
        )
        self.card_reference_paths.body.addWidget(
            _make_field_row("C20 Replacement File", _make_edit_browse_widget(self.edit_low_degree_path, self.btn_low_degree_browse), self._make_path_badge("badge_low_degree"), label_width=PATH_FIELD_LABEL_WIDTH)
        )
        self.card_reference_paths.body.addWidget(
            _make_field_row("Degree-1 File", _make_edit_browse_widget(self.edit_degree1_path, self.btn_degree1_browse), self._make_path_badge("badge_degree1"), label_width=PATH_FIELD_LABEL_WIDTH)
        )
        self.card_reference_paths.body.addWidget(
            _make_field_row("GIA Model Path", _make_edit_browse_widget(self.edit_gia_path, self.btn_gia_browse), self._make_path_badge("badge_gia"), label_width=PATH_FIELD_LABEL_WIDTH)
        )
        self.card_reference_paths.body.addWidget(
            _make_field_row("Mascon Reference File", _make_edit_browse_widget(self.edit_mascon_reference, self.btn_mascon_reference_browse), self._make_path_badge("badge_mascon_reference"), label_width=PATH_FIELD_LABEL_WIDTH)
        )
        self.card_reference_paths.body.addWidget(
            _make_field_row("Mascon GAD", _make_edit_browse_widget(self.edit_mascon_gad, self.btn_mascon_gad_browse), self._make_path_badge("badge_mascon_gad"), label_width=PATH_FIELD_LABEL_WIDTH)
        )
        self.card_reference_paths.body.addWidget(
            _make_field_row("Mascon GIA", _make_edit_browse_widget(self.edit_mascon_gia, self.btn_mascon_gia_browse), self._make_path_badge("badge_mascon_gia"), label_width=PATH_FIELD_LABEL_WIDTH)
        )

        top_grid.addWidget(self.card_input_dirs, 0, 0)
        top_grid.addWidget(self.card_output_dirs, 0, 1)
        top_grid.addWidget(self.card_reference_paths, 1, 0, 1, 2)
        top_grid.setColumnStretch(0, 1)
        top_grid.setColumnStretch(1, 1)

        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        action_row = QHBoxLayout()
        action_row.addStretch(1)
        action_row.addWidget(self.btn_load_config)
        action_row.addWidget(self.btn_save_config)
        action_row.addWidget(self.btn_validate_paths)
        wrapper_layout.addLayout(action_row)
        wrapper_layout.addLayout(top_grid)
        self.body.addWidget(wrapper)
        self.body.addStretch(1)

    def _make_path_badge(self, attr_name: str) -> QLabel:
        badge = build_badge("Pending", "primary")
        setattr(self, attr_name, badge)
        return badge


class ProcessingSetupPage(ScrollPage):
    def __init__(self):
        super().__init__("processing")
        self.add_header("Processing Setup")

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(18)

        self.card_time_range = CardFrame("Detected Time Range")
        self.lbl_detected_time_range = QLabel("Detected from GFC files: not scanned yet.")
        self.lbl_detected_time_range.setWordWrap(True)
        self.chk_manual_time_override = QCheckBox("Manual Override")
        self.chk_manual_time_override.setChecked(False)
        self.edit_start_date = _make_line_edit("2002-04-01")
        self.edit_end_date = _make_line_edit("2017-06-01")
        self.edit_start_date.setReadOnly(True)
        self.edit_end_date.setReadOnly(True)
        self.lbl_time_range_note = QLabel(
            "The default mode scans the selected GFC directory and derives the valid processing span automatically."
        )
        self.lbl_time_range_note.setWordWrap(True)
        self.card_time_range.body.addWidget(_make_field_row("Detected Range", self.lbl_detected_time_range))
        self.card_time_range.body.addWidget(_make_field_row("Time Source", self.chk_manual_time_override))
        self.card_time_range.body.addWidget(
            _make_compact_field_grid(
                [
                    ("Start Date", self.edit_start_date),
                    ("End Date", self.edit_end_date),
                ],
                columns=2,
            )
        )
        self.card_time_range.body.addWidget(self.lbl_time_range_note)

        self.card_inversion = CardFrame("Inversion & Corrections")
        self.slider_degree_order = QSlider(Qt.Horizontal)
        self.slider_degree_order.setRange(0, 240)
        self.slider_degree_order.setValue(60)
        self.lbl_degree_order = QLabel("60")
        self.lbl_degree_order.setObjectName("MonoText")
        self.chk_remove_mean = QCheckBox("Enable Mean / Anomaly Removal")
        self.chk_remove_mean.setChecked(True)
        self.cmb_anomaly_baseline = _make_choice_combo(
            [
                ("2004-01 ~ 2009-12", "standard_2004_2009"),
                ("Full Span", "input_full"),
                ("Custom Range", "custom"),
            ],
            "standard_2004_2009",
        )
        self.edit_mean_start_ym = _make_line_edit("2004-01", "YYYY-MM")
        self.edit_mean_end_ym = _make_line_edit("2009-12", "YYYY-MM")
        self.chk_lowdeg_enable = QCheckBox("Enable Low-Degree Corrections")
        self.chk_lowdeg_enable.setChecked(True)
        self.chk_replace_degree1 = QCheckBox("Degree-1 geocenter")
        self.chk_replace_degree1.setChecked(True)
        self.chk_replace_c20 = QCheckBox("C20 (SLR)")
        self.chk_replace_c20.setChecked(True)
        self.chk_replace_c30 = QCheckBox("C30 (GRACE-FO only)")
        self.chk_replace_c30.setChecked(True)
        self.lowdeg_panel = QWidget()
        self.lowdeg_panel.setObjectName("FieldBlock")
        lowdeg_layout = QGridLayout(self.lowdeg_panel)
        lowdeg_layout.setContentsMargins(0, 0, 0, 0)
        lowdeg_layout.setHorizontalSpacing(10)
        lowdeg_layout.setVerticalSpacing(8)
        lowdeg_layout.addWidget(self.chk_replace_degree1, 0, 0)
        lowdeg_layout.addWidget(self.chk_replace_c20, 0, 1)
        lowdeg_layout.addWidget(self.chk_replace_c30, 1, 0, 1, 2)
        self.chk_apply_gia = QCheckBox("Apply GIA Correction")
        self.chk_apply_gia.setChecked(False)
        self.lbl_correction_note = QLabel(
            "Low-degree replacements use TN-13 and TN-14 reference files from Data Paths. C30 is applied only to GRACE-FO months."
        )
        self.lbl_correction_note.setWordWrap(True)
        self.card_inversion.body.addWidget(_make_field_row("Maximum Degree / Order", self.slider_degree_order, self.lbl_degree_order))
        self.card_inversion.body.addWidget(_make_field_row("Mean / Anomaly", self.chk_remove_mean))
        self.row_anomaly_baseline = _make_field_row("Anomaly Baseline", self.cmb_anomaly_baseline)
        self.card_inversion.body.addWidget(self.row_anomaly_baseline)
        self.row_mean_baseline_range = _make_dual_field("Baseline Start", self.edit_mean_start_ym, "Baseline End", self.edit_mean_end_ym)
        self.card_inversion.body.addWidget(self.row_mean_baseline_range)
        self.card_inversion.body.addWidget(_make_field_row("Low-Degree", self.chk_lowdeg_enable))
        self.card_inversion.body.addWidget(self.lowdeg_panel)
        self.card_inversion.body.addWidget(_make_field_row("GIA", self.chk_apply_gia))
        self.card_inversion.body.addWidget(self.lbl_correction_note)

        self.card_grid_settings = CardFrame("Spatial Grid")
        self.edit_resolution_deg = _make_line_edit("0.50")
        self.edit_grid_lat_min = _make_line_edit("-90")
        self.edit_grid_lat_max = _make_line_edit("90")
        self.edit_grid_lon_min = _make_line_edit("-180")
        self.edit_grid_lon_max = _make_line_edit("180")
        self.lbl_grid_note = QLabel("Use the global grid by default; only tighten the extent if you explicitly need a regional crop.")
        self.lbl_grid_note.setWordWrap(True)
        self.card_grid_settings.body.addWidget(_make_field_row("Resolution (deg)", self.edit_resolution_deg))
        self.card_grid_settings.body.addWidget(_make_dual_field("Lat Min", self.edit_grid_lat_min, "Lat Max", self.edit_grid_lat_max))
        self.card_grid_settings.body.addWidget(_make_dual_field("Lon Min", self.edit_grid_lon_min, "Lon Max", self.edit_grid_lon_max))
        self.card_grid_settings.body.addWidget(self.lbl_grid_note)

        self.card_sh_tools = CardFrame("SH / Grid Utility")
        self.lbl_sh_tool_status = QLabel("Status: ready for SH/Grid conversion.")
        self.lbl_sh_tool_status.setWordWrap(True)
        self.lbl_sh_tool_note = QLabel(
            "Supplemental utility: synthesize grids from SH coefficients, or estimate SH coefficients from the current Preview grid stack."
        )
        self.lbl_sh_tool_note.setWordWrap(True)
        self.edit_sh_tool_source = _make_line_edit("", "Optional .gfc/.mat/.nc/.h5 source file")
        self.btn_sh_tool_browse = QPushButton("Browse")
        self.btn_sh_tool_browse.setObjectName("GhostButton")
        self.btn_tool_sh_to_grid = QPushButton("Run SH -> Grid Synthesis")
        self.btn_tool_sh_to_grid.setObjectName("GhostButton")
        self.btn_tool_grid_to_sh = QPushButton("Run Grid -> SH Analysis")
        self.btn_tool_grid_to_sh.setObjectName("GhostButton")
        sh_tool_row = QWidget()
        sh_tool_layout = QHBoxLayout(sh_tool_row)
        sh_tool_layout.setContentsMargins(0, 0, 0, 0)
        sh_tool_layout.setSpacing(8)
        sh_tool_layout.addWidget(self.btn_tool_sh_to_grid)
        sh_tool_layout.addWidget(self.btn_tool_grid_to_sh)
        sh_tool_layout.addStretch(1)
        self.card_sh_tools.body.addWidget(self.lbl_sh_tool_status)
        self.card_sh_tools.body.addWidget(self.lbl_sh_tool_note)
        self.card_sh_tools.body.addWidget(_make_field_row("Tool Source", _make_edit_browse_widget(self.edit_sh_tool_source, self.btn_sh_tool_browse)))
        self.card_sh_tools.body.addWidget(sh_tool_row)

        self.card_filters = CardFrame("滤波方法")
        self.btn_filter_gaussian = QCheckBox("Gaussian")
        self.btn_filter_p4m6 = QCheckBox("P4M6")
        self.btn_filter_gaussian_pnmn = QCheckBox("P4M6_GAUSS")
        self.btn_filter_ddk = QCheckBox("DDK")
        self.btn_filter_fan = QCheckBox("FAN")
        self.btn_filter_fan_pnmn = QCheckBox("P4M6_FAN")
        self.btn_filter_hsaf = QCheckBox("HSAF")
        filter_buttons = [
            self.btn_filter_gaussian,
            self.btn_filter_p4m6,
            self.btn_filter_gaussian_pnmn,
            self.btn_filter_ddk,
            self.btn_filter_fan,
            self.btn_filter_fan_pnmn,
            self.btn_filter_hsaf,
        ]
        for btn in filter_buttons:
            btn.setChecked(btn in (self.btn_filter_gaussian, self.btn_filter_p4m6, self.btn_filter_gaussian_pnmn, self.btn_filter_ddk, self.btn_filter_hsaf))

        self._selected_filter_panel = "gaussian_pnmn"
        filter_workspace = QWidget()
        filter_workspace.setObjectName("FilterWorkspace")
        filter_workspace_layout = QHBoxLayout(filter_workspace)
        filter_workspace_layout.setContentsMargins(0, 0, 0, 0)
        filter_workspace_layout.setSpacing(16)

        method_list = QFrame()
        method_list.setObjectName("FilterMethodList")
        method_list_layout = QVBoxLayout(method_list)
        method_list_layout.setContentsMargins(12, 10, 12, 10)
        method_list_layout.setSpacing(8)
        method_list_layout.addWidget(_make_row_label("滤波方法"))
        for btn in filter_buttons:
            btn.setProperty("filterMethod", True)
            method_list_layout.addWidget(btn)
        method_list_layout.addStretch(1)
        filter_workspace_layout.addWidget(method_list, 0)

        self.filter_parameter_area = QFrame()
        self.filter_parameter_area.setObjectName("FilterParameterPanel")
        self.filter_parameter_area.setMinimumWidth(340)
        filter_parameter_layout = QVBoxLayout(self.filter_parameter_area)
        filter_parameter_layout.setContentsMargins(16, 14, 16, 14)
        filter_parameter_layout.setSpacing(10)
        self.lbl_filter_parameter_title = QLabel("参数设置")
        self.lbl_filter_parameter_title.setObjectName("FilterParameterTitle")
        filter_parameter_layout.addWidget(self.lbl_filter_parameter_title)
        filter_workspace_layout.addWidget(self.filter_parameter_area, 1)
        self.card_filters.body.addWidget(filter_workspace)

        self.edit_isotropic_radius_km = _make_line_edit("300")
        self.edit_pnmn_poly_degree = _make_line_edit("4")
        self.edit_pnmn_m_start = _make_line_edit("6")
        self.cmb_ddk_type = _make_combo([f"DDK{i}" for i in range(1, 9)], "DDK4")
        self.edit_fan_radius1_km = _make_line_edit("300")
        self.edit_fan_radius2_km = _make_line_edit("300")
        self.panel_filter_gaussian = QWidget()
        gaussian_layout = QVBoxLayout(self.panel_filter_gaussian)
        gaussian_layout.setContentsMargins(0, 0, 0, 0)
        gaussian_layout.setSpacing(8)
        gaussian_layout.addWidget(_make_field_row("Gaussian 半径 (km)", self.edit_isotropic_radius_km))

        self.panel_filter_pnmn = QWidget()
        pnmn_layout = QVBoxLayout(self.panel_filter_pnmn)
        pnmn_layout.setContentsMargins(0, 0, 0, 0)
        pnmn_layout.setSpacing(8)
        pnmn_layout.addWidget(_make_compact_field_grid([("P", self.edit_pnmn_poly_degree), ("M", self.edit_pnmn_m_start)], columns=2))

        self.panel_filter_gaussian_pnmn = QWidget()
        QVBoxLayout(self.panel_filter_gaussian_pnmn).setContentsMargins(0, 0, 0, 0)

        self.panel_filter_ddk = QWidget()
        ddk_layout = QVBoxLayout(self.panel_filter_ddk)
        ddk_layout.setContentsMargins(0, 0, 0, 0)
        ddk_layout.setSpacing(8)
        ddk_layout.addWidget(_make_field_row("DDK 类型", self.cmb_ddk_type))

        self.panel_filter_fan = QWidget()
        fan_layout = QVBoxLayout(self.panel_filter_fan)
        fan_layout.setContentsMargins(0, 0, 0, 0)
        fan_layout.setSpacing(8)
        fan_layout.addWidget(_make_dual_field("FAN 半径 1 (km)", self.edit_fan_radius1_km, "FAN 半径 2 (km)", self.edit_fan_radius2_km))

        self.panel_filter_fan_pnmn = QWidget()
        QVBoxLayout(self.panel_filter_fan_pnmn).setContentsMargins(0, 0, 0, 0)

        self.panel_filter_empty = QLabel("勾选一个滤波方法后显示参数。")
        self.panel_filter_empty.setObjectName("PageSubtitle")
        self.panel_filter_empty.setWordWrap(True)

        for panel in (
            self.panel_filter_empty,
            self.panel_filter_gaussian,
            self.panel_filter_pnmn,
            self.panel_filter_gaussian_pnmn,
            self.panel_filter_ddk,
            self.panel_filter_fan,
            self.panel_filter_fan_pnmn,
        ):
            filter_parameter_layout.addWidget(panel)
            panel.setVisible(False)

        self.hsaf_detail_panel = QFrame()
        self.hsaf_detail_panel.setObjectName("FieldBlock")
        hsaf_layout = QVBoxLayout(self.hsaf_detail_panel)
        hsaf_layout.setContentsMargins(0, 4, 0, 0)
        hsaf_layout.setSpacing(10)

        self.cmb_hsaf_input = _make_combo(["P4M6", "RAW"], "P4M6")
        self.cmb_hsaf_variant = _make_combo(["全局固定", "纬度自适应"], "全局固定")

        self.edit_hsaf_iterations = _make_line_edit("")
        self.edit_hsaf_alpha = _make_line_edit("")
        self.edit_hsaf_tolerance = _make_line_edit("")
        self.edit_hsaf_alpha.setVisible(False)
        self.edit_hsaf_tolerance.setVisible(False)
        hsaf_layout.addWidget(
            _make_compact_field_grid(
                [
                    ("HSAF 输入", self.cmb_hsaf_input),
                    ("HSAF 策略", self.cmb_hsaf_variant),
                    ("迭代次数", self.edit_hsaf_iterations),
                ],
                columns=3,
            )
        )

        self.hsaf_global_panel = QWidget()
        hsaf_global_layout = QVBoxLayout(self.hsaf_global_panel)
        hsaf_global_layout.setContentsMargins(0, 0, 0, 0)
        hsaf_global_layout.setSpacing(10)
        self.lbl_hsaf_global = QLabel("全局固定参数")
        self.lbl_hsaf_global.setObjectName("LabelCaps")
        hsaf_global_layout.addWidget(self.lbl_hsaf_global)
        self.edit_hsaf_global_n = _make_line_edit("")
        self.edit_hsaf_global_p = _make_line_edit("")
        self.edit_hsaf_global_k = _make_line_edit("")
        self.edit_hsaf_global_j = _make_line_edit("")
        hsaf_global_layout.addWidget(
            _make_compact_field_grid(
                [
                    ("窗口 N", self.edit_hsaf_global_n),
                    ("嵌入 P", self.edit_hsaf_global_p),
                    ("模态 K", self.edit_hsaf_global_k),
                    ("步长 J", self.edit_hsaf_global_j),
                ],
                columns=4,
            )
        )
        hsaf_layout.addWidget(self.hsaf_global_panel)

        self.hsaf_adaptive_panel = QWidget()
        hsaf_adaptive_layout = QVBoxLayout(self.hsaf_adaptive_panel)
        hsaf_adaptive_layout.setContentsMargins(0, 0, 0, 0)
        hsaf_adaptive_layout.setSpacing(10)
        self.hsaf_adaptive_zone_fields = []
        for zone_title, lat_min_default, lat_max_default in (
            ("区域 1", "-90", "-30"),
            ("区域 2", "-30", "30"),
            ("区域 3", "30", "90"),
        ):
            zone_frame = QFrame()
            zone_frame.setObjectName("FieldBlock")
            zone_layout = QVBoxLayout(zone_frame)
            zone_layout.setContentsMargins(0, 0, 0, 0)
            zone_layout.setSpacing(8)
            zone_label = QLabel(zone_title)
            zone_label.setObjectName("LabelCaps")
            zone_layout.addWidget(zone_label)
            edit_lat_min = _make_line_edit(lat_min_default)
            edit_lat_max = _make_line_edit(lat_max_default)
            edit_n = _make_line_edit("")
            edit_p = _make_line_edit("")
            edit_k = _make_line_edit("")
            edit_j = _make_line_edit("")
            zone_layout.addWidget(
                _make_compact_field_grid(
                    [
                        ("纬度下限", edit_lat_min),
                        ("纬度上限", edit_lat_max),
                        ("窗口 N", edit_n),
                        ("嵌入 P", edit_p),
                        ("模态 K", edit_k),
                        ("步长 J", edit_j),
                    ],
                    columns=3,
                )
            )
            hsaf_adaptive_layout.addWidget(zone_frame)
            self.hsaf_adaptive_zone_fields.append(
                {
                    "lat_min": edit_lat_min,
                    "lat_max": edit_lat_max,
                    "N": edit_n,
                    "P": edit_p,
                    "K": edit_k,
                    "J": edit_j,
                }
            )
        hsaf_layout.addWidget(self.hsaf_adaptive_panel)
        filter_parameter_layout.addWidget(self.hsaf_detail_panel)
        self.hsaf_detail_panel.setVisible(False)
        self.hsaf_adaptive_panel.setVisible(False)
        filter_parameter_layout.addStretch(1)

        self.btn_load_preset = QPushButton("Load Preset")
        self.btn_save_config = QPushButton("Save Config")
        self.btn_load_preset.setObjectName("GhostButton")
        self.btn_save_config.setObjectName("PrimaryButton")
        self.btn_load_preset.setVisible(False)
        self.btn_save_config.setVisible(False)

        left_col = QVBoxLayout()
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(18)
        left_col.addWidget(self.card_time_range)
        left_col.addWidget(self.card_inversion)
        left_col.addStretch(1)

        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(18)
        right_col.addWidget(self.card_filters)
        right_col.addWidget(self.card_grid_settings)
        right_col.addStretch(1)

        left_wrap = QWidget()
        left_wrap.setLayout(left_col)
        right_wrap = QWidget()
        right_wrap.setLayout(right_col)

        grid.addWidget(left_wrap, 0, 0)
        grid.addWidget(right_wrap, 0, 1)
        grid.addWidget(self.card_sh_tools, 1, 0, 1, 2)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 0)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.addLayout(grid)
        self.body.addWidget(wrapper)
        self.body.addStretch(1)


class LeakagePage(ScrollPage):
    def __init__(self):
        super().__init__("leakage")
        self.add_header("Leakage Correction")

        self.chk_leakage_enable = QCheckBox("Enable leakage correction")
        self.chk_leakage_enable.setChecked(True)
        self.chk_leakage_enable.hide()
        self.rb_method_fm = QRadioButton("FM")
        self.rb_method_sf = QRadioButton("SF")
        self.rb_method_sf.setChecked(True)
        self.rb_method_fm.hide()
        self.rb_method_sf.hide()

        self.btn_run_leakage = QPushButton("Run Correction")
        self.btn_run_leakage.setObjectName("PrimaryButton")
        self.btn_pause_leakage = QPushButton("Pause")
        self.btn_pause_leakage.setObjectName("GhostButton")
        self.btn_stop_leakage = QPushButton("Stop")
        self.btn_stop_leakage.setObjectName("GhostButton")

        self.card_enable = CardFrame("Recommendation Summary")
        self.badge_product = build_badge("Product pending", "primary")
        self.badge_operator = build_badge("Filter pending", "primary")
        self.badge_scene = build_badge("Scene pending", "primary")
        self.badge_strategy = build_badge("Strategy pending", "primary")
        top_row = QWidget()
        top_row_layout = QHBoxLayout(top_row)
        top_row_layout.setContentsMargins(0, 0, 0, 0)
        top_row_layout.setSpacing(10)
        top_row_layout.addWidget(self.chk_leakage_enable)
        top_row_layout.addStretch(1)
        top_row_layout.addWidget(self.badge_product)
        top_row_layout.addWidget(self.badge_operator)
        top_row_layout.addWidget(self.badge_scene)
        top_row_layout.addWidget(self.badge_strategy)
        self.card_enable.body.addWidget(top_row)
        self.lbl_scientific_note = QLabel(
            "Use the automatic recommendation by default. Select an input stack, load its metadata, then run."
        )
        self.lbl_scientific_note.setWordWrap(True)
        self.card_enable.body.addWidget(self.lbl_scientific_note)

        self.card_input = CardFrame("Input and Output")
        self.edit_lrc_input = _make_line_edit("", "Stack to correct, supports MAT / NC / HDF / TXT")
        self.btn_lrc_input_browse = QPushButton("Browse")
        self.btn_lrc_input_browse.setObjectName("GhostButton")
        self.edit_reference_input = _make_line_edit("", "Optional reference data or official scaling/gain file")
        self.btn_reference_input_browse = QPushButton("Browse")
        self.btn_reference_input_browse.setObjectName("GhostButton")
        self.edit_regional_boundary = _make_line_edit("", "Regional boundary for regional mode, supports shp / txt / bln")
        self.btn_regional_boundary_browse = QPushButton("Browse")
        self.btn_regional_boundary_browse.setObjectName("GhostButton")
        self.edit_lrc_output = _make_line_edit("", "Output file or folder; leave empty to generate automatically")
        self.btn_lrc_output_browse = QPushButton("Browse")
        self.btn_lrc_output_browse.setObjectName("GhostButton")
        self.lbl_leakage_info = QLabel("Input not loaded")
        self.lbl_dataset_shape_value = QLabel("-")
        self.lbl_product_type_value = QLabel("-")
        self.btn_load_leakage_info = QPushButton("Load Input Info")
        self.btn_load_leakage_info.setObjectName("GhostButton")
        self.lbl_linkage_status = QLabel("Load input metadata first; the system will choose a recommended strategy.")
        self.lbl_linkage_status.setWordWrap(True)
        self.card_input.body.addWidget(_make_field_row("Input Stack", _make_edit_browse_widget(self.edit_lrc_input, self.btn_lrc_input_browse)))
        self.card_input.body.addWidget(_make_field_row("Reference Data", _make_edit_browse_widget(self.edit_reference_input, self.btn_reference_input_browse)))
        self.row_regional_boundary = _make_field_row("Regional Boundary", _make_edit_browse_widget(self.edit_regional_boundary, self.btn_regional_boundary_browse))
        self.card_input.body.addWidget(self.row_regional_boundary)
        self.row_regional_boundary.hide()
        self.card_input.body.addWidget(_make_field_row("Output Location", _make_edit_browse_widget(self.edit_lrc_output, self.btn_lrc_output_browse)))
        self.card_input.body.addWidget(
            _make_compact_field_grid(
                [("Input Status", self.lbl_leakage_info), ("Grid Shape", self.lbl_dataset_shape_value), ("Product Type", self.lbl_product_type_value)],
                columns=3,
            )
        )
        input_actions = QWidget()
        input_actions_layout = QHBoxLayout(input_actions)
        input_actions_layout.setContentsMargins(0, 0, 0, 0)
        input_actions_layout.setSpacing(8)
        input_actions_layout.addWidget(self.btn_load_leakage_info)
        input_actions_layout.addStretch(1)
        self.card_input.body.addWidget(input_actions)
        self.card_input.body.addWidget(self.lbl_linkage_status)

        self.card_strategy = CardFrame("Strategy")
        self.cmb_scope = _make_choice_combo([("Regional", "regional"), ("Global", "global")], "global")
        self.cmb_scope.hide()
        self.cmb_strategy_family = _make_choice_combo(
            [("Regional mode", "regional"), ("Global coastline", "global_coastal"), ("Global recovery", "global_regularized"), ("Official/native", "official")],
            "global_regularized",
        )
        self.cmb_correction_strategy = _make_choice_combo(
            [
                ("Auto recommendation", "auto"),
                ("Basin scale factor", "basin_scale_factor"),
                ("Regional forward modeling", "forward_modeling"),
                ("Global coastline Gaussian", "global_coastal_gaussian"),
                ("Global regularized recovery", "global_regularized"),
                ("Official land scaling", "official_land_scaling"),
                ("Official ocean native", "official_ocean_native"),
                ("Official mascon native, no duplicate correction", "official_mascon_native"),
            ],
            "auto",
        )
        self.cmb_scene_override = _make_choice_combo(
            [("Auto detect", "auto"), ("Inland basin", "inland_basin"), ("Lake/reservoir", "lake_reservoir"), ("Coastal zone", "coastal"), ("Cryosphere", "cryosphere")],
            "auto",
        )
        self.cmb_reference_mode = _make_choice_combo([("Trend field", "trend"), ("Mean field", "mean"), ("Median field", "median"), ("First epoch", "first")], "trend")
        self.cmb_official_mode = _make_choice_combo([("Auto detect", "auto"), ("Land scaling", "land_scaling"), ("Ocean native", "ocean_native"), ("Mascon native", "mascon_native")], "auto")
        self.lbl_operator_value = QLabel("-")
        self.lbl_scene_value = QLabel("-")
        self.lbl_recommendation_value = QLabel("-")
        self.lbl_boundary_status = QLabel("-")
        self.card_strategy.body.addWidget(
            _make_compact_field_grid(
                [("Detected Filter", self.lbl_operator_value), ("Recommended Strategy", self.lbl_recommendation_value)],
                columns=2,
            )
        )
        self.card_strategy.body.addWidget(_make_field_row("Workflow", self.cmb_strategy_family))
        self.lbl_boundary_status.hide()
        self.lbl_scene_value.hide()
        self.lbl_method_hint = QLabel("Load input metadata first; the system recommends a correction path from filter type and workflow scope.")
        self.lbl_method_hint.setWordWrap(True)
        self.card_strategy.body.addWidget(self.lbl_method_hint)

        self.card_params = CardFrame("Parameters")
        self.edit_lrc_sf_factor = _make_line_edit("1.0")
        self.edit_operator_autodetect = _make_line_edit("Auto")
        self.edit_lrc_gaussian_km = _make_line_edit("300")
        self.edit_ddk_type = _make_line_edit("DDK4")
        self.cmb_lrc_format = _make_choice_combo([("MAT file", "mat"), ("TXT file", "txt")], "mat")
        self.edit_coastal_buffer_cells = _make_line_edit("3")
        self.edit_coastal_attenuation_gain = _make_line_edit("1.0")
        self.edit_regularized_lambda = _make_line_edit("0.08")
        self.edit_regularized_step_size = _make_line_edit("1.05")
        self.edit_regularized_sigma = _make_line_edit("0.9")
        self.edit_regularized_iter = _make_line_edit("20")
        self.params_common_panel = _make_compact_field_grid(
            [("Gaussian Radius / km", self.edit_lrc_gaussian_km), ("Output Format", self.cmb_lrc_format)],
            columns=2,
        )
        self.params_regional_panel = _make_compact_field_grid(
            [("Scale Factor", self.edit_lrc_sf_factor)],
            columns=1,
        )
        self.params_coastal_panel = _make_compact_field_grid(
            [("Coastal Buffer Cells", self.edit_coastal_buffer_cells), ("Attenuation Gain", self.edit_coastal_attenuation_gain)],
            columns=2,
        )
        self.params_regularized_panel = _make_compact_field_grid(
            [("Regularization Lambda", self.edit_regularized_lambda), ("Step Size", self.edit_regularized_step_size), ("Smoothing Sigma", self.edit_regularized_sigma), ("Iterations", self.edit_regularized_iter)],
            columns=2,
        )
        self.card_params.body.addWidget(self.params_common_panel)
        self.card_params.body.addWidget(self.params_regional_panel)

        self.advanced_section = CollapsibleSection("Advanced Parameters", expanded=False)
        self.edit_fm_iteration_count = _make_line_edit("40")
        self.edit_fm_convergence_threshold = _make_line_edit("0.01")
        self.edit_fm_acceleration = _make_line_edit("1.1")
        self.edit_fm_patience = _make_line_edit("8")
        self.edit_fm_min_improve = _make_line_edit("0.0001")
        self.edit_lrc_edge_buffer = _make_line_edit("2.0")
        self.advanced_section.body.addWidget(_make_field_row("Specific Strategy", self.cmb_correction_strategy))
        self.advanced_section.body.addWidget(
            _make_compact_field_grid(
                [("Reference Mode", self.cmb_reference_mode), ("Scene Override", self.cmb_scene_override), ("Official Mode", self.cmb_official_mode), ("DDK Type", self.edit_ddk_type)],
                columns=2,
            )
        )
        self.advanced_section.body.addWidget(self.params_coastal_panel)
        self.advanced_section.body.addWidget(self.params_regularized_panel)
        self.advanced_section.body.addWidget(
            _make_compact_field_grid(
                [("FM Max Iterations", self.edit_fm_iteration_count), ("FM Convergence Threshold", self.edit_fm_convergence_threshold), ("FM Acceleration", self.edit_fm_acceleration), ("FM Patience", self.edit_fm_patience), ("Minimum Improvement", self.edit_fm_min_improve), ("Edge Buffer / cells", self.edit_lrc_edge_buffer)],
                columns=3,
            )
        )
        self.card_params.body.addWidget(self.advanced_section)

        self.card_result = CardFrame("Result Entry")
        self.card_preview = self.card_result
        self.cmb_preview_layer = _make_choice_combo([("Corrected Stack", "corrected"), ("Difference Stack", "difference"), ("Raw Stack", "raw")], "corrected")
        self.cmb_preview_figure = _make_choice_combo([("Global Map", "representative_map"), ("Regional Map", "representative_map_roi"), ("Time Series", "regional_series"), ("FM Diagnostics", "fm_rate_diagnostics")], "representative_map")
        self.cmb_preview_region = _make_choice_combo([("Main Region", "main")], "main")
        self.cmb_preview_time = _make_choice_combo([("All Epochs", "all")], "all")
        self.btn_open_preview_asset = QPushButton("Open Current Result")
        self.btn_open_preview_asset.setObjectName("GhostButton")
        self.btn_open_preview_corrected = QPushButton("View Corrected Stack in Preview")
        self.btn_open_preview_corrected.setObjectName("GhostButton")
        self.lbl_preview_status = QLabel("After the run finishes, open the corrected stack in Preview to inspect maps and series.")
        self.lbl_preview_status.setWordWrap(True)
        self.preview_image = QLabel("")
        self.preview_image.hide()
        self.cmb_preview_layer.hide()
        self.cmb_preview_figure.hide()
        self.cmb_preview_region.hide()
        self.cmb_preview_time.hide()
        result_actions = QWidget()
        result_actions_layout = QHBoxLayout(result_actions)
        result_actions_layout.setContentsMargins(0, 0, 0, 0)
        result_actions_layout.setSpacing(8)
        result_actions_layout.addWidget(self.btn_open_preview_asset)
        result_actions_layout.addWidget(self.btn_open_preview_corrected)
        result_actions_layout.addStretch(1)
        self.card_result.body.addWidget(result_actions)
        self.card_result.body.addWidget(self.lbl_preview_status)

        self.card_note = CardFrame("Diagnostics")
        self.txt_leakage_notes = QTextEdit()
        self.txt_leakage_notes.setReadOnly(True)
        self.txt_leakage_notes.setMinimumHeight(170)
        self.txt_leakage_notes.setPlaceholderText("After loading input metadata, diagnostics show product type, scene, recommendation, and applicability.")
        self.card_note.body.addWidget(self.txt_leakage_notes)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.addStretch(1)
        action_row.addWidget(self.btn_pause_leakage)
        action_row.addWidget(self.btn_stop_leakage)
        action_row.addWidget(self.btn_run_leakage)

        middle_grid = QGridLayout()
        middle_grid.setHorizontalSpacing(18)
        middle_grid.setVerticalSpacing(18)
        middle_grid.addWidget(self.card_strategy, 0, 0)
        middle_grid.addWidget(self.card_params, 0, 1)
        middle_grid.setColumnStretch(0, 1)
        middle_grid.setColumnStretch(1, 1)

        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(18)
        wrapper_layout.addLayout(action_row)
        self.card_enable.hide()
        wrapper_layout.addWidget(self.card_input)
        wrapper_layout.addLayout(middle_grid)
        wrapper_layout.addWidget(self.card_result)
        self.card_note.hide()
        self.body.addWidget(wrapper)
        self.body.addStretch(1)


class BasinPage(ScrollPage):
    def __init__(self):
        super().__init__("basin")
        self.add_header("Basin Analysis")

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(18)

        self.chk_basin_enable = QCheckBox("Active")
        self.chk_basin_enable.setChecked(True)
        self.chk_basin_enable.hide()

        self.card_grid_data = CardFrame("1. Grid Input")
        self.card_grid_data.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.edit_data_file = _make_line_edit("", "Input MAT/NC/HDF stack")
        self.btn_data_browse = QPushButton("Browse")
        self.btn_data_browse.setObjectName("GhostButton")
        self.btn_load_basin_info = QPushButton("Read Grid Metadata")
        self.btn_load_basin_info.setObjectName("GhostButton")
        self.lbl_basin_info = QLabel("Input not loaded.")
        self.lbl_basin_grid_shape = QLabel("Shape: not loaded")
        self.lbl_basin_time_range = QLabel("Time: not loaded")
        self.lbl_basin_variable = QLabel("Variable: auto")
        for label in (self.lbl_basin_info, self.lbl_basin_grid_shape, self.lbl_basin_time_range, self.lbl_basin_variable):
            label.setWordWrap(True)
        self.card_grid_data.body.addWidget(_make_stacked_field("Grid Stack", _make_edit_browse_widget(self.edit_data_file, self.btn_data_browse)))
        grid_meta = _make_compact_field_grid(
            [
                ("Input Status", self.lbl_basin_info),
                ("Grid Shape", self.lbl_basin_grid_shape),
                ("Time Coverage", self.lbl_basin_time_range),
                ("Data Variable", self.lbl_basin_variable),
            ],
            columns=2,
        )
        self.card_grid_data.body.addWidget(grid_meta)
        self.card_grid_data.body.addWidget(self.btn_load_basin_info)

        self.card_definition = CardFrame("2. Basin Boundary and Mask")
        self.edit_boundary_file = _make_line_edit("/mnt/nas_01/spatial_masks/global_hydrology_basins_v4_2.shp")
        self.btn_boundary_browse = QPushButton("Browse")
        self.btn_boundary_browse.setObjectName("GhostButton")
        self.edit_basin_name_field = _make_line_edit("Name", "Shapefile name field")
        self.btn_load_boundary_info = QPushButton("Read Boundary")
        self.btn_load_boundary_info.setObjectName("GhostButton")
        self.btn_generate_mask = QPushButton("Generate Mask")
        self.btn_generate_mask.setObjectName("GhostButton")
        self.btn_preview_selected_basin = QPushButton("Preview Selected Basin")
        self.btn_preview_selected_basin.setObjectName("PrimaryButton")
        self.lbl_boundary_info = QLabel("Boundary not loaded.")
        self.lbl_selected_basin = QLabel("Selected basin: first boundary feature")
        self.lbl_mask_info = QLabel("Mask: not generated")
        for label in (self.lbl_boundary_info, self.lbl_selected_basin, self.lbl_mask_info):
            label.setWordWrap(True)
        self.cmb_basin_selection_mode = _make_combo(["Multi-Selector", "Global Scan", "Point Buffer"], "Multi-Selector")
        self.btn_mode_multi = QPushButton("Selected Basin(s)")
        self.btn_mode_global = QPushButton("Global Scan")
        self.btn_mode_point = QPushButton("Point Buffer")
        for idx, btn in enumerate((self.btn_mode_multi, self.btn_mode_global, self.btn_mode_point)):
            btn.setCheckable(True)
            btn.setChecked(idx == 0)
            btn.setObjectName("PrimaryButton" if idx == 0 else "GhostButton")
        self.card_definition.body.addWidget(_make_stacked_field("Boundary File", _make_edit_browse_widget(self.edit_boundary_file, self.btn_boundary_browse)))
        self.card_definition.body.addWidget(_make_dual_field("Name Field", self.edit_basin_name_field, "Selection Mode", self.cmb_basin_selection_mode))
        mode_row = QWidget()
        mode_layout = QHBoxLayout(mode_row)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(8)
        mode_layout.addWidget(self.btn_mode_multi)
        mode_layout.addWidget(self.btn_mode_global)
        mode_layout.addWidget(self.btn_mode_point)
        mode_layout.addStretch(1)
        self.card_definition.body.addWidget(mode_row)
        boundary_actions = QWidget()
        boundary_actions_layout = QHBoxLayout(boundary_actions)
        boundary_actions_layout.setContentsMargins(0, 0, 0, 0)
        boundary_actions_layout.setSpacing(8)
        boundary_actions_layout.addWidget(self.btn_load_boundary_info)
        boundary_actions_layout.addWidget(self.btn_generate_mask)
        boundary_actions_layout.addWidget(self.btn_preview_selected_basin)
        boundary_actions_layout.addStretch(1)
        self.card_definition.body.addWidget(boundary_actions)
        self.card_definition.body.addWidget(_make_compact_field_grid(
            [
                ("Boundary Status", self.lbl_boundary_info),
                ("Current Basin", self.lbl_selected_basin),
                ("Mask Status", self.lbl_mask_info),
            ],
            columns=1,
        ))

        self.table_basins = QTableWidget()
        populate_table(self.table_basins, ["ID", "Basin Name", "Cells / Area", "Region / Parts"], BASIN_ROWS)
        self.table_basins.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_basins.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_basins.setMinimumHeight(150)
        self.table_basins.setMaximumHeight(230)
        self.card_definition.body.addWidget(self.table_basins)

        self.card_preview = CardFrame("Selected Basin Spatial Preview")
        self.card_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.lbl_basin_preview_status = QLabel("Preview: select one basin on the left, then render its spatial distribution and mask.")
        self.lbl_basin_preview_status.setObjectName("PageSubtitle")
        self.lbl_basin_preview_status.setWordWrap(True)
        self.basin_preview_toolbar_host = QWidget()
        self.basin_preview_toolbar_host.setObjectName("InlineToolbar")
        self.basin_preview_plot_host = QFrame()
        self.basin_preview_plot_host.setObjectName("PreviewPlotFrame")
        self.basin_preview_plot_host.setMinimumHeight(360)
        self.basin_preview_plot_host.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_plot_layout = QVBoxLayout(self.basin_preview_plot_host)
        preview_plot_layout.setContentsMargins(0, 0, 0, 0)
        preview_plot_layout.setSpacing(0)
        self.btn_refresh_basin_preview = QPushButton("Refresh Selected Basin Preview")
        self.btn_refresh_basin_preview.setObjectName("GhostButton")
        self.card_preview.body.addWidget(self.lbl_basin_preview_status)
        self.card_preview.body.addWidget(self.basin_preview_toolbar_host)
        self.card_preview.body.addWidget(self.basin_preview_plot_host)
        self.card_preview.body.addWidget(self.btn_refresh_basin_preview)

        self.card_output = CardFrame("3. Analysis Products and Output")
        self.card_output.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.edit_export_path = _make_line_edit("./output/local/basin/")
        self.chk_basin_save_series = QCheckBox("Spatial extraction: area-weighted basin time series")
        self.chk_basin_save_series.setChecked(True)
        self.chk_basin_save_stats = QCheckBox("Amplitude/trend analysis: trend, annual, and semiannual statistics")
        self.chk_basin_save_stats.setChecked(True)
        self.chk_basin_save_mask_grid = QCheckBox("Spatial grid output: mask and diagnostic grids")
        self.chk_basin_save_mask_grid.setChecked(True)
        self.chk_basin_save_ts_txt = QCheckBox("Save TXT/CSV tables")
        self.chk_basin_save_ts_txt.setChecked(True)
        self.chk_basin_save_ts_mat = QCheckBox("Save MATLAB MAT products")
        self.chk_basin_save_ts_mat.setChecked(True)
        self.chk_basin_save_grid_mat = QCheckBox("Save masked grid MAT")
        self.chk_basin_save_grid_mat.setChecked(True)
        self.card_output.body.addWidget(_make_stacked_field("Export Path", self.edit_export_path))
        self.card_output.body.addWidget(self.chk_basin_save_series)
        self.card_output.body.addWidget(self.chk_basin_save_stats)
        self.card_output.body.addWidget(self.chk_basin_save_mask_grid)
        self.card_output.body.addWidget(_make_compact_field_grid(
            [
                ("Table Output", self.chk_basin_save_ts_txt),
                ("Series MAT", self.chk_basin_save_ts_mat),
                ("Grid MAT", self.chk_basin_save_grid_mat),
            ],
            columns=1,
        ))

        self.card_temporal = CardFrame("Temporal Options")
        self.card_temporal.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.cmb_aggregation_strategy = _make_combo(["Calendar Month Mean", "10-Day Sliding Window"], "Calendar Month Mean")
        self.cmb_missing_month_fallback = _make_combo(["Linear Interpolation", "Nearest Month", "Hold Last Value"], "Linear Interpolation")
        self.lbl_temporal_note = QLabel("Monthly GRACE basin studies usually report equivalent-water-height series, linear trend, annual amplitude, and semiannual amplitude.")
        self.lbl_temporal_note.setWordWrap(True)
        self.card_temporal.body.addWidget(_make_dual_field("Aggregation", self.cmb_aggregation_strategy, "Gap Handling", self.cmb_missing_month_fallback))
        self.card_temporal.body.addWidget(self.lbl_temporal_note)
        self.card_temporal.body.addWidget(build_badge("Gap policy: gaps over 3 months require manual review", "warning"))

        self.card_series_tools = CardFrame("Quick Analysis Tools")
        self.card_series_tools.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.btn_tool_grid_to_series = QPushButton("Extract Basin Series")
        self.btn_tool_grid_to_series.setObjectName("GhostButton")
        self.btn_tool_harmonic_fit = QPushButton("Estimate Trend / Amplitude")
        self.btn_tool_harmonic_fit.setObjectName("GhostButton")
        self.lbl_series_tool_status = QLabel("Status: ready for time series extraction.")
        self.lbl_series_tool_status.setWordWrap(True)
        self.lbl_series_tool_note = QLabel(
            "Tools use the selected grid stack and boundary, then write series and harmonic-fit outputs under output/local/tools."
        )
        self.lbl_series_tool_note.setWordWrap(True)
        tool_row = QWidget()
        tool_layout = QHBoxLayout(tool_row)
        tool_layout.setContentsMargins(0, 0, 0, 0)
        tool_layout.setSpacing(8)
        tool_layout.addWidget(self.btn_tool_grid_to_series)
        tool_layout.addWidget(self.btn_tool_harmonic_fit)
        tool_layout.addStretch(1)
        self.card_series_tools.body.addWidget(tool_row)
        self.card_series_tools.body.addWidget(self.lbl_series_tool_status)
        self.card_series_tools.body.addWidget(self.lbl_series_tool_note)

        self.btn_run_basin = QPushButton("Run Analysis")
        self.btn_run_basin.setObjectName("PrimaryButton")
        self.btn_pause_basin = QPushButton("Pause")
        self.btn_pause_basin.setObjectName("GhostButton")
        self.btn_stop_basin = QPushButton("Stop")
        self.btn_stop_basin.setObjectName("GhostButton")

        right_col = QWidget()
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(18)
        right_layout.addWidget(self.card_preview)
        right_layout.addWidget(self.card_output)
        right_layout.addWidget(self.card_temporal)
        right_layout.addStretch(1)

        left_col = QWidget()
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(18)
        left_layout.addWidget(self.card_grid_data)
        left_layout.addWidget(self.card_definition)
        left_layout.addWidget(self.card_series_tools)
        left_layout.addStretch(1)

        grid.addWidget(left_col, 0, 0)
        grid.addWidget(right_col, 0, 1)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)

        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(18)
        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.addStretch(1)
        action_row.addWidget(self.btn_pause_basin)
        action_row.addWidget(self.btn_stop_basin)
        action_row.addWidget(self.btn_run_basin)
        wrapper_layout.addLayout(action_row)
        wrapper_layout.addLayout(grid)
        self.body.addWidget(wrapper)
        self.body.addStretch(1)


class PreviewPage(QWidget):
    def __init__(self):
        super().__init__()
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar_panel = QFrame()
        self.sidebar_panel.setObjectName("PreviewSidebar")
        self.sidebar_panel.setMinimumWidth(240)
        self.sidebar_panel.setMaximumWidth(400)
        sidebar_panel_layout = QVBoxLayout(self.sidebar_panel)
        sidebar_panel_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_panel_layout.setSpacing(0)

        self.sidebar_scroll = QScrollArea()
        self.sidebar_scroll.setWidgetResizable(True)
        self.sidebar_scroll.setFrameShape(QFrame.NoFrame)
        self.sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.sidebar_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.sidebar = QWidget()
        self.sidebar.setObjectName("PreviewSidebarContent")
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(16, 14, 16, 14)
        side_layout.setSpacing(10)

        controls_title = QLabel("Preview Controls")
        controls_title.setObjectName("CardTitle")
        side_layout.addWidget(controls_title)

        self.edit_dataset_source = _make_line_edit("stack_v2_grace_jpl.nc")
        self.btn_dataset_browse = QPushButton("Browse")
        self.btn_dataset_browse.setObjectName("GhostButton")
        self.btn_load_stack = QPushButton("Load Stack Info")
        self.btn_load_stack.setObjectName("GhostButton")
        self.lbl_stack_info = QLabel("Stack not loaded.")
        side_layout.addWidget(_make_stacked_field("Dataset Source", _make_edit_browse_widget(self.edit_dataset_source, self.btn_dataset_browse)))
        side_layout.addWidget(self.btn_load_stack)
        side_layout.addWidget(_make_stacked_field("Stack Status", self.lbl_stack_info))

        self.cmb_data_var = _make_combo(["ewh"], "ewh")
        side_layout.addWidget(_make_stacked_field("Data Variable", self.cmb_data_var))

        self.slider_time_index = QSlider(Qt.Horizontal)
        self.slider_time_index.setRange(0, 100)
        self.slider_time_index.setValue(75)
        self.lbl_time_index = QLabel("Index: 2018-06-15")
        side_layout.addWidget(_make_stacked_field("Time Index", self.slider_time_index, self.lbl_time_index))

        self.cmb_projection = _make_combo(
            [
                "Robinson (Global)",
                "Plate Carree",
                "Orthographic",
                "Mollweide",
                "Mercator",
                "Miller",
                "Sinusoidal",
                "Equal Earth",
                "Winkel Tripel",
                "Eckert IV",
                "Azimuthal Equidistant",
                "Stereographic",
                "Lambert Conformal",
                "Albers Equal Area",
            ],
            "Robinson (Global)",
        )
        side_layout.addWidget(_make_stacked_field("Projection", self.cmb_projection))
        self.cmb_cmap = _make_combo(
            ["RdBu_r", "viridis", "coolwarm", "Spectral_r", "terrain", "turbo", "plasma", "cividis"],
            "RdBu_r",
        )
        self.edit_cmin = _make_line_edit("", "auto")
        self.edit_cmax = _make_line_edit("", "auto")
        side_layout.addWidget(_make_stacked_field("Colormap", self.cmb_cmap))
        side_layout.addWidget(_make_dual_field("Color Min", self.edit_cmin, "Color Max", self.edit_cmax))

        self.chk_auto_region = QCheckBox("Use Detected Extent")
        self.chk_auto_region.setChecked(True)
        self.edit_region_lon_min = _make_line_edit("-180")
        self.edit_region_lon_max = _make_line_edit("180")
        self.edit_region_lat_min = _make_line_edit("-90")
        self.edit_region_lat_max = _make_line_edit("90")
        side_layout.addWidget(self.chk_auto_region)
        side_layout.addWidget(_make_dual_field("Lon Min", self.edit_region_lon_min, "Lon Max", self.edit_region_lon_max))
        side_layout.addWidget(_make_dual_field("Lat Min", self.edit_region_lat_min, "Lat Max", self.edit_region_lat_max))

        self.card_layers = CardFrame("Layer Stack")
        self.chk_layer_data = QCheckBox("Data: Mass Anomaly")
        self.chk_layer_data.setChecked(True)
        self.chk_layer_coastlines = QCheckBox("Coastlines")
        self.chk_layer_coastlines.setChecked(True)
        self.chk_layer_boundaries = QCheckBox("Boundary Overlay")
        self.chk_layer_boundaries.setChecked(False)
        self.chk_layer_grid = QCheckBox("Grid Lines")
        self.chk_layer_grid.setChecked(True)
        self.chk_layer_rivers = QCheckBox("Additional Custom SHP")
        self.chk_layer_rivers.setChecked(False)
        self.edit_boundary_overlay = _make_line_edit("", "Optional basin/custom boundary .shp/.txt/.bln")
        self.btn_boundary_overlay_browse = QPushButton("Browse")
        self.btn_boundary_overlay_browse.setObjectName("GhostButton")
        self.edit_custom_overlay = _make_line_edit("", "Optional extra shapefile overlay")
        self.btn_custom_overlay_browse = QPushButton("Browse")
        self.btn_custom_overlay_browse.setObjectName("GhostButton")
        for chk in (
            self.chk_layer_data,
            self.chk_layer_coastlines,
            self.chk_layer_boundaries,
            self.chk_layer_grid,
            self.chk_layer_rivers,
        ):
            self.card_layers.body.addWidget(chk)
            if chk is self.chk_layer_boundaries:
                self.card_layers.body.addWidget(_make_stacked_field("Boundary File", _make_edit_browse_widget(self.edit_boundary_overlay, self.btn_boundary_overlay_browse)))
            elif chk is self.chk_layer_rivers:
                self.card_layers.body.addWidget(_make_stacked_field("Custom SHP", _make_edit_browse_widget(self.edit_custom_overlay, self.btn_custom_overlay_browse)))
        side_layout.addWidget(self.card_layers)
        side_layout.addStretch(1)
        self.sidebar_scroll.setWidget(self.sidebar)
        sidebar_panel_layout.addWidget(self.sidebar_scroll, 1)

        self.sidebar_footer = QFrame()
        self.sidebar_footer.setObjectName("PreviewSidebarFooter")
        footer_layout = QVBoxLayout(self.sidebar_footer)
        footer_layout.setContentsMargins(20, 12, 20, 16)
        footer_layout.setSpacing(10)
        self.btn_plot = QPushButton("Render Preview")
        self.btn_plot.setObjectName("GhostButton")
        self.btn_export_figure = QPushButton("Export Figure")
        self.btn_export_figure.setObjectName("PrimaryButton")
        self.btn_export_figure.setStyleSheet(
            "background: #005db5; color: white; border: 1px solid #005db5; border-radius: 3px; font-weight: 600;"
        )
        self.btn_plot.setMinimumHeight(38)
        self.btn_export_figure.setMinimumHeight(38)
        footer_layout.addWidget(self.btn_plot)
        footer_layout.addWidget(self.btn_export_figure)
        sidebar_panel_layout.addWidget(self.sidebar_footer, 0)

        self.main = QFrame()
        self.main.setObjectName("PageRoot")
        main_layout = QVBoxLayout(self.main)
        main_layout.setContentsMargins(16, 10, 16, 10)
        main_layout.setSpacing(8)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)
        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(2)
        self.preview_title = QLabel("Preview & Analysis")
        self.preview_title.setObjectName("PageTitle")
        self.preview_title.setStyleSheet("font-size: 20px; font-weight: 700;")
        self.preview_subtitle = QLabel(PAGE_SUBTITLES["preview"])
        self.preview_subtitle.setObjectName("PageSubtitle")
        self.preview_subtitle.setStyleSheet("font-size: 12px;")
        title_wrap.addWidget(self.preview_title)
        title_wrap.addWidget(self.preview_subtitle)
        header_layout.addLayout(title_wrap, 1)
        self.btn_toggle_sidebar = QPushButton("Hide Controls")
        self.btn_toggle_sidebar.setObjectName("GhostButton")
        header_layout.addWidget(self.btn_toggle_sidebar, 0, alignment=Qt.AlignRight | Qt.AlignTop)
        self.btn_toggle_status = QPushButton("Hide Status")
        self.btn_toggle_status.setObjectName("GhostButton")
        header_layout.addWidget(self.btn_toggle_status, 0, alignment=Qt.AlignRight | Qt.AlignTop)
        main_layout.addWidget(header)

        self.plot_card = QFrame()
        self.plot_card.setObjectName("PageCard")
        plot_layout = QVBoxLayout(self.plot_card)
        plot_layout.setContentsMargins(12, 10, 12, 10)
        plot_layout.setSpacing(6)
        plot_header = QWidget()
        plot_header_layout = QHBoxLayout(plot_header)
        plot_header_layout.setContentsMargins(0, 0, 0, 0)
        plot_header_layout.setSpacing(8)
        self.canvas_preview_title = QLabel("Robinson Projection: June 2018")
        self.canvas_preview_title.setObjectName("PageTitle")
        self.canvas_preview_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        plot_header_layout.addWidget(self.canvas_preview_title, 1)
        self.btn_toggle_tools = QPushButton("Tools")
        self.btn_toggle_tools.setObjectName("GhostButton")
        self.btn_toggle_tools.setMinimumHeight(30)
        self.plot_toolbar_host = QFrame()
        self.plot_toolbar_host.setObjectName("PreviewToolbarHost")
        self.plot_toolbar_host.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.plot_toolbar_host.setVisible(False)
        plot_header_layout.addWidget(self.plot_toolbar_host, 0, alignment=Qt.AlignRight | Qt.AlignVCenter)
        plot_header_layout.addWidget(self.btn_toggle_tools, 0, alignment=Qt.AlignRight | Qt.AlignVCenter)
        self.plot_container = QFrame()
        self.plot_container.setObjectName("PageRoot")
        self.plot_container.setMinimumHeight(520)
        plot_layout.addWidget(plot_header)
        plot_layout.addWidget(self.plot_container, 1)

        self.card_status = CardFrame("Map Status")
        self.lbl_dataset = QLabel("GRACE Level-2 (JPL Release)")
        self.lbl_dataset.setWordWrap(True)
        self.lbl_cursor_position = QLabel("78.22 N, 15.65 E")
        self.lbl_grid_value = QLabel("-12.44 cm")
        self.lbl_engine_latency = QLabel("42 ms")
        status_grid_wrap = QWidget()
        status_grid = QGridLayout(status_grid_wrap)
        status_grid.setContentsMargins(0, 0, 0, 0)
        status_grid.setHorizontalSpacing(14)
        status_grid.setVerticalSpacing(4)
        for value_label in (self.lbl_dataset, self.lbl_cursor_position, self.lbl_grid_value, self.lbl_engine_latency):
            value_label.setObjectName("PreviewStatusValue")
        status_grid.addWidget(_make_row_label("Dataset"), 0, 0)
        status_grid.addWidget(self.lbl_dataset, 0, 1)
        status_grid.addWidget(_make_row_label("Cursor"), 0, 2)
        status_grid.addWidget(self.lbl_cursor_position, 0, 3)
        status_grid.addWidget(_make_row_label("Value"), 0, 4)
        status_grid.addWidget(self.lbl_grid_value, 0, 5)
        status_grid.addWidget(_make_row_label("Latency"), 0, 6)
        status_grid.addWidget(self.lbl_engine_latency, 0, 7)
        status_grid.setColumnStretch(1, 3)
        status_grid.setColumnStretch(3, 2)
        status_grid.setColumnStretch(5, 1)
        self.card_status.body.setContentsMargins(16, 8, 16, 8)
        self.card_status.body.setSpacing(0)
        self.card_status.body.addWidget(status_grid_wrap)
        self.card_status.setMinimumHeight(52)
        self.card_status.setMaximumHeight(68)
        self.card_status.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        self.main_splitter = QSplitter(Qt.Vertical)
        self.main_splitter.addWidget(self.plot_card)
        self.main_splitter.addWidget(self.card_status)
        self.main_splitter.setChildrenCollapsible(True)
        self.main_splitter.setStretchFactor(0, 6)
        self.main_splitter.setStretchFactor(1, 2)
        self.main_splitter.setSizes([940, 76])
        main_layout.addWidget(self.main_splitter, 1)

        self.page_splitter = QSplitter(Qt.Horizontal)
        self.page_splitter.addWidget(self.sidebar_panel)
        self.page_splitter.addWidget(self.main)
        self.page_splitter.setChildrenCollapsible(False)
        self.page_splitter.setStretchFactor(0, 2)
        self.page_splitter.setStretchFactor(1, 7)
        self.page_splitter.setSizes([320, 1320])

        root.addWidget(self.page_splitter, 1)


class RunMonitorPage(ScrollPage):
    def __init__(self):
        super().__init__("monitor")
        self.add_header("Run Output")

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(18)

        self.card_status = CardFrame("Run Summary")
        self.lbl_pipeline_status = QLabel("Idle")
        self.lbl_overall_progress = QLabel("0 / 0")
        self.lbl_current_task = QLabel("Waiting for a pipeline run.")
        self.lbl_current_subtask = QLabel("Subtask: not started")
        self.lbl_eta = QLabel("ETA: not available")
        self.bar_overall_progress = QProgressBar()
        self.bar_overall_progress.setRange(0, 100)
        self.bar_overall_progress.setValue(0)
        self.bar_overall_progress.setTextVisible(False)
        self.bar_current_task = QProgressBar()
        self.bar_current_task.setRange(0, 100)
        self.bar_current_task.setValue(0)
        self.bar_current_task.setTextVisible(False)
        self.card_status.body.addWidget(_make_field_row("Pipeline", self.lbl_pipeline_status))
        self.card_status.body.addWidget(self.bar_overall_progress)
        self.card_status.body.addWidget(_make_field_row("Current Task", self.lbl_current_task))
        self.card_status.body.addWidget(_make_field_row("Subtask", self.lbl_current_subtask))
        self.card_status.body.addWidget(_make_field_row("ETA", self.lbl_eta))
        self.card_status.body.addWidget(self.bar_current_task)

        self.card_context = CardFrame("Resolved Context")
        self.lbl_run_config = QLabel("Config: not loaded")
        self.lbl_run_filters = QLabel("Filters: not evaluated")
        self.lbl_run_output = QLabel("Output Root: not resolved")
        self.lbl_run_timespan = QLabel("Time Span: not scanned")
        for label in (self.lbl_run_config, self.lbl_run_filters, self.lbl_run_output, self.lbl_run_timespan):
            label.setWordWrap(True)
            self.card_context.body.addWidget(label)

        self.card_outputs = CardFrame("Resolved Outputs")
        self.lbl_output_root = QLabel("Output Root: not resolved")
        self.lbl_output_local = QLabel("Local Output: not resolved")
        self.lbl_output_plots = QLabel("Plots: not resolved")
        self.lbl_last_artifact = QLabel("Latest Artifact: not generated yet.")
        for label in (self.lbl_output_root, self.lbl_output_local, self.lbl_output_plots, self.lbl_last_artifact):
            label.setWordWrap(True)
            self.card_outputs.body.addWidget(label)

        self.card_controls = CardFrame("Run Controls")
        self.btn_pause_run = QPushButton("Pause Current Run")
        self.btn_pause_run.setObjectName("GhostButton")
        self.btn_abort_pipeline = QPushButton("Stop Current Run")
        self.btn_abort_pipeline.setObjectName("DangerGhostButton")
        self.btn_restart_instance = QPushButton("Clear Run State")
        self.btn_restart_instance.setObjectName("GhostButton")
        self.card_controls.body.addWidget(self.btn_pause_run)
        self.card_controls.body.addWidget(self.btn_abort_pipeline)
        self.card_controls.body.addWidget(self.btn_restart_instance)

        self.card_logs = CardFrame("Live Process Logs")
        self.text_live_logs = QTextEdit()
        self.text_live_logs.setReadOnly(True)
        self.text_live_logs.setPlainText("Run monitor initialized. Start a run to stream live logs.")
        self.card_logs.body.addWidget(self.text_live_logs)

        left_col = QVBoxLayout()
        left_col.setSpacing(18)
        left_col.addWidget(self.card_status)
        left_col.addWidget(self.card_context)
        left_col.addWidget(self.card_controls)

        right_col = QVBoxLayout()
        right_col.setSpacing(18)
        right_col.addWidget(self.card_outputs)
        right_col.addStretch(1)

        left_wrap = QWidget()
        left_wrap.setLayout(left_col)
        right_wrap = QWidget()
        right_wrap.setLayout(right_col)

        grid.addWidget(left_wrap, 0, 0)
        grid.addWidget(right_wrap, 0, 1)
        grid.addWidget(self.card_logs, 1, 0, 1, 2)
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 3)

        wrapper = QWidget()
        wrapper.setLayout(grid)
        self.body.addWidget(wrapper)
        self.body.addStretch(1)
