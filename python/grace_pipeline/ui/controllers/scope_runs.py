"""Scope-specific run entry service extracted from GUI layer."""

import os
import threading
from tkinter import messagebox


def on_run_basin(self):
    if not getattr(self, "_config_ready", False):
        messagebox.showwarning("Config", "Please load/select a config file before running.")
        return
    if getattr(self, "_active_scope", None):
        self._msg_warn("Basin", f"Another task is running: {self._active_scope}")
        return
    try:
        self._update_config()
    except Exception as e:
        messagebox.showerror("Configuration Error", str(e))
        return
    # Preflight checks on main thread
    try:
        if hasattr(self, "var_basin_enable"):
            self.var_basin_enable.set(True)
    except Exception:
        pass
    data_path = self.var_basin_data.get().strip() if hasattr(self, "var_basin_data") else ""
    if not data_path:
        messagebox.showwarning("Basin", "Please select a basin data file (mat/txt/nc/hdf).")
        return
    if not os.path.exists(data_path):
        messagebox.showwarning("Basin", f"Basin data file not found:\n{data_path}")
        return
    bfile = self.var_basin_file.get().strip() if hasattr(self, "var_basin_file") else ""
    if not bfile:
        messagebox.showwarning("Basin", "Please select a boundary file.")
        return
    if not os.path.exists(bfile):
        messagebox.showwarning("Basin", f"Boundary file not found:\n{bfile}")
        return
    # Warm up cache only when needed, to reduce UI freeze on repeated runs.
    if self._basin_cache is None or self._basin_cache_path != data_path:
        self.load_basin_info()
    if self._basin_cache is None or self._basin_cache_path != data_path:
        messagebox.showwarning("Basin", "Failed to load basin input data. Please click Load Info and confirm variable selection.")
        return
    self._set_busy_scope("basin", indeterminate=False)

    def _worker():
        err = None
        try:
            self.run_basin_analysis()
        except Exception as e:
            err = e
            try:
                import traceback

                self._append_log("[BASIN][ERROR] " + traceback.format_exc(), tag="stderr")
            except Exception:
                pass
        finally:

            def _finish():
                if err is not None:
                    self._msg_error("Basin", f"Basin analysis failed: {err}")
                self._clear_busy_scope("basin")

            self.root.after(0, _finish)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def on_run_leakage(self):
    if not getattr(self, "_config_ready", False):
        messagebox.showwarning("Config", "Please load/select a config file before running.")
        return
    if getattr(self, "_active_scope", None):
        self._msg_warn("Leakage", f"Another task is running: {self._active_scope}")
        return
    try:
        self._update_config()
    except Exception as e:
        messagebox.showerror("Configuration Error", str(e))
        return
    # Warm up cache on main thread to avoid any UI prompts from worker thread.
    data_path = self.var_lrc_input.get().strip() if hasattr(self, "var_lrc_input") else ""
    if not data_path:
        messagebox.showwarning("Leakage", "Please select an input data file.")
        return
    if self._leakage_cache is None or self._leakage_cache_path != data_path:
        try:
            self.load_leakage_info()
        except Exception:
            pass
    if self._leakage_cache is None or self._leakage_cache_path != data_path:
        messagebox.showwarning("Leakage", "Failed to load leakage input data. Please click Load Info and confirm variable selection.")
        return
    self._set_busy_scope("leakage", indeterminate=True)

    def _worker():
        err = None
        try:
            self.run_leakage_correction()
        except Exception as e:
            err = e
            try:
                import traceback

                self._append_log("[LEAKAGE][ERROR] " + traceback.format_exc(), tag="stderr")
            except Exception:
                pass
        finally:

            def _finish():
                if err is not None:
                    self._msg_error("Leakage", f"Leakage correction failed: {err}")
                self._clear_busy_scope("leakage")

            self.root.after(0, _finish)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
