"""Neutral default labels for the PySide6 UI shell.

Runtime values are populated by the Qt controller from the active configuration,
file-system probes, and live pipeline signals. Defaults in this module must not
look like real processing results.
"""

NAV_ITEMS = [
    ("dashboard", "Dashboard", "dashboard"),
    ("processing", "Filter Processing", "processing"),
    ("leakage", "Leakage Correction", "leakage"),
    ("basin", "Basin Analysis", "basin"),
    ("preview", "Preview", "preview"),
]


PAGE_TITLES = {
    "dashboard": "Dashboard",
    "data_paths": "Data Paths",
    "processing": "Filter Processing",
    "leakage": "Leakage Correction",
    "basin": "Basin Workflow",
    "preview": "Preview & Analysis",
    "monitor": "Run Monitor",
}


PAGE_SUBTITLES = {
    "dashboard": "Project overview, recent execution state, and resolved outputs.",
    "data_paths": "Internal configuration page for path widgets used by Filter Processing.",
    "processing": "Configure input/output paths, time coverage, grid geometry, inversion setup, and filters.",
    "leakage": "Choose a correction workflow, inspect input metadata, and hand results to Preview.",
    "basin": "Read GRACE grids, build basin masks, extract basin series, and estimate trend or seasonal signals.",
    "preview": "Inspect stacked products, switch projections, and manage map overlays.",
    "monitor": "Internal run monitor compatibility page.",
}


DASHBOARD_LOGS = []
PATH_ROWS = []
BASIN_ROWS = []
MONITOR_ALERTS = []


CONSOLE_LINES = [
    "GRACE-L2 desktop console initialized.",
    "Load or create a configuration, validate paths, then start a processing run.",
]
