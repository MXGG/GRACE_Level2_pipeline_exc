"""Neutral default labels for the PySide6 UI shell.

Runtime values are populated by the Qt controller from the active configuration,
file-system probes, and live pipeline signals. Defaults in this module must not
look like real processing results.
"""

NAV_ITEMS = [
    ("dashboard", "Dashboard"),
    ("data_paths", "Data Paths"),
    ("processing", "Processing Setup"),
    ("leakage", "Leakage Correction"),
    ("basin", "Basin Analysis"),
    ("preview", "Preview"),
    ("monitor", "Run Monitor"),
]


PAGE_TITLES = {
    "dashboard": "Dashboard",
    "data_paths": "Data Paths",
    "processing": "Processing Setup",
    "leakage": "Leakage Correction",
    "basin": "Basin Workflow",
    "preview": "Preview & Analysis",
    "monitor": "Run Monitor",
}


PAGE_SUBTITLES = {
    "dashboard": "Project overview, pipeline actions, and recent execution state.",
    "data_paths": "Define directory pointers and reference datasets required by the pipeline.",
    "processing": "Configure time coverage, grid geometry, inversion setup, and filters.",
    "leakage": "Choose a correction workflow, inspect input metadata, and hand results to Preview.",
    "basin": "Read GRACE grids, build basin masks, extract basin series, and estimate trend or seasonal signals.",
    "preview": "Inspect stacked products, switch projections, and manage map overlays.",
    "monitor": "Track the active run, subtask progress, resolved outputs, and process logs.",
}


DASHBOARD_LOGS = []
PATH_ROWS = []
BASIN_ROWS = []
MONITOR_ALERTS = []


CONSOLE_LINES = [
    "GRACE-L2 desktop console initialized.",
    "Load or create a configuration, validate paths, then start a processing run.",
]
