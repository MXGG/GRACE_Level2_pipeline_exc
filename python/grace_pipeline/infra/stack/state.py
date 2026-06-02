"""Stack-state service extracted from GUI layer."""

import numpy as np


def load_stack_info(self):
    path = self.var_stack_file.get().strip()
    if not path:
        self._msg_warn("Stack", "Please select a data file (mat/txt/nc/hdf).")
        return
    try:
        self._clear_large_caches(keep="stack")
        shape, lon, lat, t, meta = self._probe_stack_any(path)
        if shape is None or lon is None or lat is None:
            raise ValueError("Missing required keys (data/lon/lat).")
        nlon, nlat, nt = shape
        meta = meta or {}
        active_var = meta.get("active_var")
        var_names = meta.get("data_var_names", [])
        self._stack_cache = {
            "ewh": None,
            "lon": np.asarray(lon).squeeze(),
            "lat": np.asarray(lat).squeeze(),
            "t": t,
            "meta": meta,
            "shape": tuple(shape),
            "active_var": active_var,
        }
        self._set_stack_var_options(var_names, active_var)
        self._stack_cache_path = path
        info = f"Ready: {nlon}x{nlat}x{nt}"
        if active_var:
            info += f" ({active_var})"
        self.var_stack_info.set(info)
        self.var_time_idx.set(0)
    except Exception as e:
        self._msg_error("Stack", f"Failed to load stack: {e}")


def _set_stack_var_options(self, names, active=None):
    if not hasattr(self, "cmb_stack_var"):
        return
    try:
        names = list(names) if names else []
        self.cmb_stack_var.configure(values=names)
        if not names:
            self.var_stack_data_var.set("")
            try:
                self.cmb_stack_var.configure(state="disabled")
            except Exception:
                pass
            return
        if active not in names:
            active = names[0]
        self.var_stack_data_var.set(active)
        try:
            self.cmb_stack_var.configure(state="readonly")
        except Exception:
            pass
    except Exception:
        pass


def _on_stack_var_change(self):
    try:
        if not hasattr(self, "var_stack_data_var"):
            return
        name = self.var_stack_data_var.get().strip()
        if not name:
            return
        if isinstance(self._stack_cache, dict):
            self._stack_cache["active_var"] = name
    except Exception:
        pass


def _get_stack_data(self):
    path = self.var_stack_file.get().strip()
    if not path:
        raise ValueError("Stack file not set.")
    if self._stack_cache is None or self._stack_cache_path != path:
        self.load_stack_info()
    if self._stack_cache is None:
        raise ValueError("Stack not loaded.")
    try:
        name = self.var_stack_data_var.get().strip() if hasattr(self, "var_stack_data_var") else ""
    except Exception:
        name = ""
    if self._stack_cache.get("ewh") is None or (name and name != self._stack_cache.get("active_var")):
        self._clear_large_caches(keep="stack")
        ewh, lon, lat, t, meta = self._load_stack_any(
            path,
            active_var=name or None,
            selection_meta=self._stack_cache.get("meta"),
            select_nc_variables_cb=self._select_nc_variables,
        )
        if ewh is None or lon is None or lat is None:
            raise ValueError("Failed to load stack data.")
        self._stack_cache = {
            "ewh": ewh,
            "lon": np.asarray(lon).squeeze(),
            "lat": np.asarray(lat).squeeze(),
            "t": t,
            "meta": meta or {},
            "active_var": (meta or {}).get("active_var", name or self._stack_cache.get("active_var")),
        }
        self._stack_cache_path = path
    return self._stack_cache
