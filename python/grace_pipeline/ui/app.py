"""
Graphical User Interface for GRACE Pipeline.
"""

import os
import json
import gc
import hashlib
import threading
import time
import sys
import queue
import tkinter as tk
import numpy as np
from tkinter import ttk, filedialog, scrolledtext, messagebox, simpledialog
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable, Any, Dict, Tuple

from grace_pipeline.infra.config import get_config_dir, load_config, get_root_dir

from grace_pipeline.infra.stack.probe import probe_stack_any as service_probe_stack_any
from grace_pipeline.app.leakage import run_leakage_correction as service_run_leakage_correction
from grace_pipeline.app.lrc_matlab import (
    ensure_sf_wrapper as wf_ensure_sf_wrapper,
    compute_sf_via_matlab as wf_compute_sf_via_matlab,
    run_fm_correction as wf_run_fm_correction,
)
from grace_pipeline.app.leakage_helpers import (
    default_global_land_shp as wf_default_global_land_shp,
    build_global_land_mask as wf_build_global_land_mask,
    build_regional_leakage_mask as wf_build_regional_leakage_mask,
    infer_leakage_method_from_input as wf_infer_leakage_method_from_input,
    build_leakage_filter_options as wf_build_leakage_filter_options,
    save_leakage_output as wf_save_leakage_output,
)
from grace_pipeline.infra.stack.loader import load_stack_any as service_load_stack_any
from grace_pipeline.app.plot import _plot_stack as service_plot_stack
from grace_pipeline.infra.stack.state import (
    load_stack_info as service_load_stack_info,
    _set_stack_var_options as service_set_stack_var_options,
    _on_stack_var_change as service_on_stack_var_change,
    _get_stack_data as service_get_stack_data,
)
from grace_pipeline.infra.runtime.time_ops import (
    parse_ym as algo_parse_ym,
    build_time_from_fallback as algo_build_time_from_fallback,
    resolve_time as algo_resolve_time,
    resolve_output_file as algo_resolve_output_file,
    infer_time_labels as algo_infer_time_labels,
    infer_time_axis_for_rate as algo_infer_time_axis_for_rate,
    file_fingerprint as algo_file_fingerprint,
    build_scope_signature as algo_build_scope_signature,
)
from grace_pipeline.infra.io.gui_io_ops import (
    sanitize_mat_value as io_sanitize_mat_value,
    safe_savemat as io_safe_savemat,
    safe_write_text as io_safe_write_text,
    save_grid_txt as io_save_grid_txt,
)
from grace_pipeline.infra.runtime.cache import (
    scope_cache_dir as cache_scope_cache_dir,
    scope_cache_file as cache_scope_cache_file,
    load_scope_progress as cache_load_scope_progress,
    save_scope_progress as cache_save_scope_progress,
    save_scope_progress_throttled as cache_save_scope_progress_throttled,
    clear_scope_progress as cache_clear_scope_progress,
)
from grace_pipeline.infra.datasets.grid_ops import (
    fm_target_grid as grid_fm_target_grid,
    sf_target_grid as grid_sf_target_grid,
    regrid_regular as grid_regrid_regular,
    write_xyz_file as grid_write_xyz_file,
    read_xyz_grid as grid_read_xyz_grid,
)
from grace_pipeline.ui.plotting.projections import (
    infer_plot_lon_mode as map_infer_plot_lon_mode,
    normalize_lon_for_plot as map_normalize_lon_for_plot,
    split_plot_lon_segments as map_split_plot_lon_segments,
    normalize_lon_input as map_normalize_lon_input,
    region_is_custom as map_region_is_custom,
    parse_float as map_parse_float,
    wrap_delta_lon as map_wrap_delta_lon,
    get_proj_center as map_get_proj_center,
    get_conic_parallels as map_get_conic_parallels,
    scale_projection as map_scale_projection,
    apply_proj_scale as map_apply_proj_scale,
    proj_robinson as map_proj_robinson,
    proj_mollweide as map_proj_mollweide,
    proj_mercator as map_proj_mercator,
    proj_miller as map_proj_miller,
    proj_sinusoidal as map_proj_sinusoidal,
    proj_equalearth as map_proj_equalearth,
    proj_winkeltripel as map_proj_winkeltripel,
    proj_eckert4 as map_proj_eckert4,
    proj_orthographic as map_proj_orthographic,
    proj_aeqd as map_proj_aeqd,
    proj_stereographic as map_proj_stereographic,
    proj_lambert_conformal as map_proj_lambert_conformal,
    proj_albers as map_proj_albers,
)
from grace_pipeline.ui.plotting.boundaries import (
    plot_line as boundary_plot_line,
    split_dateline as boundary_split_dateline,
    read_boundary_file as boundary_read_boundary_file,
    boundary_bbox as boundary_boundary_bbox,
    draw_boundaries as boundary_draw_boundaries,
)
from grace_pipeline.ui.plotting.overlays import (
    draw_coastlines as overlay_draw_coastlines,
    draw_graticule as overlay_draw_graticule,
)
from grace_pipeline.infra.datasets.data_access import (
    load_basin_info as service_load_basin_info,
    load_leakage_info as service_load_leakage_info,
    _get_basin_data as service_get_basin_data,
    _get_leakage_data as service_get_leakage_data,
)
from grace_pipeline.app.basin import run_basin_analysis as service_run_basin_analysis
from grace_pipeline.ui.controllers.config import (
    load_config_file as service_load_config_file,
    _update_config as service_update_config,
    _collect_config_dict as service_collect_config_dict,
)
from grace_pipeline.ui.controllers.execution import (
    on_run as service_on_run,
    on_run_all as service_on_run_all,
    _run_thread as service_run_thread,
    _reset_ui as service_reset_ui,
)
from grace_pipeline.ui.controllers.scope_runs import (
    on_run_basin as service_on_run_basin,
    on_run_leakage as service_on_run_leakage,
)
from grace_pipeline.ui.tabs.basin import build_basin_tab as tab_build_basin_tab
from grace_pipeline.ui.tabs.common import build_common_tab as tab_build_common_tab
from grace_pipeline.ui.tabs.filters import build_filters_tab as tab_build_filters_tab
from grace_pipeline.ui.tabs.leakage import build_leakage_tab as tab_build_leakage_tab
from grace_pipeline.ui.tabs.plot import build_plot_tab as tab_build_plot_tab


class TextRedirector:
    """Redirect stdout/stderr to a Tkinter Text widget."""
    def __init__(self, widget, tag="stdout", max_lines=4000, log_fp=None):
        self.widget = widget
        self.tag = tag
        self.max_lines = max_lines
        self.log_fp = log_fp
        self._queue = queue.Queue()
        self._flush_scheduled = False

    def write(self, str):
        # Normalize CR/LF and strip ANSI codes from tqdm.
        msg = str.replace("\r", "\n")
        msg = self._strip_ansi(msg)
        if self.log_fp:
            try:
                self.log_fp.write(msg)
            except Exception:
                pass
        self._queue.put(msg)
        if not self._flush_scheduled:
            self._flush_scheduled = True
            try:
                self.widget.after(100, self._flush_queue)
            except Exception:
                self._flush_scheduled = False

    def _flush_queue(self):
        try:
            chunks = []
            while not self._queue.empty():
                chunks.append(self._queue.get_nowait())
            if chunks:
                msg = "".join(chunks)
                self.widget.configure(state="normal")
                self.widget.insert("end", msg, (self.tag,))
                self.widget.see("end")
                if self.max_lines:
                    line_count = int(self.widget.index('end-1c').split('.')[0])
                    if line_count > self.max_lines:
                        self.widget.delete('1.0', f"{line_count - self.max_lines}.0")
                self.widget.configure(state="disabled")
        finally:
            self._flush_scheduled = False
            if not self._queue.empty():
                try:
                    self._flush_scheduled = True
                    self.widget.after(100, self._flush_queue)
                except Exception:
                    self._flush_scheduled = False

    def flush(self):
        pass

    def isatty(self):
        return False

    @staticmethod
    def _strip_ansi(text):
        import re
        ansi = re.compile(r"\x1b\[[0-9;]*[mK]")
        return ansi.sub("", text)


class ScrollableFrame(ttk.Frame):
    """A scrollable frame for long forms inside notebook tabs."""
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)

        self.inner = ttk.Frame(self.canvas, padding=10)
        self._window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")

        self._bind_mousewheel()

    def _on_frame_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self._window_id, width=event.width)

    def _on_mousewheel(self, event):
        # Windows uses event.delta
        delta = int(-1 * (event.delta / 120))
        self.canvas.yview_scroll(delta, "units")

    def _bind_mousewheel(self):
        self.canvas.bind("<Enter>", lambda _e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind("<Leave>", lambda _e: self.canvas.unbind_all("<MouseWheel>"))

class GracePipelineGUI:
    _TextRedirector = TextRedirector

    def __init__(self, root):
        self.root = root
        self.root.title("GRACE Level-2 Pipeline")
        self.root.geometry("1000x800")
        self.root.minsize(900, 650)
        
        # Load default config for initial values
        self.default_cfg = load_config()
        self.cfg = self.default_cfg # Will be modified
        self.cfg_dir = get_config_dir(get_root_dir())
        self.current_cfg_path = None
        self._stack_cache = None
        self._stack_cache_path = None
        self._basin_cache = None
        self._basin_cache_path = None
        self._leakage_cache = None
        self._leakage_cache_path = None
        self._active_scope = None
        self._exec_controls = {}
        self._run_buttons = []
        self._pause_buttons = []
        self._stop_buttons = []
        self._progress_bars = []
        self._progress_vars = []
        self._scope_events = {}
        self._progress_cache_last_save = {}
        self._advanced_sections = []
        self._profile_trace_suspended = False

        self._init_path_vars()
        
        self._init_ui()

    def _normpath(self, p: str) -> str:
        try:
            return os.path.normpath(p) if p else p
        except Exception:
            return p

    def _balanced_workers(self) -> int:
        cpu = max(1, os.cpu_count() or 4)
        if cpu == 1:
            return 1
        return max(2, min(6, cpu // 2))

    def _set_packed_visible(self, widget, visible: bool):
        try:
            if visible:
                if not widget.winfo_manager():
                    info = getattr(widget, "_pack_info_cache", None) or {}
                    widget.pack(**info)
            else:
                if widget.winfo_manager() == "pack":
                    try:
                        widget._pack_info_cache = widget.pack_info()
                    except Exception:
                        widget._pack_info_cache = {"fill": tk.X, "pady": 5}
                    widget.pack_forget()
        except Exception:
            pass

    def _register_advanced_section(self, widget):
        if widget is None:
            return
        self._advanced_sections.append(widget)
        self._refresh_advanced_sections()

    def _refresh_advanced_sections(self, *_):
        visible = bool(getattr(self, "var_show_advanced", None) and self.var_show_advanced.get())
        for widget in getattr(self, "_advanced_sections", []):
            self._set_packed_visible(widget, visible)

    def _set_runtime_profile(self, profile: str, apply: bool = False):
        profile = (profile or "balanced").strip().lower()
        if profile not in ("memory-safe", "balanced", "hpc"):
            profile = "balanced"
        self._profile_trace_suspended = True
        try:
            if hasattr(self, "var_runtime_profile"):
                self.var_runtime_profile.set(profile)
        finally:
            self._profile_trace_suspended = False
        if apply:
            self._apply_runtime_profile(profile)

    def _infer_runtime_profile(self) -> str:
        try:
            workers = int(self.var_workers.get()) if hasattr(self, "var_workers") else int(getattr(self.cfg.parallel, "n_workers", 1))
        except Exception:
            workers = 1
        try:
            parallel = bool(self.var_parallel.get()) if hasattr(self, "var_parallel") else bool(getattr(self.cfg.parallel, "enable", False))
        except Exception:
            parallel = False
        try:
            allow_frozen = bool(self.var_allow_frozen_parallel.get()) if hasattr(self, "var_allow_frozen_parallel") else bool(getattr(self.cfg, "perf", {}).get("allow_frozen_parallel", False))
        except Exception:
            allow_frozen = False
        try:
            save_stack = bool(self.var_save_stack_mat.get()) if hasattr(self, "var_save_stack_mat") else bool(getattr(self.cfg.io, "save_stack_mat", True))
        except Exception:
            save_stack = True
        if parallel and workers >= 32:
            return "hpc"
        if (not parallel or workers <= 1) and not save_stack and not allow_frozen:
            return "memory-safe"
        return "balanced"

    def _apply_runtime_profile(self, profile: str):
        if self._profile_trace_suspended:
            return
        profile = (profile or "balanced").strip().lower()
        if profile == "memory-safe":
            settings = {
                "parallel": False,
                "workers": 1,
                "allow_frozen": False,
                "save_stack": False,
                "export_txt": False,
            }
        elif profile == "hpc":
            settings = {
                "parallel": True,
                "workers": 52,
                "allow_frozen": True,
                "save_stack": True,
                "export_txt": False,
            }
        else:
            settings = {
                "parallel": True,
                "workers": self._balanced_workers(),
                "allow_frozen": False,
                "save_stack": True,
                "export_txt": False,
            }
        if hasattr(self, "var_parallel"):
            self.var_parallel.set(settings["parallel"])
        if hasattr(self, "var_workers"):
            self.var_workers.set(settings["workers"])
        if hasattr(self, "var_allow_frozen_parallel"):
            self.var_allow_frozen_parallel.set(settings["allow_frozen"])
        if hasattr(self, "var_save_stack_mat"):
            self.var_save_stack_mat.set(settings["save_stack"])
        if hasattr(self, "var_export_txt"):
            self.var_export_txt.set(settings["export_txt"])
        self._refresh_summary()

    def _init_path_vars(self):
        """Initialize path-related StringVars (kept in a separate dialog)."""
        self.var_gfc = tk.StringVar(value=self._normpath(self.default_cfg.path.GFC))
        self.var_out = tk.StringVar(value=self._normpath(self.default_cfg.path.OUTPUT))
        self.var_ddk = tk.StringVar(value=self._normpath(self.default_cfg.filter.ddk.data_dir))
        self.var_aux = tk.StringVar(value=self._normpath(getattr(self.default_cfg.path, 'AUX', '')))
        self.var_boundary = tk.StringVar(value=self._normpath(getattr(self.default_cfg.path, 'BOUNDARY', '')))

        self.var_c20 = tk.StringVar(value=self._get_lowdeg_file('C20'))
        self.var_deg1 = tk.StringVar(value=self._get_lowdeg_file('DEGREE1'))
        self.var_gia = tk.StringVar(value=self._get_gia_file())

        self.var_mascon_dir = tk.StringVar(value=self._get_mascon_dir())
        self.var_mascon_gad = tk.StringVar(value=self._get_mascon_file('gad_file'))
        self.var_mascon_gia = tk.StringVar(value=self._get_mascon_file('gia_file'))

    def _create_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Config...", command=self.load_config_file)
        file_menu.add_command(label="Edit Current Config", command=self.edit_config_file)
        file_menu.add_command(label="Save Config", command=self.save_config_file)
        file_menu.add_command(label="Save Config As...", command=lambda: self.save_config_file(save_as=True))
        file_menu.add_command(label="Config Paths...", command=lambda: self._show_step("common"))
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Settings...", command=self.open_settings)
        menubar.add_cascade(label="Edit", menu=edit_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)
        
    def _init_ui(self):
        self._create_menu()
        # Top toolbar
        toolbar = ttk.Frame(self.root, padding=5)
        toolbar.pack(fill=tk.X)
        
        ttk.Button(toolbar, text="Load Config File", command=self.load_config_file).pack(side=tk.LEFT)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        ttk.Label(toolbar, text="Cfg:").pack(side=tk.LEFT)
        self.var_cfg_pick = tk.StringVar()
        self.cmb_cfg = ttk.Combobox(
            toolbar,
            textvariable=self.var_cfg_pick,
            values=self._get_cfg_files(),
            width=40,
            state="readonly",
        )
        if self.cmb_cfg["values"]:
            self.var_cfg_pick.set(self.cmb_cfg["values"][0])
        self.cmb_cfg.pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Load Selected", command=self.load_selected_cfg).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Refresh List", command=self.refresh_cfg_list).pack(side=tk.LEFT, padx=5)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
        ttk.Label(toolbar, text="Run Profile:").pack(side=tk.LEFT)
        self.var_runtime_profile = tk.StringVar(value="balanced")
        self.cmb_runtime_profile = ttk.Combobox(
            toolbar,
            textvariable=self.var_runtime_profile,
            values=["memory-safe", "balanced", "hpc"],
            width=14,
            state="readonly",
        )
        self.cmb_runtime_profile.pack(side=tk.LEFT, padx=5)
        self.var_runtime_profile.trace_add("write", lambda *_: self._apply_runtime_profile(self.var_runtime_profile.get()))
        self.var_show_advanced = tk.BooleanVar(value=False)
        self.var_show_advanced.trace_add("write", self._refresh_advanced_sections)
        ttk.Checkbutton(toolbar, text="Show Advanced", variable=self.var_show_advanced).pack(side=tk.LEFT, padx=8)

        # Horizontal section bar (workflow)
        step_bar = ttk.Frame(self.root, padding=(5, 0, 5, 5))
        step_bar.pack(fill=tk.X)
        ttk.Label(step_bar, text="Sections:").pack(side=tk.LEFT, padx=(2, 6))
        self.step_buttons = {}

        # Main PanedWindow (Horizontal): content | summary
        self.main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.content_frame = ttk.Frame(self.main_pane)
        self.summary_frame = ttk.Frame(self.main_pane)
        self.main_pane.add(self.content_frame, weight=4)
        self.main_pane.add(self.summary_frame, weight=2)

        # Content + Run/Logs dock (vertical)
        self.content_pane = ttk.PanedWindow(self.content_frame, orient=tk.VERTICAL)
        self.content_pane.pack(fill=tk.BOTH, expand=True)

        # Content container (one step visible at a time)
        self.step_container = ttk.Frame(self.content_pane)
        self.content_pane.add(self.step_container, weight=3)

        # Run/Logs dock
        self.run_dock = ttk.Frame(self.content_pane)
        self.content_pane.add(self.run_dock, weight=1)
        self.step_frames = {}

        # Step definitions: (key, label, builder)
        self.steps = [
            ("common", "Common Settings", self._build_common_step),
            ("inv", "Inversion & Filters", self._build_inversion_step),
            ("basin", "Basin Analysis", self._build_basin_step),
            ("leak", "Leakage Correction", self._build_leak_step),
            ("plot", "Preview & Plot", self._build_plot_step),
        ]

        for key, label, builder in self.steps:
            btn = ttk.Button(step_bar, text=label, command=lambda k=key: self._show_step(k))
            btn.pack(side=tk.LEFT, padx=4)
            self.step_buttons[key] = btn
            frame = ScrollableFrame(self.step_container)
            builder(frame.inner)
            frame.pack_forget()
            self.step_frames[key] = frame

        # Build Run/Logs dock (always visible)
        self._build_run_step(self.run_dock)

        # Summary panel (right)
        summary_wrap = ttk.LabelFrame(self.summary_frame, text="Summary", padding=6)
        summary_wrap.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.summary_text = scrolledtext.ScrolledText(summary_wrap, state="disabled", height=12, font=("Consolas", 9))
        self.summary_text.pack(fill=tk.BOTH, expand=True)
        btn_refresh = ttk.Button(summary_wrap, text="Refresh Summary", command=self._refresh_summary)
        btn_refresh.pack(anchor="e", pady=6)

        # Show default step
        self._show_step("common")
        self._set_runtime_profile(getattr(self.default_cfg, "perf", {}).get("runtime_profile", self._infer_runtime_profile()))
        # Disable processing UI until a config is selected.
        self._set_config_ready(False)

    def _show_step(self, key: str):
        if key not in self.step_frames:
            return
        for k, frame in self.step_frames.items():
            if k == key:
                frame.pack(fill=tk.BOTH, expand=True)
            else:
                frame.pack_forget()
        self.current_step = key
        self._refresh_summary()

    def _estimate_month_count(self, cfg) -> Optional[int]:
        start = str(getattr(cfg.time, "start_ym", "") or "").strip()
        end = str(getattr(cfg.time, "end_ym", "") or "").strip()
        try:
            ys, ms = [int(x) for x in start.split("-", 1)]
            ye, me = [int(x) for x in end.split("-", 1)]
            total = (ye - ys) * 12 + (me - ms) + 1
            return total if total > 0 else None
        except Exception:
            return None

    def _estimate_stack_memory_mb(self, cfg) -> Tuple[float, int]:
        nlon = max(1, int(round((cfg.grid.lon[1] - cfg.grid.lon[0]) / max(cfg.grid.dlon, 1e-6))) + 1)
        nlat = max(1, int(round((cfg.grid.lat[1] - cfg.grid.lat[0]) / max(cfg.grid.dlat, 1e-6))) + 1)
        nt = self._estimate_month_count(cfg) or 1
        tags = ["RAW"]
        if cfg.filter.gaussian.enable:
            tags.append("GAUSS")
        if cfg.filter.p4m6.enable:
            tags.append("P4M6")
        if cfg.filter.ddk.enable:
            tags.append(cfg.filter.ddk.type)
        if cfg.filter.fan.get("enable", False):
            tags.append("FAN")
        if cfg.filter.gaussian.enable and cfg.filter.p4m6.enable:
            tags.append("GAUSS+P4M6")
        if cfg.filter.p4m6.enable and cfg.filter.ddk.enable:
            tags.append(f"P4M6+{cfg.filter.ddk.type}")
        if cfg.filter.hankel.enable and not getattr(cfg.filter.hankel, "stack_mode", False):
            tags.append("HSAF")
        basin_cfg = cfg.basin if isinstance(cfg.basin, dict) else getattr(cfg.basin, "__dict__", {})
        needs_stack = bool(
            getattr(cfg.io, "save_stack_mat", False)
            or getattr(cfg.io, "return_stacks", False)
            or basin_cfg.get("analysis_enable", False)
            or getattr(cfg.filter.hankel, "stack_mode", False)
        )
        if not needs_stack:
            return 0.0, 0
        count = max(1, len(set(tags)))
        if getattr(cfg.filter.hankel, "stack_mode", False):
            count = max(count, 2)
        bytes_used = nlon * nlat * nt * count * 4
        return bytes_used / (1024 ** 2), count

    def _refresh_summary(self):
        try:
            try:
                self._update_config()
            except Exception:
                pass
            lines = []
            cfg = self.cfg
            lines.append("Project Summary")
            lines.append("-" * 30)
            lines.append(f"GFC: {getattr(cfg.path, 'GFC', '')}")
            lines.append(f"Output: {getattr(cfg.path, 'OUTPUT', '')}")
            ddk_path = getattr(cfg.filter.ddk, 'data_dir', '')
            lines.append(f"DDK: {ddk_path if ddk_path else '(auto)'}")
            lines.append("")
            checks = self._collect_path_checks()
            req_total = 0
            req_ok = 0
            req_missing = []
            opt_missing = []
            for label, path, is_dir, required in checks:
                if not path:
                    continue
                p = Path(path)
                exists = p.is_dir() if is_dir else p.is_file()
                if required:
                    req_total += 1
                    if exists:
                        req_ok += 1
                    else:
                        req_missing.append(label)
                else:
                    if not exists:
                        opt_missing.append(label)
            if req_total:
                lines.append(f"Path checks (required): {req_ok}/{req_total} OK")
                if req_missing:
                    lines.append("Missing required: " + ", ".join(req_missing))
                if opt_missing:
                    lines.append("Optional missing: " + ", ".join(opt_missing))
            lines.append("")
            lines.append(f"Time: {cfg.time.start_ym} -> {cfg.time.end_ym}")
            lines.append(f"Lmax: {cfg.inversion.Lmax}")
            lines.append("")
            filt = []
            if cfg.filter.gaussian.enable:
                filt.append(f"Gaussian({cfg.filter.gaussian.radius_km}km)")
            if cfg.filter.p4m6.enable:
                filt.append("P4M6")
            if cfg.filter.ddk.enable:
                filt.append(cfg.filter.ddk.type)
            if cfg.filter.fan.get("enable", False):
                filt.append("FAN")
            if cfg.filter.hankel.enable:
                filt.append("HSAF")
            lines.append("Filters: " + (", ".join(filt) if filt else "None"))
            lines.append("")
            profile = getattr(self, "var_runtime_profile", None)
            profile_name = profile.get() if profile else self._infer_runtime_profile()
            lines.append(f"Run profile: {profile_name}")
            lines.append(f"Parallel: {cfg.parallel.enable} (workers={cfg.parallel.n_workers})")
            lines.append(f"Frozen parallel: {getattr(cfg, 'perf', {}).get('allow_frozen_parallel', False)}")
            mem_mb, stack_products = self._estimate_stack_memory_mb(cfg)
            if mem_mb > 0:
                risk = "low"
                if mem_mb >= 1536:
                    risk = "high"
                elif mem_mb >= 512:
                    risk = "medium"
                lines.append(f"Estimated stack RAM: {mem_mb:.0f} MB ({stack_products} products, risk={risk})")
            else:
                lines.append("Estimated stack RAM: low (streaming monthly outputs)")
            recs = []
            if cfg.parallel.enable and cfg.parallel.n_workers > 8:
                recs.append("Reduce workers or switch to memory-safe profile.")
            if getattr(cfg.io, "save_stack_mat", False) and mem_mb >= 512:
                recs.append("Disable Save stack MAT if you only need monthly outputs.")
            if getattr(cfg.io, "export_txt", False):
                recs.append("TXT export is slower and heavier; keep it off unless needed.")
            if not req_missing and not recs:
                recs.append("Required paths look good. You can run directly with current defaults.")
            if recs:
                lines.append("")
                lines.append("Recommendations:")
                lines.extend(f"- {item}" for item in recs)

            self.summary_text.configure(state="normal")
            self.summary_text.delete("1.0", tk.END)
            self.summary_text.insert("1.0", "\n".join(lines))
            self.summary_text.configure(state="disabled")
        except Exception:
            pass

    def _build_paths_step(self, parent):
        grp_dirs = ttk.LabelFrame(parent, text="Directories", padding=10)
        grp_dirs.pack(fill=tk.X, pady=5)
        grp_dirs.columnconfigure(1, weight=1)

        def _add_dir_row(row, label, var):
            ttk.Label(grp_dirs, text=label).grid(row=row, column=0, sticky="w", pady=2)
            ttk.Entry(grp_dirs, textvariable=var, width=48).grid(row=row, column=1, padx=5, pady=2, sticky="we")
            ttk.Button(grp_dirs, text="Browse...", command=lambda: self._browse_dir(var)).grid(row=row, column=2, padx=4)

        _add_dir_row(0, "GSM (GFC) Input Directory:", self.var_gfc)
        _add_dir_row(1, "Output Directory:", self.var_out)
        _add_dir_row(2, "DDK Kernel Dir (optional):", self.var_ddk)
        _add_dir_row(3, "Aux Data Directory:", self.var_aux)
        _add_dir_row(4, "Boundary (Shapefile) Dir:", self.var_boundary)
        _add_dir_row(5, "Mascon Dir:", self.var_mascon_dir)

        grp_files = ttk.LabelFrame(parent, text="Key Files", padding=10)
        grp_files.pack(fill=tk.X, pady=5)
        grp_files.columnconfigure(1, weight=1)

        def _add_file_row(row, label, var, fts):
            ttk.Label(grp_files, text=label).grid(row=row, column=0, sticky="w", pady=2)
            ttk.Entry(grp_files, textvariable=var, width=48).grid(row=row, column=1, padx=5, pady=2, sticky="we")
            ttk.Button(grp_files, text="Browse...", command=lambda: self._browse_file(var, filetypes=fts)).grid(row=row, column=2, padx=4)

        _add_file_row(0, "C20 (TN-14) File:", self.var_c20, [("Text files", "*.txt"), ("All files", "*.*")])
        _add_file_row(1, "Degree-1 (TN-13) File:", self.var_deg1, [("Text files", "*.txt"), ("All files", "*.*")])
        _add_file_row(2, "GIA File:", self.var_gia, [("Data files", "*.*"), ("All files", "*.*")])
        _add_file_row(3, "Mascon GAD File:", self.var_mascon_gad, [("NetCDF files", "*.nc;*.nc4"), ("All files", "*.*")])
        _add_file_row(4, "Mascon GIA File:", self.var_mascon_gia, [("NetCDF files", "*.nc;*.nc4"), ("All files", "*.*")])

        btns = ttk.Frame(parent)
        btns.pack(fill=tk.X, pady=6)
        ttk.Button(btns, text="Check Paths", command=self._validate_paths).pack(side=tk.LEFT)
        ttk.Button(btns, text="Open Output Folder", command=self.open_output_folder).pack(side=tk.LEFT, padx=6)

    def _collect_path_checks(self):
        try:
            self._update_config()
        except Exception:
            pass
        cfg = self.cfg

        def _as_dict(obj):
            return obj if isinstance(obj, dict) else getattr(obj, "__dict__", {})

        lowdeg = _as_dict(getattr(cfg.inversion, "lowdeg", {}))
        gia = _as_dict(getattr(cfg.inversion, "gia", {}))
        basin_cfg = _as_dict(getattr(cfg, "basin", {}))
        ref_cfg = _as_dict(getattr(cfg, "reference", {}))

        items = []

        def _add(label, path, is_dir, required):
            if path:
                items.append((label, path, is_dir, required))

        # Required basics
        _add("GFC dir", self.var_gfc.get(), True, True)
        _add("Output dir", self.var_out.get(), True, True)

        # Low-degree replacements
        if lowdeg.get("enable", False):
            if lowdeg.get("replace_C20", True):
                _add("C20 file", self.var_c20.get(), False, True)
            if lowdeg.get("replace_C10", True):
                _add("Degree-1 file", self.var_deg1.get(), False, True)

        # GIA correction
        if gia.get("enable", False):
            _add("GIA file", self.var_gia.get(), False, True)

        # Basin analysis boundary
        if basin_cfg.get("analysis_enable", False) and hasattr(self, "var_basin_file"):
            _add("Basin boundary", self.var_basin_file.get(), False, True)

        # Optional supporting paths
        _add("Aux dir", self.var_aux.get(), True, False)
        _add("Boundary dir", self.var_boundary.get(), True, False)

        # Mascon reference (optional)
        if str(ref_cfg.get("type", "")).lower() == "mascon":
            _add("Mascon dir", self.var_mascon_dir.get(), True, False)
            undo_cfg = _as_dict(ref_cfg.get("mascon_undo", {}))
            if undo_cfg.get("enable", False):
                _add("Mascon GAD file", self.var_mascon_gad.get(), False, False)
                _add("Mascon GIA file", self.var_mascon_gia.get(), False, False)

        return items

    def _validate_paths(self):
        items = self._collect_path_checks()
        missing_required = []
        missing_optional = []
        for label, path, is_dir, required in items:
            p = Path(path)
            exists = p.is_dir() if is_dir else p.is_file()
            if not exists:
                if required:
                    missing_required.append(f"{label}: {path}")
                else:
                    missing_optional.append(f"{label}: {path}")
        if missing_required:
            msg = "Missing/invalid required paths:\n" + "\n".join(missing_required)
            if missing_optional:
                msg += "\n\nOptional missing:\n" + "\n".join(missing_optional)
            messagebox.showwarning("Paths", msg)
        elif missing_optional:
            messagebox.showinfo("Paths", "Required paths OK.\nOptional missing:\n" + "\n".join(missing_optional))
        else:
            messagebox.showinfo("Paths", "All required paths look OK.")

    def _build_common_step(self, parent):
        pane = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(pane)
        right = ttk.Frame(pane)
        pane.add(left, weight=3)
        pane.add(right, weight=2)
        self._build_paths_step(left)
        self._build_time_grid_step(right)

    def _build_time_grid_step(self, parent):
        # Time
        grp_time = ttk.LabelFrame(parent, text="Time Range", padding=10)
        grp_time.pack(fill=tk.X, pady=5)

        self.var_auto_time = tk.BooleanVar(value=self.default_cfg.time.auto_detect_gfc)
        ttk.Checkbutton(grp_time, text="Auto-detect from files", variable=self.var_auto_time, command=self._toggle_time_inputs).grid(row=0, column=0, columnspan=3, sticky="w")

        ttk.Label(grp_time, text="Start (YYYY-MM):").grid(row=1, column=0, sticky="w")
        self.var_start = tk.StringVar(value=self.default_cfg.time.start_ym)
        self.ent_start = ttk.Entry(grp_time, textvariable=self.var_start, width=15)
        self.ent_start.grid(row=1, column=1, sticky="w", padx=5)

        ttk.Label(grp_time, text="End (YYYY-MM):").grid(row=1, column=2, sticky="w")
        self.var_end = tk.StringVar(value=self.default_cfg.time.end_ym)
        self.ent_end = ttk.Entry(grp_time, textvariable=self.var_end, width=15)
        self.ent_end.grid(row=1, column=3, sticky="w", padx=5)

        self._toggle_time_inputs()

        # Grid
        grp_grid = ttk.LabelFrame(parent, text="Grid Settings", padding=10)
        grp_grid.pack(fill=tk.X, pady=5)

        lon_min, lon_max = self.default_cfg.grid.lon
        lat_min, lat_max = self.default_cfg.grid.lat
        self.var_lon_min = tk.DoubleVar(value=lon_min)
        self.var_lon_max = tk.DoubleVar(value=lon_max)
        self.var_lat_min = tk.DoubleVar(value=lat_min)
        self.var_lat_max = tk.DoubleVar(value=lat_max)
        self.var_dlon = tk.DoubleVar(value=self.default_cfg.grid.dlon)
        self.var_dlat = tk.DoubleVar(value=self.default_cfg.grid.dlat)

        ttk.Label(grp_grid, text="Lon min/max:").grid(row=0, column=0, sticky="w")
        ttk.Entry(grp_grid, textvariable=self.var_lon_min, width=8).grid(row=0, column=1, padx=2)
        ttk.Entry(grp_grid, textvariable=self.var_lon_max, width=8).grid(row=0, column=2, padx=2)
        ttk.Label(grp_grid, text="Lat min/max:").grid(row=0, column=3, sticky="w", padx=6)
        ttk.Entry(grp_grid, textvariable=self.var_lat_min, width=8).grid(row=0, column=4, padx=2)
        ttk.Entry(grp_grid, textvariable=self.var_lat_max, width=8).grid(row=0, column=5, padx=2)
        ttk.Label(grp_grid, text="dLon/dLat:").grid(row=1, column=0, sticky="w")
        ttk.Entry(grp_grid, textvariable=self.var_dlon, width=8).grid(row=1, column=1, padx=2)
        ttk.Entry(grp_grid, textvariable=self.var_dlat, width=8).grid(row=1, column=2, padx=2)

        # Outputs and performance moved to dedicated step

    def _build_output_perf_step(self, parent):
        # I/O outputs
        grp_io = ttk.LabelFrame(parent, text="I/O Outputs", padding=10)
        grp_io.pack(fill=tk.X, pady=5)
        grp_io.columnconfigure(1, weight=1)
        self.var_save_monthly_mat = tk.BooleanVar(value=self.default_cfg.io.save_monthly_mat)
        self.var_save_stack_mat = tk.BooleanVar(value=self.default_cfg.io.save_stack_mat)
        self.var_export_txt = tk.BooleanVar(value=self.default_cfg.io.export_txt)
        self.var_txt_format = tk.StringVar(value=getattr(self.default_cfg.io, 'txt_format', 'lonlatval'))

        ttk.Label(grp_io, text="Output Directory:").grid(row=0, column=0, sticky="w")
        ttk.Entry(grp_io, textvariable=self.var_out, width=50).grid(row=0, column=1, padx=5, pady=2, sticky="we")
        ttk.Button(grp_io, text="Browse...", command=lambda: self._browse_dir(self.var_out)).grid(row=0, column=2, padx=4)

        ttk.Checkbutton(grp_io, text="Save monthly MAT", variable=self.var_save_monthly_mat).grid(row=1, column=0, sticky="w", padx=4)
        ttk.Checkbutton(grp_io, text="Save stack MAT", variable=self.var_save_stack_mat).grid(row=1, column=1, sticky="w", padx=4)
        ttk.Checkbutton(grp_io, text="Export TXT", variable=self.var_export_txt).grid(row=1, column=2, sticky="w", padx=4)
        ttk.Label(grp_io, text="TXT format:").grid(row=1, column=3, sticky="w", padx=6)
        ttk.Entry(grp_io, textvariable=self.var_txt_format, width=12).grid(row=1, column=4, padx=4)

        grp_profile = ttk.LabelFrame(parent, text="Runtime Strategy", padding=10)
        grp_profile.pack(fill=tk.X, pady=5)
        grp_profile.columnconfigure(1, weight=1)
        ttk.Label(grp_profile, text="Profile:").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            grp_profile,
            textvariable=self.var_runtime_profile,
            values=["memory-safe", "balanced", "hpc"],
            state="readonly",
            width=14,
        ).grid(row=0, column=1, sticky="w", padx=5)
        ttk.Label(
            grp_profile,
            text="memory-safe: lowest RAM, balanced: desktop default, hpc: 52 workers",
            foreground="gray",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))

        grp_perf = ttk.LabelFrame(parent, text="Advanced Performance", padding=10)
        grp_perf.pack(fill=tk.X, pady=5)

        self.var_parallel = tk.BooleanVar(value=self.default_cfg.parallel.enable)
        self.chk_parallel = ttk.Checkbutton(grp_perf, text="Enable Parallel Processing", variable=self.var_parallel)
        self.chk_parallel.grid(row=0, column=0, sticky="w")

        ttk.Label(grp_perf, text="Workers:").grid(row=0, column=1, padx=10)
        self.var_workers = tk.IntVar(value=self.default_cfg.parallel.n_workers)
        ttk.Spinbox(grp_perf, from_=1, to=128, textvariable=self.var_workers, width=5).grid(row=0, column=2)

        self.var_allow_frozen_parallel = tk.BooleanVar(value=getattr(self.default_cfg, 'perf', {}).get('allow_frozen_parallel', False))
        ttk.Checkbutton(grp_perf, text="Allow parallel in EXE", variable=self.var_allow_frozen_parallel).grid(row=1, column=0, columnspan=3, sticky="w", pady=4)

        if getattr(sys, 'frozen', False):
            warn_lbl = ttk.Label(grp_perf, text="(Standalone EXE: parallel may spawn extra processes)", foreground="gray")
            warn_lbl.grid(row=0, column=3, padx=10)
            def _toggle_frozen_parallel(*_):
                if self.var_allow_frozen_parallel.get():
                    self.chk_parallel.config(state='normal')
                else:
                    self.var_parallel.set(False)
                    self.chk_parallel.config(state='disabled')
            self.var_allow_frozen_parallel.trace_add("write", _toggle_frozen_parallel)
            _toggle_frozen_parallel()
        self._register_advanced_section(grp_perf)

    def _build_inversion_step(self, parent):
        grp_in = ttk.LabelFrame(parent, text="Input (from Common Settings)", padding=10)
        grp_in.pack(fill=tk.X, pady=5)
        grp_in.columnconfigure(1, weight=1)
        ttk.Label(grp_in, text="GFC Directory:").grid(row=0, column=0, sticky="w")
        ttk.Entry(grp_in, textvariable=self.var_gfc, width=50, state="readonly").grid(row=0, column=1, padx=5, pady=2, sticky="we")
        ttk.Label(grp_in, text="DDK Kernel Dir (optional):").grid(row=1, column=0, sticky="w")
        ttk.Entry(grp_in, textvariable=self.var_ddk, width=50, state="readonly").grid(row=1, column=1, padx=5, pady=2, sticky="we")
        ttk.Label(grp_in, text="Low-degree (C20/DEG1):").grid(row=2, column=0, sticky="w")
        ttk.Entry(grp_in, textvariable=self.var_c20, width=50, state="readonly").grid(row=2, column=1, padx=5, pady=2, sticky="we")
        ttk.Entry(grp_in, textvariable=self.var_deg1, width=50, state="readonly").grid(row=3, column=1, padx=5, pady=2, sticky="we")
        ttk.Button(grp_in, text="Edit in Common Settings", command=lambda: self._show_step("common")).grid(row=0, column=2, rowspan=2, padx=6)

        self._build_output_perf_step(parent)
        self._build_filters_tab(parent)
        self._build_exec_controls(parent, scope="filters", run_label="Run Inversion/Filters", run_cmd=self.on_run)

    def _build_basin_step(self, parent):
        self._build_basin_tab(parent)
        self._build_exec_controls(parent, scope="basin", run_label="Run Basin Analysis", run_cmd=self.on_run_basin, with_pause=True)

    def _build_leak_step(self, parent):
        self._build_leakage_tab(parent)
        self._build_exec_controls(parent, scope="leakage", run_label="Run Leakage Correction", run_cmd=self.on_run_leakage, with_pause=True)

    def _build_plot_step(self, parent):
        self._build_plot_tab(parent)
        btns = ttk.Frame(parent)
        btns.pack(fill=tk.X, pady=6)
        ttk.Button(btns, text="Open Plot Window", command=self._open_plot_window).pack(side=tk.LEFT)
        ttk.Button(btns, text="Close Plot Window", command=self._close_plot_window).pack(side=tk.LEFT, padx=6)

    def _build_exec_controls(self, parent, scope: str, run_label: str, run_cmd, with_pause: bool = True):
        frame = ttk.LabelFrame(parent, text="Execution", padding=5)
        frame.pack(fill=tk.X, pady=6)

        btn_run = ttk.Button(frame, text=run_label, command=run_cmd, width=20)
        btn_run.pack(side=tk.LEFT, padx=5)

        btn_pause = None
        btn_stop = None
        if with_pause:
            btn_pause = ttk.Button(frame, text="Pause", command=self.on_pause, width=12, state='disabled')
            btn_pause.pack(side=tk.LEFT, padx=5)
            btn_stop = ttk.Button(frame, text="Stop", command=self.on_stop, width=12, state='disabled')
            btn_stop.pack(side=tk.LEFT, padx=5)

        progress = ttk.Progressbar(frame, mode='determinate', maximum=100.0)
        progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        progress_var = tk.StringVar(value="0%")
        ttk.Label(frame, textvariable=progress_var, width=6).pack(side=tk.LEFT, padx=4)

        self._exec_controls[scope] = {
            "frame": frame,
            "run": btn_run,
            "pause": btn_pause,
            "stop": btn_stop,
            "progress": progress,
            "progress_var": progress_var,
        }
        self._run_buttons.append(btn_run)
        if btn_pause is not None:
            self._pause_buttons.append(btn_pause)
        if btn_stop is not None:
            self._stop_buttons.append(btn_stop)
        self._progress_bars.append(progress)
        self._progress_vars.append(progress_var)

    def _build_run_step(self, parent):
        pane = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        pane.pack(fill=tk.BOTH, expand=True)

        control_frame = ttk.LabelFrame(pane, text="Global Execution", padding=5)
        pane.add(control_frame, weight=1)
        self.btn_run_all = ttk.Button(control_frame, text="Run All", command=self.on_run_all, width=12)
        self.btn_run_all.pack(side=tk.LEFT, padx=5)

        all_pause = threading.Event()
        all_stop = threading.Event()
        self._scope_events["all"] = {"pause": all_pause, "stop": all_stop}
        self.pause_event = all_pause
        self.stop_event = all_stop
        self.btn_pause = ttk.Button(control_frame, text="Pause", command=self.on_pause, width=12, state='disabled')
        self.btn_pause.pack(side=tk.LEFT, padx=5)

        self.btn_stop = ttk.Button(control_frame, text="Stop", command=self.on_stop, width=12, state='disabled')
        self.btn_stop.pack(side=tk.LEFT, padx=5)

        self.progress = ttk.Progressbar(control_frame, mode='determinate', maximum=100.0)
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        self.progress_var = tk.StringVar(value="0%")
        ttk.Label(control_frame, textvariable=self.progress_var, width=6).pack(side=tk.LEFT, padx=4)
        self._exec_controls["all"] = {
            "frame": control_frame,
            "run": self.btn_run_all,
            "pause": self.btn_pause,
            "stop": self.btn_stop,
            "progress": self.progress,
            "progress_var": self.progress_var,
        }
        self._run_buttons.append(self.btn_run_all)
        self._pause_buttons.append(self.btn_pause)
        self._stop_buttons.append(self.btn_stop)
        self._progress_bars.append(self.progress)
        self._progress_vars.append(self.progress_var)

        log_frame = ttk.LabelFrame(pane, text="Logs", padding=5)
        pane.add(log_frame, weight=4)

        self.log_text = scrolledtext.ScrolledText(log_frame, state='disabled', height=10, font=('Consolas', 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)

        log_btns = ttk.Frame(log_frame)
        log_btns.pack(fill=tk.X, pady=4)
        btn_export = ttk.Button(log_btns, text="Export Log", command=self.export_log)
        btn_export.pack(side=tk.LEFT)
        btn_open_log = ttk.Button(log_btns, text="Open Log Folder", command=self.open_log_folder)
        btn_open_log.pack(side=tk.LEFT, padx=6)
        btn_open_out = ttk.Button(log_btns, text="Open Output Folder", command=self.open_output_folder)
        btn_open_out.pack(side=tk.LEFT, padx=6)
        btn_clear_log = ttk.Button(log_btns, text="Clear Logs", command=self.clear_logs)
        btn_clear_log.pack(side=tk.LEFT, padx=6)
        btn_clear_cache = ttk.Button(log_btns, text="Clear Progress Cache", command=self.clear_progress_cache)
        btn_clear_cache.pack(side=tk.LEFT, padx=6)
        self._log_buttons = [btn_export, btn_open_log, btn_open_out, btn_clear_log, btn_clear_cache]

        self.log_text.tag_config("stdout", foreground="black")
        self.log_text.tag_config("stderr", foreground="red")

    def _get_scope_events(self, scope: Optional[str] = None):
        key = scope or self._active_scope or "all"
        events = self._scope_events.get(key)
        if not isinstance(events, dict):
            events = {"pause": threading.Event(), "stop": threading.Event()}
            self._scope_events[key] = events
        return events["pause"], events["stop"]

    def _linked_scopes(self, scope: str):
        scopes = [scope]
        if scope != "all" and "all" in self._exec_controls:
            scopes.append("all")
        return scopes

    def _init_plot_panel(self, parent):
        plot_wrap = ttk.LabelFrame(parent, text="Plot View", padding=5)
        plot_wrap.pack(fill=tk.BOTH, expand=True)
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
            from matplotlib.figure import Figure
            self.plot_fig = Figure(figsize=(6, 4), dpi=100)
            # Fixed layout for consistent sizing
            # Default rects; adjusted per-projection at draw time
            self._plot_axes_rect = [0.06, 0.08, 0.74, 0.86]
            self._plot_cax_rect = [0.83, 0.18, 0.022, 0.64]
            self.plot_ax = self.plot_fig.add_axes(self._plot_axes_rect)
            self.plot_canvas = FigureCanvasTkAgg(self.plot_fig, master=plot_wrap)
            self.plot_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            self.plot_toolbar = NavigationToolbar2Tk(self.plot_canvas, plot_wrap)
            self.plot_toolbar.update()
            plot_wrap.bind("<Configure>", self._resize_plot_canvas)
        except Exception as e:
            ttk.Label(plot_wrap, text=f"Plot panel init failed: {e}", foreground="red").pack(fill=tk.BOTH, expand=True)
        self._plot_wrap = plot_wrap

    def _open_plot_window(self):
        try:
            if getattr(self, "plot_window", None) is not None:
                if self.plot_window.winfo_exists():
                    self.plot_window.lift()
                    return
        except Exception:
            pass
        win = tk.Toplevel(self.root)
        win.title("Plot View")
        win.geometry("900x700")
        win.protocol("WM_DELETE_WINDOW", self._close_plot_window)
        self.plot_window = win
        self._init_plot_panel(win)

    def _close_plot_window(self):
        try:
            if getattr(self, "plot_window", None) is not None:
                try:
                    if self.plot_window.winfo_exists():
                        self.plot_window.destroy()
                except Exception:
                    pass
        finally:
            self.plot_window = None
            self.plot_fig = None
            self.plot_ax = None
            self.plot_canvas = None
            self.plot_toolbar = None
            self._plot_wrap = None

    def _ensure_plot_panel(self):
        if hasattr(self, "plot_fig") and self.plot_fig is not None:
            return True
        self._open_plot_window()
        return hasattr(self, "plot_fig") and self.plot_fig is not None

    def _resize_plot_canvas(self, event):
        if not hasattr(self, "plot_fig"):
            return
        try:
            w, h = event.width, event.height
            if w <= 10 or h <= 10:
                return
            self.plot_fig.set_size_inches(w / self.plot_fig.dpi, h / self.plot_fig.dpi, forward=False)
            if hasattr(self, "plot_canvas"):
                self.plot_canvas.draw_idle()
        except Exception:
            pass

    def _set_config_ready(self, ready: bool):
        self._config_ready = bool(ready)
        tab_state = "normal" if ready else "disabled"
        for key, btn in getattr(self, "step_buttons", {}).items():
            state = "normal" if key in ("common", "plot") else tab_state
            try:
                btn.config(state=state)
            except Exception:
                pass
        try:
            for btn in getattr(self, "_run_buttons", []):
                btn.config(state=tab_state)
            if hasattr(self, "btn_run_all"):
                self.btn_run_all.config(state=tab_state)
        except Exception:
            pass
        if not ready:
            try:
                self.btn_pause.config(state="disabled")
                self.btn_stop.config(state="disabled")
            except Exception:
                pass
        for b in getattr(self, "_log_buttons", []):
            try:
                b.config(state=tab_state)
            except Exception:
                pass

    def _get_cfg_files(self):
        if self.cfg_dir.exists():
            return [p.name for p in sorted(self.cfg_dir.glob("*.json"))]
        return []

    def refresh_cfg_list(self):
        self.cmb_cfg.configure(values=self._get_cfg_files())

    def load_selected_cfg(self):
        name = self.var_cfg_pick.get().strip()
        if not name:
            messagebox.showwarning("Config", "Please select a config JSON from the list.")
            return
        path = self.cfg_dir / name
        if not path.exists():
            messagebox.showerror("Config", f"Config not found: {path}")
            return
        self.load_config_file(path_override=path)
        
    def _build_general_tab(self, parent):
        tab_build_common_tab(self, parent)

    def _build_basin_tab(self, parent):
        tab_build_basin_tab(self, parent)

    def _build_leakage_tab(self, parent):
        tab_build_leakage_tab(self, parent)

    def _refresh_lrc_operator_params(self):
        if not hasattr(self, "_lrc_param_frames"):
            return
        raw = str(self.var_lrc_sf_method.get() if hasattr(self, "var_lrc_sf_method") else "Auto").strip().upper().replace(" ", "_")
        if raw == "HANKEL":
            raw = "HSAF"
        path = self.var_lrc_input.get().strip() if hasattr(self, "var_lrc_input") else ""
        meta = self._leakage_cache.get("meta", {}) if isinstance(getattr(self, "_leakage_cache", None), dict) else {}
        inferred, _ = self._infer_leakage_method_from_input(path, meta)
        effective = inferred if raw in ("", "AUTO") else raw
        if effective and effective.startswith("DDK"):
            effective = "DDK4"

        for f in set(self._lrc_param_frames.values()):
            try:
                f.pack_forget()
            except Exception:
                pass
        frm = self._lrc_param_frames.get(effective)
        if frm is not None:
            frm.pack(fill=tk.X, anchor="w")

        if not hasattr(self, "_lrc_operator_hint"):
            return
        if raw in ("", "AUTO"):
            if inferred:
                self._lrc_operator_hint.set(f"Operator hint: auto-detected as {inferred}")
            else:
                self._lrc_operator_hint.set("Operator hint: Auto (fallback Gaussian)")
        else:
            self._lrc_operator_hint.set(f"Operator hint: using {effective or raw}")

    def _refresh_lrc_layout(self):
        method = str(self.var_lrc_method.get() if hasattr(self, "var_lrc_method") else "FM").upper()
        scope = str(self.var_lrc_scope.get() if hasattr(self, "var_lrc_scope") else "global").lower()
        sf_auto = bool(self.var_lrc_sf_auto.get()) if hasattr(self, "var_lrc_sf_auto") else False

        # Boundary only required for regional.
        bstate = "normal" if scope == "regional" else "disabled"
        for w in (
            getattr(self, "_lrc_boundary_label", None),
            getattr(self, "_lrc_boundary_entry", None),
            getattr(self, "_lrc_boundary_btn", None),
        ):
            if w is not None:
                try:
                    w.configure(state=bstate)
                except Exception:
                    pass

        # Only SF/FM top-level options; operator shown for FM or SF-auto.
        op_needed = (method == "FM") or (method == "SF" and sf_auto)
        if hasattr(self, "_lrc_operator_group"):
            if op_needed and not self._lrc_operator_group.winfo_ismapped():
                self._lrc_operator_group.pack(fill=tk.X, pady=6)
            elif (not op_needed) and self._lrc_operator_group.winfo_ismapped():
                self._lrc_operator_group.pack_forget()
        if hasattr(self, "_lrc_sf_group"):
            if method == "SF" and not self._lrc_sf_group.winfo_ismapped():
                self._lrc_sf_group.pack(fill=tk.X, pady=6)
            elif method != "SF" and self._lrc_sf_group.winfo_ismapped():
                self._lrc_sf_group.pack_forget()
        if hasattr(self, "_lrc_fm_group"):
            if method == "FM" and not self._lrc_fm_group.winfo_ismapped():
                self._lrc_fm_group.pack(fill=tk.X, pady=6)
            elif method != "FM" and self._lrc_fm_group.winfo_ismapped():
                self._lrc_fm_group.pack_forget()

        self._refresh_lrc_operator_params()

    def _build_filters_tab(self, parent):
        tab_build_filters_tab(self, parent)

    def _build_plot_tab(self, parent):
        tab_build_plot_tab(self, parent)
        
    def _browse_dir(self, var):
        d = filedialog.askdirectory()
        if d:
            var.set(d)

    def _browse_file(self, var, filetypes=None):
        f = filedialog.askopenfilename(filetypes=filetypes or [("All files", "*.*")])
        if f:
            var.set(f)

    def _browse_save_path(self):
        f = filedialog.asksaveasfilename(
            defaultextension=f".{self.var_save_fmt.get() if hasattr(self, 'var_save_fmt') else 'png'}",
            filetypes=[("Image files", "*.png;*.jpg;*.tif;*.pdf"), ("All files", "*.*")]
        )
        if f:
            self.var_save_path.set(f)

    def _open_paths_dialog(self, title: str = "Config Paths"):
        """Open a dialog to edit file/directory paths for the config."""
        # Snapshot current values for cancel
        vars_map = {
            "GFC": self.var_gfc,
            "OUTPUT": self.var_out,
            "DDK": self.var_ddk,
            "AUX": self.var_aux,
            "BOUNDARY": self.var_boundary,
            "C20": self.var_c20,
            "DEGREE1": self.var_deg1,
            "GIA": self.var_gia,
            "MASCON_DIR": self.var_mascon_dir,
            "MASCON_GAD": self.var_mascon_gad,
            "MASCON_GIA": self.var_mascon_gia,
        }
        old = {k: v.get() for k, v in vars_map.items()}

        win = tk.Toplevel(self.root)
        win.title(title)
        win.transient(self.root)
        win.grab_set()

        frame = ttk.Frame(win, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        row = 0
        def _add_row(label, var, browse_fn, filetypes=None):
            nonlocal row
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=2)
            ttk.Entry(frame, textvariable=var, width=60).grid(row=row, column=1, padx=5, pady=2, sticky="we")
            ttk.Button(frame, text="Browse...", command=lambda: browse_fn(var, filetypes)).grid(row=row, column=2, padx=4)
            row += 1

        def _browse_file_ft(var, fts=None):
            self._browse_file(var, filetypes=fts)

        frame.columnconfigure(1, weight=1)
        _add_row("GSM (GFC) Input Directory:", self.var_gfc, lambda v, _ft: self._browse_dir(v))
        _add_row("Output Directory:", self.var_out, lambda v, _ft: self._browse_dir(v))
        _add_row("DDK Kernel Dir (optional):", self.var_ddk, lambda v, _ft: self._browse_dir(v))
        _add_row("Aux Data Directory:", self.var_aux, lambda v, _ft: self._browse_dir(v))
        _add_row("Boundary (Shapefile) Dir:", self.var_boundary, lambda v, _ft: self._browse_dir(v))
        _add_row("C20 (TN-14) File:", self.var_c20, _browse_file_ft, [("Text files", "*.txt"), ("All files", "*.*")])
        _add_row("Degree-1 (TN-13) File:", self.var_deg1, _browse_file_ft, [("Text files", "*.txt"), ("All files", "*.*")])
        _add_row("GIA File:", self.var_gia, _browse_file_ft, [("Data files", "*.*"), ("All files", "*.*")])
        _add_row("Mascon Dir:", self.var_mascon_dir, lambda v, _ft: self._browse_dir(v))
        _add_row("Mascon GAD File:", self.var_mascon_gad, _browse_file_ft, [("NetCDF files", "*.nc;*.nc4"), ("All files", "*.*")])
        _add_row("Mascon GIA File:", self.var_mascon_gia, _browse_file_ft, [("NetCDF files", "*.nc;*.nc4"), ("All files", "*.*")])

        btns = ttk.Frame(frame)
        btns.grid(row=row, column=0, columnspan=3, pady=(8, 0), sticky="e")

        def _cancel():
            for k, v in vars_map.items():
                try:
                    v.set(old.get(k, ""))
                except Exception:
                    pass
            win.destroy()

        ttk.Button(btns, text="Cancel", command=_cancel).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btns, text="OK", command=win.destroy).pack(side=tk.RIGHT)
            
    def _toggle_time_inputs(self):
        state = 'disabled' if self.var_auto_time.get() else 'normal'
        self.ent_start.config(state=state)
        self.ent_end.config(state=state)

    def _load_hsaf_defaults(self):
        """Load default HSAF parameters based on selected variant."""
        try:
            params = getattr(self.default_cfg.filter.hankel, 'params', {}) or {}
            # Allow variant-specific defaults if provided in config
            if self.var_hsaf_variant.get() == "adaptive":
                params = getattr(self.default_cfg.filter.hankel, 'adaptive_params', params) or params
            self.var_hsaf_N.set(params.get('N', 30))
            self.var_hsaf_P.set(params.get('P', 10))
            self.var_hsaf_K.set(params.get('K', 6))
            self.var_hsaf_J.set(params.get('J', 1))
            if self.var_hsaf_variant.get() == "adaptive":
                # propagate defaults into adaptive zones
                for v in getattr(self, "_hsaf_ad_vars", []):
                    v["N"].set(str(params.get("N", 30)))
                    v["P"].set(str(params.get("P", 10)))
                    v["K"].set(str(params.get("K", 6)))
                    v["J"].set(str(params.get("J", 1)))
        except Exception:
            pass

    def _toggle_hsaf_variant(self):
        try:
            adaptive = self.var_hsaf_variant.get() == "adaptive"
            state = "normal" if adaptive else "disabled"
            for w in getattr(self, "_hsaf_ad_widgets", []):
                try:
                    w.configure(state=state)
                except Exception:
                    pass
            # Basic params should be editable only in global mode
            basic_state = "disabled" if adaptive else "normal"
            for w in getattr(self, "_hsaf_basic_widgets", []):
                try:
                    w.configure(state=basic_state)
                except Exception:
                    pass
        except Exception:
            pass

    def _apply_adaptive_zones(self, zones):
        try:
            if not zones:
                return
            for i, z in enumerate(zones[:len(self._hsaf_ad_vars)]):
                v = self._hsaf_ad_vars[i]
                lat_range = z.get("lat_range", ["", ""])
                params = z.get("params", {})
                v["lat_min"].set(str(lat_range[0]))
                v["lat_max"].set(str(lat_range[1]))
                v["N"].set(str(params.get("N", v["N"].get())))
                v["P"].set(str(params.get("P", v["P"].get())))
                v["K"].set(str(params.get("K", v["K"].get())))
                v["J"].set(str(params.get("J", v["J"].get())))
        except Exception:
            pass

    load_config_file = service_load_config_file

    _collect_config_dict = service_collect_config_dict

    
    def edit_config_file(self):
        path = None
        try:
            if self.current_cfg_path:
                path = self.current_cfg_path
            else:
                pick = self.var_cfg_pick.get().strip() if hasattr(self, 'var_cfg_pick') else ''
                if pick:
                    path = self.cfg_dir / pick
        except Exception:
            path = None
        if not path:
            messagebox.showwarning("Config", "No config selected to edit.")
            return
        try:
            self._open_paths_dialog(title="Config Paths (Edit)")
        except Exception:
            pass
        try:
            os.startfile(path)
        except Exception as e:
            messagebox.showerror("Config", f"Failed to open config: {e}")

    def save_config_file(self, save_as=False):
        try:
            self._open_paths_dialog(title="Config Paths (Save)")
        except Exception:
            pass
        try:
            cfg_dict = self._collect_config_dict()
        except Exception as e:
            messagebox.showerror("Config", f"Failed to build config: {e}")
            return
        path = None
        if not save_as and self.current_cfg_path:
            path = str(self.current_cfg_path)
        else:
            path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialdir=self.cfg_dir if self.cfg_dir.exists() else Path.cwd() / "cfg",
            )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg_dict, f, indent=2)
            self.current_cfg_path = Path(path)
            self.refresh_cfg_list()
            messagebox.showinfo("Config Saved", f"Saved configuration to {path}")
        except Exception as e:
            messagebox.showerror("Config", f"Failed to save config: {e}")

    def open_settings(self):
        messagebox.showinfo("Settings", "Settings dialog is not implemented yet.")

    def show_about(self):
        messagebox.showinfo("About", "GRACE Level-2 Pipeline GUI\nPython Edition")

    on_run = service_on_run

    def _check_pause_stop(self, scope: Optional[str] = None) -> bool:
        pause_ev, stop_ev = self._get_scope_events(scope)
        if stop_ev.is_set():
            return False
        while pause_ev.is_set():
            time.sleep(0.2)
            if stop_ev.is_set():
                return False
        return True

    def _set_busy_scope(self, scope: str, *, indeterminate: bool = True):
        self._active_scope = scope
        pause_ev, stop_ev = self._get_scope_events(scope)
        self.pause_event = pause_ev
        self.stop_event = stop_ev
        try:
            pause_ev.clear()
            stop_ev.clear()
        except Exception:
            pass
        # Disable run buttons
        for btn in getattr(self, "_run_buttons", []):
            try:
                btn.config(state='disabled')
            except Exception:
                pass
        if hasattr(self, "btn_run_all"):
            try:
                self.btn_run_all.config(state='disabled')
            except Exception:
                pass
        # Enable pause/stop only for current scope and global scope.
        for btn in getattr(self, "_pause_buttons", []):
            try:
                btn.config(state='disabled', text='Pause')
            except Exception:
                pass
        for btn in getattr(self, "_stop_buttons", []):
            try:
                btn.config(state='disabled')
            except Exception:
                pass
        for scope_key in self._linked_scopes(scope):
            ctrl = getattr(self, "_exec_controls", {}).get(scope_key)
            if not ctrl:
                continue
            try:
                btn_pause = ctrl.get("pause")
                btn_stop = ctrl.get("stop")
                bar = ctrl.get("progress")
                var = ctrl.get("progress_var")
                if btn_pause is not None:
                    btn_pause.config(state='normal', text='Pause')
                if btn_stop is not None:
                    btn_stop.config(state='normal')
                if bar is not None:
                    if indeterminate:
                        bar.config(mode='indeterminate')
                        bar.start(10)
                    else:
                        bar.stop()
                        bar.config(mode='determinate', maximum=100.0)
                        bar['value'] = 0
                if var is not None:
                    var.set("..." if indeterminate else "0%")
            except Exception:
                pass

    def _clear_busy_scope(self, scope: str):
        if getattr(self, "_active_scope", None) == scope:
            self._active_scope = None
        for scope_key in self._linked_scopes(scope):
            ctrl = getattr(self, "_exec_controls", {}).get(scope_key)
            if not ctrl:
                continue
            try:
                btn_pause = ctrl.get("pause")
                btn_stop = ctrl.get("stop")
                bar = ctrl.get("progress")
                var = ctrl.get("progress_var")
                if btn_pause is not None:
                    btn_pause.config(state='disabled', text='Pause')
                if btn_stop is not None:
                    btn_stop.config(state='disabled')
                if bar is not None:
                    bar.stop()
                    bar.config(mode='determinate')
                    bar['value'] = 0
                if var is not None:
                    var.set("0%")
            except Exception:
                pass
        self._reset_ui()

    def _msg_info(self, title: str, msg: str):
        if threading.current_thread() is threading.main_thread():
            messagebox.showinfo(title, msg)
            return
        self.root.after(0, lambda: messagebox.showinfo(title, msg))

    def _msg_warn(self, title: str, msg: str):
        if threading.current_thread() is threading.main_thread():
            messagebox.showwarning(title, msg)
            return
        self.root.after(0, lambda: messagebox.showwarning(title, msg))

    def _msg_error(self, title: str, msg: str):
        if threading.current_thread() is threading.main_thread():
            messagebox.showerror(title, msg)
            return
        self.root.after(0, lambda: messagebox.showerror(title, msg))

    def _append_log(self, msg: str, tag: str = "stdout"):
        if not hasattr(self, "log_text"):
            return
        text = str(msg)
        if not text.endswith("\n"):
            text += "\n"

        def _do():
            try:
                self.log_text.configure(state="normal")
                self.log_text.insert("end", text, (tag,))
                self.log_text.see("end")
                line_count = int(self.log_text.index('end-1c').split('.')[0])
                if line_count > 4000:
                    self.log_text.delete('1.0', f"{line_count - 4000}.0")
                self.log_text.configure(state="disabled")
            except Exception:
                pass

        if threading.current_thread() is threading.main_thread():
            _do()
        else:
            try:
                self.root.after(0, _do)
            except Exception:
                pass

    def _set_scope_progress_pct(self, scope: str, pct: float, text: Optional[str] = None):
        try:
            pct = float(pct)
        except Exception:
            pct = 0.0
        pct = max(0.0, min(100.0, pct))

        def _do():
            ctrl = getattr(self, "_exec_controls", {}).get(scope)
            if not ctrl:
                return
            try:
                bar = ctrl.get("progress")
                var = ctrl.get("progress_var")
                if bar is not None:
                    bar.stop()
                    bar.config(mode='determinate', maximum=100.0)
                    bar['value'] = pct
                if var is not None:
                    var.set(text if text is not None else f"{pct:4.1f}%")
            except Exception:
                pass
            try:
                if hasattr(self, "progress") and self.progress is not None:
                    self.progress.stop()
                    self.progress.config(mode='determinate', maximum=100.0)
                    self.progress['value'] = pct
                if hasattr(self, "progress_var") and self.progress_var is not None:
                    self.progress_var.set(text if text is not None else f"{pct:4.1f}%")
            except Exception:
                pass

        if threading.current_thread() is threading.main_thread():
            _do()
        else:
            try:
                self.root.after(0, _do)
            except Exception:
                pass

    def _set_scope_progress_indeterminate(self, scope: str, text: str = "..."):
        def _do():
            for scope_key in self._linked_scopes(scope):
                ctrl = getattr(self, "_exec_controls", {}).get(scope_key)
                if not ctrl:
                    continue
                try:
                    bar = ctrl.get("progress")
                    var = ctrl.get("progress_var")
                    if bar is not None:
                        bar.stop()
                        bar.config(mode="indeterminate")
                        bar.start(10)
                    if var is not None:
                        var.set(text)
                except Exception:
                    pass

        if threading.current_thread() is threading.main_thread():
            _do()
        else:
            try:
                self.root.after(0, _do)
            except Exception:
                pass

    on_run_basin = service_on_run_basin
    on_run_leakage = service_on_run_leakage

    on_run_all = service_on_run_all
        
    _update_config = service_update_config

    _run_thread = service_run_thread
    _reset_ui = service_reset_ui

    def _update_progress(self, done, total):
        try:
            if total and total > 0:
                pct = max(0.0, min(100.0, (done / total) * 100.0))
            else:
                pct = 0.0
            scope = getattr(self, "_active_scope", None) or "all"
            for scope_key in self._linked_scopes(scope):
                ctrl = getattr(self, "_exec_controls", {}).get(scope_key)
                if not ctrl:
                    continue
                try:
                    bar = ctrl.get("progress")
                    var = ctrl.get("progress_var")
                    if bar is not None:
                        bar['value'] = pct
                    if var is not None:
                        var.set(f"{pct:4.1f}%")
                except Exception:
                    pass
        except Exception:
            pass

    def on_pause(self):
        scope = getattr(self, "_active_scope", None)
        if not scope:
            return
        pause_ev, _ = self._get_scope_events(scope)
        if pause_ev.is_set():
            pause_ev.clear()
            text = 'Pause'
        else:
            pause_ev.set()
            text = 'Resume'
        for scope_key in self._linked_scopes(scope):
            ctrl = getattr(self, "_exec_controls", {}).get(scope_key)
            if not ctrl:
                continue
            btn = ctrl.get("pause")
            if btn is not None:
                try:
                    btn.config(text=text)
                except Exception:
                    pass

    def on_stop(self):
        scope = getattr(self, "_active_scope", None)
        if not scope:
            return
        pause_ev, stop_ev = self._get_scope_events(scope)
        stop_ev.set()
        pause_ev.clear()
        for scope_key in self._linked_scopes(scope):
            ctrl = getattr(self, "_exec_controls", {}).get(scope_key)
            if not ctrl:
                continue
            btn_stop = ctrl.get("stop")
            btn_pause = ctrl.get("pause")
            try:
                if btn_stop is not None:
                    btn_stop.config(state='disabled')
                if btn_pause is not None:
                    btn_pause.config(state='disabled', text='Pause')
            except Exception:
                pass

    def clear_progress_cache(self):
        try:
            self._clear_scope_progress("basin")
            self._clear_scope_progress("leakage")
            messagebox.showinfo("Progress Cache", "Progress cache cleared.")
        except Exception as e:
            messagebox.showerror("Progress Cache", f"Failed to clear cache: {e}")

    def clear_logs(self):
        if not hasattr(self, "log_text"):
            return
        try:
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", tk.END)
            self.log_text.configure(state="disabled")
        except Exception as e:
            messagebox.showwarning("Clear Logs", f"Failed to clear logs: {e}")

    def export_log(self):
        content = self.log_text.get("1.0", tk.END)
        if not content.strip():
            messagebox.showinfo("Export Log", "Log is empty.")
            return
        f = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if f:
            Path(f).write_text(content, encoding="utf-8")
            messagebox.showinfo("Export Log", f"Saved to {f}")

    def open_log_folder(self):
        log_dir = Path(self.cfg.path.OUTPUT) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(log_dir))
        except Exception:
            messagebox.showwarning("Open Log Folder", f"Could not open: {log_dir}")

    def open_output_folder(self):
        try:
            out_dir = Path(self.var_out.get()) if hasattr(self, "var_out") else Path(self.cfg.path.OUTPUT)
        except Exception:
            out_dir = Path(self.cfg.path.OUTPUT)
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        try:
            os.startfile(str(out_dir))
        except Exception:
            messagebox.showwarning("Open Output Folder", f"Could not open: {out_dir}")

    def _get_lowdeg_file(self, key, cfg=None):
        cfg = cfg or self.default_cfg
        lowdeg = getattr(cfg.inversion, 'lowdeg', {}) or {}
        if isinstance(lowdeg, dict):
            return lowdeg.get('files', {}).get(key, '')
        return ''

    def _get_gia_file(self, cfg=None):
        cfg = cfg or self.default_cfg
        gia = getattr(cfg.inversion, 'gia', {}) or {}
        if isinstance(gia, dict):
            return gia.get('file', '')
        return ''

    def _get_mascon_dir(self, cfg=None):
        cfg = cfg or self.default_cfg
        ref = getattr(cfg, 'reference', {}) or {}
        if isinstance(ref, dict):
            return ref.get('mascon_dir', '')
        return ''

    def _get_mascon_file(self, key, cfg=None):
        cfg = cfg or self.default_cfg
        ref = getattr(cfg, 'reference', {}) or {}
        if isinstance(ref, dict):
            return ref.get('mascon_undo', {}).get(key, '')
        return ''

    def _clear_large_caches(self, keep: Optional[str] = None):
        mapping = {
            "stack": ("_stack_cache", "_stack_cache_path"),
            "basin": ("_basin_cache", "_basin_cache_path"),
            "leakage": ("_leakage_cache", "_leakage_cache_path"),
        }
        for name, attrs in mapping.items():
            if name == keep:
                continue
            for attr in attrs:
                try:
                    setattr(self, attr, None)
                except Exception:
                    pass
        try:
            gc.collect()
        except Exception:
            pass

    def _probe_stack_any(self, path):
        return service_probe_stack_any(
            path,
            load_stack_any_cb=lambda p: self._load_stack_any(p),
            select_nc_variables_cb=self._select_nc_variables,
        )

    def _load_stack_any(self, path, active_var=None, selection_meta=None, select_nc_variables_cb=None):
        return service_load_stack_any(
            path,
            active_var=active_var,
            selection_meta=selection_meta,
            select_nc_variables_cb=select_nc_variables_cb,
        )

    load_stack_info = service_load_stack_info
    load_basin_info = service_load_basin_info
    load_leakage_info = service_load_leakage_info
    _set_stack_var_options = service_set_stack_var_options
    _on_stack_var_change = service_on_stack_var_change
    _get_stack_data = service_get_stack_data
    _get_basin_data = service_get_basin_data
    _get_leakage_data = service_get_leakage_data

    def _sanitize_mat_value(self, v):
        return io_sanitize_mat_value(v)

    def _safe_savemat(self, path, data):
        return io_safe_savemat(path, data)

    def _safe_write_text(self, path, lines):
        return io_safe_write_text(path, lines)

    def _save_grid_txt(self, path, lon_vec, lat_vec, grid):
        return io_save_grid_txt(path, lon_vec, lat_vec, grid)

    def _scope_cache_dir(self) -> Path:
        out_dir = ""
        try:
            out_dir = self._normpath(getattr(self.cfg.path, "OUTPUT", ""))
        except Exception:
            out_dir = ""
        return cache_scope_cache_dir(out_dir, str(get_root_dir()))

    def _scope_cache_file(self, scope: str) -> Path:
        out_dir = ""
        try:
            out_dir = self._normpath(getattr(self.cfg.path, "OUTPUT", ""))
        except Exception:
            out_dir = ""
        return cache_scope_cache_file(scope, out_dir, str(get_root_dir()))

    def _file_fingerprint(self, path: str) -> Dict[str, Any]:
        return algo_file_fingerprint(path)

    def _build_scope_signature(self, scope: str, payload: Dict[str, Any]) -> str:
        return algo_build_scope_signature(scope, payload, self.cfg)

    def _load_scope_progress(self, scope: str, signature: str) -> Optional[Dict[str, Any]]:
        out_dir = ""
        try:
            out_dir = self._normpath(getattr(self.cfg.path, "OUTPUT", ""))
        except Exception:
            out_dir = ""
        return cache_load_scope_progress(scope, signature, out_dir, str(get_root_dir()))

    def _save_scope_progress(self, scope: str, signature: str, state: Dict[str, Any]):
        out_dir = ""
        try:
            out_dir = self._normpath(getattr(self.cfg.path, "OUTPUT", ""))
        except Exception:
            out_dir = ""
        return cache_save_scope_progress(
            scope,
            signature,
            state,
            self._progress_cache_last_save,
            out_dir,
            str(get_root_dir()),
        )

    def _save_scope_progress_throttled(
        self,
        scope: str,
        signature: str,
        state: Dict[str, Any],
        *,
        min_interval_s: float = 1.5,
        force: bool = False,
    ):
        out_dir = ""
        try:
            out_dir = self._normpath(getattr(self.cfg.path, "OUTPUT", ""))
        except Exception:
            out_dir = ""
        return cache_save_scope_progress_throttled(
            scope,
            signature,
            state,
            self._progress_cache_last_save,
            out_dir,
            str(get_root_dir()),
            min_interval_s=min_interval_s,
            force=force,
        )

    def _clear_scope_progress(self, scope: str):
        out_dir = ""
        try:
            out_dir = self._normpath(getattr(self.cfg.path, "OUTPUT", ""))
        except Exception:
            out_dir = ""
        return cache_clear_scope_progress(
            scope,
            self._progress_cache_last_save,
            out_dir,
            str(get_root_dir()),
        )

    def _select_nc_variables(self, ds, lon_key=None, lat_key=None, time_key=None, data_keys=None):
        var_names = list(ds.variables.keys())
        data_candidates = []
        for name in var_names:
            try:
                v = ds.variables[name]
                if v.ndim < 2:
                    continue
                shape = "x".join(str(s) for s in getattr(v, "shape", ()))
                data_candidates.append((name, shape))
            except Exception:
                continue

        if not data_candidates:
            messagebox.showwarning("NetCDF", "No 2D/3D data variables found in this file.")
            return None

        data_names = [name for name, _shape in data_candidates]

        def _fallback_prompt():
            choices = ", ".join(var_names)
            lon_sel = simpledialog.askstring("Select Longitude Variable", f"Available: {choices}\nInput lon variable:")
            lat_sel = simpledialog.askstring("Select Latitude Variable", f"Available: {choices}\nInput lat variable:")
            time_sel = simpledialog.askstring("Select Time Variable (optional)", f"Available: {choices}\nInput time variable (blank if none):")
            data_sel = simpledialog.askstring("Select Data Variable(s)", f"Available: {choices}\nInput data vars (comma-separated):")
            if not lon_sel or not lat_sel:
                return None
            data_list = [s.strip() for s in (data_sel or "").split(",") if s.strip()]
            if not data_list:
                return None
            return lon_sel.strip(), lat_sel.strip(), (time_sel.strip() or None), data_list

        try:
            win = tk.Toplevel(self.root)
            win.title("Select NetCDF Variables")
            win.transient(self.root)
            win.grab_set()

            frame = ttk.Frame(win, padding=10)
            frame.pack(fill=tk.BOTH, expand=True)
            frame.columnconfigure(1, weight=1)
            frame.rowconfigure(4, weight=1)

            ttk.Label(frame, text="Longitude:").grid(row=0, column=0, sticky="w")
            var_lon = tk.StringVar(value=lon_key or "")
            cmb_lon = ttk.Combobox(frame, textvariable=var_lon, values=var_names, width=24, state="readonly")
            cmb_lon.grid(row=0, column=1, sticky="w", padx=4)

            ttk.Label(frame, text="Latitude:").grid(row=1, column=0, sticky="w")
            var_lat = tk.StringVar(value=lat_key or "")
            cmb_lat = ttk.Combobox(frame, textvariable=var_lat, values=var_names, width=24, state="readonly")
            cmb_lat.grid(row=1, column=1, sticky="w", padx=4)

            ttk.Label(frame, text="Time (optional):").grid(row=2, column=0, sticky="w")
            time_values = ["<none>"] + var_names
            var_time = tk.StringVar(value=time_key if time_key else "<none>")
            cmb_time = ttk.Combobox(frame, textvariable=var_time, values=time_values, width=24, state="readonly")
            cmb_time.grid(row=2, column=1, sticky="w", padx=4)

            ttk.Label(frame, text="Data variables (multi-select):").grid(row=3, column=0, sticky="w")
            list_frame = ttk.Frame(frame)
            list_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(4, 6))
            list_frame.columnconfigure(0, weight=1)
            list_frame.rowconfigure(0, weight=1)

            listbox = tk.Listbox(list_frame, selectmode="extended", height=8)
            vsb = ttk.Scrollbar(list_frame, orient="vertical", command=listbox.yview)
            listbox.configure(yscrollcommand=vsb.set)
            listbox.grid(row=0, column=0, sticky="nsew")
            vsb.grid(row=0, column=1, sticky="ns")

            for name, shape in data_candidates:
                listbox.insert(tk.END, f"{name}  ({shape})")

            if data_keys:
                for i, n in enumerate(data_names):
                    if n in data_keys:
                        listbox.selection_set(i)
            elif data_names:
                listbox.selection_set(0)

            result = {"ok": False, "lon": None, "lat": None, "time": None, "sel": None}

            def _ok():
                try:
                    sel = [data_names[i] for i in listbox.curselection()]
                except Exception:
                    sel = []
                if not var_lon.get().strip() or not var_lat.get().strip():
                    messagebox.showwarning("NetCDF", "Please select lon/lat variables.")
                    return
                if not sel:
                    messagebox.showwarning("NetCDF", "Please select at least one data variable.")
                    return
                result["ok"] = True
                result["lon"] = var_lon.get().strip()
                result["lat"] = var_lat.get().strip()
                t_sel = var_time.get().strip()
                result["time"] = None if t_sel == "<none>" else t_sel
                result["sel"] = sel
                win.destroy()

            def _cancel():
                win.destroy()

            win.protocol("WM_DELETE_WINDOW", _cancel)

            btns = ttk.Frame(frame)
            btns.grid(row=5, column=0, columnspan=2, sticky="e")
            ttk.Button(btns, text="OK", command=_ok).pack(side=tk.RIGHT, padx=4)
            ttk.Button(btns, text="Cancel", command=_cancel).pack(side=tk.RIGHT)

            win.wait_window()
            if not result.get("ok"):
                return None

            return result["lon"], result["lat"], result["time"], result["sel"]
        except tk.TclError:
            return _fallback_prompt()

    def _parse_ym(self, s: str):
        return algo_parse_ym(s)

    def _build_time_from_fallback(self, nt: int):
        start_ym = self.var_basin_start.get() if hasattr(self, 'var_basin_start') else None
        step = self.var_basin_step.get() if hasattr(self, 'var_basin_step') else 1
        return algo_build_time_from_fallback(start_ym, step, nt)

    def _resolve_time(self, t_arr, nt: int, meta: Optional[Dict[str, Any]] = None):
        use_file_time = bool(getattr(self, 'var_basin_use_file_time', tk.BooleanVar(value=True)).get())
        start_ym = self.var_basin_start.get() if hasattr(self, 'var_basin_start') else None
        step = self.var_basin_step.get() if hasattr(self, 'var_basin_step') else 1
        return algo_resolve_time(
            t_arr,
            nt,
            use_file_time=use_file_time,
            fallback_start_ym=start_ym,
            fallback_step=step,
            meta=meta,
        )

    run_basin_analysis = service_run_basin_analysis

    def _resolve_output_file(self, out_path: str, in_path: str, suffix: str, ext: str):
        return algo_resolve_output_file(out_path, in_path, suffix, ext)

    def _infer_time_labels(self, t_arr, nt):
        return algo_infer_time_labels(t_arr, nt)

    def _infer_time_axis_for_rate(self, t_arr, nt: int) -> np.ndarray:
        return algo_infer_time_axis_for_rate(t_arr, nt)

    def _fm_target_grid(self):
        return grid_fm_target_grid()

    def _sf_target_grid(self, grid_interval=0.5):
        return grid_sf_target_grid(grid_interval=grid_interval)

    def _regrid_regular(self, lon_in, lat_in, grid_in, lon_out, lat_out):
        return grid_regrid_regular(lon_in, lat_in, grid_in, lon_out, lat_out)

    def _write_xyz_file(self, path, lon_vec, lat_vec, grid):
        return grid_write_xyz_file(path, lon_vec, lat_vec, grid)

    def _read_xyz_grid(self, path):
        return grid_read_xyz_grid(path)

    def _ensure_sf_wrapper(self, out_dir: Path):
        return wf_ensure_sf_wrapper(out_dir)

    def _compute_sf_via_matlab(self, boundary_path, grid_interval=0.5):
        matlab = self.var_lrc_matlab.get().strip() if hasattr(self, "var_lrc_matlab") else "matlab"
        return wf_compute_sf_via_matlab(
            boundary_path,
            grid_interval=grid_interval,
            output_dir=str(self.cfg.path.OUTPUT),
            matlab=matlab,
            sf_method=(str(self.var_lrc_sf_method.get()).upper() if hasattr(self, "var_lrc_sf_method") else "GAUSSIAN"),
            sf_gauss=(float(self.var_lrc_sf_gauss.get()) if hasattr(self, "var_lrc_sf_gauss") else 300.0),
            sf_fan_r1=(float(self.var_lrc_sf_fan_r1.get()) if hasattr(self, "var_lrc_sf_fan_r1") else 300.0),
            sf_fan_r2=(float(self.var_lrc_sf_fan_r2.get()) if hasattr(self, "var_lrc_sf_fan_r2") else 300.0),
            sf_ddk=(str(self.var_lrc_sf_ddk.get()) if hasattr(self, "var_lrc_sf_ddk") else "DDK4"),
            sf_p4_deg=(int(self.var_lrc_sf_p4_deg.get()) if hasattr(self, "var_lrc_sf_p4_deg") else 4),
            sf_p4_m=(int(self.var_lrc_sf_p4_m.get()) if hasattr(self, "var_lrc_sf_p4_m") else 6),
            sf_hsa_window=(int(self.var_lrc_sf_hsa_window.get()) if hasattr(self, "var_lrc_sf_hsa_window") else 60),
            sf_hsa_p=(int(self.var_lrc_sf_hsa_p.get()) if hasattr(self, "var_lrc_sf_hsa_p") else 20),
            sf_hsa_order=(int(self.var_lrc_sf_hsa_order.get()) if hasattr(self, "var_lrc_sf_hsa_order") else 6),
            sf_hsa_buffer=(int(self.var_lrc_sf_hsa_buffer.get()) if hasattr(self, "var_lrc_sf_hsa_buffer") else 10),
            sf_hsa_ts=(int(self.var_lrc_sf_hsa_ts.get()) if hasattr(self, "var_lrc_sf_hsa_ts") else 1),
            sf_toolbox=(self._normpath(self.var_lrc_toolbox.get()) if hasattr(self, "var_lrc_toolbox") else ""),
            sf_target_grid_cb=self._sf_target_grid,
        )

    def _run_fm_correction(self, grid3d, lon_vec, lat_vec, t_arr, script_path, matlab):
        return wf_run_fm_correction(
            grid3d,
            lon_vec,
            lat_vec,
            t_arr,
            script_path,
            matlab,
            output_dir=str(self.cfg.path.OUTPUT),
            infer_time_labels_cb=self._infer_time_labels,
            fm_target_grid_cb=self._fm_target_grid,
            regrid_regular_cb=self._regrid_regular,
            write_xyz_file_cb=self._write_xyz_file,
            read_xyz_grid_cb=self._read_xyz_grid,
        )

    def _default_global_land_shp(self) -> Path:
        return wf_default_global_land_shp(str(get_root_dir()))

    def _build_global_land_mask(self, lon_vec: np.ndarray, lat_vec: np.ndarray) -> np.ndarray:
        mask, key = wf_build_global_land_mask(
            lon_vec,
            lat_vec,
            root_dir=str(get_root_dir()),
            cache_key=getattr(self, "_global_land_mask_key", None),
            cache_mask=getattr(self, "_global_land_mask", None),
        )
        self._global_land_mask_key = key
        self._global_land_mask = mask.copy()
        return mask

    def _build_leakage_mask(self, scope: str, lon_vec: np.ndarray, lat_vec: np.ndarray) -> np.ndarray:
        scope = str(scope or "global").lower()
        if scope != "regional":
            return self._build_global_land_mask(lon_vec, lat_vec)

        bfile = self.var_lrc_boundary.get().strip() if hasattr(self, "var_lrc_boundary") else ""
        mask, key = wf_build_regional_leakage_mask(
            bfile,
            lon_vec,
            lat_vec,
            cache_key=getattr(self, "_regional_leak_mask_key", None),
            cache_mask=getattr(self, "_regional_leak_mask", None),
        )
        self._regional_leak_mask_key = key
        self._regional_leak_mask = mask.copy()
        return mask

    def _infer_leakage_method_from_input(self, in_path: str, data_meta: Optional[Dict[str, Any]] = None):
        return wf_infer_leakage_method_from_input(in_path, data_meta)

    def _build_leakage_filter_options(
        self,
        in_path: str = "",
        data_meta: Optional[Dict[str, Any]] = None,
    ):
        try:
            perf = getattr(self.cfg, "perf", {}) or {}
        except Exception:
            perf = {}
        return wf_build_leakage_filter_options(
            raw_method=(str(self.var_lrc_sf_method.get()) if hasattr(self, "var_lrc_sf_method") else "AUTO"),
            in_path=in_path,
            data_meta=data_meta,
            sf_ddk=(str(self.var_lrc_sf_ddk.get()) if hasattr(self, "var_lrc_sf_ddk") else "DDK4"),
            parallel_enable=bool(getattr(self.cfg.parallel, "enable", False)),
            parallel_n_workers=int(getattr(self.cfg.parallel, "n_workers", 1)),
            frozen_allow_parallel=bool(perf.get("allow_frozen_parallel", False)),
            frozen_max_workers=int(perf.get("frozen_max_workers", 0) or 0),
            hsaf_n=(int(self.var_hsaf_N.get()) if hasattr(self, "var_hsaf_N") else (int(self.var_lrc_sf_hsa_window.get()) if hasattr(self, "var_lrc_sf_hsa_window") else 60)),
            hsaf_p=(int(self.var_hsaf_P.get()) if hasattr(self, "var_hsaf_P") else (int(self.var_lrc_sf_hsa_p.get()) if hasattr(self, "var_lrc_sf_hsa_p") else 20)),
            hsaf_k=(int(self.var_hsaf_K.get()) if hasattr(self, "var_hsaf_K") else (int(self.var_lrc_sf_hsa_order.get()) if hasattr(self, "var_lrc_sf_hsa_order") else 6)),
            hsaf_j=(int(self.var_hsaf_J.get()) if hasattr(self, "var_hsaf_J") else (int(self.var_lrc_sf_hsa_buffer.get()) if hasattr(self, "var_lrc_sf_hsa_buffer") else 10)),
            hsaf_input=(str(self.var_hsaf_input.get()) if hasattr(self, "var_hsaf_input") else "P4M6"),
            sf_gauss=(float(self.var_lrc_sf_gauss.get()) if hasattr(self, "var_lrc_sf_gauss") else 300.0),
            sf_fan_r1=(float(self.var_lrc_sf_fan_r1.get()) if hasattr(self, "var_lrc_sf_fan_r1") else 300.0),
            sf_fan_r2=(float(self.var_lrc_sf_fan_r2.get()) if hasattr(self, "var_lrc_sf_fan_r2") else 300.0),
            sf_hsa_ts=(float(self.var_lrc_sf_hsa_ts.get()) if hasattr(self, "var_lrc_sf_hsa_ts") else 1.0),
            sf_p4_deg=(int(self.var_lrc_sf_p4_deg.get()) if hasattr(self, "var_lrc_sf_p4_deg") else 4),
            sf_p4_m=(int(self.var_lrc_sf_p4_m.get()) if hasattr(self, "var_lrc_sf_p4_m") else 6),
            lmax=(int(self.var_lmax.get()) if hasattr(self, "var_lmax") else 60),
            ddk_data_dir=(self.var_ddk.get().strip() if hasattr(self, "var_ddk") else ""),
            log_info_cb=lambda m: self._append_log(m),
            log_warn_cb=lambda m: self._append_log(m, tag="stderr"),
        )

    def _save_leakage_output(self, grid_out, lon_vec, lat_vec, t_arr, labels, in_path, out_path, suffix):
        return wf_save_leakage_output(
            fmt=(str(self.var_lrc_fmt.get()).lower() if hasattr(self, "var_lrc_fmt") else "mat"),
            grid_out=grid_out,
            lon_vec=lon_vec,
            lat_vec=lat_vec,
            t_arr=t_arr,
            labels=labels,
            in_path=in_path,
            out_path=out_path,
            suffix=suffix,
            resolve_output_file_cb=self._resolve_output_file,
            save_grid_txt_cb=self._save_grid_txt,
            safe_savemat_cb=self._safe_savemat,
        )

    run_leakage_correction = service_run_leakage_correction
    _plot_stack = service_plot_stack

    def _pcolor_proj(self, ax, x, y, grid_plot, cmap, norm):
        try:
            mask = ~np.isfinite(x) | ~np.isfinite(y) | ~np.isfinite(grid_plot)
            # Mask seam jumps to avoid wrap artifacts
            try:
                dx = np.abs(np.diff(x, axis=1))
                dy = np.abs(np.diff(y, axis=1))
                xr = np.nanmax(x) - np.nanmin(x)
                yr = np.nanmax(y) - np.nanmin(y)
                thresh_x = 0.5 * xr if np.isfinite(xr) else 0
                thresh_y = 0.5 * yr if np.isfinite(yr) else 0
                if thresh_x > 0:
                    jump = np.zeros_like(grid_plot, dtype=bool)
                    jump[:, 1:] |= dx > thresh_x
                    if thresh_y > 0:
                        jump[:, 1:] |= dy > thresh_y
                    mask = mask | jump
            except Exception:
                pass
            grid_masked = np.ma.array(grid_plot, mask=mask)
        except Exception:
            grid_masked = grid_plot
        return ax.pcolormesh(x, y, grid_masked, shading='auto', cmap=cmap, norm=norm, edgecolors='none', linewidth=0, antialiased=False)
    def _infer_plot_lon_mode(self, lon):
        return map_infer_plot_lon_mode(lon)

    def _normalize_lon_for_plot(self, lons, lon_mode=None):
        mode = lon_mode or getattr(self, "_plot_lon_mode", "-180_180")
        return map_normalize_lon_for_plot(lons, mode)

    def _split_plot_lon_segments(self, lons, lats, lon0=0.0, plate_carree=False):
        return map_split_plot_lon_segments(
            lons,
            lats,
            self._split_dateline,
            lon0=lon0,
            plate_carree=plate_carree,
            lon_mode=getattr(self, "_plot_lon_mode", "-180_180"),
        )

    def _normalize_lon_input(self, val):
        return map_normalize_lon_input(val)

    def _region_is_custom(self):
        try:
            lon_min = float(self.var_r_lon_min.get())
            lon_max = float(self.var_r_lon_max.get())
            lat_min = float(self.var_r_lat_min.get())
            lat_max = float(self.var_r_lat_max.get())
        except Exception:
            return False
        return map_region_is_custom(lon_min, lon_max, lat_min, lat_max)

    def _parse_float(self, s):
        return map_parse_float(s)

    def _wrap_delta_lon(self, lon_deg, lon0):
        return map_wrap_delta_lon(lon_deg, lon0)

    def _get_proj_center(self, lon, lat):
        return map_get_proj_center(lon, lat)

    def _get_conic_parallels(self, lat_min, lat_max):
        return map_get_conic_parallels(lat_min, lat_max)


    def _scale_projection(self, x, y, target_ratio=2.0):
        x2, y2, sc, x0 = map_scale_projection(x, y, target_ratio=target_ratio)
        self._proj_scale = sc
        self._proj_x0 = x0
        return x2, y2
    def _get_axes_ratio(self):
        try:
            if not hasattr(self, "plot_fig") or self.plot_fig is None:
                return 2.0
            fig_w, fig_h = self.plot_fig.get_size_inches()
            rect = getattr(self, "_plot_axes_rect", None)
            if rect is None:
                rect = self.plot_ax.get_position().bounds
            return (rect[2] * fig_w) / (rect[3] * fig_h)
        except Exception:
            return 2.0


    def _apply_proj_scale(self, x):
        return map_apply_proj_scale(
            x,
            proj_scale=getattr(self, "_proj_scale", None),
            proj_x0=getattr(self, "_proj_x0", None),
        )
    def _proj_robinson(self, lon_deg, lat_deg, lon0=0.0):
        return map_proj_robinson(lon_deg, lat_deg, lon0=lon0)

    def _proj_mollweide(self, lon_deg, lat_deg, lon0=0.0):
        return map_proj_mollweide(lon_deg, lat_deg, lon0=lon0)

    def _proj_mercator(self, lon_deg, lat_deg, lon0=0.0):
        return map_proj_mercator(lon_deg, lat_deg, lon0=lon0)

    def _proj_miller(self, lon_deg, lat_deg, lon0=0.0):
        return map_proj_miller(lon_deg, lat_deg, lon0=lon0)

    def _proj_sinusoidal(self, lon_deg, lat_deg, lon0=0.0):
        return map_proj_sinusoidal(lon_deg, lat_deg, lon0=lon0)

    def _proj_equalearth(self, lon_deg, lat_deg, lon0=0.0):
        return map_proj_equalearth(lon_deg, lat_deg, lon0=lon0)

    def _proj_winkeltripel(self, lon_deg, lat_deg, lon0=0.0):
        return map_proj_winkeltripel(lon_deg, lat_deg, lon0=lon0)

    def _proj_eckert4(self, lon_deg, lat_deg, lon0=0.0):
        return map_proj_eckert4(lon_deg, lat_deg, lon0=lon0)

    def _proj_orthographic(self, lon_deg, lat_deg, lon0=0.0, lat0=0.0):
        return map_proj_orthographic(lon_deg, lat_deg, lon0=lon0, lat0=lat0)

    def _proj_aeqd(self, lon_deg, lat_deg, lon0=0.0, lat0=0.0):
        return map_proj_aeqd(lon_deg, lat_deg, lon0=lon0, lat0=lat0)

    def _proj_stereographic(self, lon_deg, lat_deg, lon0=0.0, lat0=0.0):
        return map_proj_stereographic(lon_deg, lat_deg, lon0=lon0, lat0=lat0)

    def _proj_lambert_conformal(self, lon_deg, lat_deg, lon0=0.0, lat0=0.0, lat1=30.0, lat2=60.0):
        return map_proj_lambert_conformal(lon_deg, lat_deg, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)

    def _proj_albers(self, lon_deg, lat_deg, lon0=0.0, lat0=0.0, lat1=30.0, lat2=60.0):
        return map_proj_albers(lon_deg, lat_deg, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)

    def _plot_line(self, ax, x, y, **kwargs):
        return boundary_plot_line(ax, x, y, **kwargs)


    def _split_dateline(self, lons, lats, threshold=180.0, lon0=None):
        return boundary_split_dateline(lons, lats, self._wrap_delta_lon, threshold=threshold, lon0=lon0)

    def _read_boundary_file(self, path: str, name_field: str = "Name"):
        return boundary_read_boundary_file(path, name_field=name_field)

    def _boundary_bbox(self, boundaries):
        return boundary_boundary_bbox(boundaries)

    def _project_by_name(self, name, lons, lats, *, lon0=0.0, lat0=0.0, lat1=30.0, lat2=60.0):
        if name == "Robinson":
            return self._proj_robinson(lons, lats, lon0=lon0)
        if name == "Mollweide":
            return self._proj_mollweide(lons, lats, lon0=lon0)
        if name == "EqualEarth":
            return self._proj_equalearth(lons, lats, lon0=lon0)
        if name == "WinkelTripel":
            return self._proj_winkeltripel(lons, lats, lon0=lon0)
        if name == "EckertIV":
            return self._proj_eckert4(lons, lats, lon0=lon0)
        if name == "Mercator":
            return self._proj_mercator(lons, lats, lon0=lon0)
        if name == "Miller":
            return self._proj_miller(lons, lats, lon0=lon0)
        if name == "Sinusoidal":
            return self._proj_sinusoidal(lons, lats, lon0=lon0)
        if name == "Orthographic":
            return self._proj_orthographic(lons, lats, lon0=lon0, lat0=lat0)
        if name == "AzimuthalEquidistant":
            return self._proj_aeqd(lons, lats, lon0=lon0, lat0=lat0)
        if name == "Stereographic":
            return self._proj_stereographic(lons, lats, lon0=lon0, lat0=lat0)
        if name == "LambertConformal":
            return self._proj_lambert_conformal(lons, lats, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
        if name == "AlbersEqualArea":
            return self._proj_albers(lons, lats, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
        raise ValueError(f"Unsupported projection: {name}")

    def _draw_boundaries(self, ax, boundaries, proj="PlateCarree", lon0=0.0, lat0=0.0, lat1=30.0, lat2=60.0, bbox=None):
        return boundary_draw_boundaries(
            ax,
            boundaries,
            proj=proj,
            lon0=lon0,
            lat0=lat0,
            lat1=lat1,
            lat2=lat2,
            bbox=bbox,
            normalize_lon_for_plot_cb=self._normalize_lon_for_plot,
            split_dateline_cb=self._split_dateline,
            split_plot_lon_segments_cb=self._split_plot_lon_segments,
            apply_proj_scale_cb=self._apply_proj_scale,
            plot_line_cb=self._plot_line,
            projector_cb=self._project_by_name,
        )
    def _draw_coastlines(self, ax, proj="PlateCarree", lon0=0.0, lat0=0.0, lat1=30.0, lat2=60.0, bbox=None):
        coast_path = self.var_coast.get() if hasattr(self, "var_coast") else ""
        return overlay_draw_coastlines(
            ax,
            coast_path=coast_path,
            proj=proj,
            lon0=lon0,
            lat0=lat0,
            lat1=lat1,
            lat2=lat2,
            bbox=bbox,
            normalize_lon_for_plot_cb=self._normalize_lon_for_plot,
            split_dateline_cb=self._split_dateline,
            split_plot_lon_segments_cb=self._split_plot_lon_segments,
            apply_proj_scale_cb=self._apply_proj_scale,
            plot_line_cb=self._plot_line,
            projector_cb=self._project_by_name,
        )

    def _draw_graticule(self, ax, proj="PlateCarree", lon0=0.0, lat0=0.0, lat1=30.0, lat2=60.0):
        return overlay_draw_graticule(
            ax,
            proj=proj,
            lon0=lon0,
            lat0=lat0,
            lat1=lat1,
            lat2=lat2,
            plot_lon_mode=getattr(self, "_plot_lon_mode", "-180_180"),
            apply_proj_scale_cb=self._apply_proj_scale,
            plot_line_cb=self._plot_line,
            projector_cb=self._project_by_name,
        )

    def plot_stack(self):
        try:
            region = bool(getattr(self, "var_plot_use_region", tk.BooleanVar(value=False)).get())
        except Exception:
            region = False
        try:
            if not region and hasattr(self, "var_plot_boundary") and self.var_plot_boundary.get().strip():
                if bool(getattr(self, "var_plot_auto_region", tk.BooleanVar(value=True)).get()):
                    region = True
        except Exception:
            pass
        self._plot_stack(region=region)

    def plot_stack_global(self):
        self._plot_stack(region=False)

    def plot_stack_region(self):
        self._plot_stack(region=True)

    def save_plot(self):
        if not hasattr(self, "plot_fig") or self.plot_fig is None:
            messagebox.showwarning("Save Plot", "No plot available.")
            return
        path = self.var_save_path.get().strip() if hasattr(self, "var_save_path") else ""
        if not path:
            self._browse_save_path()
            path = self.var_save_path.get().strip()
        if not path:
            return
        try:
            dpi = int(self.var_save_dpi.get()) if hasattr(self, "var_save_dpi") else 300
        except Exception:
            dpi = 300
        fmt = self.var_save_fmt.get().strip().lower() if hasattr(self, "var_save_fmt") else "png"
        if fmt and not path.lower().endswith(f".{fmt}"):
            path = f"{path}.{fmt}"
        try:
            self.plot_fig.savefig(path, dpi=dpi, bbox_inches="tight")
            messagebox.showinfo("Save Plot", f"Saved to {path}")
        except Exception as e:
            messagebox.showerror("Save Plot", f"Failed to save plot: {e}")

def start_gui():
    # Reduce resource usage for GUI startup.
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("NUMEXPR_MAX_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    root = tk.Tk()
    app = GracePipelineGUI(root)
    root.mainloop()

if __name__ == "__main__":
    start_gui()





