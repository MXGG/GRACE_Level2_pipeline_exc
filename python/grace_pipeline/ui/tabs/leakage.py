"""Leakage tab builder."""

import tkinter as tk
from tkinter import ttk


def build_leakage_tab(gui, parent):
    leak_cfg = getattr(gui.default_cfg, "leakage", {}) if hasattr(gui.default_cfg, "leakage") else {}

    grp = ttk.LabelFrame(parent, text="Leakage Reduction/Correction", padding=10)
    grp.pack(fill=tk.X, pady=6)
    grp.columnconfigure(1, weight=1)

    gui.var_lrc_enable = tk.BooleanVar(value=bool(leak_cfg.get("enable", False)))
    ttk.Checkbutton(grp, text="Enable Leakage Reduction/Correction", variable=gui.var_lrc_enable).grid(row=0, column=0, sticky="w", pady=2)

    ttk.Label(grp, text="Scope:").grid(row=0, column=2, sticky="e")
    gui.var_lrc_scope = tk.StringVar(value=str(leak_cfg.get("scope", "global")).lower())
    ttk.Combobox(grp, textvariable=gui.var_lrc_scope, values=["global", "regional"], width=10, state="readonly").grid(row=0, column=3, sticky="w")

    ttk.Label(grp, text="Method:").grid(row=0, column=4, sticky="e")
    gui.var_lrc_method = tk.StringVar(value=str(leak_cfg.get("method", "SF")).upper())
    ttk.Combobox(grp, textvariable=gui.var_lrc_method, values=["FM", "SF"], width=8, state="readonly").grid(row=0, column=5, sticky="w")

    gui.var_lrc_input = tk.StringVar(value=gui._normpath(leak_cfg.get("input", "")))
    ttk.Label(grp, text="Input data (mat/txt/nc/hdf):").grid(row=1, column=0, sticky="w")
    ttk.Entry(grp, textvariable=gui.var_lrc_input).grid(row=1, column=1, columnspan=4, padx=5, pady=2, sticky="we")
    ttk.Button(
        grp,
        text="Browse...",
        command=lambda: gui._browse_file(
            gui.var_lrc_input,
            filetypes=[("Data files", "*.mat;*.txt;*.nc;*.nc4;*.cdf;*.hdf;*.h5;*.hdf5;*.he5"), ("All", "*.*")],
        ),
    ).grid(row=1, column=5, padx=4)
    ttk.Button(grp, text="Load Info", command=gui.load_leakage_info).grid(row=1, column=6, padx=4)

    gui.var_lrc_output = tk.StringVar(value=gui._normpath(leak_cfg.get("output", "")))
    ttk.Label(grp, text="Output path (file/dir):").grid(row=2, column=0, sticky="w")
    ttk.Entry(grp, textvariable=gui.var_lrc_output).grid(row=2, column=1, columnspan=4, padx=5, pady=2, sticky="we")
    ttk.Button(grp, text="Browse...", command=lambda: gui._browse_dir(gui.var_lrc_output)).grid(row=2, column=5, padx=4)

    gui.var_lrc_fmt = tk.StringVar(value=str(leak_cfg.get("format", "mat")).lower())
    ttk.Label(grp, text="Output format:").grid(row=2, column=6, sticky="e")
    ttk.Combobox(grp, textvariable=gui.var_lrc_fmt, values=["mat", "txt"], width=8, state="readonly").grid(row=2, column=7, sticky="w")

    gui.var_lrc_boundary = tk.StringVar(value=gui._normpath(leak_cfg.get("boundary_file", "")))
    gui._lrc_boundary_label = ttk.Label(grp, text="Boundary (regional):")
    gui._lrc_boundary_label.grid(row=3, column=0, sticky="w")
    gui._lrc_boundary_entry = ttk.Entry(grp, textvariable=gui.var_lrc_boundary)
    gui._lrc_boundary_entry.grid(row=3, column=1, columnspan=4, padx=5, pady=2, sticky="we")
    gui._lrc_boundary_btn = ttk.Button(
        grp,
        text="Browse...",
        command=lambda: gui._browse_file(gui.var_lrc_boundary, filetypes=[("Boundary files", "*.shp;*.txt;*.bln"), ("All", "*.*")]),
    )
    gui._lrc_boundary_btn.grid(row=3, column=5, padx=4)

    gui.var_lrc_info = tk.StringVar(value="No data loaded")
    ttk.Label(grp, textvariable=gui.var_lrc_info, foreground="gray").grid(row=4, column=1, columnspan=6, sticky="w")

    gui.var_lrc_matlab = tk.StringVar(value=gui._normpath(leak_cfg.get("matlab", "matlab")))
    gui.var_lrc_script_global = tk.StringVar(value=gui._normpath(leak_cfg.get("script_global", "")))
    gui.var_lrc_script_region = tk.StringVar(value=gui._normpath(leak_cfg.get("script_region", "")))
    gui.var_lrc_toolbox = tk.StringVar(value=gui._normpath(leak_cfg.get("sf_toolbox", "")))

    gui._lrc_operator_group = ttk.LabelFrame(parent, text="Forward Operator (for FM and SF Auto)", padding=10)
    gui._lrc_operator_group.pack(fill=tk.X, pady=6)
    gui._lrc_operator_group.columnconfigure(1, weight=1)

    gui.var_lrc_sf_method = tk.StringVar(value=str(leak_cfg.get("sf_method", "Auto")))
    ttk.Label(gui._lrc_operator_group, text="Operator:").grid(row=0, column=0, sticky="w")
    ttk.Combobox(
        gui._lrc_operator_group,
        textvariable=gui.var_lrc_sf_method,
        values=["Auto", "Gaussian", "P4M6", "Gaussian_Decorrelation", "Fan", "Fan_Decorrelation", "DDK4", "HSAF"],
        width=24,
        state="readonly",
    ).grid(row=0, column=1, sticky="w", padx=5)
    gui._lrc_operator_hint = tk.StringVar(value="Operator hint: Auto")
    ttk.Label(gui._lrc_operator_group, textvariable=gui._lrc_operator_hint, foreground="gray").grid(row=0, column=2, sticky="w", padx=10)

    gui._lrc_operator_param_wrap = ttk.Frame(gui._lrc_operator_group)
    gui._lrc_operator_param_wrap.grid(row=1, column=0, columnspan=4, sticky="we", pady=(8, 0))

    gui.var_lrc_sf_grid = tk.DoubleVar(value=float(leak_cfg.get("sf_grid_interval", 0.5)))
    gui.var_lrc_sf_gauss = tk.DoubleVar(value=float(leak_cfg.get("sf_gauss_km", getattr(gui.default_cfg.filter.gaussian, "radius_km", 300))))
    gui.var_lrc_sf_fan_r1 = tk.DoubleVar(value=float(leak_cfg.get("sf_fan_r1_km", gui.default_cfg.filter.fan.get("radius1_km", 300))))
    gui.var_lrc_sf_fan_r2 = tk.DoubleVar(value=float(leak_cfg.get("sf_fan_r2_km", gui.default_cfg.filter.fan.get("radius2_km", 300))))
    gui.var_lrc_sf_ddk = tk.StringVar(value=str(leak_cfg.get("sf_ddk_type", "DDK4")))
    gui.var_lrc_sf_p4_deg = tk.IntVar(value=int(leak_cfg.get("sf_p4_deg", gui.default_cfg.filter.p4m6.poly_deg)))
    gui.var_lrc_sf_p4_m = tk.IntVar(value=int(leak_cfg.get("sf_p4_m", gui.default_cfg.filter.p4m6.m_start)))
    gui.var_lrc_sf_hsa_window = tk.IntVar(value=int(leak_cfg.get("sf_hsa_window", 60)))
    gui.var_lrc_sf_hsa_p = tk.IntVar(value=int(leak_cfg.get("sf_hsa_p", 20)))
    gui.var_lrc_sf_hsa_order = tk.IntVar(value=int(leak_cfg.get("sf_hsa_order", 6)))
    gui.var_lrc_sf_hsa_buffer = tk.IntVar(value=int(leak_cfg.get("sf_hsa_buffer", 10)))
    gui.var_lrc_sf_hsa_ts = tk.IntVar(value=int(leak_cfg.get("sf_hsa_ts", 1)))

    gui._lrc_param_frames = {}

    f_gauss = ttk.Frame(gui._lrc_operator_param_wrap)
    ttk.Label(f_gauss, text="Gaussian radius (km):").pack(side=tk.LEFT)
    ttk.Entry(f_gauss, textvariable=gui.var_lrc_sf_gauss, width=10).pack(side=tk.LEFT, padx=6)
    gui._lrc_param_frames["GAUSSIAN"] = f_gauss
    gui._lrc_param_frames["GAUSSIAN_DECORRELATION"] = f_gauss

    f_fan = ttk.Frame(gui._lrc_operator_param_wrap)
    ttk.Label(f_fan, text="Fan r1/r2 (km):").pack(side=tk.LEFT)
    ttk.Entry(f_fan, textvariable=gui.var_lrc_sf_fan_r1, width=8).pack(side=tk.LEFT, padx=4)
    ttk.Entry(f_fan, textvariable=gui.var_lrc_sf_fan_r2, width=8).pack(side=tk.LEFT, padx=4)
    gui._lrc_param_frames["FAN"] = f_fan
    gui._lrc_param_frames["FAN_DECORRELATION"] = f_fan

    f_ddk = ttk.Frame(gui._lrc_operator_param_wrap)
    ttk.Label(f_ddk, text="DDK type:").pack(side=tk.LEFT)
    ttk.Combobox(f_ddk, textvariable=gui.var_lrc_sf_ddk, values=[f"DDK{i}" for i in range(1, 9)], width=10, state="readonly").pack(side=tk.LEFT, padx=6)
    gui._lrc_param_frames["DDK4"] = f_ddk

    f_p4 = ttk.Frame(gui._lrc_operator_param_wrap)
    ttk.Label(f_p4, text="P4M6 degree/order-start:").pack(side=tk.LEFT)
    ttk.Entry(f_p4, textvariable=gui.var_lrc_sf_p4_deg, width=6).pack(side=tk.LEFT, padx=4)
    ttk.Entry(f_p4, textvariable=gui.var_lrc_sf_p4_m, width=6).pack(side=tk.LEFT, padx=4)
    gui._lrc_param_frames["P4M6"] = f_p4

    f_hsaf = ttk.Frame(gui._lrc_operator_param_wrap)
    ttk.Label(f_hsaf, text="HSAF N/P/K/J/Ts:").pack(side=tk.LEFT)
    ttk.Entry(f_hsaf, textvariable=gui.var_lrc_sf_hsa_window, width=6).pack(side=tk.LEFT, padx=2)
    ttk.Entry(f_hsaf, textvariable=gui.var_lrc_sf_hsa_p, width=6).pack(side=tk.LEFT, padx=2)
    ttk.Entry(f_hsaf, textvariable=gui.var_lrc_sf_hsa_order, width=6).pack(side=tk.LEFT, padx=2)
    ttk.Entry(f_hsaf, textvariable=gui.var_lrc_sf_hsa_buffer, width=6).pack(side=tk.LEFT, padx=2)
    ttk.Entry(f_hsaf, textvariable=gui.var_lrc_sf_hsa_ts, width=6).pack(side=tk.LEFT, padx=2)
    gui._lrc_param_frames["HSAF"] = f_hsaf

    gui._lrc_sf_group = ttk.LabelFrame(parent, text="SF Settings", padding=10)
    gui._lrc_sf_group.pack(fill=tk.X, pady=6)
    gui.var_lrc_sf_auto = tk.BooleanVar(value=bool(leak_cfg.get("sf_auto", False)))
    ttk.Checkbutton(gui._lrc_sf_group, text="Auto-compute SF (Built-in, from selected operator)", variable=gui.var_lrc_sf_auto).grid(
        row=0, column=0, sticky="w", columnspan=3
    )
    gui.var_lrc_sf = tk.DoubleVar(value=float(leak_cfg.get("sf_factor", 1.0)))
    ttk.Label(gui._lrc_sf_group, text="Manual scale factor:").grid(row=1, column=0, sticky="w")
    ttk.Entry(gui._lrc_sf_group, textvariable=gui.var_lrc_sf, width=12).grid(row=1, column=1, sticky="w", padx=6)
    ttk.Label(gui._lrc_sf_group, text="(Used when auto-compute is unchecked)", foreground="gray").grid(row=1, column=2, sticky="w")

    gui._lrc_fm_group = ttk.LabelFrame(parent, text="FM Settings", padding=10)
    gui._lrc_fm_group.pack(fill=tk.X, pady=6)
    gui.var_lrc_fm_max_iter = tk.IntVar(value=int(leak_cfg.get("fm_max_iter", 40)))
    gui.var_lrc_fm_min_iter = tk.IntVar(value=int(leak_cfg.get("fm_min_iter", 3)))
    gui.var_lrc_fm_tol = tk.DoubleVar(value=float(leak_cfg.get("fm_tol", 0.01)))
    gui.var_lrc_fm_accel = tk.DoubleVar(value=float(leak_cfg.get("fm_accel", 1.1)))
    gui.var_lrc_fm_patience = tk.IntVar(value=int(leak_cfg.get("fm_patience", 8)))
    gui.var_lrc_fm_min_improve = tk.DoubleVar(value=float(leak_cfg.get("fm_min_improve", 0.0001)))

    ttk.Label(gui._lrc_fm_group, text="max_iter/min_iter:").grid(row=0, column=0, sticky="w")
    ttk.Entry(gui._lrc_fm_group, textvariable=gui.var_lrc_fm_max_iter, width=7).grid(row=0, column=1, sticky="w", padx=3)
    ttk.Entry(gui._lrc_fm_group, textvariable=gui.var_lrc_fm_min_iter, width=7).grid(row=0, column=2, sticky="w", padx=3)
    ttk.Label(gui._lrc_fm_group, text="tol / accel:").grid(row=0, column=3, sticky="w", padx=(12, 0))
    ttk.Entry(gui._lrc_fm_group, textvariable=gui.var_lrc_fm_tol, width=8).grid(row=0, column=4, sticky="w", padx=3)
    ttk.Entry(gui._lrc_fm_group, textvariable=gui.var_lrc_fm_accel, width=8).grid(row=0, column=5, sticky="w", padx=3)
    ttk.Label(gui._lrc_fm_group, text="patience / min_improve:").grid(row=1, column=0, sticky="w")
    ttk.Entry(gui._lrc_fm_group, textvariable=gui.var_lrc_fm_patience, width=7).grid(row=1, column=1, sticky="w", padx=3)
    ttk.Entry(gui._lrc_fm_group, textvariable=gui.var_lrc_fm_min_improve, width=8).grid(row=1, column=2, sticky="w", padx=3)

    gui.var_lrc_method.trace_add("write", lambda *_: gui._refresh_lrc_layout())
    gui.var_lrc_scope.trace_add("write", lambda *_: gui._refresh_lrc_layout())
    gui.var_lrc_sf_auto.trace_add("write", lambda *_: gui._refresh_lrc_layout())
    gui.var_lrc_sf_method.trace_add("write", lambda *_: gui._refresh_lrc_operator_params())
    gui._refresh_lrc_layout()
