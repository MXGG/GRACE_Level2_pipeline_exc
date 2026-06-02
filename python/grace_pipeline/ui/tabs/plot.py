"""Plot tab builder."""

import tkinter as tk
from tkinter import ttk


def build_plot_tab(gui, parent):
    """Build the plot/preview tab."""
    grp_plot = ttk.LabelFrame(parent, text="Plot Data (mat/txt/nc/hdf)", padding=10)
    grp_plot.pack(fill=tk.X, pady=5)
    grp_plot.columnconfigure(1, weight=1)

    gui.var_stack_file = tk.StringVar()
    ttk.Label(grp_plot, text="Data file:").grid(row=0, column=0, sticky="w")
    ttk.Entry(grp_plot, textvariable=gui.var_stack_file, width=46).grid(row=0, column=1, padx=5, pady=2, sticky="we")
    ttk.Button(
        grp_plot,
        text="Browse...",
        command=lambda: gui._browse_file(
            gui.var_stack_file,
            filetypes=[("Data files", "*.mat;*.txt;*.nc;*.nc4;*.cdf;*.hdf;*.h5;*.hdf5;*.he5"), ("All files", "*.*")],
        ),
    ).grid(row=0, column=2)
    ttk.Button(grp_plot, text="Read Info", command=gui.load_stack_info).grid(row=0, column=3, padx=4)

    ttk.Label(grp_plot, text="Data variable:").grid(row=1, column=0, sticky="w")
    gui.var_stack_data_var = tk.StringVar(value="")
    gui.cmb_stack_var = ttk.Combobox(grp_plot, textvariable=gui.var_stack_data_var, values=[], width=22, state="readonly")
    gui.cmb_stack_var.grid(row=1, column=1, sticky="w", padx=5, pady=2)
    gui.cmb_stack_var.bind("<<ComboboxSelected>>", lambda _e: gui._on_stack_var_change())
    gui.cmb_stack_var.configure(state="disabled")

    gui.var_stack_info = tk.StringVar(value="No stack loaded")
    ttk.Label(grp_plot, textvariable=gui.var_stack_info, foreground="gray").grid(row=2, column=1, sticky="w")

    ttk.Label(grp_plot, text="Time index (0-based):").grid(row=3, column=0, sticky="w")
    gui.var_time_idx = tk.IntVar(value=0)
    ttk.Spinbox(grp_plot, from_=0, to=9999, textvariable=gui.var_time_idx, width=8).grid(row=3, column=1, sticky="w", padx=5)

    grp_region = ttk.LabelFrame(parent, text="Region Crop (optional)", padding=10)
    grp_region.pack(fill=tk.X, pady=5)
    grp_region.columnconfigure(1, weight=1)
    gui.var_r_lon_min = tk.DoubleVar(value=-180.0)
    gui.var_r_lon_max = tk.DoubleVar(value=180.0)
    gui.var_r_lat_min = tk.DoubleVar(value=-90.0)
    gui.var_r_lat_max = tk.DoubleVar(value=90.0)
    gui.var_plot_use_region = tk.BooleanVar(value=False)
    ttk.Checkbutton(grp_region, text="Use region crop", variable=gui.var_plot_use_region).grid(row=0, column=0, sticky="w", padx=2, pady=2, columnspan=2)

    ttk.Label(grp_region, text="Lon min/max:").grid(row=1, column=0, sticky="w")
    ttk.Entry(grp_region, textvariable=gui.var_r_lon_min, width=8).grid(row=1, column=1, padx=2)
    ttk.Entry(grp_region, textvariable=gui.var_r_lon_max, width=8).grid(row=1, column=2, padx=2)
    ttk.Label(grp_region, text="Lat min/max:").grid(row=1, column=3, sticky="w", padx=6)
    ttk.Entry(grp_region, textvariable=gui.var_r_lat_min, width=8).grid(row=1, column=4, padx=2)
    ttk.Entry(grp_region, textvariable=gui.var_r_lat_max, width=8).grid(row=1, column=5, padx=2)

    grp_plot_opts = ttk.LabelFrame(parent, text="Plot Options", padding=10)
    grp_plot_opts.pack(fill=tk.X, pady=5)
    grp_plot_opts.columnconfigure(1, weight=1)
    ttk.Label(grp_plot_opts, text="Projection:").grid(row=0, column=0, sticky="w")
    gui.var_proj = tk.StringVar(value="Robinson")
    ttk.Combobox(
        grp_plot_opts,
        textvariable=gui.var_proj,
        values=[
            "Robinson", "Mollweide", "EqualEarth", "WinkelTripel", "EckertIV",
            "PlateCarree", "Equirectangular", "Sinusoidal", "Miller", "Mercator",
            "Orthographic", "AzimuthalEquidistant", "Stereographic",
            "LambertConformal", "AlbersEqualArea",
        ],
        width=14,
        state="readonly",
    ).grid(row=0, column=1, padx=5)
    ttk.Label(grp_plot_opts, text="Colormap:").grid(row=0, column=2, sticky="w")
    gui.var_cmap = tk.StringVar(value="RdBu_r")
    ttk.Combobox(
        grp_plot_opts,
        textvariable=gui.var_cmap,
        values=["RdBu_r", "Spectral", "seismic", "coolwarm", "BrBG", "PiYG", "jet", "viridis", "turbo", "plasma", "magma", "cividis"],
        width=10,
        state="readonly",
    ).grid(row=0, column=3, padx=5)
    ttk.Label(grp_plot_opts, text="Caxis min/max:").grid(row=1, column=0, sticky="w")
    gui.var_cmin = tk.StringVar(value="")
    gui.var_cmax = tk.StringVar(value="")
    ttk.Entry(grp_plot_opts, textvariable=gui.var_cmin, width=8).grid(row=1, column=1, padx=5, sticky="w")
    ttk.Entry(grp_plot_opts, textvariable=gui.var_cmax, width=8).grid(row=1, column=2, padx=5, sticky="w")
    ttk.Label(grp_plot_opts, text="Coastline (.shp):").grid(row=2, column=0, sticky="w")
    gui.var_coast = tk.StringVar(value=gui._normpath(getattr(gui.default_cfg.path, "BOUNDARY", "")))
    ttk.Entry(grp_plot_opts, textvariable=gui.var_coast, width=50).grid(row=2, column=1, columnspan=2, padx=5, pady=2, sticky="w")
    ttk.Button(grp_plot_opts, text="Browse...", command=lambda: gui._browse_file(gui.var_coast)).grid(row=2, column=3, padx=5)

    ttk.Label(grp_plot_opts, text="Boundary (.shp/.txt/.bln):").grid(row=3, column=0, sticky="w")
    gui.var_plot_boundary = tk.StringVar(value="")
    ttk.Entry(grp_plot_opts, textvariable=gui.var_plot_boundary, width=40).grid(row=3, column=1, columnspan=2, padx=5, pady=2, sticky="we")
    ttk.Button(
        grp_plot_opts,
        text="Browse...",
        command=lambda: gui._browse_file(
            gui.var_plot_boundary,
            filetypes=[("Boundary files", "*.shp;*.txt;*.bln"), ("All files", "*.*")],
        ),
    ).grid(row=3, column=3, padx=5)
    gui.var_plot_auto_region = tk.BooleanVar(value=True)
    ttk.Checkbutton(grp_plot_opts, text="Auto region from boundary", variable=gui.var_plot_auto_region).grid(row=3, column=4, sticky="w", padx=4)

    grp_save = ttk.LabelFrame(parent, text="Save Figure", padding=10)
    grp_save.pack(fill=tk.X, pady=5)
    ttk.Label(grp_save, text="Save path:").grid(row=0, column=0, sticky="w")
    gui.var_save_path = tk.StringVar(value="")
    ttk.Entry(grp_save, textvariable=gui.var_save_path, width=50).grid(row=0, column=1, padx=5, sticky="we")
    ttk.Button(grp_save, text="Browse...", command=gui._browse_save_path).grid(row=0, column=2, padx=5)
    ttk.Label(grp_save, text="DPI:").grid(row=0, column=3, sticky="w")
    gui.var_save_dpi = tk.IntVar(value=300)
    ttk.Entry(grp_save, textvariable=gui.var_save_dpi, width=6).grid(row=0, column=4, padx=4)
    ttk.Label(grp_save, text="Format:").grid(row=0, column=5, sticky="w")
    gui.var_save_fmt = tk.StringVar(value="png")
    ttk.Combobox(grp_save, textvariable=gui.var_save_fmt, values=["png", "jpg", "tif", "pdf"], width=6, state="readonly").grid(row=0, column=6, padx=4)
    ttk.Button(grp_save, text="Save Plot", command=gui.save_plot).grid(row=0, column=7, padx=6)
    grp_save.columnconfigure(1, weight=1)

    grp_btn = ttk.Frame(parent)
    grp_btn.pack(fill=tk.X, pady=5)
    ttk.Button(grp_btn, text="Plot", command=gui.plot_stack).pack(side=tk.LEFT)
