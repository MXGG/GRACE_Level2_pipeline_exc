"""Filters tab builder."""

import tkinter as tk
from tkinter import ttk


def build_filters_tab(gui, parent):
    """Build the inversion and filters tab."""
    grp_inv = ttk.LabelFrame(parent, text="Inversion", padding=10)
    grp_inv.pack(fill=tk.X, pady=5)

    ttk.Label(grp_inv, text="Max Degree (Lmax):").pack(side=tk.LEFT)
    gui.var_lmax = tk.IntVar(value=gui.default_cfg.inversion.Lmax)
    ttk.Entry(grp_inv, textvariable=gui.var_lmax, width=8).pack(side=tk.LEFT, padx=5)

    gui.var_demean = tk.BooleanVar(value=gui.default_cfg.inversion.remove_mean)
    ttk.Checkbutton(grp_inv, text="Remove Mean Field", variable=gui.var_demean).pack(side=tk.LEFT, padx=15)
    ttk.Label(grp_inv, text="Baseline (YYYY-MM):").pack(side=tk.LEFT, padx=8)
    gui.var_mean_start = tk.StringVar(value=getattr(gui.default_cfg.inversion, "mean_start_ym", "") or "")
    gui.var_mean_end = tk.StringVar(value=getattr(gui.default_cfg.inversion, "mean_end_ym", "") or "")
    ttk.Entry(grp_inv, textvariable=gui.var_mean_start, width=10).pack(side=tk.LEFT, padx=2)
    ttk.Label(grp_inv, text="~").pack(side=tk.LEFT)
    ttk.Entry(grp_inv, textvariable=gui.var_mean_end, width=10).pack(side=tk.LEFT, padx=2)

    grp_filt = ttk.LabelFrame(parent, text="滤波方法", padding=10)
    grp_filt.pack(fill=tk.BOTH, expand=True, pady=5)

    f_gauss = ttk.Frame(grp_filt)
    f_gauss.pack(fill=tk.X, pady=2)
    gui.var_gauss = tk.BooleanVar(value=gui.default_cfg.filter.gaussian.enable)
    ttk.Checkbutton(f_gauss, text="Gaussian", variable=gui.var_gauss, width=15).pack(side=tk.LEFT)
    ttk.Label(f_gauss, text="半径 (km):").pack(side=tk.LEFT)
    gui.var_gauss_rad = tk.DoubleVar(value=gui.default_cfg.filter.gaussian.radius_km)
    ttk.Entry(f_gauss, textvariable=gui.var_gauss_rad, width=8).pack(side=tk.LEFT, padx=5)

    f_p4m6 = ttk.Frame(grp_filt)
    f_p4m6.pack(fill=tk.X, pady=2)
    gui.var_p4m6 = tk.BooleanVar(value=gui.default_cfg.filter.p4m6.enable)
    ttk.Checkbutton(f_p4m6, text="P4M6", variable=gui.var_p4m6, width=15).pack(side=tk.LEFT)
    ttk.Label(f_p4m6, text="P:").pack(side=tk.LEFT, padx=4)
    gui.var_p4_deg = tk.IntVar(value=gui.default_cfg.filter.p4m6.poly_deg)
    ttk.Entry(f_p4m6, textvariable=gui.var_p4_deg, width=6).pack(side=tk.LEFT, padx=2)
    ttk.Label(f_p4m6, text="M:").pack(side=tk.LEFT, padx=4)
    gui.var_p4_m = tk.IntVar(value=gui.default_cfg.filter.p4m6.m_start)
    ttk.Entry(f_p4m6, textvariable=gui.var_p4_m, width=6).pack(side=tk.LEFT, padx=2)

    f_ddk = ttk.Frame(grp_filt)
    f_ddk.pack(fill=tk.X, pady=2)
    gui.var_ddk_enable = tk.BooleanVar(value=gui.default_cfg.filter.ddk.enable)
    ttk.Checkbutton(f_ddk, text="DDK", variable=gui.var_ddk_enable, width=15).pack(side=tk.LEFT)
    ttk.Label(f_ddk, text="类型:").pack(side=tk.LEFT)
    gui.var_ddk_type = tk.StringVar(value=gui.default_cfg.filter.ddk.type)
    ttk.Combobox(f_ddk, textvariable=gui.var_ddk_type, values=[f"DDK{i}" for i in range(1, 9)], width=8).pack(side=tk.LEFT, padx=5)

    f_hsaf = ttk.Frame(grp_filt)
    f_hsaf.pack(fill=tk.X, pady=2)
    gui.var_hsaf = tk.BooleanVar(value=gui.default_cfg.filter.hankel.enable)
    ttk.Checkbutton(f_hsaf, text="HSAF", variable=gui.var_hsaf, width=15).pack(side=tk.LEFT)
    ttk.Label(f_hsaf, text="策略:").pack(side=tk.LEFT, padx=6)
    gui.var_hsaf_variant = tk.StringVar(value=getattr(gui.default_cfg.filter.hankel, "variant", "global"))
    ttk.Radiobutton(f_hsaf, text="全局", variable=gui.var_hsaf_variant, value="global").pack(side=tk.LEFT)
    ttk.Radiobutton(f_hsaf, text="自适应", variable=gui.var_hsaf_variant, value="adaptive").pack(side=tk.LEFT, padx=4)
    ttk.Label(f_hsaf, text="输入:").pack(side=tk.LEFT, padx=6)
    gui.var_hsaf_input = tk.StringVar(value=getattr(gui.default_cfg.filter, "pre_hankel_input", "P4M6"))
    ttk.Combobox(f_hsaf, textvariable=gui.var_hsaf_input, values=["RAW", "P4M6"], width=6, state="readonly").pack(side=tk.LEFT, padx=2)
    ttk.Label(f_hsaf, text="模式:").pack(side=tk.LEFT, padx=6)
    gui.var_hsaf_mode = tk.StringVar(value="ola")
    ttk.Entry(f_hsaf, textvariable=gui.var_hsaf_mode, width=8, state="disabled").pack(side=tk.LEFT)

    f_fan = ttk.Frame(grp_filt)
    f_fan.pack(fill=tk.X, pady=2)
    gui.var_fan = tk.BooleanVar(value=gui.default_cfg.filter.fan.get("enable", False))
    ttk.Checkbutton(f_fan, text="FAN", variable=gui.var_fan, width=15).pack(side=tk.LEFT)
    ttk.Label(f_fan, text="半径 1 (km):").pack(side=tk.LEFT, padx=4)
    gui.var_fan_r1 = tk.DoubleVar(value=gui.default_cfg.filter.fan.get("radius1_km", 300))
    ttk.Entry(f_fan, textvariable=gui.var_fan_r1, width=8).pack(side=tk.LEFT, padx=2)
    ttk.Label(f_fan, text="半径 2 (km):").pack(side=tk.LEFT, padx=4)
    gui.var_fan_r2 = tk.DoubleVar(value=gui.default_cfg.filter.fan.get("radius2_km", 300))
    ttk.Entry(f_fan, textvariable=gui.var_fan_r2, width=8).pack(side=tk.LEFT, padx=2)

    grp_hsaf = ttk.LabelFrame(parent, text="HSAF 参数", padding=10)
    grp_hsaf.pack(fill=tk.X, pady=5)
    params = getattr(gui.default_cfg.filter.hankel, "params", {}) or {}
    gui.var_hsaf_N = tk.IntVar(value=params.get("N", 30))
    gui.var_hsaf_P = tk.IntVar(value=params.get("P", 10))
    gui.var_hsaf_K = tk.IntVar(value=params.get("K", 6))
    gui.var_hsaf_J = tk.IntVar(value=params.get("J", 1))
    ttk.Label(grp_hsaf, text="N").grid(row=0, column=0, sticky="w")
    eN = ttk.Entry(grp_hsaf, textvariable=gui.var_hsaf_N, width=6)
    eN.grid(row=0, column=1, padx=4)
    ttk.Label(grp_hsaf, text="P").grid(row=0, column=2, sticky="w")
    eP = ttk.Entry(grp_hsaf, textvariable=gui.var_hsaf_P, width=6)
    eP.grid(row=0, column=3, padx=4)
    ttk.Label(grp_hsaf, text="K").grid(row=0, column=4, sticky="w")
    eK = ttk.Entry(grp_hsaf, textvariable=gui.var_hsaf_K, width=6)
    eK.grid(row=0, column=5, padx=4)
    ttk.Label(grp_hsaf, text="J").grid(row=0, column=6, sticky="w")
    eJ = ttk.Entry(grp_hsaf, textvariable=gui.var_hsaf_J, width=6)
    eJ.grid(row=0, column=7, padx=4)
    btn_hsaf_defaults = ttk.Button(grp_hsaf, text="加载默认值", command=gui._load_hsaf_defaults)
    btn_hsaf_defaults.grid(row=0, column=8, padx=8)
    gui._hsaf_basic_widgets = [eN, eP, eK, eJ, btn_hsaf_defaults]
    gui._register_advanced_section(grp_hsaf)

    grp_hsaf_ad = ttk.LabelFrame(parent, text="HSAF 自适应分区", padding=10)
    grp_hsaf_ad.pack(fill=tk.X, pady=5)
    headers = ["分区", "纬度下限", "纬度上限", "N", "P", "K", "J"]
    for c, h in enumerate(headers):
        ttk.Label(grp_hsaf_ad, text=h).grid(row=0, column=c, padx=4, sticky="w")
    gui._hsaf_ad_widgets = []
    gui._hsaf_ad_vars = []
    defaults = [(-90, -30), (-30, 30), (30, 90)]
    for i in range(3):
        ttk.Label(grp_hsaf_ad, text=f"{i+1}").grid(row=i + 1, column=0, padx=4, sticky="w")
        v_lat_min = tk.StringVar(value=str(defaults[i][0]))
        v_lat_max = tk.StringVar(value=str(defaults[i][1]))
        vN = tk.StringVar(value=str(gui.var_hsaf_N.get()))
        vP = tk.StringVar(value=str(gui.var_hsaf_P.get()))
        vK = tk.StringVar(value=str(gui.var_hsaf_K.get()))
        vJ = tk.StringVar(value=str(gui.var_hsaf_J.get()))
        e1 = ttk.Entry(grp_hsaf_ad, textvariable=v_lat_min, width=8)
        e2 = ttk.Entry(grp_hsaf_ad, textvariable=v_lat_max, width=8)
        e3 = ttk.Entry(grp_hsaf_ad, textvariable=vN, width=6)
        e4 = ttk.Entry(grp_hsaf_ad, textvariable=vP, width=6)
        e5 = ttk.Entry(grp_hsaf_ad, textvariable=vK, width=6)
        e6 = ttk.Entry(grp_hsaf_ad, textvariable=vJ, width=6)
        e1.grid(row=i + 1, column=1, padx=2)
        e2.grid(row=i + 1, column=2, padx=2)
        e3.grid(row=i + 1, column=3, padx=2)
        e4.grid(row=i + 1, column=4, padx=2)
        e5.grid(row=i + 1, column=5, padx=2)
        e6.grid(row=i + 1, column=6, padx=2)
        gui._hsaf_ad_widgets.extend([e1, e2, e3, e4, e5, e6])
        gui._hsaf_ad_vars.append({
            "lat_min": v_lat_min,
            "lat_max": v_lat_max,
            "N": vN,
            "P": vP,
            "K": vK,
            "J": vJ,
        })
    gui._grp_hsaf_ad = grp_hsaf_ad
    gui.var_hsaf_variant.trace_add("write", lambda *_: gui._toggle_hsaf_variant())
    gui._toggle_hsaf_variant()
    gui._register_advanced_section(grp_hsaf_ad)
