"""Basin tab builder."""

from pathlib import Path
import tkinter as tk
from tkinter import ttk


def build_basin_tab(gui, parent):
    """Build the basin-analysis tab."""
    grp_input = ttk.LabelFrame(parent, text="Input Data", padding=10)
    grp_input.pack(fill=tk.X, pady=6)
    grp_input.columnconfigure(1, weight=1)

    gui.var_basin_enable = tk.BooleanVar(value=bool(getattr(gui.default_cfg, "basin", {}).get("analysis_enable", False)))
    ttk.Checkbutton(grp_input, text="Enable Basin Analysis", variable=gui.var_basin_enable).grid(row=0, column=0, sticky="w", pady=2)

    gui.var_basin_data = tk.StringVar(value="")
    ttk.Label(grp_input, text="Data file (mat/txt/nc/hdf):").grid(row=1, column=0, sticky="w")
    ttk.Entry(grp_input, textvariable=gui.var_basin_data).grid(row=1, column=1, padx=5, pady=2, sticky="we")
    ttk.Button(
        grp_input,
        text="Browse...",
        command=lambda: gui._browse_file(gui.var_basin_data, filetypes=[("Data files", "*.mat;*.txt;*.nc;*.nc4;*.cdf;*.hdf;*.h5;*.hdf5;*.he5"), ("All", "*.*")]),
    ).grid(row=1, column=2)
    ttk.Button(grp_input, text="Load Info", command=gui.load_basin_info).grid(row=1, column=3, padx=4)

    gui.var_basin_tag = tk.StringVar(value="DATA")
    ttk.Label(grp_input, text="Tag (output name):").grid(row=2, column=0, sticky="w")
    ttk.Entry(grp_input, textvariable=gui.var_basin_tag, width=12).grid(row=2, column=1, sticky="w", padx=5)

    gui.var_basin_info = tk.StringVar(value="No data loaded")
    ttk.Label(grp_input, textvariable=gui.var_basin_info, foreground="gray").grid(row=3, column=1, columnspan=3, sticky="w")

    grp_boundary = ttk.LabelFrame(parent, text="Boundary Selection", padding=10)
    grp_boundary.pack(fill=tk.X, pady=6)
    grp_boundary.columnconfigure(1, weight=1)

    gui.var_basin_file = tk.StringVar(value=gui._normpath(getattr(gui.default_cfg, "basin", {}).get("boundary_file", "")))
    ttk.Label(grp_boundary, text="Boundary File (shp/txt/bln):").grid(row=0, column=0, sticky="w")
    ttk.Entry(grp_boundary, textvariable=gui.var_basin_file).grid(row=0, column=1, padx=5, pady=2, sticky="we")
    ttk.Button(
        grp_boundary,
        text="Browse...",
        command=lambda: gui._browse_file(gui.var_basin_file, filetypes=[("Boundary files", "*.shp;*.txt;*.bln"), ("All", "*.*")]),
    ).grid(row=0, column=2)

    gui.var_basin_name = tk.StringVar(value=getattr(gui.default_cfg, "basin", {}).get("name", ""))
    ttk.Label(grp_boundary, text="Basin Name (optional):").grid(row=1, column=0, sticky="w")
    ttk.Entry(grp_boundary, textvariable=gui.var_basin_name).grid(row=1, column=1, padx=5, pady=2, sticky="we")
    gui.var_basin_name_field = tk.StringVar(value=getattr(gui.default_cfg, "basin", {}).get("name_field", "Name"))
    ttk.Label(grp_boundary, text="Name Field:").grid(row=1, column=2, sticky="w")
    ttk.Entry(grp_boundary, textvariable=gui.var_basin_name_field, width=12).grid(row=1, column=3, padx=5, pady=2, sticky="w")

    grp_time = ttk.LabelFrame(parent, text="Time Handling", padding=10)
    grp_time.pack(fill=tk.X, pady=6)
    grp_time.columnconfigure(1, weight=1)
    gui.var_basin_use_file_time = tk.BooleanVar(value=True)
    ttk.Checkbutton(grp_time, text="Use time variable from file if available", variable=gui.var_basin_use_file_time).grid(row=0, column=0, columnspan=3, sticky="w")
    gui.var_basin_start = tk.StringVar(value="")
    gui.var_basin_step = tk.IntVar(value=1)
    ttk.Label(grp_time, text="Fallback start (YYYY-MM):").grid(row=1, column=0, sticky="w")
    ttk.Entry(grp_time, textvariable=gui.var_basin_start, width=12).grid(row=1, column=1, padx=5, sticky="w")
    ttk.Label(grp_time, text="Step (months):").grid(row=1, column=2, sticky="w", padx=6)
    ttk.Entry(grp_time, textvariable=gui.var_basin_step, width=6).grid(row=1, column=3, padx=5, sticky="w")

    grp_out = ttk.LabelFrame(parent, text="Outputs", padding=10)
    grp_out.pack(fill=tk.X, pady=6)
    grp_out.columnconfigure(1, weight=1)

    gui.var_basin_out_dir = tk.StringVar(value=gui._normpath(str(Path(gui.cfg.path.OUTPUT) / "basin")))
    ttk.Label(grp_out, text="Output directory:").grid(row=0, column=0, sticky="w")
    ttk.Entry(grp_out, textvariable=gui.var_basin_out_dir).grid(row=0, column=1, padx=5, pady=2, sticky="we")
    ttk.Button(grp_out, text="Browse...", command=lambda: gui._browse_dir(gui.var_basin_out_dir)).grid(row=0, column=2)

    gui.var_basin_prefix = tk.StringVar(value="basin")
    ttk.Label(grp_out, text="Filename prefix:").grid(row=1, column=0, sticky="w")
    ttk.Entry(grp_out, textvariable=gui.var_basin_prefix, width=16).grid(row=1, column=1, padx=5, sticky="w")

    gui.var_basin_do_ts = tk.BooleanVar(value=True)
    gui.var_basin_do_stats = tk.BooleanVar(value=True)
    gui.var_basin_do_grid = tk.BooleanVar(value=True)
    ttk.Checkbutton(grp_out, text="Compute time series", variable=gui.var_basin_do_ts).grid(row=2, column=0, sticky="w", padx=4)
    ttk.Checkbutton(grp_out, text="Compute trend/amp/phase", variable=gui.var_basin_do_stats).grid(row=2, column=1, sticky="w", padx=4)
    ttk.Checkbutton(grp_out, text="Compute spatial grids (mean/trend/amp/phase)", variable=gui.var_basin_do_grid).grid(row=2, column=2, sticky="w", padx=4)

    gui.var_basin_save_ts_txt = tk.BooleanVar(value=True)
    gui.var_basin_save_ts_mat = tk.BooleanVar(value=False)
    gui.var_basin_save_grid_txt = tk.BooleanVar(value=False)
    gui.var_basin_save_grid_mat = tk.BooleanVar(value=True)
    ttk.Checkbutton(grp_out, text="Save TS TXT", variable=gui.var_basin_save_ts_txt).grid(row=3, column=0, sticky="w", padx=4)
    ttk.Checkbutton(grp_out, text="Save TS MAT", variable=gui.var_basin_save_ts_mat).grid(row=3, column=1, sticky="w", padx=4)
    ttk.Checkbutton(grp_out, text="Save Grid TXT", variable=gui.var_basin_save_grid_txt).grid(row=3, column=2, sticky="w", padx=4)
    ttk.Checkbutton(grp_out, text="Save Grid MAT", variable=gui.var_basin_save_grid_mat).grid(row=3, column=3, sticky="w", padx=4)
