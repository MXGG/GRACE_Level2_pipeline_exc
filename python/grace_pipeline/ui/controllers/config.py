"""Configuration load/update service extracted from GUI layer."""

import copy
from pathlib import Path

from tkinter import filedialog, messagebox

from grace_pipeline.infra.config import DDKFilterConfig, load_config


def load_config_file(self, path_override=None):
    """Load configuration from JSON file."""
    f = path_override
    if f is None:
        f = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=self.cfg_dir if self.cfg_dir.exists() else Path.cwd() / "cfg",
        )
    if f:
        try:
            new_cfg = load_config(user_config=str(f))
            self.cfg = new_cfg
            try:
                self.current_cfg_path = Path(f)
            except Exception:
                self.current_cfg_path = None
            self.var_gfc.set(self._normpath(new_cfg.path.GFC))
            self.var_out.set(self._normpath(new_cfg.path.OUTPUT))
            self.var_ddk.set(self._normpath(new_cfg.filter.ddk.data_dir))
            self.var_aux.set(self._normpath(getattr(new_cfg.path, "AUX", "")))
            self.var_boundary.set(self._normpath(getattr(new_cfg.path, "BOUNDARY", "")))
            if hasattr(self, "var_coast"):
                self.var_coast.set(self._normpath(getattr(new_cfg.path, "BOUNDARY", "")))
            self.var_c20.set(self._normpath(self._get_lowdeg_file("C20", new_cfg)))
            self.var_deg1.set(self._normpath(self._get_lowdeg_file("DEGREE1", new_cfg)))
            self.var_gia.set(self._normpath(self._get_gia_file(new_cfg)))
            self.var_mascon_dir.set(self._normpath(self._get_mascon_dir(new_cfg)))
            self.var_mascon_gad.set(self._normpath(self._get_mascon_file("gad_file", new_cfg)))
            self.var_mascon_gia.set(self._normpath(self._get_mascon_file("gia_file", new_cfg)))

            self.var_auto_time.set(new_cfg.time.auto_detect_gfc)
            self.var_start.set(new_cfg.time.start_ym)
            self.var_end.set(new_cfg.time.end_ym)
            self._toggle_time_inputs()

            self.var_lon_min.set(new_cfg.grid.lon[0])
            self.var_lon_max.set(new_cfg.grid.lon[1])
            self.var_lat_min.set(new_cfg.grid.lat[0])
            self.var_lat_max.set(new_cfg.grid.lat[1])
            self.var_dlon.set(new_cfg.grid.dlon)
            self.var_dlat.set(new_cfg.grid.dlat)

            if hasattr(self, "var_save_monthly_mat"):
                self.var_save_monthly_mat.set(bool(new_cfg.io.save_monthly_mat))
            if hasattr(self, "var_save_stack_mat"):
                self.var_save_stack_mat.set(bool(new_cfg.io.save_stack_mat))
            if hasattr(self, "var_export_txt"):
                self.var_export_txt.set(bool(new_cfg.io.export_txt))
            if hasattr(self, "var_txt_format"):
                self.var_txt_format.set(getattr(new_cfg.io, "txt_format", "lonlatval"))

            self.var_parallel.set(new_cfg.parallel.enable)
            self.var_workers.set(new_cfg.parallel.n_workers)
            try:
                self.var_allow_frozen_parallel.set(getattr(new_cfg, "perf", {}).get("allow_frozen_parallel", False))
            except Exception:
                pass
            self._set_runtime_profile(getattr(new_cfg, "perf", {}).get("runtime_profile", self._infer_runtime_profile()))

            self.var_lmax.set(new_cfg.inversion.Lmax)
            self.var_demean.set(new_cfg.inversion.remove_mean)
            self.var_mean_start.set(getattr(new_cfg.inversion, "mean_start_ym", "") or "")
            self.var_mean_end.set(getattr(new_cfg.inversion, "mean_end_ym", "") or "")

            try:
                basin_cfg = new_cfg.basin if isinstance(new_cfg.basin, dict) else new_cfg.basin.__dict__
            except Exception:
                basin_cfg = {}
            if hasattr(self, "var_basin_enable"):
                self.var_basin_enable.set(bool(basin_cfg.get("analysis_enable", False)))
                self.var_basin_file.set(self._normpath(basin_cfg.get("boundary_file", "")))
                self.var_basin_name.set(basin_cfg.get("name", ""))
                self.var_basin_name_field.set(basin_cfg.get("name_field", "Name"))

            try:
                leak_cfg = new_cfg.leakage if isinstance(new_cfg.leakage, dict) else new_cfg.leakage.__dict__
            except Exception:
                leak_cfg = {}
            if hasattr(self, "var_lrc_enable"):
                self.var_lrc_enable.set(bool(leak_cfg.get("enable", False)))
                self.var_lrc_scope.set(str(leak_cfg.get("scope", "global")).lower())
                self.var_lrc_method.set(str(leak_cfg.get("method", "SF")).upper())
                self.var_lrc_sf.set(float(leak_cfg.get("sf_factor", 1.0)))
                self.var_lrc_input.set(self._normpath(leak_cfg.get("input", "")))
                self.var_lrc_output.set(self._normpath(leak_cfg.get("output", "")))
                if hasattr(self, "var_lrc_fmt"):
                    self.var_lrc_fmt.set(str(leak_cfg.get("format", "mat")).lower())
                self.var_lrc_boundary.set(self._normpath(leak_cfg.get("boundary_file", "")))
                self.var_lrc_script_global.set(self._normpath(leak_cfg.get("script_global", "")))
                self.var_lrc_script_region.set(self._normpath(leak_cfg.get("script_region", "")))
                self.var_lrc_matlab.set(self._normpath(leak_cfg.get("matlab", "matlab")))
                if hasattr(self, "var_lrc_sf_auto"):
                    self.var_lrc_sf_auto.set(bool(leak_cfg.get("sf_auto", False)))
                if hasattr(self, "var_lrc_sf_method"):
                    self.var_lrc_sf_method.set(str(leak_cfg.get("sf_method", "Auto")))
                if hasattr(self, "var_lrc_sf_gauss"):
                    self.var_lrc_sf_gauss.set(float(leak_cfg.get("sf_gauss_km", self.var_lrc_sf_gauss.get())))
                if hasattr(self, "var_lrc_sf_fan_r1"):
                    self.var_lrc_sf_fan_r1.set(float(leak_cfg.get("sf_fan_r1_km", self.var_lrc_sf_fan_r1.get())))
                if hasattr(self, "var_lrc_sf_fan_r2"):
                    self.var_lrc_sf_fan_r2.set(float(leak_cfg.get("sf_fan_r2_km", self.var_lrc_sf_fan_r2.get())))
                if hasattr(self, "var_lrc_sf_ddk"):
                    self.var_lrc_sf_ddk.set(str(leak_cfg.get("sf_ddk_type", self.var_lrc_sf_ddk.get())))
                if hasattr(self, "var_lrc_sf_p4_deg"):
                    self.var_lrc_sf_p4_deg.set(int(leak_cfg.get("sf_p4_deg", self.var_lrc_sf_p4_deg.get())))
                if hasattr(self, "var_lrc_sf_p4_m"):
                    self.var_lrc_sf_p4_m.set(int(leak_cfg.get("sf_p4_m", self.var_lrc_sf_p4_m.get())))
                if hasattr(self, "var_lrc_sf_grid"):
                    self.var_lrc_sf_grid.set(float(leak_cfg.get("sf_grid_interval", self.var_lrc_sf_grid.get())))
                if hasattr(self, "var_lrc_sf_hsa_window"):
                    self.var_lrc_sf_hsa_window.set(int(leak_cfg.get("sf_hsa_window", self.var_lrc_sf_hsa_window.get())))
                if hasattr(self, "var_lrc_sf_hsa_p"):
                    self.var_lrc_sf_hsa_p.set(int(leak_cfg.get("sf_hsa_p", self.var_lrc_sf_hsa_p.get())))
                if hasattr(self, "var_lrc_sf_hsa_order"):
                    self.var_lrc_sf_hsa_order.set(int(leak_cfg.get("sf_hsa_order", self.var_lrc_sf_hsa_order.get())))
                if hasattr(self, "var_lrc_sf_hsa_buffer"):
                    self.var_lrc_sf_hsa_buffer.set(int(leak_cfg.get("sf_hsa_buffer", self.var_lrc_sf_hsa_buffer.get())))
                if hasattr(self, "var_lrc_sf_hsa_ts"):
                    self.var_lrc_sf_hsa_ts.set(int(leak_cfg.get("sf_hsa_ts", self.var_lrc_sf_hsa_ts.get())))
                if hasattr(self, "var_lrc_toolbox"):
                    self.var_lrc_toolbox.set(self._normpath(leak_cfg.get("sf_toolbox", self.var_lrc_toolbox.get())))
                if hasattr(self, "var_lrc_fm_max_iter"):
                    self.var_lrc_fm_max_iter.set(int(leak_cfg.get("fm_max_iter", self.var_lrc_fm_max_iter.get())))
                if hasattr(self, "var_lrc_fm_min_iter"):
                    self.var_lrc_fm_min_iter.set(int(leak_cfg.get("fm_min_iter", self.var_lrc_fm_min_iter.get())))
                if hasattr(self, "var_lrc_fm_tol"):
                    self.var_lrc_fm_tol.set(float(leak_cfg.get("fm_tol", self.var_lrc_fm_tol.get())))
                if hasattr(self, "var_lrc_fm_accel"):
                    self.var_lrc_fm_accel.set(float(leak_cfg.get("fm_accel", self.var_lrc_fm_accel.get())))
                if hasattr(self, "var_lrc_fm_patience"):
                    self.var_lrc_fm_patience.set(int(leak_cfg.get("fm_patience", self.var_lrc_fm_patience.get())))
                if hasattr(self, "var_lrc_fm_min_improve"):
                    self.var_lrc_fm_min_improve.set(float(leak_cfg.get("fm_min_improve", self.var_lrc_fm_min_improve.get())))
                if hasattr(self, "var_lrc_fm_autocap_hsaf_iter"):
                    self.var_lrc_fm_autocap_hsaf_iter.set(
                        bool(leak_cfg.get("fm_autocap_hsaf_iter", self.var_lrc_fm_autocap_hsaf_iter.get()))
                    )
                if hasattr(self, "var_lrc_fm_hsaf_iter_cap"):
                    self.var_lrc_fm_hsaf_iter_cap.set(int(leak_cfg.get("fm_hsaf_iter_cap", self.var_lrc_fm_hsaf_iter_cap.get())))
                if hasattr(self, "var_lrc_fm_allow_hsaf_parallel"):
                    self.var_lrc_fm_allow_hsaf_parallel.set(
                        bool(leak_cfg.get("fm_allow_hsaf_parallel", self.var_lrc_fm_allow_hsaf_parallel.get()))
                    )
                if hasattr(self, "var_lrc_fm_hsaf_outer_workers_cap"):
                    self.var_lrc_fm_hsaf_outer_workers_cap.set(
                        int(leak_cfg.get("fm_hsaf_outer_workers_cap", self.var_lrc_fm_hsaf_outer_workers_cap.get()))
                    )
                if hasattr(self, "var_lrc_fm_hsaf_inner_workers"):
                    self.var_lrc_fm_hsaf_inner_workers.set(
                        int(leak_cfg.get("fm_hsaf_inner_workers", self.var_lrc_fm_hsaf_inner_workers.get()))
                    )
                if hasattr(self, "_refresh_lrc_layout"):
                    self._refresh_lrc_layout()

            self.var_gauss.set(new_cfg.filter.gaussian.enable)
            self.var_gauss_rad.set(new_cfg.filter.gaussian.radius_km)

            self.var_p4m6.set(new_cfg.filter.p4m6.enable)
            self.var_p4_deg.set(new_cfg.filter.p4m6.poly_deg)
            self.var_p4_m.set(new_cfg.filter.p4m6.m_start)

            self.var_ddk_enable.set(new_cfg.filter.ddk.enable)
            self.var_ddk_type.set(new_cfg.filter.ddk.type)

            self.var_hsaf.set(new_cfg.filter.hankel.enable)
            self.var_hsaf_variant.set(getattr(new_cfg.filter.hankel, "variant", "global"))
            if hasattr(self, "var_hsaf_input"):
                self.var_hsaf_input.set(getattr(new_cfg.filter, "pre_hankel_input", "P4M6"))
            self.var_hsaf_mode.set("ola")
            self.var_fan.set(new_cfg.filter.fan.get("enable", False))
            self.var_fan_r1.set(new_cfg.filter.fan.get("radius1_km", 300))
            self.var_fan_r2.set(new_cfg.filter.fan.get("radius2_km", 300))

            params = getattr(new_cfg.filter.hankel, "params", {}) or {}
            self.var_hsaf_N.set(params.get("N", 30))
            self.var_hsaf_P.set(params.get("P", 10))
            self.var_hsaf_K.set(params.get("K", 6))
            self.var_hsaf_J.set(params.get("J", 1))
            try:
                ad = getattr(new_cfg.filter.hankel, "adaptive", [])
                self._apply_adaptive_zones(ad)
            except Exception:
                pass

            try:
                self._show_step("common")
                self._refresh_summary()
            except Exception:
                pass
            self._set_config_ready(True)
            messagebox.showinfo("Config Loaded", f"Loaded configuration from {Path(f).name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load config: {e}")


def _update_config(self):
    """Map GUI variables back to config object."""
    self.cfg.path.GFC = self._normpath(self.var_gfc.get())
    self.cfg.path.OUTPUT = self._normpath(self.var_out.get())
    if hasattr(self.cfg.path, "AUX"):
        self.cfg.path.AUX = self._normpath(self.var_aux.get())
    if hasattr(self.cfg.path, "BOUNDARY"):
        self.cfg.path.BOUNDARY = self._normpath(self.var_boundary.get())

    if not hasattr(self.cfg.filter, "ddk"):
        self.cfg.filter.ddk = DDKFilterConfig(enable=False, type="DDK4", data_dir="")

    ddk_path = self._normpath(self.var_ddk.get())
    if not ddk_path:
        ddk_path = self._normpath(getattr(self.default_cfg.filter.ddk, "data_dir", ""))
    self.cfg.filter.ddk.data_dir = ddk_path

    if not isinstance(self.cfg.inversion.lowdeg, dict):
        self.cfg.inversion.lowdeg = {}
    self.cfg.inversion.lowdeg["files"] = {
        "C20": self._normpath(self.var_c20.get()),
        "DEGREE1": self._normpath(self.var_deg1.get()),
    }
    if not isinstance(self.cfg.inversion.gia, dict):
        self.cfg.inversion.gia = {}
    self.cfg.inversion.gia["file"] = self._normpath(self.var_gia.get())

    if not isinstance(self.cfg.reference, dict):
        self.cfg.reference = {}
    self.cfg.reference["mascon_dir"] = self._normpath(self.var_mascon_dir.get())
    self.cfg.reference.setdefault("mascon_undo", {})
    if isinstance(self.cfg.reference.get("mascon_undo"), dict):
        self.cfg.reference["mascon_undo"]["gad_file"] = self._normpath(self.var_mascon_gad.get())
        self.cfg.reference["mascon_undo"]["gia_file"] = self._normpath(self.var_mascon_gia.get())

    self.cfg.time.auto_detect_gfc = self.var_auto_time.get()
    if not self.var_auto_time.get():
        self.cfg.time.start_ym = self.var_start.get()
        self.cfg.time.end_ym = self.var_end.get()

    self.cfg.parallel.enable = self.var_parallel.get()
    self.cfg.parallel.n_workers = self.var_workers.get()

    self.cfg.inversion.Lmax = self.var_lmax.get()
    self.cfg.inversion.remove_mean = self.var_demean.get()
    self.cfg.inversion.mean_start_ym = self.var_mean_start.get().strip()
    self.cfg.inversion.mean_end_ym = self.var_mean_end.get().strip()

    self.cfg.grid.lon = (self.var_lon_min.get(), self.var_lon_max.get())
    self.cfg.grid.lat = (self.var_lat_min.get(), self.var_lat_max.get())
    self.cfg.grid.dlon = self.var_dlon.get()
    self.cfg.grid.dlat = self.var_dlat.get()

    try:
        self.cfg.io.save_monthly_mat = bool(self.var_save_monthly_mat.get())
        self.cfg.io.save_stack_mat = bool(self.var_save_stack_mat.get())
        self.cfg.io.export_txt = bool(self.var_export_txt.get())
        self.cfg.io.txt_format = self.var_txt_format.get().strip() or "lonlatval"
    except Exception:
        pass

    self.cfg.filter.gaussian.enable = self.var_gauss.get()
    self.cfg.filter.gaussian.radius_km = self.var_gauss_rad.get()
    self.cfg.filter.p4m6.enable = self.var_p4m6.get()
    self.cfg.filter.p4m6.poly_deg = self.var_p4_deg.get()
    self.cfg.filter.p4m6.m_start = self.var_p4_m.get()
    self.cfg.filter.ddk.enable = self.var_ddk_enable.get()
    self.cfg.filter.ddk.type = self.var_ddk_type.get()
    self.cfg.filter.hankel.enable = self.var_hsaf.get()
    self.cfg.filter.hankel.variant = self.var_hsaf_variant.get()
    self.cfg.filter.hankel.mode = self.var_hsaf_mode.get() or "ola"
    if hasattr(self, "var_hsaf_input"):
        self.cfg.filter.pre_hankel_input = self.var_hsaf_input.get().strip() or "P4M6"
    if not isinstance(self.cfg.filter.fan, dict):
        self.cfg.filter.fan = {}
    self.cfg.filter.fan["enable"] = self.var_fan.get()
    self.cfg.filter.fan["radius1_km"] = self.var_fan_r1.get()
    self.cfg.filter.fan["radius2_km"] = self.var_fan_r2.get()
    self.cfg.filter.hankel.params = {
        "N": self.var_hsaf_N.get(),
        "P": self.var_hsaf_P.get(),
        "K": self.var_hsaf_K.get(),
        "J": self.var_hsaf_J.get(),
    }
    if self.cfg.filter.hankel.variant == "adaptive":
        zones = []
        for v in getattr(self, "_hsaf_ad_vars", []):
            lat_min = v["lat_min"].get().strip()
            lat_max = v["lat_max"].get().strip()
            if not lat_min or not lat_max:
                continue
            try:
                lat_min_f = float(lat_min)
                lat_max_f = float(lat_max)
            except Exception:
                raise ValueError("Invalid adaptive lat range.")
            params = {}
            try:
                params["N"] = int(float(v["N"].get()))
                params["P"] = int(float(v["P"].get()))
                params["K"] = int(float(v["K"].get()))
                params["J"] = int(float(v["J"].get()))
            except Exception:
                raise ValueError("Invalid adaptive parameters (N/P/K/J).")
            zones.append({"lat_range": [lat_min_f, lat_max_f], "params": params})
        self.cfg.filter.hankel.adaptive = zones
    else:
        self.cfg.filter.hankel.adaptive = []

    if not isinstance(self.cfg.basin, dict):
        self.cfg.basin = {}
    self.cfg.basin["analysis_enable"] = bool(self.var_basin_enable.get())
    self.cfg.basin["boundary_file"] = self._normpath(self.var_basin_file.get())
    self.cfg.basin["name"] = self.var_basin_name.get().strip()
    self.cfg.basin["name_field"] = self.var_basin_name_field.get().strip() or "Name"

    if not isinstance(self.cfg.leakage, dict):
        self.cfg.leakage = {}
    self.cfg.leakage["enable"] = bool(self.var_lrc_enable.get()) if hasattr(self, "var_lrc_enable") else False
    self.cfg.leakage["scope"] = str(self.var_lrc_scope.get()).lower() if hasattr(self, "var_lrc_scope") else "global"
    self.cfg.leakage["method"] = str(self.var_lrc_method.get()).upper() if hasattr(self, "var_lrc_method") else "SF"

    def _safe_float(var, default):
        try:
            return float(var.get())
        except Exception:
            return float(default)

    def _safe_int(var, default):
        try:
            return int(float(var.get()))
        except Exception:
            return int(default)

    self.cfg.leakage["sf_factor"] = _safe_float(self.var_lrc_sf, 1.0) if hasattr(self, "var_lrc_sf") else 1.0
    self.cfg.leakage["input"] = self._normpath(self.var_lrc_input.get()) if hasattr(self, "var_lrc_input") else ""
    self.cfg.leakage["output"] = self._normpath(self.var_lrc_output.get()) if hasattr(self, "var_lrc_output") else ""
    self.cfg.leakage["format"] = str(self.var_lrc_fmt.get()).lower() if hasattr(self, "var_lrc_fmt") else "mat"
    self.cfg.leakage["boundary_file"] = self._normpath(self.var_lrc_boundary.get()) if hasattr(self, "var_lrc_boundary") else ""
    self.cfg.leakage["script_global"] = self._normpath(self.var_lrc_script_global.get()) if hasattr(self, "var_lrc_script_global") else ""
    self.cfg.leakage["script_region"] = self._normpath(self.var_lrc_script_region.get()) if hasattr(self, "var_lrc_script_region") else ""
    self.cfg.leakage["matlab"] = self._normpath(self.var_lrc_matlab.get()) if hasattr(self, "var_lrc_matlab") else "matlab"
    self.cfg.leakage["sf_auto"] = bool(self.var_lrc_sf_auto.get()) if hasattr(self, "var_lrc_sf_auto") else False
    self.cfg.leakage["sf_method"] = str(self.var_lrc_sf_method.get()) if hasattr(self, "var_lrc_sf_method") else "Auto"
    self.cfg.leakage["sf_gauss_km"] = _safe_float(self.var_lrc_sf_gauss, 300.0) if hasattr(self, "var_lrc_sf_gauss") else 300.0
    self.cfg.leakage["sf_fan_r1_km"] = _safe_float(self.var_lrc_sf_fan_r1, 300.0) if hasattr(self, "var_lrc_sf_fan_r1") else 300.0
    self.cfg.leakage["sf_fan_r2_km"] = _safe_float(self.var_lrc_sf_fan_r2, 300.0) if hasattr(self, "var_lrc_sf_fan_r2") else 300.0
    self.cfg.leakage["sf_ddk_type"] = str(self.var_lrc_sf_ddk.get()) if hasattr(self, "var_lrc_sf_ddk") else "DDK4"
    self.cfg.leakage["sf_p4_deg"] = _safe_int(self.var_lrc_sf_p4_deg, 4) if hasattr(self, "var_lrc_sf_p4_deg") else 4
    self.cfg.leakage["sf_p4_m"] = _safe_int(self.var_lrc_sf_p4_m, 6) if hasattr(self, "var_lrc_sf_p4_m") else 6
    self.cfg.leakage["sf_grid_interval"] = _safe_float(self.var_lrc_sf_grid, 0.5) if hasattr(self, "var_lrc_sf_grid") else 0.5
    self.cfg.leakage["sf_hsa_window"] = _safe_int(self.var_lrc_sf_hsa_window, 60) if hasattr(self, "var_lrc_sf_hsa_window") else 60
    self.cfg.leakage["sf_hsa_p"] = _safe_int(self.var_lrc_sf_hsa_p, 20) if hasattr(self, "var_lrc_sf_hsa_p") else 20
    self.cfg.leakage["sf_hsa_order"] = _safe_int(self.var_lrc_sf_hsa_order, 6) if hasattr(self, "var_lrc_sf_hsa_order") else 6
    self.cfg.leakage["sf_hsa_buffer"] = _safe_int(self.var_lrc_sf_hsa_buffer, 10) if hasattr(self, "var_lrc_sf_hsa_buffer") else 10
    self.cfg.leakage["sf_hsa_ts"] = _safe_int(self.var_lrc_sf_hsa_ts, 1) if hasattr(self, "var_lrc_sf_hsa_ts") else 1
    self.cfg.leakage["sf_toolbox"] = self._normpath(self.var_lrc_toolbox.get()) if hasattr(self, "var_lrc_toolbox") else ""
    self.cfg.leakage["fm_max_iter"] = _safe_int(self.var_lrc_fm_max_iter, 40) if hasattr(self, "var_lrc_fm_max_iter") else 40
    self.cfg.leakage["fm_min_iter"] = _safe_int(self.var_lrc_fm_min_iter, 3) if hasattr(self, "var_lrc_fm_min_iter") else 3
    self.cfg.leakage["fm_tol"] = _safe_float(self.var_lrc_fm_tol, 0.01) if hasattr(self, "var_lrc_fm_tol") else 0.01
    self.cfg.leakage["fm_accel"] = _safe_float(self.var_lrc_fm_accel, 1.1) if hasattr(self, "var_lrc_fm_accel") else 1.1
    self.cfg.leakage["fm_patience"] = _safe_int(self.var_lrc_fm_patience, 8) if hasattr(self, "var_lrc_fm_patience") else 8
    self.cfg.leakage["fm_min_improve"] = (
        _safe_float(self.var_lrc_fm_min_improve, 1.0e-4) if hasattr(self, "var_lrc_fm_min_improve") else 1.0e-4
    )
    self.cfg.leakage["fm_autocap_hsaf_iter"] = (
        bool(self.var_lrc_fm_autocap_hsaf_iter.get())
        if hasattr(self, "var_lrc_fm_autocap_hsaf_iter")
        else bool(self.cfg.leakage.get("fm_autocap_hsaf_iter", True))
    )
    self.cfg.leakage["fm_hsaf_iter_cap"] = (
        _safe_int(self.var_lrc_fm_hsaf_iter_cap, 40)
        if hasattr(self, "var_lrc_fm_hsaf_iter_cap")
        else int(self.cfg.leakage.get("fm_hsaf_iter_cap", 40))
    )
    self.cfg.leakage["fm_allow_hsaf_parallel"] = (
        bool(self.var_lrc_fm_allow_hsaf_parallel.get())
        if hasattr(self, "var_lrc_fm_allow_hsaf_parallel")
        else bool(self.cfg.leakage.get("fm_allow_hsaf_parallel", True))
    )
    self.cfg.leakage["fm_hsaf_outer_workers_cap"] = (
        _safe_int(self.var_lrc_fm_hsaf_outer_workers_cap, 12)
        if hasattr(self, "var_lrc_fm_hsaf_outer_workers_cap")
        else int(self.cfg.leakage.get("fm_hsaf_outer_workers_cap", 12))
    )
    self.cfg.leakage["fm_hsaf_inner_workers"] = (
        _safe_int(self.var_lrc_fm_hsaf_inner_workers, 1)
        if hasattr(self, "var_lrc_fm_hsaf_inner_workers")
        else int(self.cfg.leakage.get("fm_hsaf_inner_workers", 1))
    )

    if not isinstance(self.cfg.perf, dict):
        self.cfg.perf = {}
    allow_frozen = bool(self.var_allow_frozen_parallel.get())
    self.cfg.perf["allow_frozen_parallel"] = allow_frozen
    self.cfg.perf["frozen_max_workers"] = int(self.var_workers.get()) if allow_frozen else 0
    self.cfg.perf["runtime_profile"] = (
        self.var_runtime_profile.get().strip().lower() if hasattr(self, "var_runtime_profile") else "balanced"
    )


def _collect_config_dict(self):
    """Build a JSON-serializable config dict from current GUI state."""
    self._update_config()
    base = {}
    try:
        base = copy.deepcopy(getattr(self.cfg, "_raw", {}))
    except Exception:
        base = {}

    def _ensure(d, key):
        if key not in d or not isinstance(d[key], dict):
            d[key] = {}
        return d[key]

    path_cfg = _ensure(base, "path")
    path_cfg["GFC"] = self._normpath(self.var_gfc.get())
    path_cfg["OUTPUT"] = self._normpath(self.var_out.get())
    path_cfg["AUX"] = self._normpath(self.var_aux.get())
    path_cfg["BOUNDARY"] = self._normpath(self.var_boundary.get())
    path_cfg["DDK"] = self._normpath(self.var_ddk.get())

    time_cfg = _ensure(base, "time")
    time_cfg["auto_detect_gfc"] = bool(self.var_auto_time.get())
    time_cfg["start_ym"] = self.var_start.get()
    time_cfg["end_ym"] = self.var_end.get()

    grid_cfg = _ensure(base, "grid")
    grid_cfg["lon"] = [float(self.var_lon_min.get()), float(self.var_lon_max.get())]
    grid_cfg["lat"] = [float(self.var_lat_min.get()), float(self.var_lat_max.get())]
    grid_cfg["dlon"] = float(self.var_dlon.get())
    grid_cfg["dlat"] = float(self.var_dlat.get())

    inv_cfg = _ensure(base, "inversion")
    inv_cfg["Lmax"] = int(self.var_lmax.get())
    inv_cfg["remove_mean"] = bool(self.var_demean.get())
    inv_cfg["mean_start_ym"] = self.var_mean_start.get().strip()
    inv_cfg["mean_end_ym"] = self.var_mean_end.get().strip()
    inv_cfg.setdefault("lowdeg", {})
    inv_cfg["lowdeg"]["files"] = {
        "C20": self._normpath(self.var_c20.get()),
        "DEGREE1": self._normpath(self.var_deg1.get()),
    }
    inv_cfg.setdefault("gia", {})
    inv_cfg["gia"]["file"] = self._normpath(self.var_gia.get())

    filt_cfg = _ensure(base, "filter")
    filt_cfg.setdefault("gaussian", {})
    filt_cfg["gaussian"]["enable"] = bool(self.var_gauss.get())
    filt_cfg["gaussian"]["radius_km"] = float(self.var_gauss_rad.get())
    filt_cfg.setdefault("p4m6", {})
    filt_cfg["p4m6"]["enable"] = bool(self.var_p4m6.get())
    filt_cfg["p4m6"]["poly_deg"] = int(self.var_p4_deg.get())
    filt_cfg["p4m6"]["m_start"] = int(self.var_p4_m.get())
    filt_cfg.setdefault("ddk", {})
    filt_cfg["ddk"]["enable"] = bool(self.var_ddk_enable.get())
    filt_cfg["ddk"]["type"] = self.var_ddk_type.get()
    filt_cfg["ddk"]["data_dir"] = self._normpath(self.var_ddk.get())
    filt_cfg.setdefault("fan", {})
    filt_cfg["fan"]["enable"] = bool(self.var_fan.get())
    filt_cfg["fan"]["radius1_km"] = float(self.var_fan_r1.get())
    filt_cfg["fan"]["radius2_km"] = float(self.var_fan_r2.get())
    filt_cfg["pre_hankel_input"] = self.var_hsaf_input.get().strip() if hasattr(self, "var_hsaf_input") else "P4M6"
    filt_cfg.setdefault("hankel", {})
    filt_cfg["hankel"]["enable"] = bool(self.var_hsaf.get())
    filt_cfg["hankel"]["variant"] = self.var_hsaf_variant.get()
    filt_cfg["hankel"]["mode"] = self.var_hsaf_mode.get() or "ola"
    filt_cfg["hankel"]["params"] = {
        "N": int(self.var_hsaf_N.get()),
        "P": int(self.var_hsaf_P.get()),
        "K": int(self.var_hsaf_K.get()),
        "J": int(self.var_hsaf_J.get()),
    }
    filt_cfg["hankel"]["adaptive"] = getattr(self.cfg.filter.hankel, "adaptive", [])

    io_cfg = _ensure(base, "io")
    io_cfg["save_monthly_mat"] = bool(self.var_save_monthly_mat.get())
    io_cfg["save_stack_mat"] = bool(self.var_save_stack_mat.get())
    io_cfg["export_txt"] = bool(self.var_export_txt.get())
    io_cfg["txt_format"] = self.var_txt_format.get().strip() or "lonlatval"

    par_cfg = _ensure(base, "parallel")
    par_cfg["enable"] = bool(self.var_parallel.get())
    par_cfg["nWorkers"] = int(self.var_workers.get())

    ref_cfg = _ensure(base, "reference")
    ref_cfg["mascon_dir"] = self._normpath(self.var_mascon_dir.get())
    ref_cfg.setdefault("mascon_undo", {})
    ref_cfg["mascon_undo"]["gad_file"] = self._normpath(self.var_mascon_gad.get())
    ref_cfg["mascon_undo"]["gia_file"] = self._normpath(self.var_mascon_gia.get())

    basin_cfg = _ensure(base, "basin")
    basin_cfg["analysis_enable"] = bool(self.var_basin_enable.get())
    basin_cfg["boundary_file"] = self._normpath(self.var_basin_file.get())
    basin_cfg["name"] = self.var_basin_name.get().strip()
    basin_cfg["name_field"] = self.var_basin_name_field.get().strip() or "Name"

    leak_cfg = _ensure(base, "leakage")
    leak_cfg["enable"] = bool(self.var_lrc_enable.get()) if hasattr(self, "var_lrc_enable") else False
    leak_cfg["scope"] = str(self.var_lrc_scope.get()).lower() if hasattr(self, "var_lrc_scope") else "global"
    leak_cfg["method"] = str(self.var_lrc_method.get()).upper() if hasattr(self, "var_lrc_method") else "SF"
    leak_cfg["sf_factor"] = float(self.var_lrc_sf.get()) if hasattr(self, "var_lrc_sf") else 1.0
    leak_cfg["input"] = self._normpath(self.var_lrc_input.get()) if hasattr(self, "var_lrc_input") else ""
    leak_cfg["output"] = self._normpath(self.var_lrc_output.get()) if hasattr(self, "var_lrc_output") else ""
    leak_cfg["format"] = str(self.var_lrc_fmt.get()).lower() if hasattr(self, "var_lrc_fmt") else "mat"
    leak_cfg["boundary_file"] = self._normpath(self.var_lrc_boundary.get()) if hasattr(self, "var_lrc_boundary") else ""
    leak_cfg["script_global"] = self._normpath(self.var_lrc_script_global.get()) if hasattr(self, "var_lrc_script_global") else ""
    leak_cfg["script_region"] = self._normpath(self.var_lrc_script_region.get()) if hasattr(self, "var_lrc_script_region") else ""
    leak_cfg["matlab"] = self._normpath(self.var_lrc_matlab.get()) if hasattr(self, "var_lrc_matlab") else "matlab"
    leak_cfg["sf_auto"] = bool(self.var_lrc_sf_auto.get()) if hasattr(self, "var_lrc_sf_auto") else False
    leak_cfg["sf_method"] = str(self.var_lrc_sf_method.get()) if hasattr(self, "var_lrc_sf_method") else "Auto"
    leak_cfg["sf_gauss_km"] = float(self.var_lrc_sf_gauss.get()) if hasattr(self, "var_lrc_sf_gauss") else 300.0
    leak_cfg["sf_fan_r1_km"] = float(self.var_lrc_sf_fan_r1.get()) if hasattr(self, "var_lrc_sf_fan_r1") else 300.0
    leak_cfg["sf_fan_r2_km"] = float(self.var_lrc_sf_fan_r2.get()) if hasattr(self, "var_lrc_sf_fan_r2") else 300.0
    leak_cfg["sf_ddk_type"] = str(self.var_lrc_sf_ddk.get()) if hasattr(self, "var_lrc_sf_ddk") else "DDK4"
    leak_cfg["sf_p4_deg"] = int(self.var_lrc_sf_p4_deg.get()) if hasattr(self, "var_lrc_sf_p4_deg") else 4
    leak_cfg["sf_p4_m"] = int(self.var_lrc_sf_p4_m.get()) if hasattr(self, "var_lrc_sf_p4_m") else 6
    leak_cfg["sf_grid_interval"] = float(self.var_lrc_sf_grid.get()) if hasattr(self, "var_lrc_sf_grid") else 0.5
    leak_cfg["sf_hsa_window"] = int(self.var_lrc_sf_hsa_window.get()) if hasattr(self, "var_lrc_sf_hsa_window") else 60
    leak_cfg["sf_hsa_p"] = int(self.var_lrc_sf_hsa_p.get()) if hasattr(self, "var_lrc_sf_hsa_p") else 20
    leak_cfg["sf_hsa_order"] = int(self.var_lrc_sf_hsa_order.get()) if hasattr(self, "var_lrc_sf_hsa_order") else 6
    leak_cfg["sf_hsa_buffer"] = int(self.var_lrc_sf_hsa_buffer.get()) if hasattr(self, "var_lrc_sf_hsa_buffer") else 10
    leak_cfg["sf_hsa_ts"] = int(self.var_lrc_sf_hsa_ts.get()) if hasattr(self, "var_lrc_sf_hsa_ts") else 1
    leak_cfg["sf_toolbox"] = self._normpath(self.var_lrc_toolbox.get()) if hasattr(self, "var_lrc_toolbox") else ""
    leak_cfg["fm_max_iter"] = (
        int(self.var_lrc_fm_max_iter.get()) if hasattr(self, "var_lrc_fm_max_iter") else int(leak_cfg.get("fm_max_iter", 40))
    )
    leak_cfg["fm_min_iter"] = (
        int(self.var_lrc_fm_min_iter.get()) if hasattr(self, "var_lrc_fm_min_iter") else int(leak_cfg.get("fm_min_iter", 3))
    )
    leak_cfg["fm_tol"] = (
        float(self.var_lrc_fm_tol.get()) if hasattr(self, "var_lrc_fm_tol") else float(leak_cfg.get("fm_tol", 0.01))
    )
    leak_cfg["fm_accel"] = (
        float(self.var_lrc_fm_accel.get()) if hasattr(self, "var_lrc_fm_accel") else float(leak_cfg.get("fm_accel", 1.1))
    )
    leak_cfg["fm_patience"] = (
        int(self.var_lrc_fm_patience.get()) if hasattr(self, "var_lrc_fm_patience") else int(leak_cfg.get("fm_patience", 8))
    )
    leak_cfg["fm_min_improve"] = (
        float(self.var_lrc_fm_min_improve.get())
        if hasattr(self, "var_lrc_fm_min_improve")
        else float(leak_cfg.get("fm_min_improve", 1.0e-4))
    )
    leak_cfg["fm_autocap_hsaf_iter"] = (
        bool(self.var_lrc_fm_autocap_hsaf_iter.get())
        if hasattr(self, "var_lrc_fm_autocap_hsaf_iter")
        else bool(leak_cfg.get("fm_autocap_hsaf_iter", True))
    )
    leak_cfg["fm_hsaf_iter_cap"] = (
        int(self.var_lrc_fm_hsaf_iter_cap.get())
        if hasattr(self, "var_lrc_fm_hsaf_iter_cap")
        else int(leak_cfg.get("fm_hsaf_iter_cap", 40))
    )
    leak_cfg["fm_allow_hsaf_parallel"] = (
        bool(self.var_lrc_fm_allow_hsaf_parallel.get())
        if hasattr(self, "var_lrc_fm_allow_hsaf_parallel")
        else bool(leak_cfg.get("fm_allow_hsaf_parallel", True))
    )
    leak_cfg["fm_hsaf_outer_workers_cap"] = (
        int(self.var_lrc_fm_hsaf_outer_workers_cap.get())
        if hasattr(self, "var_lrc_fm_hsaf_outer_workers_cap")
        else int(leak_cfg.get("fm_hsaf_outer_workers_cap", 12))
    )
    leak_cfg["fm_hsaf_inner_workers"] = (
        int(self.var_lrc_fm_hsaf_inner_workers.get())
        if hasattr(self, "var_lrc_fm_hsaf_inner_workers")
        else int(leak_cfg.get("fm_hsaf_inner_workers", 1))
    )

    perf_cfg = _ensure(base, "perf")
    allow_frozen = bool(self.var_allow_frozen_parallel.get())
    perf_cfg["allow_frozen_parallel"] = allow_frozen
    perf_cfg["frozen_max_workers"] = int(self.var_workers.get()) if allow_frozen else 0
    perf_cfg["runtime_profile"] = (
        self.var_runtime_profile.get().strip().lower() if hasattr(self, "var_runtime_profile") else "balanced"
    )

    return base
