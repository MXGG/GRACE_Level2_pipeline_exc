"""Basin/Leakage data access service extracted from GUI layer."""

import threading

import numpy as np


def load_basin_info(self):
    path = self.var_basin_data.get().strip() if hasattr(self, "var_basin_data") else ""
    if not path:
        self._msg_warn("Basin", "Please select a data file (mat/txt/nc/hdf).")
        return
    try:
        self._clear_large_caches(keep="basin")
        ewh, lon, lat, t, meta = self._load_stack_any(path)
        if ewh is None or lon is None or lat is None:
            raise ValueError("Missing required keys (data/lon/lat).")
        if ewh.ndim == 2:
            ewh = ewh[:, :, None]
        nlon, nlat, nt = ewh.shape
        self._basin_cache = {"ewh": ewh, "lon": lon.squeeze(), "lat": lat.squeeze(), "t": t, "meta": meta or {}}
        active_var = meta.get("active_var") if isinstance(meta, dict) else None
        if active_var:
            self._basin_cache["active_var"] = active_var
        self._basin_cache_path = path
        if hasattr(self, "var_basin_info"):
            info = f"Loaded: {nlon}x{nlat}x{nt}"
            if active_var:
                info += f" ({active_var})"
            self.var_basin_info.set(info)
    except Exception as e:
        self._msg_error("Basin", f"Failed to load data: {e}")


def load_leakage_info(self):
    path = self.var_lrc_input.get().strip() if hasattr(self, "var_lrc_input") else ""
    if not path:
        self._msg_warn("Leakage", "Please select a data file (mat/txt/nc/hdf).")
        return
    try:
        self._clear_large_caches(keep="leakage")
        ewh, lon, lat, t, meta = self._load_stack_any(path)
        if ewh is None or lon is None or lat is None:
            raise ValueError("Missing required keys (data/lon/lat).")
        if ewh.ndim == 2:
            ewh = ewh[:, :, None]
        nlon, nlat, nt = ewh.shape
        self._leakage_cache = {"ewh": ewh, "lon": lon.squeeze(), "lat": lat.squeeze(), "t": t, "meta": meta or {}}
        active_var = meta.get("active_var") if isinstance(meta, dict) else None
        if active_var:
            self._leakage_cache["active_var"] = active_var
        self._leakage_cache_path = path
        if hasattr(self, "var_lrc_info"):
            info = f"Loaded: {nlon}x{nlat}x{nt}"
            if active_var:
                info += f" ({active_var})"
            self.var_lrc_info.set(info)
        inferred_method, inferred_ddk = self._infer_leakage_method_from_input(path, meta or {})
        if inferred_method:
            if hasattr(self, "var_lrc_sf_ddk") and inferred_ddk:
                try:
                    self.var_lrc_sf_ddk.set(str(inferred_ddk))
                except Exception:
                    pass
            self._append_log(f"[LEAKAGE] Input-detected operator: {inferred_method}")
        if hasattr(self, "_refresh_lrc_layout"):
            self._refresh_lrc_layout()
    except Exception as e:
        self._msg_error("Leakage", f"Failed to load data: {e}")


def _get_basin_data(self):
    path = self.var_basin_data.get().strip() if hasattr(self, "var_basin_data") else ""
    if not path:
        raise ValueError("Basin data file not set.")
    if self._basin_cache is None or self._basin_cache_path != path:
        if threading.current_thread() is not threading.main_thread():
            raise ValueError("Basin data is not preloaded. Please click Load Info before running.")
        self.load_basin_info()
    if self._basin_cache is None:
        raise ValueError("Basin data not loaded.")
    return self._basin_cache


def _get_leakage_data(self):
    path = self.var_lrc_input.get().strip() if hasattr(self, "var_lrc_input") else ""
    if not path:
        raise ValueError("Leakage input not set.")
    if self._leakage_cache is None or self._leakage_cache_path != path:
        if threading.current_thread() is not threading.main_thread():
            raise ValueError("Leakage input data is not preloaded. Please click Load Data before running.")
        self.load_leakage_info()
    if self._leakage_cache is None:
        raise ValueError("Leakage input data not loaded.")
    return self._leakage_cache
