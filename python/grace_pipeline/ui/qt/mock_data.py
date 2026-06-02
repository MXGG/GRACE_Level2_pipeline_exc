"""Mock data for the first-stage PySide6 UI shell."""

NAV_ITEMS = [
    ("dashboard", "Dashboard"),
    ("data_paths", "Data Paths"),
    ("processing", "Processing Setup"),
    ("leakage", "Leakage Correction"),
    ("basin", "Basin Analysis"),
    ("preview", "Preview"),
]


PAGE_TITLES = {
    "dashboard": "Dashboard",
    "data_paths": "Data Paths",
    "processing": "Processing Setup",
    "leakage": "Leakage Correction",
    "basin": "Basin Workflow",
    "preview": "Preview & Analysis",
    "monitor": "Run Output",
}


PAGE_SUBTITLES = {
    "dashboard": "Project overview, pipeline actions, and recent execution state.",
    "data_paths": "Define directory pointers and reference datasets required by the pipeline.",
    "processing": "Configure time coverage, grid geometry, inversion setup, and filters.",
    "leakage": "Choose a correction workflow, inspect input metadata, and hand results to Preview.",
    "basin": "Read GRACE grids, build basin masks, extract basin series, and estimate trend or seasonal signals.",
    "preview": "Inspect stacked products, switch projections, and manage map overlays.",
    "monitor": "Track live progress, inspect outputs, and review process logs.",
}


DASHBOARD_LOGS = [
    ("2023-10-24 10:15", "JPL_RL06_MASCON_V02_Full", "SUCCESS", "01:42:12"),
    ("2023-10-23 16:30", "JPL_RL06_TEST_GAUSS_300km", "FAILED", "00:04:18"),
    ("2023-10-22 09:45", "JPL_RL06_MASCON_V01_Baseline", "SUCCESS", "01:38:55"),
]


PATH_ROWS = [
    ("GFC Input Directory", "/mnt/scientific/grace/v2/gfc_raw_2024", "Verified"),
    ("DDK Data Directory", "/data/filters/ddk_v5/null", "Invalid Path"),
    ("Main Output Root", "/mnt/storage/out/grace_l2_run_alpha", "Verified"),
    ("Boundary Path", "/data/ref/boundaries/world_geom.shp", "Verified"),
    ("Low-Degree Path", "/data/ref/low_deg/TN13_SLR_C20.txt", "Warning"),
    ("Mascon Reference", "/data/ref/mascons/jpl_rl06_v2.nc", "Verified"),
]


BASIN_ROWS = [
    ("AMZ_01", "Amazon Basin", "6,144,727", "South America"),
    ("MSI_04", "Mississippi-Missouri", "3,202,230", "North America"),
    ("NLE_02", "Nile River", "3,349,000", "Africa"),
    ("YGT_09", "Yangtze (Chang Jiang)", "1,808,500", "East Asia"),
]


MONITOR_ALERTS = [
    ("WARNING", "Inconsistent metadata in source file 'GRACE_2023_201.dat'"),
    ("INFO", "HPC cluster node switch detected. Job migrating to node-05."),
]


CONSOLE_LINES = [
    "[2023-10-27 14:25:01] INFO: Initializing SH conversion module...",
    "[2023-10-27 14:25:04] INFO: Loading spherical harmonics coefficients up to degree 60.",
    "[2023-10-27 14:25:08] SUCCESS: Coefficients validated. Chi-square = 1.042.",
    "[2023-10-27 14:25:12] INFO: Commencing spatial grid interpolation (0.25deg resolution).",
    "[2023-10-27 14:25:15] INFO: Applying Gaussian smoothing filter (r=300km)...",
    "[2023-10-27 14:25:30] INFO: Processing tile 42 of 180...",
]
