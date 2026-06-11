"""Qt controller layer that bridges the PySide6 shell and existing pipeline services."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import os
import sys
import threading
import time
import webbrowser
from datetime import datetime, timedelta
from calendar import monthrange
from pathlib import Path

import numpy as np
from scipy.io import loadmat
from PySide6.QtCore import QDir, QObject, QSignalBlocker, Qt, Signal, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from grace_pipeline.app.basin import run_basin_analysis as service_run_basin_analysis
from grace_pipeline.app.leakage import run_leakage_correction as service_run_leakage_correction
from grace_pipeline.basin import (
    compute_weighted_mean as basin_compute_weighted_mean,
    fit_seasonal_trend as basin_fit_seasonal_trend,
    make_mask as basin_make_mask,
    read_boundary as basin_read_boundary,
)
from grace_pipeline.basin.boundary import resolve_shapefile_name_field
from grace_pipeline.core.grid import ensure_latlon_order, make_lonlat_vec
from grace_pipeline.app.leakage_helpers import (
    build_global_land_mask,
    build_leakage_filter_options,
    build_regional_leakage_mask,
    infer_leakage_method_from_input,
    save_leakage_output,
)
from grace_pipeline.domain.leakage import classify_leakage_scene, infer_operator_spec, recommend_correction_method, resolve_strategy_request
from grace_pipeline.app.pipeline import run_pipeline
from grace_pipeline.core.time_index import TimeEntry, build_time_index, extract_ym_from_gfc, summarize_time_coverage
from grace_pipeline.infra.config import Config, find_default_config, get_config_dir, get_root_dir, load_config
from grace_pipeline.inversion.gfc_reader import read_gfc, read_gsm_month
from grace_pipeline.inversion.low_degree import compute_mean_sh, get_mean_mode, replace_low_degree, select_mean_sh
from grace_pipeline.inversion.sh_synthesis import ewh_analysis, ewh_synthesis
from grace_pipeline.infra.stack.loader import load_stack_any, load_stack_slice_any
from grace_pipeline.infra.stack.probe import probe_stack_any
from grace_pipeline.services.gfc_download import (
    clear_earthdata_token,
    clear_earthdata_credentials,
    download_gfc_range,
    download_low_degree_files,
    download_mascon_nc,
    has_earthdata_credentials,
    current_earthdata_login,
    infer_center_from_gfc_dir,
    infer_center_from_gfc_file,
    normalize_center,
    save_earthdata_token,
    EARTHDATA_TOKEN_URL,
    EARTHDATA_TOKEN_STORE,
    CMR_GRANULE_URL,
)
from grace_pipeline.ui.plotting.boundaries import (
    boundary_bbox,
    draw_boundaries,
    plot_line,
    read_boundary_file,
    split_dateline,
)
from grace_pipeline.ui.plotting.overlays import draw_coastlines, draw_graticule
from grace_pipeline.ui.plotting.projections import (
    apply_proj_scale,
    get_conic_parallels,
    get_proj_center,
    infer_plot_lon_mode,
    normalize_lon_for_plot,
    normalize_lon_input,
    parse_float,
    proj_aeqd,
    proj_albers,
    proj_eckert4,
    proj_equalearth,
    proj_lambert_conformal,
    proj_mercator,
    proj_miller,
    proj_mollweide,
    proj_orthographic,
    proj_robinson,
    proj_sinusoidal,
    proj_stereographic,
    proj_winkeltripel,
    scale_projection,
    split_plot_lon_segments,
    wrap_delta_lon,
)
from grace_pipeline.ui.qt.path_defaults import DEFAULT_DATA_PATHS
from grace_pipeline.ui.qt.preferences import UIPreferences
from grace_pipeline.ui.qt.theme import COLOR
from grace_pipeline.ui.qt.widgets import populate_table


ROOT_DIR = get_root_dir().resolve()
DEFAULT_CFG_PATH = find_default_config(ROOT_DIR) or (ROOT_DIR / "cfg" / "default.json")
DEFAULT_CFG_DIR = get_config_dir(ROOT_DIR)
DEFAULT_USER_CFG_PATH = DEFAULT_CFG_DIR / "user.json"
DEFAULT_COASTLINE_PATH = DEFAULT_DATA_PATHS["COASTLINE_SHP"]


class UiSettingsDialog(QDialog):
    """Settings dialog for theme and language preferences."""

    def __init__(self, window, preferences: UIPreferences):
        super().__init__(window)
        self.window = window
        self.setWindowTitle(window.translate_text("Settings"))
        self.setModal(True)
        self.resize(420, 220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)

        self.cmb_theme = QComboBox()
        self.cmb_theme.addItem(window.translate_text("System"), "system")
        self.cmb_theme.addItem(window.translate_text("Light"), "light")
        self.cmb_theme.addItem(window.translate_text("Dark"), "dark")
        self.cmb_theme.setCurrentIndex(max(0, self.cmb_theme.findData(preferences.theme)))

        self.cmb_language = QComboBox()
        self.cmb_language.addItem(window.translate_text("English"), "en")
        self.cmb_language.addItem(window.translate_text("Chinese"), "zh")
        self.cmb_language.setCurrentIndex(max(0, self.cmb_language.findData(preferences.language)))

        form.addRow(window.translate_text("Theme"), self.cmb_theme)
        form.addRow(window.translate_text("Language"), self.cmb_language)
        layout.addLayout(form)

        theme_note = QLabel(window.translate_text("System follows desktop appearance when available."))
        theme_note.setWordWrap(True)
        theme_note.setObjectName("PageSubtitle")
        layout.addWidget(theme_note)

        lang_note = QLabel(window.translate_text("Choose between English and Simplified Chinese for the interface."))
        lang_note.setWordWrap(True)
        lang_note.setObjectName("PageSubtitle")
        layout.addWidget(lang_note)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply)
        self.buttons.button(QDialogButtonBox.Ok).setText(window.translate_text("OK"))
        self.buttons.button(QDialogButtonBox.Cancel).setText(window.translate_text("Cancel"))
        self.buttons.button(QDialogButtonBox.Apply).setText(window.translate_text("Apply"))
        layout.addWidget(self.buttons)

    def current_preferences(self) -> UIPreferences:
        return UIPreferences(
            theme=str(self.cmb_theme.currentData()),
            language=str(self.cmb_language.currentData()),
        )


class QtVar:
    """Small Tk-like variable adapter for legacy services."""

    def __init__(self, value=None):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


class QtSignals(QObject):
    log = Signal(str, str)
    message = Signal(str, str, str)
    progress = Signal(str, float, str)
    status = Signal(str, str)
    gfc_download_done = Signal(object)


class SignalLogWriter(io.TextIOBase):
    def __init__(self, signals: QtSignals, tag: str):
        super().__init__()
        self._signals = signals
        self._tag = tag
        self._buf = ""

    def write(self, text):
        if not text:
            return 0
        self._buf += str(text)
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                self._signals.log.emit(line, self._tag)
        return len(text)

    def flush(self):
        if self._buf.strip():
            self._signals.log.emit(self._buf.rstrip(), self._tag)
        self._buf = ""


class QtWorkflowHost:
    """Host object that satisfies the legacy basin/leakage service contract."""

    run_basin_analysis = service_run_basin_analysis
    run_leakage_correction = service_run_leakage_correction

    def __init__(self, window, signals: QtSignals):
        self.window = window
        self.signals = signals
        self.cfg_dir = DEFAULT_USER_CFG_PATH.parent
        self.current_cfg_path: Path | None = None
        self.default_cfg = self._load_default_cfg()
        self.cfg = self.default_cfg
        self._active_scope = ""
        self._scope_events = {
            "all": {"pause": threading.Event(), "stop": threading.Event()},
            "basin": {"pause": threading.Event(), "stop": threading.Event()},
            "leakage": {"pause": threading.Event(), "stop": threading.Event()},
        }
        self._progress_cache_last_save = {}
        self._global_land_mask_key = None
        self._global_land_mask = None
        self._regional_leak_mask_key = None
        self._regional_leak_mask = None
        self._stack_cache = None
        self._stack_cache_path = ""
        self._stack_cache_meta = {}
        self._stack_info_cache = None
        self._stack_frame_cache = {}
        self._basin_cache = None
        self._basin_cache_path = ""
        self._leakage_cache = None
        self._leakage_cache_path = ""

        self.var_basin_enable = QtVar(False)
        self.var_basin_data = QtVar("")
        self.var_basin_file = QtVar("")
        self.var_basin_name = QtVar("")
        self.var_basin_names = QtVar([])
        self.var_basin_name_field = QtVar("Name")
        self.var_basin_out_dir = QtVar("")
        self.var_basin_prefix = QtVar("basin")
        self.var_basin_tag = QtVar("DATA")
        self.var_basin_do_ts = QtVar(True)
        self.var_basin_do_stats = QtVar(True)
        self.var_basin_do_grid = QtVar(True)
        self.var_basin_save_ts_txt = QtVar(True)
        self.var_basin_save_ts_mat = QtVar(True)
        self.var_basin_save_grid_txt = QtVar(False)
        self.var_basin_save_grid_mat = QtVar(True)
        self.var_basin_use_file_time = QtVar(True)
        self.var_basin_start = QtVar("")
        self.var_basin_step = QtVar("1")

        self.var_lrc_enable = QtVar(True)
        self.var_lrc_scope = QtVar("global")
        self.var_lrc_method = QtVar("SF")
        self.var_lrc_sf = QtVar(1.0)
        self.var_lrc_input = QtVar("")
        self.var_lrc_output = QtVar("")
        self.var_lrc_fmt = QtVar("mat")
        self.var_lrc_boundary = QtVar("")
        self.var_lrc_sf_method = QtVar("Auto")
        self.var_lrc_sf_auto = QtVar(False)
        self.var_lrc_sf_gauss = QtVar(300.0)
        self.var_lrc_sf_fan_r1 = QtVar(300.0)
        self.var_lrc_sf_fan_r2 = QtVar(300.0)
        self.var_lrc_sf_ddk = QtVar("DDK4")
        self.var_lrc_sf_p4_deg = QtVar(4)
        self.var_lrc_sf_p4_m = QtVar(6)
        self.var_lrc_sf_grid = QtVar(0.5)
        self.var_lrc_sf_hsa_window = QtVar(60)
        self.var_lrc_sf_hsa_p = QtVar(20)
        self.var_lrc_sf_hsa_order = QtVar(6)
        self.var_lrc_sf_hsa_buffer = QtVar(10)
        self.var_lrc_sf_hsa_ts = QtVar(1)
        self.var_lrc_toolbox = QtVar("")
        self.var_lrc_script_global = QtVar("")
        self.var_lrc_script_region = QtVar("")
        self.var_lrc_matlab = QtVar("matlab")
        self.var_lrc_fm_max_iter = QtVar(40)
        self.var_lrc_fm_min_iter = QtVar(3)
        self.var_lrc_fm_tol = QtVar(0.01)
        self.var_lrc_fm_accel = QtVar(1.1)
        self.var_lrc_fm_patience = QtVar(8)
        self.var_lrc_fm_min_improve = QtVar(1.0e-4)
        self.var_lrc_fm_autocap_hsaf_iter = QtVar(True)
        self.var_lrc_fm_hsaf_iter_cap = QtVar(40)
        self.var_lrc_fm_allow_hsaf_parallel = QtVar(True)
        self.var_lrc_fm_hsaf_outer_workers_cap = QtVar(12)
        self.var_lrc_fm_hsaf_inner_workers = QtVar(1)

    def _load_default_cfg(self) -> Config:
        if DEFAULT_CFG_PATH.exists():
            return load_config(default_config=DEFAULT_CFG_PATH, root_dir=ROOT_DIR)
        return load_config(root_dir=ROOT_DIR)

    def _normpath(self, value: str) -> str:
        s = str(value or "").strip()
        if not s:
            return ""
        return os.path.normpath(os.path.expandvars(s))

    def _append_log(self, text: str, tag: str = "stdout"):
        self.signals.log.emit(str(text), tag)

    def _msg_info(self, title: str, text: str):
        self.signals.message.emit("info", title, text)

    def _msg_warn(self, title: str, text: str):
        self.signals.message.emit("warning", title, text)

    def _msg_error(self, title: str, text: str):
        self.signals.message.emit("error", title, text)

    def _get_scope_events(self, scope: str):
        scope = scope if scope in self._scope_events else "all"
        return self._scope_events[scope]["pause"], self._scope_events[scope]["stop"]

    def _check_pause_stop(self) -> bool:
        scope = self._active_scope or "all"
        pause_event, stop_event = self._get_scope_events(scope)
        while pause_event.is_set():
            if stop_event.is_set():
                return False
            time.sleep(0.2)
        return not stop_event.is_set()

    def _set_scope_progress_pct(self, scope: str, pct: float, text: str | None = None):
        pct = float(max(0.0, min(100.0, pct)))
        self.signals.progress.emit(scope, pct, text or f"{pct:4.1f}%")

    def _set_scope_progress_indeterminate(self, scope: str, text: str = "..."):
        self.signals.progress.emit(scope, -1.0, text)

    def _scope_cache_dir(self) -> Path:
        out_root = Path(getattr(self.cfg.path, "OUTPUT", ROOT_DIR / "output"))
        cache_dir = out_root / "CACHE" / "qt_ui"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def _file_fingerprint(self, path: str) -> dict:
        p = Path(path.strip()) if path else None
        if not p or not p.exists():
            return {"path": str(path or ""), "exists": False}
        stat = p.stat()
        return {"path": str(p.resolve()), "exists": True, "size": int(stat.st_size), "mtime": int(stat.st_mtime)}

    def _build_scope_signature(self, scope: str, payload: dict) -> str:
        text = json.dumps({"scope": scope, "payload": payload}, ensure_ascii=True, sort_keys=True, default=str)
        return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]

    def _load_scope_progress(self, scope: str, sig: str) -> dict:
        p = self._scope_cache_dir() / f"{scope}_{sig}.json"
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_scope_progress_throttled(self, scope: str, sig: str, state: dict, min_interval_s: float = 2.0, force: bool = False):
        now = time.time()
        last = float(self._progress_cache_last_save.get((scope, sig), 0.0))
        if not force and now - last < min_interval_s:
            return
        p = self._scope_cache_dir() / f"{scope}_{sig}.json"
        p.write_text(json.dumps({"state": state, "saved_at": now}, ensure_ascii=False, indent=2), encoding="utf-8")
        self._progress_cache_last_save[(scope, sig)] = now

    def _clear_scope_progress(self, scope: str):
        for p in self._scope_cache_dir().glob(f"{scope}_*.json"):
            with contextlib.suppress(Exception):
                p.unlink()

    def _safe_savemat(self, path: str, payload: dict):
        import scipy.io as sio

        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(out.suffix + ".tmp")
        sio.savemat(str(tmp), payload, do_compression=True, appendmat=False)
        os.replace(str(tmp), str(out))

    def _safe_write_text(self, path: str, lines):
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(out.suffix + ".tmp")
        text = "\n".join(str(x) for x in lines)
        tmp.write_text(text, encoding="utf-8")
        os.replace(str(tmp), str(out))

    def _save_grid_txt(self, path: str, lon_vec, lat_vec, grid):
        lines = ["lon,lat,value"]
        arr = np.asarray(grid, dtype=float)
        for i, lon in enumerate(np.asarray(lon_vec).squeeze()):
            for j, lat in enumerate(np.asarray(lat_vec).squeeze()):
                lines.append(f"{float(lon):.6f},{float(lat):.6f},{float(arr[i, j]):.6f}")
        self._safe_write_text(path, lines)

    def _resolve_time(self, t_arr, nt: int, meta: dict | None = None):
        meta = meta or {}
        if t_arr is None:
            labels = [f"{i + 1:03d}" for i in range(nt)]
            years = np.arange(nt, dtype=float)
            return years, labels
        flat = np.asarray(t_arr).reshape(-1)
        time_units = str(meta.get("time_units") or "").strip().lower()
        time_calendar = str(meta.get("time_calendar") or "").strip().lower()
        numeric = None
        with contextlib.suppress(Exception):
            numeric = np.asarray(flat, dtype=float)

        def _parse_since_base(keyword: str):
            if keyword not in time_units:
                return None
            raw_base = time_units.split(keyword, 1)[1].strip().split()[0]
            raw_base = raw_base.replace("z", "+00:00")
            with contextlib.suppress(Exception):
                dt = datetime.fromisoformat(raw_base)
                return dt.replace(tzinfo=None)
            with contextlib.suppress(Exception):
                return datetime.strptime(raw_base[:10], "%Y-%m-%d")
            return None

        day_base = _parse_since_base("days since")
        month_base = _parse_since_base("months since")
        year_base = _parse_since_base("years since")
        if day_base is None and numeric is not None:
            finite = numeric[np.isfinite(numeric)]
            looks_like_mascon_day_offset = bool(
                finite.size
                and 30.0 <= float(np.nanmin(finite))
                and float(np.nanmax(finite)) <= 20000.0
                and (
                    "day" in time_units
                    or time_calendar
                    or "lwe" in str(meta.get("active_var", "")).lower()
                    or "mascon" in str(meta.get("active_var", "")).lower()
                )
            )
            if looks_like_mascon_day_offset:
                day_base = datetime(2002, 1, 1)

        def _add_months(base: datetime, months_value: float) -> datetime:
            whole = int(np.floor(float(months_value)))
            frac = float(months_value) - whole
            month0 = (base.month - 1) + whole
            year = base.year + month0 // 12
            month = month0 % 12 + 1
            day = min(base.day, monthrange(year, month)[1])
            dt = datetime(year, month, day)
            if frac:
                dt = dt + timedelta(days=frac * monthrange(year, month)[1])
            return dt

        def _format_decimal_year(value: float):
            year = int(np.floor(float(value)))
            rem = float(value) - year
            if 1800 <= year <= 2300:
                month = max(1, min(12, int(np.floor(rem * 12.0)) + 1))
                return year, month
            return None

        def _format_yyyymm(value: float):
            intval = int(round(float(value)))
            year = intval // 100
            month = intval % 100
            if 1800 <= year <= 2300 and 1 <= month <= 12:
                return year, month
            return None

        def _finite_float(value):
            with contextlib.suppress(Exception):
                out = float(value)
                if np.isfinite(out):
                    return out
            return None

        labels = []
        years = []
        for idx, item in enumerate(flat[:nt]):
            try:
                numeric_item = _finite_float(item)
                if hasattr(item, "strftime"):
                    labels.append(item.strftime("%Y-%m"))
                    years.append(item.year + (item.month - 0.5) / 12.0)
                elif day_base is not None and numeric_item is not None:
                    dt = day_base + timedelta(days=numeric_item)
                    labels.append(dt.strftime("%Y-%m"))
                    years.append(dt.year + (dt.month - 0.5) / 12.0)
                elif month_base is not None and numeric_item is not None:
                    dt = _add_months(month_base, numeric_item)
                    labels.append(dt.strftime("%Y-%m"))
                    years.append(dt.year + (dt.month - 0.5) / 12.0)
                elif year_base is not None and numeric_item is not None:
                    dt = _add_months(year_base, numeric_item * 12.0)
                    labels.append(dt.strftime("%Y-%m"))
                    years.append(dt.year + (dt.month - 0.5) / 12.0)
                elif numeric_item is not None and _format_yyyymm(numeric_item) is not None:
                    year, month = _format_yyyymm(numeric_item)
                    labels.append(f"{year:04d}-{month:02d}")
                    years.append(year + (month - 0.5) / 12.0)
                elif numeric_item is not None and _format_decimal_year(numeric_item) is not None:
                    year, month = _format_decimal_year(numeric_item)
                    labels.append(f"{year:04d}-{month:02d}")
                    years.append(year + (month - 0.5) / 12.0)
                else:
                    s = str(item).strip()
                    if len(s) >= 7 and s[4] in "-/":
                        year = int(s[:4])
                        month = int(s[5:7])
                        labels.append(f"{year:04d}-{month:02d}")
                        years.append(year + (month - 0.5) / 12.0)
                    else:
                        labels.append(s or f"{idx + 1:03d}")
                        years.append(float(idx))
            except Exception:
                labels.append(f"{idx + 1:03d}")
                years.append(float(idx))
        while len(labels) < nt:
            labels.append(f"{len(labels) + 1:03d}")
            years.append(float(len(years)))
        return np.asarray(years, dtype=float), labels

    def _infer_time_labels(self, t_arr, nt: int):
        return self._resolve_time(t_arr, nt)[1]

    def _resolve_output_file(self, out_path: str, in_path: str, suffix: str, ext: str):
        out_path = str(out_path or "").strip()
        if out_path:
            out = Path(out_path)
            if out.suffix.lower() != f".{ext.lower()}":
                out = out.with_suffix(f".{ext}")
        else:
            stem = Path(in_path).stem if in_path else "leakage"
            out_dir = Path(getattr(self.cfg.path, "OUTPUT", ROOT_DIR / "output")) / "local" / "leakage"
            out = out_dir / f"{stem}_{suffix}.{ext}"
        out.parent.mkdir(parents=True, exist_ok=True)
        return str(out), str(out.parent)

    def _select_nc_variables(self, ds, lon_key, lat_key, time_key, data_keys):
        items = list(data_keys or [])
        if not items:
            items = [name for name, var in ds.variables.items() if getattr(var, "ndim", 0) >= 2]
        chosen, ok = QInputDialog.getItem(self.window, "Select NetCDF Variable", "Data Variable", items, 0, False)
        if not ok:
            raise ValueError("NetCDF variable selection cancelled.")
        return lon_key, lat_key, time_key, [chosen]

    def _load_stack_any(self, path: str, active_var: str | None = None, selection_meta: dict | None = None):
        return load_stack_any(path, active_var=active_var, selection_meta=selection_meta, select_nc_variables_cb=self._select_nc_variables)

    def load_stack_info(self, path: str):
        shape, lon, lat, t_arr, meta = probe_stack_any(path, self._load_stack_any, self._select_nc_variables)
        if not shape:
            raise ValueError("Unable to inspect stack file.")
        if self._stack_cache_path != path:
            self._stack_cache = None
            self._stack_frame_cache = {}
        self._stack_cache_path = path
        self._stack_cache_meta = meta or {}
        self._stack_info_cache = {"path": path, "shape": shape, "lon": lon, "lat": lat, "t": t_arr, "meta": meta or {}}
        return dict(self._stack_info_cache)

    def get_stack_data(self, path: str, active_var: str | None = None):
        if self._stack_cache is not None and self._stack_cache_path == path:
            if not active_var or self._stack_cache.get("meta", {}).get("active_var") == active_var:
                return self._stack_cache
        ewh, lon, lat, t_arr, meta = self._load_stack_any(path, active_var=active_var, selection_meta=self._stack_cache_meta)
        if ewh is None:
            raise ValueError("Unable to load stack data.")
        data = {"ewh": ewh, "lon": lon, "lat": lat, "t": t_arr, "meta": meta or {}}
        self._stack_cache = data
        self._stack_cache_path = path
        self._stack_cache_meta = meta or {}
        self._stack_info_cache = {
            "path": path,
            "shape": tuple(np.asarray(ewh).shape),
            "lon": lon,
            "lat": lat,
            "t": t_arr,
            "meta": meta or {},
        }
        self._stack_frame_cache = {}
        return data

    def get_stack_frame(self, path: str, time_index: int, active_var: str | None = None):
        path = path.strip()
        if not path:
            raise ValueError("Stack path not set.")
        active_name = active_var or self._stack_cache_meta.get("active_var")
        frame_key = (path, active_name or "", int(time_index))
        cached = self._stack_frame_cache.get(frame_key)
        if cached is not None:
            return cached

        if self._stack_cache is not None and self._stack_cache_path == path:
            cache_meta = self._stack_cache.get("meta", {}) or {}
            cache_active = cache_meta.get("active_var")
            if not active_name or cache_active == active_name:
                ewh = np.asarray(self._stack_cache["ewh"])
                idx = max(0, min(int(time_index), (ewh.shape[2] - 1) if ewh.ndim >= 3 else 0))
                t_arr = self._stack_cache.get("t")
                t_val = None
                if t_arr is not None:
                    t_flat = np.asarray(t_arr).reshape(-1)
                    if t_flat.size:
                        t_val = t_flat[max(0, min(idx, t_flat.size - 1))]
                frame = {
                    "grid": np.asarray(ewh[:, :, idx] if ewh.ndim >= 3 else ewh, dtype=float),
                    "lon": np.asarray(self._stack_cache["lon"], dtype=float).squeeze(),
                    "lat": np.asarray(self._stack_cache["lat"], dtype=float).squeeze(),
                    "t": t_val,
                    "meta": cache_meta,
                }
                self._stack_frame_cache[frame_key] = frame
                return frame

        grid, lon, lat, t_val, meta = load_stack_slice_any(
            path,
            time_index=time_index,
            active_var=active_name,
            selection_meta=self._stack_cache_meta,
        )
        if grid is None or lon is None or lat is None:
            data = self.get_stack_data(path, active_var=active_name)
            ewh = np.asarray(data["ewh"])
            idx = max(0, min(int(time_index), (ewh.shape[2] - 1) if ewh.ndim >= 3 else 0))
            t_arr = data.get("t")
            t_val = None
            if t_arr is not None:
                t_flat = np.asarray(t_arr).reshape(-1)
                if t_flat.size:
                    t_val = t_flat[max(0, min(idx, t_flat.size - 1))]
            frame = {
                "grid": np.asarray(ewh[:, :, idx] if ewh.ndim >= 3 else ewh, dtype=float),
                "lon": np.asarray(data["lon"], dtype=float).squeeze(),
                "lat": np.asarray(data["lat"], dtype=float).squeeze(),
                "t": t_val,
                "meta": data.get("meta", {}) or {},
            }
        else:
            frame = {
                "grid": np.asarray(grid, dtype=float),
                "lon": np.asarray(lon, dtype=float).squeeze(),
                "lat": np.asarray(lat, dtype=float).squeeze(),
                "t": t_val,
                "meta": meta or {},
            }
        if len(self._stack_frame_cache) > 6:
            self._stack_frame_cache.clear()
        self._stack_frame_cache[frame_key] = frame
        return frame

    def load_basin_info(self):
        path = self.var_basin_data.get().strip()
        info = self.load_stack_info(path)
        self._basin_cache = self.get_stack_data(path, active_var=info["meta"].get("active_var"))
        self._basin_cache_path = path
        return info

    def _get_basin_data(self):
        path = self.var_basin_data.get().strip()
        if self._basin_cache is None or self._basin_cache_path != path:
            self.load_basin_info()
        return self._basin_cache

    def load_leakage_info(self):
        path = self.var_lrc_input.get().strip()
        info = self.load_stack_info(path)
        self._leakage_cache = self.get_stack_data(path, active_var=info["meta"].get("active_var"))
        self._leakage_cache_path = path
        return info

    def _get_leakage_data(self):
        path = self.var_lrc_input.get().strip()
        if self._leakage_cache is None or self._leakage_cache_path != path:
            self.load_leakage_info()
        return self._leakage_cache

    def _build_global_land_mask(self, lon_vec, lat_vec):
        mask, key = build_global_land_mask(
            np.asarray(lon_vec),
            np.asarray(lat_vec),
            root_dir=str(ROOT_DIR),
            cache_key=self._global_land_mask_key,
            cache_mask=self._global_land_mask,
        )
        self._global_land_mask_key = key
        self._global_land_mask = mask
        return mask

    def _build_leakage_mask(self, scope: str, lon_vec, lat_vec):
        scope = str(scope or "global").lower()
        if scope == "regional":
            mask, key = build_regional_leakage_mask(
                self.var_lrc_boundary.get().strip(),
                np.asarray(lon_vec),
                np.asarray(lat_vec),
                cache_key=self._regional_leak_mask_key,
                cache_mask=self._regional_leak_mask,
            )
            self._regional_leak_mask_key = key
            self._regional_leak_mask = mask
            return mask
        return self._build_global_land_mask(lon_vec, lat_vec)

    def _build_leakage_filter_options(self, in_path: str = "", data_meta: dict | None = None):
        return build_leakage_filter_options(
            raw_method=self.var_lrc_sf_method.get(),
            in_path=in_path,
            data_meta=data_meta,
            sf_ddk=self.var_lrc_sf_ddk.get(),
            parallel_enable=bool(getattr(self.cfg.parallel, "enable", False)),
            parallel_n_workers=int(getattr(self.cfg.parallel, "n_workers", 1)),
            frozen_allow_parallel=bool(getattr(self.cfg, "perf", {}).get("allow_frozen_parallel", False)),
            frozen_max_workers=int(getattr(self.cfg, "perf", {}).get("frozen_max_workers", 0) or 0),
            hsaf_n=int(self.cfg.filter.hankel.params.get("N", 30)),
            hsaf_p=int(self.cfg.filter.hankel.params.get("P", 10)),
            hsaf_k=int(self.cfg.filter.hankel.params.get("K", 6)),
            hsaf_j=int(self.cfg.filter.hankel.params.get("J", 1)),
            hsaf_input=getattr(self.cfg.filter, "pre_hankel_input", "P4M6"),
            sf_gauss=float(self.var_lrc_sf_gauss.get()),
            sf_fan_r1=float(self.var_lrc_sf_fan_r1.get()),
            sf_fan_r2=float(self.var_lrc_sf_fan_r2.get()),
            sf_hsa_ts=float(self.var_lrc_sf_hsa_ts.get()),
            sf_p4_deg=int(self.var_lrc_sf_p4_deg.get()),
            sf_p4_m=int(self.var_lrc_sf_p4_m.get()),
            lmax=int(self.cfg.inversion.Lmax),
            ddk_data_dir=str(self.cfg.filter.ddk.data_dir),
            log_info_cb=self._append_log,
            log_warn_cb=lambda t: self._append_log(t, tag="stderr"),
        )

    def _save_leakage_output(self, grid_out, lon_vec, lat_vec, t_arr, labels, in_path, out_path, suffix):
        return save_leakage_output(
            fmt=self.var_lrc_fmt.get(),
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


class MainWindowController:
    """Wires the Qt shell to the existing Python business logic."""

    def __init__(self, window):
        self.window = window
        self.signals = QtSignals()
        self.host = QtWorkflowHost(window, self.signals)
        self._threads: dict[str, threading.Thread] = {}
        self._canvas = None
        self._figure = None
        self._ax = None
        self._basin_preview_canvas = None
        self._basin_preview_figure = None
        self._basin_preview_ax = None
        self._basin_preview_toolbar = None
        self._basin_boundaries = []
        self._proj_scale = None
        self._proj_x0 = None
        self._preview_pick_state = None
        self._preview_full_view = None
        self._top_status_text = "READY"
        self._last_overall_pct = 0.0
        self._last_overall_detail = "0/0"
        self._pending_terminal_status: tuple[str, str] | None = None
        self._pending_terminal_scope = ""

        self._connect_signals()
        self._mount_plot_canvas()
        self._mount_basin_preview_canvas()
        self._bind_ui()
        self._bootstrap_default_config()

    def _connect_signals(self):
        self.signals.log.connect(self.on_log)
        self.signals.message.connect(self.on_message)
        self.signals.progress.connect(self.on_progress)
        self.signals.status.connect(self.on_status)
        self.signals.gfc_download_done.connect(self._on_gfc_download_done)
        self._run_watchdog = QTimer(self.window)
        self._run_watchdog.timeout.connect(self._poll_terminal_run_state)
        self._run_watchdog.start(600)

    def _bind_ui(self):
        w = self.window
        w.btn_run.clicked.connect(self.on_run_pipeline)
        w.btn_pause.clicked.connect(self.on_pause_active)
        w.btn_stop.clicked.connect(self.on_stop_active)
        w.btn_settings.clicked.connect(self.on_open_settings)
        w.btn_help.clicked.connect(self.on_open_help)

        w.page_dashboard.btn_load_config.clicked.connect(self.on_load_config)
        w.page_dashboard.btn_save_config.clicked.connect(self.on_save_config)
        w.page_dashboard.btn_validate_paths.clicked.connect(self.on_validate_paths)
        w.page_dashboard.btn_open_data_paths.clicked.connect(lambda: w.set_active_page("data_paths"))
        w.page_dashboard.btn_open_processing.clicked.connect(lambda: w.set_active_page("processing"))
        w.page_dashboard.btn_open_preview.clicked.connect(lambda: w.set_active_page("preview"))
        if w.page_dashboard.btn_run_full is not w.btn_run:
            w.page_dashboard.btn_run_full.clicked.connect(self.on_run_pipeline)

        w.page_data_paths.btn_load_config.clicked.connect(self.on_load_config)
        w.page_data_paths.btn_save_config.clicked.connect(self.on_save_config)
        w.page_data_paths.btn_validate_paths.clicked.connect(self.on_validate_paths)
        w.page_data_paths.btn_download_gfc_range.clicked.connect(self.on_download_gfc_range)
        w.page_data_paths.btn_open_download_site.clicked.connect(self.on_open_download_site)
        w.page_data_paths.cmb_gfc_center.currentTextChanged.connect(lambda *_args: self._sync_download_source_controls(update_options=False))
        w.page_data_paths.cmb_download_product.currentTextChanged.connect(lambda *_args: self._sync_download_source_controls(update_options=True))

        w.page_processing.btn_load_preset.clicked.connect(self.on_load_config)
        w.page_processing.btn_save_config.clicked.connect(self.on_save_config)
        w.page_processing.btn_tool_sh_to_grid.clicked.connect(self.on_tool_sh_to_grid)
        w.page_processing.btn_tool_grid_to_sh.clicked.connect(self.on_tool_grid_to_sh)

        for edit, btn, mode, dialog_filter in (
            (w.page_data_paths.edit_gfc_input_dir, w.page_data_paths.btn_gfc_browse, "dir", ""),
            (w.page_data_paths.edit_download_dir, w.page_data_paths.btn_download_dir_browse, "dir", ""),
            (w.page_data_paths.edit_ddk_data_dir, w.page_data_paths.btn_ddk_browse, "dir", ""),
            (w.page_data_paths.edit_main_output_root, w.page_data_paths.btn_output_browse, "dir", ""),
            (w.page_data_paths.edit_aux_path, w.page_data_paths.btn_aux_browse, "dir", ""),
            (w.page_data_paths.edit_boundary_root, w.page_data_paths.btn_boundary_root_browse, "dir", ""),
            (w.page_data_paths.edit_boundary_path, w.page_data_paths.btn_boundary_browse, "file", "Shapefiles (*.shp);;All Files (*)"),
            (w.page_data_paths.edit_low_degree_path, w.page_data_paths.btn_low_degree_browse, "file", "Text Files (*.txt);;All Files (*)"),
            (w.page_data_paths.edit_degree1_path, w.page_data_paths.btn_degree1_browse, "file", "Text Files (*.txt);;All Files (*)"),
            (w.page_data_paths.edit_gia_path, w.page_data_paths.btn_gia_browse, "file", "Text Files (*.txt);;All Files (*)"),
            (w.page_data_paths.edit_mascon_root, w.page_data_paths.btn_mascon_root_browse, "dir", ""),
            (w.page_data_paths.edit_mascon_reference, w.page_data_paths.btn_mascon_reference_browse, "file", "NetCDF/MAT (*.nc *.nc4 *.cdf *.mat);;All Files (*)"),
            (w.page_data_paths.edit_mascon_gad, w.page_data_paths.btn_mascon_gad_browse, "file", "NetCDF Files (*.nc *.nc4 *.cdf);;All Files (*)"),
            (w.page_data_paths.edit_mascon_gia, w.page_data_paths.btn_mascon_gia_browse, "file", "NetCDF Files (*.nc *.nc4 *.cdf);;All Files (*)"),
            (w.page_leakage.edit_lrc_input, w.page_leakage.btn_lrc_input_browse, "file", ""),
            (w.page_leakage.edit_reference_input, w.page_leakage.btn_reference_input_browse, "file", ""),
            (w.page_leakage.edit_lrc_output, w.page_leakage.btn_lrc_output_browse, "save_file", ""),
            (w.page_leakage.edit_regional_boundary, w.page_leakage.btn_regional_boundary_browse, "file_or_dir", ""),
            (w.page_basin.edit_data_file, w.page_basin.btn_data_browse, "file", ""),
            (w.page_basin.edit_boundary_file, w.page_basin.btn_boundary_browse, "file_or_dir", ""),
            (w.page_preview.edit_dataset_source, w.page_preview.btn_dataset_browse, "file", ""),
            (w.page_preview.edit_boundary_overlay, w.page_preview.btn_boundary_overlay_browse, "file_or_dir", "Boundary Files (*.shp *.txt *.bln);;All Files (*)"),
            (w.page_preview.edit_custom_overlay, w.page_preview.btn_custom_overlay_browse, "file_or_dir", "Shapefiles (*.shp);;All Files (*)"),
            (w.page_processing.edit_sh_tool_source, w.page_processing.btn_sh_tool_browse, "file", "GRACE/Grids (*.gfc *.mat *.nc *.nc4 *.cdf *.h5 *.hdf5);;All Files (*)"),
        ):
            btn.clicked.connect(
                lambda checked=False, target=edit, path_mode=mode, file_filter=dialog_filter: self.browse_into(target, path_mode, file_filter)
            )

        for edit, base_dir in (
            (w.page_data_paths.edit_gfc_input_dir, ROOT_DIR),
            (w.page_data_paths.edit_download_dir, ROOT_DIR),
            (w.page_data_paths.edit_ddk_data_dir, ROOT_DIR),
            (w.page_data_paths.edit_aux_path, ROOT_DIR),
            (w.page_data_paths.edit_boundary_root, ROOT_DIR),
            (w.page_data_paths.edit_boundary_path, ROOT_DIR),
            (w.page_data_paths.edit_low_degree_path, ROOT_DIR),
            (w.page_data_paths.edit_degree1_path, ROOT_DIR),
            (w.page_data_paths.edit_gia_path, ROOT_DIR),
            (w.page_data_paths.edit_mascon_root, ROOT_DIR),
            (w.page_data_paths.edit_mascon_reference, ROOT_DIR),
            (w.page_data_paths.edit_mascon_gad, w.page_data_paths.edit_mascon_root),
            (w.page_data_paths.edit_mascon_gia, w.page_data_paths.edit_mascon_root),
            (w.page_data_paths.edit_main_output_root, ROOT_DIR),
        ):
            edit.editingFinished.connect(lambda target=edit, base=base_dir: self._normalize_path_edit(target, base_dir=base))
            edit.textChanged.connect(lambda *_args: self._sync_data_path_badges())
        w.page_data_paths.edit_main_output_root.textChanged.connect(self._sync_logs_path_from_output_root)
        w.page_data_paths.edit_boundary_path.textChanged.connect(lambda *_args: self._sync_boundary_root_from_file())
        w.page_data_paths.edit_boundary_root.textChanged.connect(lambda *_args: self._sync_boundary_file_from_root())
        w.page_data_paths.edit_mascon_reference.textChanged.connect(lambda *_args: self._sync_mascon_root_from_reference())
        w.page_data_paths.edit_mascon_root.textChanged.connect(lambda *_args: self._sync_mascon_reference_from_root())
        w.page_data_paths.edit_gfc_input_dir.textChanged.connect(lambda *_args: self._refresh_detected_time_range())
        w.page_data_paths.btn_toggle_reference_roots.toggled.connect(self.on_toggle_reference_roots)

        for btn in (
            w.page_processing.btn_filter_gaussian,
            w.page_processing.btn_filter_p4m6,
            w.page_processing.btn_filter_gaussian_pnmn,
            w.page_processing.btn_filter_ddk,
            w.page_processing.btn_filter_fan,
            w.page_processing.btn_filter_fan_pnmn,
            w.page_processing.btn_filter_hsaf,
        ):
            btn.toggled.connect(self._sync_processing_filter_button_styles)
        for btn, panel_name in (
            (w.page_processing.btn_filter_gaussian, "gaussian"),
            (w.page_processing.btn_filter_p4m6, "pnmn"),
            (w.page_processing.btn_filter_gaussian_pnmn, "gaussian_pnmn"),
            (w.page_processing.btn_filter_ddk, "ddk"),
            (w.page_processing.btn_filter_fan, "fan"),
            (w.page_processing.btn_filter_fan_pnmn, "fan_pnmn"),
            (w.page_processing.btn_filter_hsaf, "hsaf"),
        ):
            btn.clicked.connect(lambda _checked=False, name=panel_name: self._select_processing_filter_panel(name))
        w.page_processing.cmb_hsaf_variant.currentTextChanged.connect(self._sync_processing_hsaf_controls)
        w.page_processing.slider_degree_order.valueChanged.connect(self._update_degree_order_label)
        w.page_processing.chk_manual_time_override.toggled.connect(self._sync_processing_time_override_state)
        w.page_processing.chk_remove_mean.toggled.connect(self._sync_processing_mean_controls)
        w.page_processing.cmb_anomaly_baseline.currentIndexChanged.connect(self._sync_processing_mean_controls)
        w.page_processing.chk_lowdeg_enable.toggled.connect(self._sync_processing_lowdeg_controls)
        for widget in (
            w.page_processing.chk_remove_mean,
            w.page_processing.chk_lowdeg_enable,
            w.page_processing.chk_replace_degree1,
            w.page_processing.chk_replace_c20,
            w.page_processing.chk_replace_c30,
            w.page_processing.chk_apply_gia,
            w.page_processing.cmb_anomaly_baseline,
            w.page_processing.edit_mean_start_ym,
            w.page_processing.edit_mean_end_ym,
        ):
            if hasattr(widget, "toggled"):
                widget.toggled.connect(self._sync_dashboard_run_summary)
            if hasattr(widget, "currentTextChanged"):
                widget.currentTextChanged.connect(self._sync_dashboard_run_summary)
            if hasattr(widget, "textChanged"):
                widget.textChanged.connect(self._sync_dashboard_run_summary)

        w.page_basin.btn_load_basin_info.clicked.connect(self.on_load_basin_info)
        if hasattr(w.page_basin, "btn_load_boundary_info"):
            w.page_basin.btn_load_boundary_info.clicked.connect(self.on_load_basin_boundary_info)
        if hasattr(w.page_basin, "btn_generate_mask"):
            w.page_basin.btn_generate_mask.clicked.connect(self.on_generate_basin_mask_preview)
        if hasattr(w.page_basin, "btn_preview_selected_basin"):
            w.page_basin.btn_preview_selected_basin.clicked.connect(lambda: self.on_refresh_basin_preview(show_errors=True))
        if hasattr(w.page_basin, "btn_refresh_basin_preview"):
            w.page_basin.btn_refresh_basin_preview.clicked.connect(lambda: self.on_refresh_basin_preview(show_errors=True))
        if hasattr(w.page_basin, "cmb_preview_basin"):
            w.page_basin.cmb_preview_basin.currentIndexChanged.connect(lambda *_args: self.on_basin_preview_target_changed())
        if hasattr(w.page_basin, "slider_basin_time_index"):
            w.page_basin.slider_basin_time_index.valueChanged.connect(lambda *_args: self.on_basin_preview_target_changed())
        w.page_basin.btn_tool_grid_to_series.clicked.connect(self.on_tool_grid_to_series)
        w.page_basin.btn_tool_harmonic_fit.clicked.connect(self.on_tool_harmonic_fit)
        w.page_basin.btn_run_basin.clicked.connect(self.on_run_basin)
        w.page_basin.btn_pause_basin.clicked.connect(lambda: self.on_pause_scope("basin"))
        w.page_basin.btn_stop_basin.clicked.connect(lambda: self.on_stop_scope("basin"))
        w.page_basin.cmb_basin_selection_mode.currentIndexChanged.connect(self.on_basin_selection_mode_changed)
        w.page_basin.table_basins.itemSelectionChanged.connect(self.on_basin_table_selection_changed)
        w.page_basin.btn_mode_multi.clicked.connect(lambda: self.set_basin_selection_mode(0))
        w.page_basin.btn_mode_global.clicked.connect(lambda: self.set_basin_selection_mode(1))
        w.page_basin.btn_mode_point.clicked.connect(lambda: self.set_basin_selection_mode(2))

        w.page_leakage.btn_load_leakage_info.clicked.connect(self.on_load_leakage_info)
        w.page_leakage.btn_run_leakage.clicked.connect(self.on_run_leakage)
        w.page_leakage.btn_pause_leakage.clicked.connect(lambda: self.on_pause_scope("leakage"))
        w.page_leakage.btn_stop_leakage.clicked.connect(lambda: self.on_stop_scope("leakage"))
        w.page_leakage.btn_open_preview_asset.clicked.connect(self.on_open_leakage_preview_asset)
        w.page_leakage.btn_open_preview_corrected.clicked.connect(self.on_open_leakage_preview_corrected)
        w.page_leakage.cmb_strategy_family.currentIndexChanged.connect(self.on_leakage_strategy_changed)
        w.page_leakage.cmb_correction_strategy.currentIndexChanged.connect(self.on_leakage_strategy_changed)
        w.page_leakage.cmb_scope.currentIndexChanged.connect(self.on_leakage_strategy_changed)
        w.page_leakage.cmb_preview_figure.currentIndexChanged.connect(self.on_refresh_leakage_preview)
        w.page_leakage.cmb_preview_layer.currentIndexChanged.connect(self.on_refresh_leakage_preview)
        w.page_leakage.cmb_preview_time.currentIndexChanged.connect(self.on_refresh_leakage_preview)

        w.page_preview.btn_load_stack.clicked.connect(self.on_load_stack_info)
        w.page_preview.btn_plot.clicked.connect(self.on_render_preview)
        w.page_preview.btn_export_figure.clicked.connect(self.on_export_figure)
        w.page_preview.btn_toggle_tools.clicked.connect(self.on_toggle_preview_tools)
        w.page_preview.btn_toggle_sidebar.clicked.connect(self.on_toggle_preview_sidebar)
        w.page_preview.btn_toggle_status.clicked.connect(self.on_toggle_preview_status)
        w.page_preview.slider_time_index.valueChanged.connect(self.on_preview_index_changed)
        w.page_preview.cmb_data_var.currentTextChanged.connect(lambda _t: self.on_preview_var_changed())
        w.page_preview.chk_auto_region.toggled.connect(self.on_preview_region_mode_changed)
        w.page_preview.chk_layer_boundaries.toggled.connect(self._sync_preview_overlay_controls)
        w.page_preview.chk_layer_rivers.toggled.connect(self._sync_preview_overlay_controls)
        self._sync_preview_overlay_controls()

        w.page_monitor.btn_pause_run.clicked.connect(self.on_pause_active)
        w.page_monitor.btn_abort_pipeline.clicked.connect(self.on_stop_active)
        w.page_monitor.btn_restart_instance.clicked.connect(self.on_reset_monitor)

    def _bootstrap_default_config(self):
        if DEFAULT_USER_CFG_PATH.exists():
            self.load_config_from_path(DEFAULT_USER_CFG_PATH)
        else:
            self.push_config_to_ui(self.host.cfg)
            self.refresh_dashboard()
        self.on_preview_region_mode_changed(self.window.page_preview.chk_auto_region.isChecked())

    def _mount_plot_canvas(self):
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
        from matplotlib.figure import Figure
        from PySide6.QtWidgets import QVBoxLayout

        self._figure = Figure(figsize=(10, 6), dpi=100)
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._nav_toolbar = NavigationToolbar2QT(self._canvas, self.window)
        self._nav_toolbar.setMovable(False)
        keep = {"Home", "Back", "Forward", "Pan", "Zoom"}
        for action in list(self._nav_toolbar.actions()):
            text = (action.text() or "").strip()
            if text not in keep:
                self._nav_toolbar.removeAction(action)
            elif text == "Home":
                with contextlib.suppress(Exception):
                    action.triggered.disconnect()
                action.triggered.connect(self.on_preview_home)
        self._canvas.mpl_connect("button_press_event", self.on_preview_canvas_event)
        self._canvas.mpl_connect("motion_notify_event", self.on_preview_canvas_event)
        layout = self.window.page_preview.plot_container.layout()
        if layout is None:
            layout = QVBoxLayout(self.window.page_preview.plot_container)
            layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)
        toolbar_layout = self.window.page_preview.plot_toolbar_host.layout()
        if toolbar_layout is None:
            toolbar_layout = QHBoxLayout(self.window.page_preview.plot_toolbar_host)
            toolbar_layout.setContentsMargins(6, 2, 6, 2)
            toolbar_layout.setSpacing(2)
        toolbar_layout.addWidget(self._nav_toolbar, 0, Qt.AlignRight | Qt.AlignVCenter)
        self._ax = self._figure.add_subplot(111)
        self._sync_preview_tools_button()

    def _mount_basin_preview_canvas(self):
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
        from matplotlib.figure import Figure
        from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

        page = self.window.page_basin
        self._basin_preview_figure = Figure(figsize=(7.2, 4.6), dpi=100)
        self._basin_preview_canvas = FigureCanvasQTAgg(self._basin_preview_figure)
        self._basin_preview_toolbar = NavigationToolbar2QT(self._basin_preview_canvas, self.window)
        self._basin_preview_toolbar.setMovable(False)
        keep = {"Home", "Back", "Forward", "Pan", "Zoom", "Save"}
        for action in list(self._basin_preview_toolbar.actions()):
            text = (action.text() or "").strip()
            if text and text not in keep:
                self._basin_preview_toolbar.removeAction(action)

        plot_layout = page.basin_preview_plot_host.layout()
        if plot_layout is None:
            plot_layout = QVBoxLayout(page.basin_preview_plot_host)
            plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.addWidget(self._basin_preview_canvas)

        toolbar_layout = page.basin_preview_toolbar_host.layout()
        if toolbar_layout is None:
            toolbar_layout = QHBoxLayout(page.basin_preview_toolbar_host)
            toolbar_layout.setContentsMargins(0, 0, 0, 0)
            toolbar_layout.setSpacing(2)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self._basin_preview_toolbar, 0, Qt.AlignRight | Qt.AlignVCenter)

        self._basin_preview_ax = self._basin_preview_figure.add_subplot(111)
        self._basin_preview_ax.set_facecolor("#eef4f8")
        self._basin_preview_ax.text(0.5, 0.5, "Load grid data to render preview", ha="center", va="center", transform=self._basin_preview_ax.transAxes)
        self._basin_preview_canvas.draw_idle()

    def refresh_plot_theme(self):
        if self._figure is None or self._ax is None:
            return
        self._figure.set_facecolor(COLOR["surface"])
        self._ax.set_facecolor(COLOR["surface"])
        if self._canvas is not None:
            self._canvas.draw_idle()

    def _native_path(self, value, base_dir=None) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        base_text = ""
        if isinstance(base_dir, QLineEdit):
            base_text = base_dir.text().strip()
        elif callable(base_dir):
            base_text = str(base_dir() or "").strip()
        elif base_dir:
            base_text = str(base_dir).strip()
        candidate = Path(os.path.expandvars(os.path.expanduser(text)))
        if base_text and not candidate.is_absolute():
            candidate = Path(os.path.expandvars(os.path.expanduser(base_text))) / candidate
        return QDir.toNativeSeparators(os.path.normpath(str(candidate)))

    def _display_path(self, value, fallback=None, base_dir=None, require_exists: bool = False) -> str:
        normalized = self._native_path(value, base_dir=base_dir)
        if normalized and (not require_exists or Path(normalized).exists()):
            return normalized
        if fallback is None:
            return normalized
        return self._native_path(fallback)

    def _resolve_boundary_file(self, value) -> str:
        normalized = self._native_path(value, base_dir=ROOT_DIR)
        if not normalized:
            normalized = self._native_path(DEFAULT_DATA_PATHS["BOUNDARY_SHP"])
        candidate = Path(normalized)
        if candidate.is_dir():
            preferred = candidate / "LargeBasin.shp"
            if preferred.exists():
                return self._native_path(preferred)
            first = next(iter(sorted(candidate.glob("*.shp"))), None)
            if first is not None:
                return self._native_path(first)
        if candidate.suffix.lower() != ".shp" and candidate.with_suffix(".shp").exists():
            return self._native_path(candidate.with_suffix(".shp"))
        if candidate.exists():
            return self._native_path(candidate)
        return self._native_path(DEFAULT_DATA_PATHS["BOUNDARY_SHP"])

    def _resolve_mascon_reference_file(self, mascon_dir, pattern: str = "") -> str:
        root = Path(self._display_path(mascon_dir, fallback=DEFAULT_DATA_PATHS["MASCON_DIR"], base_dir=ROOT_DIR, require_exists=False))
        pattern_text = str(pattern or "").strip()
        if pattern_text and "{YYYYMM}" not in pattern_text:
            candidate = Path(self._native_path(pattern_text, base_dir=root))
            if candidate.exists():
                return self._native_path(candidate)
        default_file = Path(DEFAULT_DATA_PATHS["MASCON_REFERENCE_FILE"])
        if default_file.exists():
            return self._native_path(default_file)
        files = [p for p in sorted(root.glob("*.nc")) if "GAD-component" not in p.name and "GIA-component" not in p.name]
        if files:
            return self._native_path(files[0])
        return self._native_path(default_file)

    def _validate_shapefile(self, value: str) -> tuple[str, str]:
        path_text = self._resolve_boundary_file(value)
        shp_path = Path(path_text)
        if not shp_path.exists():
            return ("Missing", "danger")
        required = [shp_path.with_suffix(".shx"), shp_path.with_suffix(".dbf"), shp_path.with_suffix(".prj")]
        missing = [path.suffix.lower() for path in required if not path.exists()]
        if missing:
            return (f"Missing {' '.join(missing)}", "warning")
        return ("OK", "success")

    def _set_badge_state(self, badge: QLabel, text: str, variant: str) -> None:
        badge.setText(text)
        badge.setProperty("variant", variant)
        badge.style().unpolish(badge)
        badge.style().polish(badge)

    def _set_edit_text(self, edit: QLineEdit, text: str, block_signals: bool = False) -> None:
        blocker = QSignalBlocker(edit) if block_signals else None
        edit.setText(text)
        edit.setToolTip(text or "")
        if text:
            edit.setCursorPosition(0)
        if blocker is not None:
            del blocker

    def _enabled_filter_names(self) -> list[str]:
        page = self.window.page_processing
        mapping = (
            (page.btn_filter_gaussian, "Gaussian"),
            (page.btn_filter_p4m6, "P4M6"),
            (page.btn_filter_gaussian_pnmn, "P4M6_GAUSS"),
            (page.btn_filter_ddk, self._combo_value(page.cmb_ddk_type) or "DDK4"),
            (page.btn_filter_fan, "FAN"),
            (page.btn_filter_fan_pnmn, "P4M6_FAN"),
            (page.btn_filter_hsaf, "HSAF"),
        )
        return [name for btn, name in mapping if btn.isChecked()]

    def _sync_processing_filter_button_styles(self, *_args) -> None:
        self._sync_processing_filter_panels()
        self._sync_processing_hsaf_controls()
        self._sync_dashboard_run_summary()

    def _processing_filter_buttons(self) -> dict[str, QCheckBox]:
        page = self.window.page_processing
        return {
            "gaussian": page.btn_filter_gaussian,
            "pnmn": page.btn_filter_p4m6,
            "gaussian_pnmn": page.btn_filter_gaussian_pnmn,
            "ddk": page.btn_filter_ddk,
            "fan": page.btn_filter_fan,
            "fan_pnmn": page.btn_filter_fan_pnmn,
            "hsaf": page.btn_filter_hsaf,
        }

    def _sync_processing_filter_panels(self) -> None:
        page = self.window.page_processing
        buttons = self._processing_filter_buttons()
        active = str(getattr(page, "_selected_filter_panel", "") or "")
        active_checked = bool(active and active in buttons and buttons[active].isChecked())
        title_map = {
            "gaussian": "Gaussian 参数",
            "pnmn": "PnMl 参数",
            "gaussian_pnmn": "Gaussian+PnMl 参数",
            "ddk": "DDK 参数",
            "fan": "FAN 参数",
            "fan_pnmn": "FAN+PnMl 参数",
            "hsaf": "HSAF 参数",
        }
        page.lbl_filter_parameter_title.setText(title_map.get(active, "参数设置") if active_checked else "参数设置")
        page.panel_filter_empty.setVisible(not active_checked)
        page.panel_filter_gaussian.setVisible(active_checked and active in {"gaussian", "gaussian_pnmn"})
        page.panel_filter_pnmn.setVisible(active_checked and active in {"pnmn", "gaussian_pnmn", "fan_pnmn", "hsaf"})
        page.panel_filter_gaussian_pnmn.setVisible(False)
        page.panel_filter_ddk.setVisible(active_checked and active == "ddk")
        page.panel_filter_fan.setVisible(active_checked and active in {"fan", "fan_pnmn"})
        page.panel_filter_fan_pnmn.setVisible(False)
        for name, button in buttons.items():
            button.setProperty("filterActive", bool(active_checked and name == active))
            button.style().unpolish(button)
            button.style().polish(button)

    def _select_processing_filter_panel(self, panel_name: str) -> None:
        page = self.window.page_processing
        button = self._processing_filter_buttons().get(str(panel_name))
        page._selected_filter_panel = str(panel_name) if button is not None and button.isChecked() else ""
        self._sync_processing_filter_button_styles()

    def _default_hsaf_adaptive_zones(self, params: Optional[dict] = None) -> list[dict]:
        base = dict(params or {})
        n = int(base.get("N", 30) or 30)
        p = int(base.get("P", 8) or 8)
        k = int(base.get("K", 4) or 4)
        j = int(base.get("J", 1) or 1)
        return [
            {"lat_range": [-90.0, -30.0], "params": {"N": n, "P": p, "K": k, "J": j}},
            {"lat_range": [-30.0, 30.0], "params": {"N": n, "P": p, "K": k, "J": j}},
            {"lat_range": [30.0, 90.0], "params": {"N": n, "P": p, "K": k, "J": j}},
        ]

    def _hsaf_variant_to_ui(self, value: str) -> str:
        return "纬度自适应" if str(value or "").strip().lower() == "adaptive" else "全局固定"

    def _hsaf_variant_from_ui(self, value: str) -> str:
        text = str(value or "").strip().lower()
        return "adaptive" if ("adaptive" in text or "自适应" in text) else "global"

    @staticmethod
    def _combo_value(combo: QComboBox) -> str:
        data = combo.currentData()
        return str(data if data not in (None, "") else combo.currentText()).strip()

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: str) -> None:
        value = str(value or "").strip()
        idx = combo.findData(value)
        if idx < 0:
            idx = combo.findText(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            combo.setCurrentText(value)

    @staticmethod
    def _leakage_label(value: str) -> str:
        mapping = {
            "grid_stack": "\u7f51\u683c\u6808",
            "official_land_grid": "\u5b98\u65b9\u9646\u5730\u683c\u7f51",
            "official_scaling_grid": "\u5b98\u65b9\u7f29\u653e\u683c\u7f51",
            "mascon_native": "Mascon \u539f\u751f\u4ea7\u54c1",
            "FORWARD_MODELING": "\u533a\u57df\u6b63\u6f14\u5efa\u6a21",
            "BASIN_SCALE_FACTOR": "\u533a\u57df\u5c3a\u5ea6\u56e0\u5b50",
            "GRIDDED_GAIN_FACTOR": "\u683c\u70b9\u5c3a\u5ea6\u56e0\u5b50\uff08\u9ad8\u7ea7\uff09",
            "OFFICIAL_SCALING": "\u5b98\u65b9\u7f29\u653e/\u589e\u76ca",
            "OFFICIAL_LAND_SCALING": "\u5b98\u65b9\u9646\u5730 scaling",
            "OFFICIAL_OCEAN_NATIVE": "\u5b98\u65b9\u6d77\u6d0b\u539f\u751f",
            "OFFICIAL_MASCON_NATIVE": "\u5b98\u65b9 Mascon \u539f\u751f\uff08\u4e0d\u91cd\u590d\u6821\u6b63\uff09",
            "GLOBAL_COASTAL_GAUSSIAN": "\u5168\u7403\u6d77\u5cb8\u7ebf Gaussian",
            "GLOBAL_REGULARIZED": "\u5168\u7403\u6b63\u5219\u5316\u6062\u590d",
            "MODEL_BASED_ADDITIVE": "\u52a0\u6cd5\u6821\u6b63\uff08\u9ad8\u7ea7\uff09",
            "inland_basin": "\u5185\u9646\u6d41\u57df",
            "lake_reservoir": "\u6e56\u6cca/\u6c34\u5e93",
            "coastal": "\u6d77\u5cb8\u5e26",
            "cryosphere": "\u51b0\u51bb\u5708",
            "GAUSSIAN": "Gaussian",
            "FAN": "FAN",
            "FAN_DECORRELATION": "FAN+P4M6",
            "P4M6": "P4M6",
            "DDK4": "DDK4",
            "DDK1": "DDK1",
            "DDK2": "DDK2",
            "DDK3": "DDK3",
            "DDK5": "DDK5",
            "DDK6": "DDK6",
            "DDK7": "DDK7",
            "DDK8": "DDK8",
            "HSAF": "HSAF",
            "NONE": "\u672a\u8bc6\u522b",
            "regional": "\u533a\u57df\u6a21\u5f0f",
            "global": "\u5168\u7403\u6a21\u5f0f",
            "official": "\u5b98\u65b9/\u539f\u751f",
            "global_coastal": "\u5168\u7403\u6d77\u5cb8\u7ebf",
            "global_regularized": "\u5168\u7403\u6062\u590d",
            "auto": "\u81ea\u52a8\u63a8\u8350",
            "none": "\u65e0",
            "mean": "\u5747\u503c\u573a",
            "median": "\u4e2d\u4f4d\u573a",
            "trend": "\u8d8b\u52bf\u573a",
            "first": "\u9996\u65f6\u6b21",
            "direct": "\u76f4\u63a5\u5e94\u7528",
            "land_scaling": "\u9646\u5730 scaling",
            "ocean_native": "\u6d77\u6d0b\u539f\u751f",
        }
        return mapping.get(str(value), str(value))



    def _sync_processing_hsaf_controls(self, *_args) -> None:
        page = self.window.page_processing
        hsaf_enabled = page.btn_filter_hsaf.isChecked()
        hsaf_active = str(getattr(page, "_selected_filter_panel", "") or "") == "hsaf"
        hsaf_visible = bool(hsaf_enabled and hsaf_active)
        variant = self._hsaf_variant_from_ui(self._combo_value(page.cmb_hsaf_variant)) if hasattr(page, "cmb_hsaf_variant") else "global"
        page.hsaf_detail_panel.setVisible(hsaf_visible)
        page.hsaf_detail_panel.setEnabled(hsaf_enabled)
        page.hsaf_global_panel.setVisible(hsaf_visible and variant != "adaptive")
        page.hsaf_adaptive_panel.setVisible(hsaf_visible and variant == "adaptive")
        self.window.refresh_translations()

    def _update_degree_order_label(self, value: int) -> None:
        self.window.page_processing.lbl_degree_order.setText(str(int(value)))
        self._sync_dashboard_run_summary()

    def _detect_time_entries_for_ui(self) -> list:
        gfc_dir = self._native_path(self.window.page_data_paths.edit_gfc_input_dir.text(), base_dir=ROOT_DIR)
        if not gfc_dir or not Path(gfc_dir).exists():
            return []
        cfg_dict = copy.deepcopy(getattr(self.host.cfg, "_raw", {}) or getattr(self.host.default_cfg, "_raw", {}))
        cfg_dict.setdefault("path", {})["GFC"] = gfc_dir
        cfg_dict.setdefault("time", {})["auto_detect_gfc"] = True
        cfg = Config(cfg_dict)
        try:
            return build_time_index(cfg)
        except Exception:
            return []

    def _refresh_detected_time_range(self) -> None:
        page = self.window.page_processing
        entries = self._detect_time_entries_for_ui()
        if entries:
            detected_text = f"{entries[0].ym} -> {entries[-1].ym} ({len(entries)} months)"
            detected_start = self._date_from_ym(entries[0].ym)
            detected_end = self._date_from_ym(entries[-1].ym)
            self._set_edit_text(self.window.page_data_paths.edit_download_start_ym, entries[0].ym, block_signals=True)
            self._set_edit_text(self.window.page_data_paths.edit_download_end_ym, entries[-1].ym, block_signals=True)
        else:
            detected_text = "Detected from GFC files: no valid files found."
            detected_start = ""
            detected_end = ""
            if not self.window.page_data_paths.edit_download_start_ym.text().strip():
                self._set_edit_text(self.window.page_data_paths.edit_download_start_ym, "", block_signals=True)
            if not self.window.page_data_paths.edit_download_end_ym.text().strip():
                self._set_edit_text(self.window.page_data_paths.edit_download_end_ym, "", block_signals=True)
        page.lbl_detected_time_range.setText(detected_text)
        self.window.page_data_paths.lbl_gfc_detected_range.setText(detected_text)
        if not page.chk_manual_time_override.isChecked():
            self._set_edit_text(page.edit_start_date, detected_start, block_signals=True)
            self._set_edit_text(page.edit_end_date, detected_end, block_signals=True)
        self.refresh_dashboard()

    def _sync_download_source_controls(self, update_options: bool = True) -> None:
        page = self.window.page_data_paths
        product_type = self._download_product_type()
        if update_options:
            current = self._combo_value(page.cmb_gfc_center)
            values = ["CSR", "JPL", "GSFC"] if product_type == "MASCON_NC" else ["自动", "CSR", "JPL", "GFZ", "HUST", "ITSG"]
            with QSignalBlocker(page.cmb_gfc_center):
                page.cmb_gfc_center.clear()
                for value in values:
                    page.cmb_gfc_center.addItem(value, value)
                page.cmb_gfc_center.setCurrentText(current if current in values else values[0])
        center = self._configured_gfc_center()
        if hasattr(page, "cmb_mascon_resolution"):
            page.cmb_mascon_resolution.setVisible(product_type == "MASCON_NC")
        page.btn_download_gfc_range.setText("下载 Mascon" if product_type == "MASCON_NC" else "下载 GFC")
        page.btn_download_gfc_range.setToolTip(page.lbl_gfc_download_status.text())
        if product_type == "GSM" and center in {"CSR", "JPL", "GFZ"}:
            self._apply_low_degree_files_for_center(center)
            login = current_earthdata_login()
            if login:
                page.lbl_gfc_download_status.setText(f"{center} GSM 使用 PO.DAAC；Earthdata 登录态：{login}。")
            else:
                page.lbl_gfc_download_status.setText(f"{center} GSM 使用 PO.DAAC；下载前会请求 Earthdata 登录。")
        elif product_type == "GSM" and center in {"HUST", "ITSG"}:
            page.lbl_gfc_download_status.setText(f"{center} GSM 使用 ICGEM 下载，无需 Earthdata 登录。")
        elif product_type == "MASCON_NC":
            page.lbl_gfc_download_status.setText("Mascon NC 支持 CSR、JPL、GSFC；分辨率需与机构发布产品匹配。")
        page.btn_open_download_site.setToolTip(self._download_source_url(product_type, center))
        page.btn_download_gfc_range.setToolTip(page.lbl_gfc_download_status.text())

    def _configured_gfc_center(self) -> str:
        page = self.window.page_data_paths
        selected = self._combo_value(page.cmb_gfc_center) if hasattr(page, "cmb_gfc_center") else "自动"
        if str(selected).upper() not in {"AUTO", "自动"}:
            return normalize_center(selected)
        center = infer_center_from_gfc_dir(self._native_path(page.edit_gfc_input_dir.text(), base_dir=ROOT_DIR))
        return center if center != "UNKNOWN" else "CSR"

    def _configured_mascon_resolution(self) -> str | None:
        page = self.window.page_data_paths
        if not hasattr(page, "cmb_mascon_resolution"):
            return None
        return self._combo_value(page.cmb_mascon_resolution).replace("°", "").strip()

    def _download_product_type(self) -> str:
        page = self.window.page_data_paths
        value = self._combo_value(page.cmb_download_product) if hasattr(page, "cmb_download_product") else "GSM 文件"
        return "MASCON_NC" if "MASCON" in str(value).upper() else "GSM"

    def _download_needs_earthdata(self, product_type: str, center: str) -> bool:
        center = normalize_center(center)
        if product_type == "MASCON_NC":
            return center.startswith("JPL") or center == "JPL"
        return center in {"CSR", "JPL", "GFZ"}

    def _download_source_url(self, product_type: str | None = None, center: str | None = None) -> str:
        product_type = product_type or self._download_product_type()
        center = normalize_center(center or self._configured_gfc_center())
        if product_type == "MASCON_NC":
            if center == "CSR":
                return "https://www2.csr.utexas.edu/grace/RL06_mascons.html"
            if center == "GSFC":
                return "https://earth.gsfc.nasa.gov/geo/data/grace-mascons"
            return "https://podaac.jpl.nasa.gov/dataset/TELLUS_GRAC-GRFO_MASCON_GRID_RL06.3_V4"
        if center == "HUST":
            return "https://icgem.gfz-potsdam.de/sp/03_other/HUST/HUST-Grace2016/unfiltered"
        if center == "ITSG":
            return "https://icgem.gfz-potsdam.de/sp/03_other/ITSG/ITSG-Grace2018/monthly"
        return CMR_GRANULE_URL

    def on_open_download_site(self) -> None:
        url = self._download_source_url()
        webbrowser.open(url)
        self.on_log(f"[GFC] Opened data source page: {url}", "stdout")

    def _ensure_earthdata_auth_for_download(self, product_type: str, center: str) -> bool:
        if not self._download_needs_earthdata(product_type, center):
            return True
        if has_earthdata_credentials():
            return True
        return self.on_earthdata_auth(require_credentials=True)

    def _low_degree_dir(self) -> Path:
        current = self.window.page_data_paths.edit_low_degree_path.text().strip()
        if current:
            return Path(self._native_path(current, base_dir=ROOT_DIR)).parent
        return Path(DEFAULT_DATA_PATHS["LOW_DEGREE_C20"]).parent

    def _discover_low_degree_files(self, low_degree_dir: str | Path | None = None) -> dict[str, Path]:
        root = Path(low_degree_dir) if low_degree_dir else self._low_degree_dir()
        return {
            "C20": root / "TN-14_C30_C20_GSFC_SLR.txt",
            "DEGREE1_CSR": root / "TN-13_GEOC_CSR_RL0603.txt",
            "DEGREE1_JPL": root / "TN-13_GEOC_JPL_RL0603.txt",
            "DEGREE1_GFZ": root / "TN-13_GEOC_GFZ_RL0603.txt",
        }

    def _apply_low_degree_files_for_center(self, center: str, files: dict[str, Path] | None = None) -> None:
        page = self.window.page_data_paths
        center = normalize_center(center)
        files = files or self._discover_low_degree_files()
        c20_path = files.get("C20")
        degree1_path = files.get(f"DEGREE1_{center}")
        if c20_path and c20_path.exists():
            self._set_edit_text(page.edit_low_degree_path, self._native_path(c20_path), block_signals=True)
        if degree1_path and degree1_path.exists():
            self._set_edit_text(page.edit_degree1_path, self._native_path(degree1_path), block_signals=True)
        if hasattr(page, "cmb_gfc_center"):
            self._set_combo_value(page.cmb_gfc_center, center)
        page.lbl_gfc_download_status.setText(f"Low-degree: {center} TN-13 selected; TN-14 C20/C30 selected.")
        self._sync_data_path_badges()

    def on_auto_low_degree_from_gsm(self) -> None:
        page = self.window.page_data_paths
        center = infer_center_from_gfc_dir(self._native_path(page.edit_gfc_input_dir.text(), base_dir=ROOT_DIR))
        if center == "UNKNOWN":
            center = self._configured_gfc_center()
        self._apply_low_degree_files_for_center(center)
        self.on_log(f"[GFC] Auto low-degree selection center={center}", "stdout")

    def _gfc_download_range(self) -> tuple[str, str]:
        download_page = self.window.page_data_paths
        start = self._ym_from_date(download_page.edit_download_start_ym.text().strip())
        end = self._ym_from_date(download_page.edit_download_end_ym.text().strip())
        page = self.window.page_processing
        if not start:
            start = self._ym_from_date(page.edit_start_date.text().strip())
        if not end:
            end = self._ym_from_date(page.edit_end_date.text().strip())
        if not start or not end:
            entries = self._detect_time_entries_for_ui()
            if entries:
                start, end = entries[0].ym, entries[-1].ym
        if not start or not end:
            raise ValueError("Set a valid start/end month before downloading files.")
        return start, end

    def on_download_gfc_range(self) -> None:
        page = self.window.page_data_paths
        download_dir = self._native_path(page.edit_download_dir.text(), base_dir=ROOT_DIR)
        if not download_dir:
            self._show_warning("下载数据", "请先设置下载文件夹。")
            return
        start_ym, end_ym = self._gfc_download_range()
        center = self._configured_gfc_center()
        product_type = self._download_product_type()
        if product_type == "MASCON_NC" and center not in {"CSR", "JPL", "GSFC"}:
            self._show_warning("下载 Mascon", "Mascon NC 下载目前支持 CSR、JPL 和 GSFC。")
            return
        if not self._ensure_earthdata_auth_for_download(product_type, center):
            return
        low_degree_dir = self._low_degree_dir()
        page.lbl_gfc_download_status.setText(f"正在下载 {center} {product_type}：{start_ym} 到 {end_ym}...")

        def progress(text: str) -> None:
            self.signals.log.emit(f"[GFC] {text}", "stdout")

        def progress_pct(pct: float, text: str) -> None:
            self.signals.progress.emit("download", pct, text)

        def task() -> None:
            if product_type == "MASCON_NC":
                result = download_mascon_nc(
                    out_dir=download_dir,
                    source=center,
                    start_ym=start_ym,
                    end_ym=end_ym,
                    resolution=self._configured_mascon_resolution(),
                    progress=progress,
                    progress_pct=progress_pct,
                )
            else:
                result = download_gfc_range(
                    gfc_dir=download_dir,
                    start_ym=start_ym,
                    end_ym=end_ym,
                    center=center,
                    low_degree_dir=low_degree_dir,
                    progress=progress,
                    progress_pct=progress_pct,
                )
            self.signals.gfc_download_done.emit(result)

        self._run_in_thread("download", task, "DOWNLOADING DATA")

    def _on_gfc_download_done(self, result) -> None:
        page = self.window.page_data_paths
        if getattr(result, "product_type", "GSM") == "GSM":
            if result.files or result.skipped:
                self._set_edit_text(page.edit_gfc_input_dir, self._native_path(page.edit_download_dir.text(), base_dir=ROOT_DIR), block_signals=True)
            self._apply_low_degree_files_for_center(result.center, result.low_degree_files or None)
        elif result.files:
            self._set_edit_text(page.edit_mascon_reference, self._native_path(result.files[0]), block_signals=True)
        self._refresh_detected_time_range()
        page.lbl_gfc_download_status.setText(
            f"{getattr(result, 'product_type', 'GSM')} 下载完成：新增 {len(result.files)} 个，已存在 {len(result.skipped)} 个；机构={result.center}。"
        )
        self.on_log(
            f"[GFC] Download complete type={getattr(result, 'product_type', 'GSM')} center={result.center} downloaded={len(result.files)} skipped={len(result.skipped)}",
            "stdout",
        )

    def on_earthdata_auth(self, require_credentials: bool = False) -> bool:
        dialog = QDialog(self.window)
        dialog.setWindowTitle("Earthdata Login")
        dialog.setModal(True)
        dialog.resize(620, 320)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 14, 16, 14)
        current_login = current_earthdata_login()
        netrc_path = Path.home() / ".netrc"
        label = QLabel(
            f"Current local Earthdata state: {current_login or 'none'}\n"
            f"Token store: {EARTHDATA_TOKEN_STORE}\n"
            f"netrc file: {netrc_path}\n"
            "Open the official Earthdata token page in your browser, sign in there, generate a user token, then paste it below. "
            "Tokens are stored in a local token store, not in JSON configs."
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        btn_open = QPushButton("Open Earthdata Token Page")
        btn_open.setObjectName("PrimaryButton")
        btn_open.clicked.connect(lambda: webbrowser.open(EARTHDATA_TOKEN_URL))
        layout.addWidget(btn_open, 0, Qt.AlignLeft)
        form = QFormLayout()
        edit_label = QLineEdit(current_login or "earthdata")
        edit_token = QLineEdit()
        edit_token.setEchoMode(QLineEdit.Password)
        chk_replace = QCheckBox("Set this token as active")
        chk_replace.setChecked(True)
        chk_clear = QCheckBox("Clear saved Earthdata tokens")
        chk_clear_netrc = QCheckBox("Clear local .netrc Earthdata credentials")
        form.addRow("Account Label", edit_label)
        form.addRow("User Token", edit_token)
        form.addRow("", chk_replace)
        form.addRow("", chk_clear)
        form.addRow("", chk_clear_netrc)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        if dialog.exec() != QDialog.Accepted:
            if require_credentials:
                self._show_warning("Earthdata Auth", "Earthdata credentials are required for this download.")
            return False
        try:
            cleared: list[str] = []
            if chk_clear.isChecked():
                path = clear_earthdata_token()
                cleared.append(f"tokens: {path}")
                self.on_log(f"[AUTH] Cleared Earthdata tokens in {path}", "stdout")
            if chk_clear_netrc.isChecked():
                path = clear_earthdata_credentials()
                cleared.append(f"netrc: {path}")
                self.on_log(f"[AUTH] Cleared Earthdata .netrc credentials in {path}", "stdout")
            if cleared:
                page = self.window.page_data_paths
                page.lbl_gfc_download_status.setText("Earthdata credentials cleared from " + "; ".join(cleared) + ".")
                return not require_credentials
            path = save_earthdata_token(edit_label.text(), edit_token.text(), replace_active=chk_replace.isChecked())
            self.window.page_data_paths.lbl_gfc_download_status.setText(f"Earthdata token saved to {path}.")
            self.on_log(f"[AUTH] Saved Earthdata token label={edit_label.text().strip()} in {path}", "stdout")
            return True
        except Exception as exc:
            self._show_warning("Earthdata Auth", str(exc))
            return False

    def _sync_processing_time_override_state(self, checked: bool) -> None:
        page = self.window.page_processing
        page.edit_start_date.setReadOnly(not checked)
        page.edit_end_date.setReadOnly(not checked)
        self._refresh_detected_time_range()
        self._sync_dashboard_run_summary()

    def _sync_processing_mean_controls(self, *_args) -> None:
        page = self.window.page_processing
        enabled = page.chk_remove_mean.isChecked()
        baseline_mode = self._combo_value(page.cmb_anomaly_baseline)
        custom_enabled = enabled and baseline_mode == "custom"
        page.cmb_anomaly_baseline.setEnabled(enabled)
        if hasattr(page, "row_anomaly_baseline"):
            page.row_anomaly_baseline.setVisible(enabled)
        for widget_name in ("row_mean_baseline_range", "edit_mean_start_ym", "edit_mean_end_ym"):
            widget = getattr(page, widget_name, None)
            if widget is not None:
                widget.setVisible(custom_enabled)
                widget.setEnabled(custom_enabled)
        self._sync_dashboard_run_summary()

    def _sync_processing_lowdeg_controls(self, *_args) -> None:
        page = self.window.page_processing
        enabled = page.chk_lowdeg_enable.isChecked()
        for chk in (page.chk_replace_degree1, page.chk_replace_c20, page.chk_replace_c30):
            chk.setEnabled(enabled)
        if hasattr(page, "lowdeg_panel"):
            page.lowdeg_panel.setVisible(enabled)
        self._sync_dashboard_run_summary()

    def set_basin_selection_mode(self, index: int) -> None:
        page = self.window.page_basin
        index = max(0, min(2, int(index)))
        if page.cmb_basin_selection_mode.currentIndex() != index:
            page.cmb_basin_selection_mode.setCurrentIndex(index)
        self.on_basin_selection_mode_changed(index)

    def on_basin_selection_mode_changed(self, index: int) -> None:
        page = self.window.page_basin
        index = max(0, min(2, int(index)))
        for idx, btn in enumerate((page.btn_mode_multi, page.btn_mode_global, page.btn_mode_point)):
            btn.setChecked(idx == index)
            btn.setObjectName("PrimaryButton" if idx == index else "GhostButton")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        if hasattr(page, "lbl_selected_basin"):
            selected = self._preview_basin_name()
            page.lbl_selected_basin.setText(f"Preview basin: {selected or 'first boundary feature'}")

    def on_basin_table_selection_changed(self) -> None:
        page = self.window.page_basin
        names = self._selected_basin_names()
        if not names:
            return
        if hasattr(page, "cmb_preview_basin"):
            idx = page.cmb_preview_basin.findText(names[0])
            if idx >= 0 and page.cmb_preview_basin.currentIndex() != idx:
                page.cmb_preview_basin.setCurrentIndex(idx)
        if hasattr(page, "lbl_selected_basin"):
            page.lbl_selected_basin.setText(f"Preview basin: {names[0]}")
        if hasattr(page, "lbl_basin_preview_status"):
            page.lbl_basin_preview_status.setText(f"Preview target: {names[0]}.")

    def on_basin_preview_target_changed(self) -> None:
        page = self.window.page_basin
        self._sync_basin_time_slice_label()
        selected = self._preview_basin_name()
        if selected and hasattr(page, "lbl_selected_basin"):
            page.lbl_selected_basin.setText(f"Preview basin: {selected}")
        with contextlib.suppress(Exception):
            self.on_refresh_basin_preview(show_errors=False)

    def _basin_name_field(self) -> str:
        page = self.window.page_basin
        if hasattr(page, "cmb_basin_name_field"):
            value = page.cmb_basin_name_field.currentText().strip()
            if value:
                return value
        if hasattr(page, "edit_basin_name_field"):
            value = page.edit_basin_name_field.text().strip()
            if value:
                return value
        return "Name"

    def _populate_basin_name_field_options(self, boundary_path: str) -> str:
        page = self.window.page_basin
        current = self._basin_name_field()
        if Path(boundary_path).suffix.lower() != ".shp" or not hasattr(page, "cmb_basin_name_field"):
            return current
        try:
            import shapefile

            sf = shapefile.Reader(boundary_path)
            fields = [str(f[0]) for f in sf.fields[1:]]
        except Exception:
            return current
        resolved = current
        if fields:
            lower_fields = {field.lower(): field for field in fields}
            if current.lower() not in lower_fields:
                with contextlib.suppress(Exception):
                    resolved = resolve_shapefile_name_field(boundary_path, current) or fields[0]
            else:
                resolved = lower_fields[current.lower()]
        page.cmb_basin_name_field.blockSignals(True)
        page.cmb_basin_name_field.clear()
        for field in fields or [resolved or "Name"]:
            page.cmb_basin_name_field.addItem(field, field)
        if resolved:
            idx = page.cmb_basin_name_field.findText(resolved)
            if idx >= 0:
                page.cmb_basin_name_field.setCurrentIndex(idx)
            else:
                page.cmb_basin_name_field.setEditText(resolved)
            if hasattr(page, "edit_basin_name_field"):
                page.edit_basin_name_field.setText(resolved)
        page.cmb_basin_name_field.blockSignals(False)
        return resolved or current

    def _resolve_basin_boundary_file(self, value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        path = Path(self._native_path(raw, base_dir=ROOT_DIR))
        if path.is_dir():
            preferred = path / "LargeBasin.shp"
            if preferred.exists():
                return str(preferred)
            for pattern in ("*.shp", "*.bln", "*.txt"):
                matches = sorted(path.glob(pattern))
                if matches:
                    return str(matches[0])
            raise FileNotFoundError(f"No .shp/.bln/.txt boundary file found in: {path}")
        return str(path)

    def _selected_basin_name(self) -> str:
        names = self._selected_basin_names()
        return names[0] if names else ""

    def _preview_basin_name(self) -> str:
        page = self.window.page_basin
        if hasattr(page, "cmb_preview_basin"):
            text = str(page.cmb_preview_basin.currentText() or "").strip()
            if text and text != "First boundary":
                return text
        return self._selected_basin_name()

    def _sync_basin_time_slice_label(self) -> None:
        page = self.window.page_basin
        if not hasattr(page, "slider_basin_time_index") or not hasattr(page, "lbl_basin_time_slice"):
            return
        idx = int(page.slider_basin_time_index.value())
        total = int(page.slider_basin_time_index.maximum()) + 1
        label = ""
        with contextlib.suppress(Exception):
            cache = self.host._basin_cache or {}
            shape = np.asarray(cache.get("ewh")).shape
            nt = int(shape[2]) if len(shape) >= 3 else 1
            _t_years, labels = self.host._resolve_time(cache.get("t"), nt, meta=cache.get("meta", {}) or {})
            if labels and 0 <= idx < len(labels):
                label = str(labels[idx])
        suffix = f" | {label}" if label else ""
        page.lbl_basin_time_slice.setText(f"Time slice: {idx + 1} / {max(1, total)}{suffix}")

    def _selected_basin_names(self) -> list[str]:
        page = self.window.page_basin
        rows = set()
        selection = page.table_basins.selectionModel()
        if selection is not None:
            rows.update(index.row() for index in selection.selectedRows())
        if not rows and page.table_basins.currentRow() >= 0:
            rows.add(page.table_basins.currentRow())
        names = []
        for row_idx in sorted(rows):
            item = page.table_basins.item(row_idx, 1)
            if item is not None:
                name = str(item.text() or "").strip()
                if name:
                    names.append(name)
        return names

    def _populate_basin_table_from_boundaries(self, boundaries, lon_vec=None, lat_vec=None) -> None:
        rows = []
        for idx, basin in enumerate(boundaries, start=1):
            name = str(getattr(basin, "name", "") or f"basin_{idx}")
            lon = np.asarray(getattr(basin, "lon", []), dtype=float)
            lat = np.asarray(getattr(basin, "lat", []), dtype=float)
            vertex_count = int(np.count_nonzero(np.isfinite(lon)))
            part_count = len(getattr(basin, "parts", []) or []) or 1
            cells_text = f"{vertex_count} vertices"
            if lon_vec is not None and lat_vec is not None:
                with contextlib.suppress(Exception):
                    mask = basin_make_mask(basin, np.asarray(lon_vec, dtype=float).squeeze(), np.asarray(lat_vec, dtype=float).squeeze())
                    cells_text = f"{int(np.count_nonzero(mask))} grid cells"
            finite_lon = lon[np.isfinite(lon)]
            finite_lat = lat[np.isfinite(lat)]
            region = f"{part_count} part(s)"
            if finite_lon.size and finite_lat.size:
                region = (
                    f"{float(np.nanmin(finite_lon)):.2f}..{float(np.nanmax(finite_lon)):.2f}, "
                    f"{float(np.nanmin(finite_lat)):.2f}..{float(np.nanmax(finite_lat)):.2f} | {part_count} part(s)"
                )
            rows.append((str(idx), name, cells_text, region))
        page = self.window.page_basin
        populate_table(page.table_basins, ["ID", "Basin Name", "Cells / Area", "Region / Parts"], rows)
        page.table_basins.setSelectionMode(QAbstractItemView.ExtendedSelection)
        page.table_basins.setSelectionBehavior(type(page.table_basins).SelectRows)
        if hasattr(page, "cmb_preview_basin"):
            current = self._preview_basin_name()
            page.cmb_preview_basin.blockSignals(True)
            page.cmb_preview_basin.clear()
            if rows:
                for row in rows:
                    page.cmb_preview_basin.addItem(row[1], row[1])
                idx = page.cmb_preview_basin.findText(current)
                page.cmb_preview_basin.setCurrentIndex(idx if idx >= 0 else 0)
            else:
                page.cmb_preview_basin.addItem("First boundary", "")
            page.cmb_preview_basin.blockSignals(False)
        if rows:
            page.table_basins.selectRow(0)

    def _sync_dashboard_run_summary(self) -> None:
        dashboard = self.window.page_dashboard
        output_root = self._native_path(getattr(self.host.cfg.path, "OUTPUT", ""), base_dir=ROOT_DIR) or self.window.page_data_paths.edit_main_output_root.text().strip()
        filters = ", ".join(self._enabled_filter_names()) or "None"
        dashboard.lbl_active_filters.setText(f"Filters: {filters}")
        dashboard.lbl_active_io.setText(f"I/O: {output_root}")
        if not self.host._active_scope:
            dashboard.lbl_dashboard_status.setText("Idle")
            dashboard.lbl_dashboard_counts.setText("0 / 0")
            dashboard.lbl_dashboard_stage.setText("Ready to run with the current configuration.")
            dashboard.lbl_active_run_name.setText("Ready")
            dashboard.lbl_active_task.setText("No pipeline activity yet.")
            dashboard.lbl_active_counts.setText("0 / 0")
            dashboard.bar_active_run.setValue(0)
            self._set_progress_active(dashboard.bar_active_run, False)
        self.window.refresh_translations()

    @staticmethod
    def _set_progress_active(bar, active: bool) -> None:
        bar.setProperty("active", bool(active))
        bar.style().unpolish(bar)
        bar.style().polish(bar)

    def _sync_monitor_context(self) -> None:
        cfg = self.host.cfg
        output_root = self._native_path(getattr(cfg.path, "OUTPUT", ""), base_dir=ROOT_DIR)
        output_local = self._native_path(Path(output_root) / "local") if output_root else ""
        output_plots = self._native_path(Path(output_local) / "plots") if output_local else ""
        output_stacks = self._native_path(Path(output_local) / "stacks") if output_local else ""
        output_monthly = self._native_path(Path(output_local) / "monthly_mat") if output_local else ""
        output_logs = self._native_path(Path(output_local) / "logs") if output_local else ""
        self.window.page_monitor.lbl_run_config.setText(
            f"Config: {self.host.current_cfg_path.name if self.host.current_cfg_path else 'In-Memory Config'}"
        )
        self.window.page_monitor.lbl_run_filters.setText(f"Filters: {', '.join(self._enabled_filter_names()) or 'None'}")
        self.window.page_monitor.lbl_run_output.setText(f"Output Root: {output_root or 'Not configured'}")
        self.window.page_monitor.lbl_run_timespan.setText(
            f"Time Span: {getattr(cfg.time, 'start_ym', '--')} to {getattr(cfg.time, 'end_ym', '--')}"
        )
        self.window.page_monitor.lbl_output_root.setText(f"Output Root: {output_root or 'Not configured'}")
        self.window.page_monitor.lbl_output_local.setText(f"Local Output: {output_local or 'Not resolved'}")
        self.window.page_monitor.lbl_output_plots.setText(
            f"Plots: {output_plots or 'Not resolved'}"
        )
        self.window.page_dashboard.lbl_preview_root.setText(f"Output Root: {output_root or 'Not resolved'}")
        self.window.page_dashboard.lbl_preview_output.setText(f"Local Output: {output_local or 'Not resolved'}")
        self.window.page_dashboard.lbl_preview_stacks.setText(f"Stacks: {output_stacks or 'Not resolved'}")
        self.window.page_dashboard.lbl_preview_monthly.setText(f"Monthly MAT: {output_monthly or 'Not resolved'}")
        self.window.page_dashboard.lbl_preview_plots.setText(f"Plots: {output_plots or 'Not resolved'}")
        self.window.page_dashboard.lbl_preview_logs.setText(f"Logs: {output_logs or 'Not resolved'}")
        self.window.refresh_translations()

    def _poll_terminal_run_state(self) -> None:
        if not self._pending_terminal_status or not self._pending_terminal_scope:
            return
        thread = self._threads.get(self._pending_terminal_scope)
        if thread is None or not thread.is_alive():
            terminal_status = self._pending_terminal_status
            self._pending_terminal_status = None
            self._pending_terminal_scope = ""
            self.on_status(*terminal_status)

    def _sync_data_path_badges(self) -> None:
        page = self.window.page_data_paths

        def update(badge: QLabel, value: str, success_text: str, missing_text: str, allow_missing: bool = False) -> None:
            exists = bool(value and Path(value).exists())
            if exists:
                self._set_badge_state(badge, success_text, "success")
            elif allow_missing:
                self._set_badge_state(badge, missing_text, "warning")
            else:
                self._set_badge_state(badge, missing_text, "danger")

        update(page.badge_gfc_input, page.edit_gfc_input_dir.text().strip(), "Verified", "Missing")
        ddk_ok = self._ddk_kernel_files(page.edit_ddk_data_dir.text().strip())
        self._set_badge_state(page.badge_ddk_data, "Built-in" if ddk_ok else "Missing kernels", "success" if ddk_ok else "warning")
        update(page.badge_output_root, page.edit_main_output_root.text().strip(), "Verified", "Will create", allow_missing=True)
        update(page.badge_logs_dir, page.edit_logs_dir.text().strip(), "Ready", "Auto-generated", allow_missing=True)
        update(page.badge_aux_path, page.edit_aux_path.text().strip(), "OK", "Missing")
        update(page.badge_boundary_root, page.edit_boundary_root.text().strip(), "OK", "Missing")
        boundary_text, boundary_variant = self._validate_shapefile(page.edit_boundary_path.text().strip())
        self._set_badge_state(page.badge_boundary_path, boundary_text, boundary_variant)
        update(page.badge_low_degree, page.edit_low_degree_path.text().strip(), "OK", "Missing")
        update(page.badge_degree1, page.edit_degree1_path.text().strip(), "OK", "Missing")
        update(page.badge_gia, page.edit_gia_path.text().strip(), "OK", "Missing")
        update(page.badge_mascon_root, page.edit_mascon_root.text().strip(), "OK", "Missing")
        update(page.badge_mascon_reference, page.edit_mascon_reference.text().strip(), "OK", "Missing")
        update(page.badge_mascon_gad, page.edit_mascon_gad.text().strip(), "OK", "Missing")
        update(page.badge_mascon_gia, page.edit_mascon_gia.text().strip(), "OK", "Missing")
        self.window.refresh_translations()

    def _sync_logs_path_from_output_root(self, _text: str | None = None) -> None:
        page = self.window.page_data_paths
        output_root = self._native_path(page.edit_main_output_root.text(), base_dir=ROOT_DIR)
        if output_root:
            self._set_edit_text(page.edit_logs_dir, self._native_path(Path(output_root) / "logs"), block_signals=True)
        self._sync_data_path_badges()

    def _sync_boundary_root_from_file(self) -> None:
        page = self.window.page_data_paths
        boundary_file = self._resolve_boundary_file(page.edit_boundary_path.text())
        if boundary_file:
            self._set_edit_text(page.edit_boundary_root, self._native_path(Path(boundary_file).parent), block_signals=True)

    def _sync_boundary_file_from_root(self) -> None:
        page = self.window.page_data_paths
        boundary_root = page.edit_boundary_root.text().strip()
        if not boundary_root:
            return
        self._set_edit_text(page.edit_boundary_path, self._resolve_boundary_file(boundary_root), block_signals=True)

    def _sync_mascon_root_from_reference(self) -> None:
        page = self.window.page_data_paths
        reference_file = self._display_path(
            page.edit_mascon_reference.text().strip(),
            fallback=DEFAULT_DATA_PATHS["MASCON_REFERENCE_FILE"],
            base_dir=ROOT_DIR,
            require_exists=False,
        )
        if reference_file:
            self._set_edit_text(page.edit_mascon_root, self._native_path(Path(reference_file).parent), block_signals=True)

    def _sync_mascon_reference_from_root(self) -> None:
        page = self.window.page_data_paths
        mascon_root = page.edit_mascon_root.text().strip()
        if not mascon_root:
            return
        self._set_edit_text(
            page.edit_mascon_reference,
            self._resolve_mascon_reference_file(mascon_root),
            block_signals=True,
        )

    def _normalize_mascon_component_edits(self, only_if_empty: bool = False) -> None:
        page = self.window.page_data_paths
        mascon_dir = self._display_path(
            page.edit_mascon_root.text() or Path(page.edit_mascon_reference.text() or DEFAULT_DATA_PATHS["MASCON_REFERENCE_FILE"]).parent,
            fallback=DEFAULT_DATA_PATHS["MASCON_DIR"],
            base_dir=ROOT_DIR,
            require_exists=False,
        )
        for edit, default_key in (
            (page.edit_mascon_gad, "MASCON_GAD"),
            (page.edit_mascon_gia, "MASCON_GIA"),
        ):
            if only_if_empty and edit.text().strip():
                continue
            normalized = self._display_path(
                edit.text().strip() or DEFAULT_DATA_PATHS[default_key],
                fallback=DEFAULT_DATA_PATHS[default_key],
                base_dir=mascon_dir,
                require_exists=False,
            )
            self._set_edit_text(edit, normalized, block_signals=True)

    def _normalize_path_edit(self, edit: QLineEdit, base_dir=None) -> None:
        normalized = self._native_path(edit.text(), base_dir=base_dir)
        if normalized:
            if edit is self.window.page_data_paths.edit_boundary_path:
                self._set_edit_text(edit, self._resolve_boundary_file(normalized), block_signals=True)
            elif edit is self.window.page_data_paths.edit_mascon_reference:
                self._set_edit_text(
                    edit,
                    self._display_path(normalized, fallback=DEFAULT_DATA_PATHS["MASCON_REFERENCE_FILE"], base_dir=ROOT_DIR, require_exists=False),
                    block_signals=True,
                )
            else:
                self._set_edit_text(edit, normalized, block_signals=True)
        if edit is self.window.page_data_paths.edit_main_output_root:
            self._sync_logs_path_from_output_root()
        elif edit is self.window.page_data_paths.edit_boundary_path:
            self._sync_boundary_root_from_file()
        elif edit is self.window.page_data_paths.edit_boundary_root:
            self._sync_boundary_file_from_root()
        elif edit is self.window.page_data_paths.edit_mascon_reference:
            self._sync_mascon_root_from_reference()
            self._normalize_mascon_component_edits(only_if_empty=False)
        elif edit is self.window.page_data_paths.edit_mascon_root:
            self._sync_mascon_reference_from_root()
            self._normalize_mascon_component_edits(only_if_empty=False)
        self._sync_data_path_badges()

    def browse_into(self, edit, mode: str = "file", file_filter: str = ""):
        base_dir = ROOT_DIR
        if edit in (self.window.page_data_paths.edit_mascon_gad, self.window.page_data_paths.edit_mascon_gia):
            base_dir = self.window.page_data_paths.edit_mascon_root
        current_text = self._native_path(edit.text(), base_dir=base_dir) if edit.text().strip() else str(ROOT_DIR)
        current = Path(current_text).expanduser()
        start = str(current.parent if current.suffix else current)
        selected = ""
        dialog_filter = file_filter or "All Files (*)"
        mode = str(mode or "file").lower()
        if mode == "dir":
            selected = QFileDialog.getExistingDirectory(self.window, self.window.translate_text("Folder..."), start)
        elif mode == "save_file":
            selected, _ = QFileDialog.getSaveFileName(self.window, self.window.translate_text("Save Config"), start, dialog_filter)
        elif mode == "file_or_dir":
            prefer_dir = current.exists() and current.is_dir()
            if prefer_dir:
                selected = QFileDialog.getExistingDirectory(self.window, self.window.translate_text("Folder..."), start)
                if not selected:
                    selected, _ = QFileDialog.getOpenFileName(self.window, self.window.translate_text("File..."), start, dialog_filter)
            else:
                selected, _ = QFileDialog.getOpenFileName(self.window, self.window.translate_text("File..."), start, dialog_filter)
                if not selected:
                    selected = QFileDialog.getExistingDirectory(self.window, self.window.translate_text("Folder..."), start)
        else:
            selected, _ = QFileDialog.getOpenFileName(self.window, self.window.translate_text("File..."), start, dialog_filter)
        if selected:
            self._set_edit_text(edit, self._native_path(selected))

    def on_toggle_reference_roots(self, checked: bool):
        page = self.window.page_data_paths
        page.reference_roots_panel.setVisible(checked)
        page.btn_toggle_reference_roots.setText("Hide Root Paths" if checked else "Show Root Paths")
        self.window.refresh_translations()

    def on_load_config(self):
        path, _ = QFileDialog.getOpenFileName(self.window, self.window.translate_text("Load Config"), str(self.host.cfg_dir), "JSON (*.json)")
        if path:
            self.load_config_from_path(path)

    def load_config_from_path(self, path):
        cfg = load_config(user_config=path, default_config=DEFAULT_CFG_PATH if DEFAULT_CFG_PATH.exists() else None, root_dir=ROOT_DIR)
        self.host.cfg = cfg
        self.host.current_cfg_path = Path(path)
        self.push_config_to_ui(cfg)
        self.refresh_dashboard()
        self.window.set_top_status("CONFIG READY", "success")
        self.on_log(f"[CONFIG] Loaded {path}", "stdout")

    def on_save_config(self):
        self.pull_ui_to_host()
        base = copy.deepcopy(getattr(self.host.cfg, "_raw", {}) or getattr(self.host.default_cfg, "_raw", {}))
        cfg_dict = self.collect_config_dict(base)
        start = str(self.host.current_cfg_path or (self.host.cfg_dir / "user_qt.json"))
        path, _ = QFileDialog.getSaveFileName(self.window, self.window.translate_text("Save Config"), start, "JSON (*.json)")
        if not path:
            return
        Path(path).write_text(json.dumps(cfg_dict, ensure_ascii=False, indent=2), encoding="utf-8")
        self.host.cfg = Config(copy.deepcopy(cfg_dict))
        self.host.current_cfg_path = Path(path)
        self.refresh_dashboard()
        self.window.set_top_status("CONFIG SAVED", "success")
        self.on_log(f"[CONFIG] Saved {path}", "stdout")

    def on_open_settings(self):
        dialog = UiSettingsDialog(self.window, self.window.ui_preferences)

        def apply_preferences():
            self.window.apply_ui_preferences(dialog.current_preferences(), persist=True)
            self.refresh_dashboard()
            self._sync_monitor_context()
            self._sync_data_path_badges()
            self.window.refresh_translations()

        dialog.buttons.button(QDialogButtonBox.Apply).clicked.connect(apply_preferences)
        dialog.buttons.accepted.connect(lambda: (apply_preferences(), dialog.accept()))
        dialog.buttons.rejected.connect(dialog.reject)
        dialog.exec()

    def on_open_help(self):
        dialog = QDialog(self.window)
        is_zh = getattr(self.window.ui_preferences, "language", "en") == "zh"
        dialog.setWindowTitle("页面帮助" if is_zh else "Page Help")
        dialog.resize(920, 680)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 12, 16, 12)
        body = QTextEdit()
        body.setReadOnly(True)
        if is_zh:
            help_text = (
                "快速操作（推荐）\n\n"
                "泄漏校正页：\n"
                "1. 选择输入栈（必填）\n"
                "2. 可选参考数据（可留空）\n"
                "3. 点击“读取输入信息”\n"
                "4. 保持“自动推荐”并运行\n"
                "5. 点击“在预览页查看校正栈”查看地图结果\n\n"
                "说明：\n"
                "- 默认按全球模式推荐，不要求区域边界。\n"
                "- 只有明确选择区域策略时才需要区域边界文件。\n"
                "- Mascon 原生输入默认不重复做 SH 泄漏校正。\n\n"
                "页面职责：\n"
                "- 总览：状态、路径校验、运行和输出结构\n"
                "- 数据路径：输入、输出和参考数据配置\n"
                "- 处理设置：时间、反演、网格和滤波参数\n"
                "- 泄漏校正：算法选择与运行入口\n"
                "- 流域分析：流域时序与统计\n"
                "- 预览：地图/图件显示与导出\n\n"
                "输入输出：\n"
                "- 输入常见格式：MAT / NC / TXT\n"
                "- 输出核心文件：corrected_stack.mat、difference_stack.mat、summary.json、preview_manifest.json"
            )
        else:
            help_text = (
                "Recommended workflow\n\n"
                "Leakage correction:\n"
                "1. Select the input stack.\n"
                "2. Optionally select reference data.\n"
                "3. Click Load Input Info.\n"
                "4. Keep Auto recommendation unless a specific method is required.\n"
                "5. Open the corrected stack in Preview to inspect maps and series.\n\n"
                "Notes:\n"
                "- The default recommendation uses global mode and does not require a regional boundary.\n"
                "- Regional boundaries are required only for explicitly regional strategies.\n"
                "- Native mascon products are not corrected again through the SH leakage workflow.\n\n"
                "Pages:\n"
                "- Dashboard: status, path validation, run control, and output structure.\n"
                "- Data Paths: input, output, and reference datasets.\n"
                "- Processing Setup: time span, inversion, grid, and filters.\n"
                "- Leakage Correction: method selection and execution.\n"
                "- Basin Analysis: basin series and statistics.\n"
                "- Preview: map display and export.\n\n"
                "Input/output:\n"
                "- Common input formats: MAT / NC / TXT.\n"
                "- Core outputs: corrected_stack.mat, difference_stack.mat, summary.json, preview_manifest.json."
            )
        body.setPlainText(help_text)
        layout.addWidget(body, 1)
        btn_close = QPushButton("关闭" if is_zh else "Close")
        btn_close.setObjectName("PrimaryButton")
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close, 0, Qt.AlignRight)
        dialog.exec()

    def collect_config_dict(self, base: dict | None = None) -> dict:
        w = self.window
        base = copy.deepcopy(base or {})
        path_cfg = base.setdefault("path", {})
        ref_cfg = base.setdefault("reference", {})
        ref_cfg.setdefault("mascon_undo", {})
        time_cfg = base.setdefault("time", {})
        grid_cfg = base.setdefault("grid", {})
        inv_cfg = base.setdefault("inversion", {})
        inv_cfg.setdefault("lowdeg", {})
        inv_cfg.setdefault("gia", {})
        filt_cfg = base.setdefault("filter", {})
        filt_cfg.setdefault("gaussian", {})
        filt_cfg.setdefault("p4m6", {})
        filt_cfg.setdefault("ddk", {})
        filt_cfg.setdefault("fan", {})
        filt_cfg.setdefault("hankel", {})
        filt_cfg.setdefault("combinations", {})
        filt_cfg["hankel"].setdefault("params", {})
        basin_cfg = base.setdefault("basin", {})
        leak_cfg = base.setdefault("leakage", {})
        par_cfg = base.setdefault("parallel", {})

        path_cfg["GFC"] = self._native_path(w.page_data_paths.edit_gfc_input_dir.text(), base_dir=ROOT_DIR)
        path_cfg["OUTPUT"] = self._native_path(w.page_data_paths.edit_main_output_root.text(), base_dir=ROOT_DIR)
        path_cfg["AUX"] = self._native_path(w.page_data_paths.edit_aux_path.text(), base_dir=ROOT_DIR)
        boundary_file = self._resolve_boundary_file(w.page_data_paths.edit_boundary_path.text())
        path_cfg["BOUNDARY"] = self._native_path(Path(boundary_file).parent if boundary_file else DEFAULT_DATA_PATHS["BOUNDARY"], base_dir=ROOT_DIR)
        path_cfg["DDK"] = self._native_path(w.page_data_paths.edit_ddk_data_dir.text(), base_dir=ROOT_DIR)
        filt_cfg["ddk"]["data_dir"] = path_cfg["DDK"]
        mascon_reference = self._display_path(
            w.page_data_paths.edit_mascon_reference.text(),
            fallback=DEFAULT_DATA_PATHS["MASCON_REFERENCE_FILE"],
            base_dir=ROOT_DIR,
            require_exists=False,
        )
        ref_cfg["mascon_dir"] = self._native_path(Path(mascon_reference).parent if mascon_reference else DEFAULT_DATA_PATHS["MASCON_DIR"], base_dir=ROOT_DIR)
        ref_cfg["mascon_pattern"] = Path(mascon_reference).name if mascon_reference else Path(DEFAULT_DATA_PATHS["MASCON_REFERENCE_FILE"]).name
        ref_cfg["mascon_undo"]["gad_file"] = self._native_path(
            w.page_data_paths.edit_mascon_gad.text(),
            base_dir=ref_cfg["mascon_dir"],
        )
        ref_cfg["mascon_undo"]["gia_file"] = self._native_path(
            w.page_data_paths.edit_mascon_gia.text(),
            base_dir=ref_cfg["mascon_dir"],
        )
        lowdeg_files = inv_cfg["lowdeg"].setdefault("files", {})
        lowdeg_files["C20"] = self._native_path(w.page_data_paths.edit_low_degree_path.text(), base_dir=ROOT_DIR)
        selected_degree1 = self._display_path(
            w.page_data_paths.edit_degree1_path.text(),
            fallback=DEFAULT_DATA_PATHS["LOW_DEGREE_DEGREE1"],
            base_dir=ROOT_DIR,
            require_exists=True,
        )
        lowdeg_files["DEGREE1"] = selected_degree1
        for key, path in self._discover_low_degree_files().items():
            if key.startswith("DEGREE1_") and Path(path).exists():
                lowdeg_files[key] = self._native_path(path, base_dir=ROOT_DIR)
        active_center = self._configured_gfc_center()
        active_key = f"DEGREE1_{active_center}"
        if active_key in lowdeg_files:
            lowdeg_files["DEGREE1"] = lowdeg_files[active_key]
        inv_cfg["gia"]["file"] = self._native_path(w.page_data_paths.edit_gia_path.text(), base_dir=ROOT_DIR)
        detected_entries = self._detect_time_entries_for_ui()
        detected_start = detected_entries[0].ym if detected_entries else ""
        detected_end = detected_entries[-1].ym if detected_entries else ""
        manual_override = w.page_processing.chk_manual_time_override.isChecked()
        time_cfg["auto_detect_gfc"] = not manual_override
        time_cfg["start_ym"] = self._ym_from_date(w.page_processing.edit_start_date.text().strip()) if manual_override else detected_start
        time_cfg["end_ym"] = self._ym_from_date(w.page_processing.edit_end_date.text().strip()) if manual_override else detected_end

        d = self._safe_float(w.page_processing.edit_resolution_deg.text(), 1.0)
        grid_cfg["lon"] = [
            self._safe_float(w.page_processing.edit_grid_lon_min.text(), -180.0),
            self._safe_float(w.page_processing.edit_grid_lon_max.text(), 180.0),
        ]
        grid_cfg["lat"] = [
            self._safe_float(w.page_processing.edit_grid_lat_min.text(), -90.0),
            self._safe_float(w.page_processing.edit_grid_lat_max.text(), 90.0),
        ]
        grid_cfg["dlon"] = d
        grid_cfg["dlat"] = d

        inv_cfg["Lmax"] = int(w.page_processing.slider_degree_order.value())
        inv_cfg["remove_mean"] = bool(w.page_processing.chk_remove_mean.isChecked())
        baseline_mode = self._combo_value(w.page_processing.cmb_anomaly_baseline)
        if baseline_mode not in {"standard_2004_2009", "input_full", "custom"}:
            baseline_mode = "standard_2004_2009" if baseline_mode == "2004-01 ~ 2009-12" else "input_full"
        inv_cfg["mean_baseline_mode"] = baseline_mode
        if not inv_cfg["remove_mean"]:
            inv_cfg["mean_start_ym"] = ""
            inv_cfg["mean_end_ym"] = ""
        elif baseline_mode == "standard_2004_2009":
            inv_cfg["mean_start_ym"] = "2004-01"
            inv_cfg["mean_end_ym"] = "2009-12"
        elif baseline_mode == "custom":
            custom_start = self._ym_from_date(w.page_processing.edit_mean_start_ym.text().strip())
            custom_end = self._ym_from_date(w.page_processing.edit_mean_end_ym.text().strip())
            if detected_start and custom_start and custom_start < detected_start:
                custom_start = detected_start
            if detected_end and custom_start and custom_start > detected_end:
                custom_start = detected_end
            if detected_start and custom_end and custom_end < detected_start:
                custom_end = detected_start
            if detected_end and custom_end and custom_end > detected_end:
                custom_end = detected_end
            if custom_start and custom_end and custom_start > custom_end:
                custom_start = custom_end
            inv_cfg["mean_start_ym"] = custom_start
            inv_cfg["mean_end_ym"] = custom_end
        else:
            inv_cfg["mean_start_ym"] = ""
            inv_cfg["mean_end_ym"] = ""
        lowdeg_cfg = inv_cfg.setdefault("lowdeg", {})
        lowdeg_cfg["enable"] = bool(w.page_processing.chk_lowdeg_enable.isChecked())
        lowdeg_cfg["replace_degree1"] = bool(w.page_processing.chk_replace_degree1.isChecked())
        lowdeg_cfg["replace_C10"] = bool(w.page_processing.chk_replace_degree1.isChecked())
        lowdeg_cfg["replace_C20"] = bool(w.page_processing.chk_replace_c20.isChecked())
        lowdeg_cfg["replace_C30"] = bool(w.page_processing.chk_replace_c30.isChecked())
        inv_cfg["gia"]["enable"] = bool(w.page_processing.chk_apply_gia.isChecked())
        combo_gaussian_pnmn = bool(w.page_processing.btn_filter_gaussian_pnmn.isChecked())
        combo_fan_pnmn = bool(w.page_processing.btn_filter_fan_pnmn.isChecked())
        filt_cfg["gaussian"]["enable"] = bool(w.page_processing.btn_filter_gaussian.isChecked())
        filt_cfg["gaussian"]["radius_km"] = self._safe_float(w.page_processing.edit_isotropic_radius_km.text(), 300.0)
        filt_cfg["p4m6"]["enable"] = bool(w.page_processing.btn_filter_p4m6.isChecked())
        filt_cfg["p4m6"]["poly_deg"] = int(round(self._safe_float(w.page_processing.edit_pnmn_poly_degree.text(), 4.0)))
        filt_cfg["p4m6"]["m_start"] = int(round(self._safe_float(w.page_processing.edit_pnmn_m_start.text(), 6.0)))
        filt_cfg["ddk"]["enable"] = bool(w.page_processing.btn_filter_ddk.isChecked())
        filt_cfg["ddk"]["type"] = self._combo_value(w.page_processing.cmb_ddk_type) or filt_cfg["ddk"].get("type", "DDK4")
        filt_cfg["fan"]["enable"] = bool(w.page_processing.btn_filter_fan.isChecked())
        filt_cfg["fan"]["radius1_km"] = self._safe_float(w.page_processing.edit_fan_radius1_km.text(), 300.0)
        filt_cfg["fan"]["radius2_km"] = self._safe_float(w.page_processing.edit_fan_radius2_km.text(), 300.0)
        filt_cfg["combinations"] = {
            "gaussian_pnmn": combo_gaussian_pnmn,
            "fan_pnmn": combo_fan_pnmn,
        }
        filt_cfg["hankel"]["enable"] = w.page_processing.btn_filter_hsaf.isChecked()
        filt_cfg["pre_hankel_input"] = self._combo_value(w.page_processing.cmb_hsaf_input) or filt_cfg.get("pre_hankel_input", "P4M6")
        filt_cfg["hankel"]["variant"] = self._hsaf_variant_from_ui(self._combo_value(w.page_processing.cmb_hsaf_variant))
        base_hsaf_params = dict(filt_cfg["hankel"].get("params", {}) or {})
        filt_cfg["hankel"]["params"]["N"] = int(round(self._safe_float(w.page_processing.edit_hsaf_global_n.text(), float(base_hsaf_params.get("N", 30)))))
        filt_cfg["hankel"]["params"]["P"] = int(round(self._safe_float(w.page_processing.edit_hsaf_global_p.text(), float(base_hsaf_params.get("P", 8)))))
        filt_cfg["hankel"]["params"]["K"] = int(round(self._safe_float(w.page_processing.edit_hsaf_global_k.text(), float(base_hsaf_params.get("K", 4)))))
        filt_cfg["hankel"]["params"]["J"] = int(round(self._safe_float(w.page_processing.edit_hsaf_global_j.text(), float(base_hsaf_params.get("J", 1)))))
        filt_cfg["hankel"]["params"]["iterations"] = max(
            1,
            int(round(self._safe_float(w.page_processing.edit_hsaf_iterations.text(), float(base_hsaf_params.get("iterations", 1))))),
        )
        filt_cfg["hankel"]["params"]["alpha_cutoff"] = self._safe_float(w.page_processing.edit_hsaf_alpha.text(), 0.0035)
        filt_cfg["hankel"]["params"]["convergence_tol"] = self._safe_float(w.page_processing.edit_hsaf_tolerance.text(), 1.0e-7)
        adaptive_existing = list(filt_cfg["hankel"].get("adaptive", []) or [])
        adaptive_defaults = self._default_hsaf_adaptive_zones(filt_cfg["hankel"]["params"])
        adaptive_zones = []
        for idx, fields in enumerate(w.page_processing.hsaf_adaptive_zone_fields):
            fallback_zone = adaptive_existing[idx] if idx < len(adaptive_existing) else adaptive_defaults[idx]
            fallback_params = dict(fallback_zone.get("params", {}) or {})
            lat_range = list(fallback_zone.get("lat_range", adaptive_defaults[idx]["lat_range"]))
            adaptive_zones.append(
                {
                    "lat_range": [
                        self._safe_float(fields["lat_min"].text(), float(lat_range[0])),
                        self._safe_float(fields["lat_max"].text(), float(lat_range[1])),
                    ],
                    "params": {
                        "N": int(round(self._safe_float(fields["N"].text(), float(fallback_params.get("N", filt_cfg["hankel"]["params"]["N"]))))),
                        "P": int(round(self._safe_float(fields["P"].text(), float(fallback_params.get("P", filt_cfg["hankel"]["params"]["P"]))))),
                        "K": int(round(self._safe_float(fields["K"].text(), float(fallback_params.get("K", filt_cfg["hankel"]["params"]["K"]))))),
                        "J": int(round(self._safe_float(fields["J"].text(), float(fallback_params.get("J", filt_cfg["hankel"]["params"]["J"]))))),
                    },
                }
            )
        filt_cfg["hankel"]["adaptive"] = adaptive_zones

        basin_cfg["analysis_enable"] = w.page_basin.chk_basin_enable.isChecked()
        basin_cfg["data_file"] = w.page_basin.edit_data_file.text().strip()
        basin_cfg["boundary_file"] = self._resolve_basin_boundary_file(w.page_basin.edit_boundary_file.text().strip())
        selected_basins = self._selected_basin_names()
        basin_cfg["name"] = "" if w.page_basin.cmb_basin_selection_mode.currentIndex() == 1 else (selected_basins[0] if selected_basins else "")
        basin_cfg["names"] = [] if w.page_basin.cmb_basin_selection_mode.currentIndex() == 1 else selected_basins
        basin_cfg["name_field"] = self._basin_name_field()
        basin_cfg["output_dir"] = w.page_basin.edit_export_path.text().strip()
        basin_cfg["aggregation_strategy"] = w.page_basin.cmb_aggregation_strategy.currentText().strip()
        basin_cfg["missing_month_fallback"] = w.page_basin.cmb_missing_month_fallback.currentText().strip()
        if hasattr(w.page_basin, "chk_basin_save_series"):
            basin_cfg["do_time_series"] = bool(w.page_basin.chk_basin_save_series.isChecked())
            basin_cfg["do_statistics"] = bool(w.page_basin.chk_basin_save_stats.isChecked())
            basin_cfg["do_grid"] = bool(w.page_basin.chk_basin_save_mask_grid.isChecked())
            basin_cfg["save_ts_txt"] = bool(w.page_basin.chk_basin_save_ts_txt.isChecked())
            basin_cfg["save_ts_mat"] = bool(w.page_basin.chk_basin_save_ts_mat.isChecked())
            basin_cfg["save_grid_mat"] = bool(w.page_basin.chk_basin_save_grid_mat.isChecked())

        leak_cfg.pop("fm_operator", None)
        if isinstance(leak_cfg.get("FM"), dict):
            leak_cfg["FM"].pop("operator", None)
        leak_cfg["enable"] = True
        leak_cfg["strategy_family"] = self._combo_value(w.page_leakage.cmb_strategy_family).lower() if hasattr(w.page_leakage, "cmb_strategy_family") else "global_regularized"
        leak_cfg["scope"] = "regional" if leak_cfg["strategy_family"] == "regional" else "global"
        strategy = self._combo_value(w.page_leakage.cmb_correction_strategy).lower()
        leak_cfg["correction_strategy"] = strategy or "auto"
        leak_cfg["method"] = "FM" if strategy == "forward_modeling" else "SF"
        leak_cfg["official_mode"] = self._combo_value(w.page_leakage.cmb_official_mode).lower() if hasattr(w.page_leakage, "cmb_official_mode") else "auto"
        leak_cfg["scene_override"] = self._combo_value(w.page_leakage.cmb_scene_override).lower()
        leak_cfg["reference_mode"] = self._combo_value(w.page_leakage.cmb_reference_mode).lower()
        leak_cfg["reference_input"] = w.page_leakage.edit_reference_input.text().strip()
        leak_cfg["input"] = w.page_leakage.edit_lrc_input.text().strip()
        leak_cfg["output"] = w.page_leakage.edit_lrc_output.text().strip()
        leak_cfg["boundary_file"] = w.page_leakage.edit_regional_boundary.text().strip()
        leak_cfg["sf_factor"] = self._safe_float(w.page_leakage.edit_lrc_sf_factor.text(), 1.0)
        leak_cfg["format"] = self._combo_value(w.page_leakage.cmb_lrc_format).lower() or "mat"
        # Keep operator selection in auto mode for simplified UI and robust input-based detection.
        leak_cfg["sf_method"] = "Auto"
        leak_cfg["sf_gauss_km"] = self._safe_float(w.page_leakage.edit_lrc_gaussian_km.text(), 300.0)
        leak_cfg["sf_ddk_type"] = w.page_leakage.edit_ddk_type.text().strip() or "DDK4"
        leak_cfg["fm_max_iter"] = max(1, int(round(self._safe_float(w.page_leakage.edit_fm_iteration_count.text(), 40.0))))
        leak_cfg["fm_tol"] = self._safe_float(w.page_leakage.edit_fm_convergence_threshold.text(), 0.01)
        leak_cfg["fm_accel"] = self._safe_float(w.page_leakage.edit_fm_acceleration.text(), 1.1)
        leak_cfg["fm_patience"] = max(0, int(round(self._safe_float(w.page_leakage.edit_fm_patience.text(), 8.0))))
        leak_cfg["fm_min_improve"] = self._safe_float(w.page_leakage.edit_fm_min_improve.text(), 1.0e-4)
        leak_cfg.setdefault("fm_min_iter", 3)
        leak_cfg.setdefault("fm_metric", "land_weighted_mean")
        leak_cfg.setdefault("fm_mass_conservation", "legacy_land_mean_fill")
        leak_cfg.setdefault("fm_output_mode", "mask_zero")
        leak_cfg["FM"] = {
            "nIter": leak_cfg["fm_max_iter"],
            "minIter": leak_cfg["fm_min_iter"],
            "tol_rmse_mm": leak_cfg["fm_tol"],
            "accel": leak_cfg["fm_accel"],
            "patience": leak_cfg["fm_patience"],
            "min_improve": leak_cfg["fm_min_improve"],
            "metric": leak_cfg["fm_metric"],
            "mass_conservation": leak_cfg["fm_mass_conservation"],
            "output_mode": leak_cfg["fm_output_mode"],
        }
        leak_cfg["coastal_buffer_cells"] = max(1, int(round(self._safe_float(w.page_leakage.edit_coastal_buffer_cells.text(), 3.0)))) if hasattr(w.page_leakage, "edit_coastal_buffer_cells") else 3
        leak_cfg["coastal_attenuation_gain"] = self._safe_float(w.page_leakage.edit_coastal_attenuation_gain.text(), 1.0) if hasattr(w.page_leakage, "edit_coastal_attenuation_gain") else 1.0
        leak_cfg["regularized_lambda"] = self._safe_float(w.page_leakage.edit_regularized_lambda.text(), 0.18) if hasattr(w.page_leakage, "edit_regularized_lambda") else 0.18
        leak_cfg["regularized_step_size"] = self._safe_float(w.page_leakage.edit_regularized_step_size.text(), 0.9) if hasattr(w.page_leakage, "edit_regularized_step_size") else 0.9
        leak_cfg["regularized_sigma"] = self._safe_float(w.page_leakage.edit_regularized_sigma.text(), 1.2) if hasattr(w.page_leakage, "edit_regularized_sigma") else 1.2
        leak_cfg["regularized_iter"] = max(1, int(round(self._safe_float(w.page_leakage.edit_regularized_iter.text(), 10.0)))) if hasattr(w.page_leakage, "edit_regularized_iter") else 10

        par_cfg["enable"] = True
        par_cfg["nWorkers"] = int(base.get("parallel", {}).get("nWorkers", base.get("parallel", {}).get("n_workers", 4)))
        return base

    def push_config_to_ui(self, cfg: Config):
        w = self.window
        raw = getattr(cfg, "_raw", {})
        output_root = self._display_path(
            getattr(cfg.path, "OUTPUT", ""),
            fallback=DEFAULT_DATA_PATHS["OUTPUT"],
            base_dir=ROOT_DIR,
            require_exists=False,
        )
        boundary_root = self._display_path(
            getattr(cfg.path, "BOUNDARY", ""),
            fallback=DEFAULT_DATA_PATHS["BOUNDARY"],
            base_dir=ROOT_DIR,
            require_exists=True,
        )
        boundary_file = self._resolve_boundary_file(boundary_root)
        mascon_dir = self._display_path(
            cfg.get("reference.mascon_dir", ""),
            fallback=DEFAULT_DATA_PATHS["MASCON_DIR"],
            base_dir=ROOT_DIR,
            require_exists=True,
        )
        mascon_reference = self._resolve_mascon_reference_file(mascon_dir, cfg.get("reference.mascon_pattern", ""))
        ddk_value = getattr(cfg.filter.ddk, "data_dir", "") or getattr(cfg.path, "DDK", "")

        self._set_edit_text(
            w.page_data_paths.edit_gfc_input_dir,
            self._display_path(getattr(cfg.path, "GFC", ""), fallback=DEFAULT_DATA_PATHS["GFC"], base_dir=ROOT_DIR, require_exists=True),
        )
        self._set_edit_text(
            w.page_data_paths.edit_download_dir,
            self._display_path(getattr(cfg.path, "GFC", ""), fallback=DEFAULT_DATA_PATHS["GFC"], base_dir=ROOT_DIR, require_exists=False),
        )
        self._set_edit_text(w.page_data_paths.edit_main_output_root, output_root)
        self._set_edit_text(w.page_data_paths.edit_logs_dir, self._native_path(Path(output_root) / "logs"))
        self._set_edit_text(
            w.page_data_paths.edit_ddk_data_dir,
            self._display_path(ddk_value, fallback=DEFAULT_DATA_PATHS["DDK"], base_dir=ROOT_DIR, require_exists=True),
        )
        self._set_edit_text(
            w.page_data_paths.edit_aux_path,
            self._display_path(getattr(cfg.path, "AUX", ""), fallback=DEFAULT_DATA_PATHS["AUX"], base_dir=ROOT_DIR, require_exists=True),
        )
        self._set_edit_text(w.page_data_paths.edit_boundary_root, boundary_root)
        self._set_edit_text(w.page_data_paths.edit_boundary_path, boundary_file)
        self._set_edit_text(
            w.page_data_paths.edit_low_degree_path,
            self._display_path(
                cfg.get("inversion.lowdeg.files.C20", ""),
                fallback=DEFAULT_DATA_PATHS["LOW_DEGREE_C20"],
                base_dir=ROOT_DIR,
                require_exists=True,
            ),
        )
        detected_center = infer_center_from_gfc_dir(
            self._display_path(getattr(cfg.path, "GFC", ""), fallback=DEFAULT_DATA_PATHS["GFC"], base_dir=ROOT_DIR, require_exists=False)
        )
        degree1_key = f"inversion.lowdeg.files.DEGREE1_{detected_center}" if detected_center != "UNKNOWN" else "inversion.lowdeg.files.DEGREE1"
        self._set_edit_text(
            w.page_data_paths.edit_degree1_path,
            self._display_path(
                cfg.get(degree1_key, "") or cfg.get("inversion.lowdeg.files.DEGREE1", ""),
                fallback=DEFAULT_DATA_PATHS["LOW_DEGREE_DEGREE1"],
                base_dir=ROOT_DIR,
                require_exists=True,
            ),
        )
        if detected_center != "UNKNOWN":
            self._set_combo_value(w.page_data_paths.cmb_gfc_center, detected_center)
        self._set_edit_text(
            w.page_data_paths.edit_gia_path,
            self._display_path(cfg.get("inversion.gia.file", ""), fallback=DEFAULT_DATA_PATHS["GIA"], base_dir=ROOT_DIR, require_exists=True),
        )
        self._set_edit_text(w.page_data_paths.edit_mascon_root, mascon_dir)
        self._set_edit_text(w.page_data_paths.edit_mascon_reference, mascon_reference)
        self._set_edit_text(
            w.page_data_paths.edit_mascon_gad,
            self._display_path(
                cfg.get("reference.mascon_undo.gad_file", ""),
                fallback=DEFAULT_DATA_PATHS["MASCON_GAD"],
                base_dir=mascon_dir,
                require_exists=True,
            ),
        )
        self._set_edit_text(
            w.page_data_paths.edit_mascon_gia,
            self._display_path(
                cfg.get("reference.mascon_undo.gia_file", ""),
                fallback=DEFAULT_DATA_PATHS["MASCON_GIA"],
                base_dir=mascon_dir,
                require_exists=True,
            ),
        )
        self._sync_data_path_badges()

        manual_override = not bool(getattr(cfg.time, "auto_detect_gfc", True))
        with QSignalBlocker(w.page_processing.chk_manual_time_override):
            w.page_processing.chk_manual_time_override.setChecked(manual_override)
        self._set_edit_text(w.page_processing.edit_start_date, self._date_from_ym(getattr(cfg.time, "start_ym", "")), block_signals=True)
        self._set_edit_text(w.page_processing.edit_end_date, self._date_from_ym(getattr(cfg.time, "end_ym", "")), block_signals=True)
        w.page_processing.edit_resolution_deg.setText(str(getattr(cfg.grid, "dlon", 1.0)))
        w.page_processing.edit_grid_lat_min.setText(str(cfg.grid.lat[0]))
        w.page_processing.edit_grid_lat_max.setText(str(cfg.grid.lat[1]))
        w.page_processing.edit_grid_lon_min.setText(str(cfg.grid.lon[0]))
        w.page_processing.edit_grid_lon_max.setText(str(cfg.grid.lon[1]))
        w.page_processing.slider_degree_order.setValue(int(cfg.inversion.Lmax))
        self._update_degree_order_label(int(cfg.inversion.Lmax))
        with QSignalBlocker(w.page_processing.chk_remove_mean):
            w.page_processing.chk_remove_mean.setChecked(bool(getattr(cfg.inversion, "remove_mean", True)))
        mean_start = str(getattr(cfg.inversion, "mean_start_ym", "") or "")
        mean_end = str(getattr(cfg.inversion, "mean_end_ym", "") or "")
        mean_mode = str(getattr(cfg.inversion, "mean_baseline_mode", "") or "").strip()
        if mean_mode not in {"standard_2004_2009", "input_full", "custom"}:
            if mean_start == "2004-01" and mean_end == "2009-12":
                mean_mode = "standard_2004_2009"
            elif mean_start or mean_end:
                mean_mode = "custom"
            else:
                mean_mode = "input_full"
        with QSignalBlocker(w.page_processing.cmb_anomaly_baseline):
            self._set_combo_value(w.page_processing.cmb_anomaly_baseline, mean_mode)
        self._set_edit_text(w.page_processing.edit_mean_start_ym, mean_start or "2004-01", block_signals=True)
        self._set_edit_text(w.page_processing.edit_mean_end_ym, mean_end or "2009-12", block_signals=True)
        lowdeg_cfg = getattr(cfg.inversion, "lowdeg", {}) or {}
        replace_degree1 = bool(lowdeg_cfg.get("replace_degree1", lowdeg_cfg.get("replace_C10", True)))
        with QSignalBlocker(w.page_processing.chk_lowdeg_enable):
            w.page_processing.chk_lowdeg_enable.setChecked(bool(lowdeg_cfg.get("enable", True)))
        with QSignalBlocker(w.page_processing.chk_replace_degree1):
            w.page_processing.chk_replace_degree1.setChecked(replace_degree1)
        with QSignalBlocker(w.page_processing.chk_replace_c20):
            w.page_processing.chk_replace_c20.setChecked(bool(lowdeg_cfg.get("replace_C20", True)))
        with QSignalBlocker(w.page_processing.chk_replace_c30):
            w.page_processing.chk_replace_c30.setChecked(bool(lowdeg_cfg.get("replace_C30", True)))
        with QSignalBlocker(w.page_processing.chk_apply_gia):
            w.page_processing.chk_apply_gia.setChecked(bool(cfg.get("inversion.gia.enable", False)))
        combinations = getattr(cfg.filter, "combinations", {}) or {}
        w.page_processing.btn_filter_gaussian.setChecked(bool(cfg.filter.gaussian.enable))
        w.page_processing.btn_filter_p4m6.setChecked(bool(cfg.filter.p4m6.enable))
        w.page_processing.btn_filter_gaussian_pnmn.setChecked(bool(combinations.get("gaussian_pnmn", bool(cfg.filter.gaussian.enable and cfg.filter.p4m6.enable))))
        w.page_processing.btn_filter_ddk.setChecked(bool(cfg.filter.ddk.enable))
        w.page_processing.btn_filter_fan.setChecked(bool(getattr(cfg.filter, "fan", {}).get("enable", False)))
        w.page_processing.btn_filter_fan_pnmn.setChecked(
            bool(combinations.get("fan_pnmn", bool(getattr(cfg.filter, "fan", {}).get("enable", False) and cfg.filter.p4m6.enable)))
        )
        w.page_processing.btn_filter_hsaf.setChecked(bool(cfg.filter.hankel.enable))
        self._sync_processing_filter_button_styles()
        params = getattr(cfg.filter.hankel, "params", {}) or {}
        if getattr(cfg.filter.ddk, "type", ""):
            self._set_combo_value(w.page_processing.cmb_ddk_type, str(getattr(cfg.filter.ddk, "type", "DDK4")))
        w.page_processing.edit_isotropic_radius_km.setText(str(getattr(cfg.filter.gaussian, "radius_km", 300.0)))
        w.page_processing.edit_pnmn_poly_degree.setText(str(getattr(cfg.filter.p4m6, "poly_deg", 4)))
        w.page_processing.edit_pnmn_m_start.setText(str(getattr(cfg.filter.p4m6, "m_start", 6)))
        w.page_processing.edit_fan_radius1_km.setText(str(getattr(cfg.filter.fan, "radius1_km", 300.0)))
        w.page_processing.edit_fan_radius2_km.setText(str(getattr(cfg.filter.fan, "radius2_km", 300.0)))
        self._set_combo_value(w.page_processing.cmb_hsaf_input, str(getattr(cfg.filter, "pre_hankel_input", "P4M6")))
        self._set_combo_value(w.page_processing.cmb_hsaf_variant, self._hsaf_variant_to_ui(str(getattr(cfg.filter.hankel, "variant", "global"))))
        w.page_processing.edit_hsaf_global_n.setText(str(params.get("N", 30)))
        w.page_processing.edit_hsaf_global_p.setText(str(params.get("P", 8)))
        w.page_processing.edit_hsaf_global_k.setText(str(params.get("K", 4)))
        w.page_processing.edit_hsaf_global_j.setText(str(params.get("J", 1)))
        w.page_processing.edit_hsaf_iterations.setText(str(params.get("iterations", 1)))
        w.page_processing.edit_hsaf_alpha.setText(str(params.get("alpha_cutoff", 0.0035)))
        w.page_processing.edit_hsaf_tolerance.setText(str(params.get("convergence_tol", 1.0e-7)))
        adaptive_cfg = list(getattr(cfg.filter.hankel, "adaptive", []) or [])
        adaptive_defaults = self._default_hsaf_adaptive_zones(params)
        for idx, fields in enumerate(w.page_processing.hsaf_adaptive_zone_fields):
            zone = adaptive_cfg[idx] if idx < len(adaptive_cfg) else adaptive_defaults[idx]
            lat_range = list(zone.get("lat_range", adaptive_defaults[idx]["lat_range"]))
            zone_params = dict(zone.get("params", {}) or {})
            fields["lat_min"].setText(str(lat_range[0]))
            fields["lat_max"].setText(str(lat_range[1]))
            fields["N"].setText(str(zone_params.get("N", params.get("N", 30))))
            fields["P"].setText(str(zone_params.get("P", params.get("P", 8))))
            fields["K"].setText(str(zone_params.get("K", params.get("K", 4))))
            fields["J"].setText(str(zone_params.get("J", params.get("J", 1))))
        self._sync_processing_hsaf_controls()
        self._sync_processing_time_override_state(manual_override)
        self._sync_processing_mean_controls()
        self._sync_processing_lowdeg_controls()
        self._refresh_detected_time_range()
        self._sync_download_source_controls()

        basin_cfg = raw.get("basin", {})
        w.page_basin.chk_basin_enable.setChecked(bool(basin_cfg.get("analysis_enable", False)))
        w.page_basin.edit_data_file.setText(str(basin_cfg.get("data_file", "")))
        w.page_basin.edit_boundary_file.setText(str(basin_cfg.get("boundary_file", "")))
        if hasattr(w.page_basin, "edit_basin_name_field"):
            w.page_basin.edit_basin_name_field.setText(str(basin_cfg.get("name_field", "Name") or "Name"))
        if hasattr(w.page_basin, "cmb_basin_name_field"):
            w.page_basin.cmb_basin_name_field.setEditText(str(basin_cfg.get("name_field", "Name") or "Name"))
        w.page_basin.edit_export_path.setText(str(basin_cfg.get("output_dir", Path(getattr(cfg.path, "OUTPUT", "")) / "local" / "basin")))
        if basin_cfg.get("aggregation_strategy"):
            w.page_basin.cmb_aggregation_strategy.setCurrentText(str(basin_cfg.get("aggregation_strategy")))
        if basin_cfg.get("missing_month_fallback"):
            w.page_basin.cmb_missing_month_fallback.setCurrentText(str(basin_cfg.get("missing_month_fallback")))
        if hasattr(w.page_basin, "chk_basin_save_series"):
            w.page_basin.chk_basin_save_series.setChecked(bool(basin_cfg.get("do_time_series", True)))
            w.page_basin.chk_basin_save_stats.setChecked(bool(basin_cfg.get("do_statistics", True)))
            w.page_basin.chk_basin_save_mask_grid.setChecked(bool(basin_cfg.get("do_grid", True)))
            w.page_basin.chk_basin_save_ts_txt.setChecked(bool(basin_cfg.get("save_ts_txt", True)))
            w.page_basin.chk_basin_save_ts_mat.setChecked(bool(basin_cfg.get("save_ts_mat", True)))
            w.page_basin.chk_basin_save_grid_mat.setChecked(bool(basin_cfg.get("save_grid_mat", True)))

        leak_cfg = raw.get("leakage", {})
        w.page_leakage.chk_leakage_enable.setChecked(True)
        method = str(leak_cfg.get("method", "FM")).upper()
        strategy = str(leak_cfg.get("correction_strategy", "auto")).lower()
        if strategy == "scale_factor":
            strategy = "basin_scale_factor"
        w.page_leakage.rb_method_fm.setChecked(method == "FM")
        w.page_leakage.rb_method_sf.setChecked(method != "FM")
        self._set_combo_value(w.page_leakage.cmb_strategy_family, str(leak_cfg.get("strategy_family", "global_regularized")).lower() or "global_regularized")
        if w.page_leakage.cmb_correction_strategy.findData(strategy or "auto") < 0:
            strategy = "auto"
        self._set_combo_value(w.page_leakage.cmb_correction_strategy, strategy or "auto")
        self._set_combo_value(w.page_leakage.cmb_scene_override, str(leak_cfg.get("scene_override", "auto")).lower() or "auto")
        self._set_combo_value(w.page_leakage.cmb_reference_mode, str(leak_cfg.get("reference_mode", "trend")).lower() or "trend")
        if hasattr(w.page_leakage, "cmb_official_mode"):
            self._set_combo_value(w.page_leakage.cmb_official_mode, str(leak_cfg.get("official_mode", "auto")).lower() or "auto")
        family_seed = self._combo_value(w.page_leakage.cmb_strategy_family).lower()
        self._set_combo_value(w.page_leakage.cmb_scope, "regional" if family_seed == "regional" else "global")
        w.page_leakage.edit_lrc_input.setText(str(leak_cfg.get("input", "")))
        w.page_leakage.edit_reference_input.setText(str(leak_cfg.get("reference_input", "")))
        w.page_leakage.edit_lrc_output.setText(str(leak_cfg.get("output", "")))
        w.page_leakage.edit_regional_boundary.setText(str(leak_cfg.get("boundary_file", "")))
        w.page_leakage.edit_lrc_sf_factor.setText(str(leak_cfg.get("sf_factor", 1.0)))
        self._set_combo_value(w.page_leakage.cmb_lrc_format, str(leak_cfg.get("format", "mat")).lower())
        w.page_leakage.edit_operator_autodetect.setText("Auto")
        w.page_leakage.edit_lrc_gaussian_km.setText(str(leak_cfg.get("sf_gauss_km", 300.0)))
        w.page_leakage.edit_ddk_type.setText(str(leak_cfg.get("sf_ddk_type", "DDK4")))
        w.page_leakage.edit_fm_iteration_count.setText(str(leak_cfg.get("fm_max_iter", 40)))
        w.page_leakage.edit_fm_convergence_threshold.setText(str(leak_cfg.get("fm_tol", 0.01)))
        w.page_leakage.edit_fm_acceleration.setText(str(leak_cfg.get("fm_accel", 1.1)))
        w.page_leakage.edit_fm_patience.setText(str(leak_cfg.get("fm_patience", 8)))
        w.page_leakage.edit_fm_min_improve.setText(str(leak_cfg.get("fm_min_improve", 1.0e-4)))
        if hasattr(w.page_leakage, "edit_coastal_buffer_cells"):
            w.page_leakage.edit_coastal_buffer_cells.setText(str(leak_cfg.get("coastal_buffer_cells", 3)))
        if hasattr(w.page_leakage, "edit_coastal_attenuation_gain"):
            w.page_leakage.edit_coastal_attenuation_gain.setText(str(leak_cfg.get("coastal_attenuation_gain", 1.0)))
        if hasattr(w.page_leakage, "edit_regularized_lambda"):
            w.page_leakage.edit_regularized_lambda.setText(str(leak_cfg.get("regularized_lambda", 0.18)))
        if hasattr(w.page_leakage, "edit_regularized_step_size"):
            w.page_leakage.edit_regularized_step_size.setText(str(leak_cfg.get("regularized_step_size", 0.9)))
        if hasattr(w.page_leakage, "edit_regularized_sigma"):
            w.page_leakage.edit_regularized_sigma.setText(str(leak_cfg.get("regularized_sigma", 1.2)))
        if hasattr(w.page_leakage, "edit_regularized_iter"):
            w.page_leakage.edit_regularized_iter.setText(str(leak_cfg.get("regularized_iter", 10)))
        self.on_leakage_strategy_changed()

    def pull_ui_to_host(self):
        cfg_dict = self.collect_config_dict(copy.deepcopy(getattr(self.host.cfg, "_raw", {}) or getattr(self.host.default_cfg, "_raw", {})))
        self.host.cfg = Config(copy.deepcopy(cfg_dict))
        w = self.window
        self.host.var_basin_enable.set(w.page_basin.chk_basin_enable.isChecked())
        self.host.var_basin_data.set(w.page_basin.edit_data_file.text().strip())
        self.host.var_basin_file.set(self._resolve_basin_boundary_file(w.page_basin.edit_boundary_file.text().strip()))
        self.host.var_basin_name_field.set(self._basin_name_field())
        basin_names = [] if w.page_basin.cmb_basin_selection_mode.currentIndex() == 1 else self._selected_basin_names()
        basin_name = basin_names[0] if basin_names else ""
        self.host.var_basin_name.set(basin_name)
        if hasattr(self.host, "var_basin_names"):
            self.host.var_basin_names.set(basin_names)
        self.host.var_basin_out_dir.set(w.page_basin.edit_export_path.text().strip())
        self.host.var_basin_use_file_time.set(True)
        self.host.var_basin_do_grid.set(bool(getattr(w.page_basin, "chk_basin_save_mask_grid", None).isChecked()) if hasattr(w.page_basin, "chk_basin_save_mask_grid") else True)
        self.host.var_basin_do_ts.set(bool(getattr(w.page_basin, "chk_basin_save_series", None).isChecked()) if hasattr(w.page_basin, "chk_basin_save_series") else True)
        self.host.var_basin_do_stats.set(bool(getattr(w.page_basin, "chk_basin_save_stats", None).isChecked()) if hasattr(w.page_basin, "chk_basin_save_stats") else True)
        self.host.var_basin_save_ts_txt.set(bool(getattr(w.page_basin, "chk_basin_save_ts_txt", None).isChecked()) if hasattr(w.page_basin, "chk_basin_save_ts_txt") else True)
        self.host.var_basin_save_ts_mat.set(bool(getattr(w.page_basin, "chk_basin_save_ts_mat", None).isChecked()) if hasattr(w.page_basin, "chk_basin_save_ts_mat") else True)
        self.host.var_basin_save_grid_txt.set(False)
        self.host.var_basin_save_grid_mat.set(bool(getattr(w.page_basin, "chk_basin_save_grid_mat", None).isChecked()) if hasattr(w.page_basin, "chk_basin_save_grid_mat") else True)

        self.host.var_lrc_enable.set(True)
        family_value = self._combo_value(w.page_leakage.cmb_strategy_family).lower()
        self.host.var_lrc_scope.set("regional" if family_value == "regional" else "global")
        strategy = self._combo_value(w.page_leakage.cmb_correction_strategy).lower()
        self.host.var_lrc_method.set("FM" if strategy == "forward_modeling" else "SF")
        self.host.var_lrc_sf.set(self._safe_float(w.page_leakage.edit_lrc_sf_factor.text(), 1.0))
        self.host.var_lrc_input.set(w.page_leakage.edit_lrc_input.text().strip())
        self.host.var_lrc_output.set(w.page_leakage.edit_lrc_output.text().strip())
        self.host.var_lrc_fmt.set(self._combo_value(w.page_leakage.cmb_lrc_format).lower())
        self.host.var_lrc_boundary.set(w.page_leakage.edit_regional_boundary.text().strip())
        # Simplified leakage UI always uses input-based auto operator detection.
        self.host.var_lrc_sf_method.set("Auto")
        self.host.var_lrc_sf_gauss.set(self._safe_float(w.page_leakage.edit_lrc_gaussian_km.text(), 300.0))
        self.host.var_lrc_sf_ddk.set(w.page_leakage.edit_ddk_type.text().strip() or "DDK4")
        self.host.var_lrc_fm_max_iter.set(max(1, int(round(self._safe_float(w.page_leakage.edit_fm_iteration_count.text(), 40.0)))))
        self.host.var_lrc_fm_tol.set(self._safe_float(w.page_leakage.edit_fm_convergence_threshold.text(), 0.01))
        self.host.var_lrc_fm_accel.set(self._safe_float(w.page_leakage.edit_fm_acceleration.text(), 1.1))
        self.host.var_lrc_fm_patience.set(max(0, int(round(self._safe_float(w.page_leakage.edit_fm_patience.text(), 8.0)))))
        self.host.var_lrc_fm_min_improve.set(self._safe_float(w.page_leakage.edit_fm_min_improve.text(), 1.0e-4))
        if self.window.page_preview.edit_dataset_source.text().strip():
            self.host._stack_cache_path = self.window.page_preview.edit_dataset_source.text().strip()

    def refresh_dashboard(self):
        cfg = self.host.cfg
        dashboard = self.window.page_dashboard
        dashboard.lbl_project_name.setText(self.host.current_cfg_path.name if self.host.current_cfg_path else "In-Memory Config")
        dashboard.lbl_last_edited.setText(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        dashboard.lbl_uid.setText(hashlib.sha1(json.dumps(getattr(cfg, "_raw", {}), sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12])
        output_root = self._native_path(getattr(cfg.path, "OUTPUT", ""), base_dir=ROOT_DIR)
        dashboard.lbl_output_root.setText(output_root)
        dashboard.lbl_output_hint.setText("Local execution | Output directories resolved from active config.")
        time_entries = self._detect_time_entries_for_ui()
        count = len(time_entries)
        dashboard.lbl_data_count.setText(str(count))
        if time_entries:
            cov = summarize_time_coverage(time_entries)
            dashboard.lbl_time_span.setText(
                f"{int(cov.get('available_month_count', count))} GFC files | "
                f"{time_entries[0].ym} // {time_entries[-1].ym} | "
                f"missing={int(cov.get('missing_month_count', 0))} "
                f"(GRACE={int(cov.get('grace_missing_count', 0))})"
            )
        else:
            dashboard.lbl_time_span.setText("GFC data files | not detected")
        basin_enabled = bool(getattr(cfg, "basin", {}).get("analysis_enable", False))
        leak_enabled = bool(getattr(cfg, "leakage", {}).get("enable", False))
        dashboard.badge_summary_state.setText("Ready to Process")
        dashboard.badge_summary_state.setProperty("variant", "success")
        dashboard.badge_summary_state.style().unpolish(dashboard.badge_summary_state)
        dashboard.badge_summary_state.style().polish(dashboard.badge_summary_state)
        dashboard.lbl_active_run_name.setText("Configured")
        dashboard.lbl_active_task.setText(f"Basin={'ON' if basin_enabled else 'OFF'} | Leakage={'ON' if leak_enabled else 'OFF'}")
        self._sync_dashboard_run_summary()
        self._sync_monitor_context()

    def on_validate_paths(self):
        for edit, base_dir in (
            (self.window.page_data_paths.edit_gfc_input_dir, ROOT_DIR),
            (self.window.page_data_paths.edit_aux_path, ROOT_DIR),
            (self.window.page_data_paths.edit_boundary_root, ROOT_DIR),
            (self.window.page_data_paths.edit_boundary_path, ROOT_DIR),
            (self.window.page_data_paths.edit_low_degree_path, ROOT_DIR),
            (self.window.page_data_paths.edit_degree1_path, ROOT_DIR),
            (self.window.page_data_paths.edit_gia_path, ROOT_DIR),
            (self.window.page_data_paths.edit_mascon_root, ROOT_DIR),
            (self.window.page_data_paths.edit_mascon_reference, ROOT_DIR),
            (self.window.page_data_paths.edit_mascon_gad, self.window.page_data_paths.edit_mascon_root),
            (self.window.page_data_paths.edit_mascon_gia, self.window.page_data_paths.edit_mascon_root),
            (self.window.page_data_paths.edit_main_output_root, ROOT_DIR),
        ):
            self._normalize_path_edit(edit, base_dir=base_dir)
        checks = [
            ("GFC", self.window.page_data_paths.edit_gfc_input_dir.text()),
            ("OUTPUT", self.window.page_data_paths.edit_main_output_root.text()),
            ("LOGS", self.window.page_data_paths.edit_logs_dir.text()),
            ("AUX", self.window.page_data_paths.edit_aux_path.text()),
            ("BoundaryRoot", self.window.page_data_paths.edit_boundary_root.text()),
            ("Boundary", self.window.page_data_paths.edit_boundary_path.text()),
            ("LowDegree", self.window.page_data_paths.edit_low_degree_path.text()),
            ("Degree1", self.window.page_data_paths.edit_degree1_path.text()),
            ("GIA", self.window.page_data_paths.edit_gia_path.text()),
            ("MasconRoot", self.window.page_data_paths.edit_mascon_root.text()),
            ("MasconDir", self.window.page_data_paths.edit_mascon_reference.text()),
            ("MasconGAD", self.window.page_data_paths.edit_mascon_gad.text()),
            ("MasconGIA", self.window.page_data_paths.edit_mascon_gia.text()),
        ]
        ok = 0
        for name, value in checks:
            exists = bool(value and Path(value).exists())
            self.on_log(f"[PATH] {name}: {'OK' if exists else 'MISSING'} -> {value}", "stderr" if not exists else "stdout")
            ok += int(exists)
        if self.window.page_processing.btn_filter_ddk.isChecked():
            kernels = self._ddk_kernel_files()
            if kernels:
                self.on_log(f"[PATH] DDK kernels: OK ({len(kernels)} files)", "stdout")
            else:
                self.on_log(f"[PATH] DDK kernels: MISSING -> {self.window.page_data_paths.edit_ddk_data_dir.text()}", "stderr")
        self._sync_data_path_badges()
        self._refresh_detected_time_range()
        self._show_info("Path Validation", f"Validated {len(checks)} paths, {ok} exist.")

    def on_load_basin_info(self):
        try:
            self.pull_ui_to_host()
            info = self.host.load_basin_info()
            shape = info["shape"]
            meta = info.get("meta", {})
            page = self.window.page_basin
            nt = int(shape[2]) if len(shape) >= 3 else 1
            active_var = str(meta.get("active_var", "ewh"))
            page.lbl_basin_info.setText(f"Loaded: {Path(self.host.var_basin_data.get()).name}")
            if hasattr(page, "lbl_basin_grid_shape"):
                page.lbl_basin_grid_shape.setText(f"Shape: {shape[0]} x {shape[1]} x {nt}")
            if hasattr(page, "lbl_basin_variable"):
                page.lbl_basin_variable.setText(f"Variable: {active_var}")
            if hasattr(page, "lbl_basin_time_range"):
                time_text = "Time: not detected"
                with contextlib.suppress(Exception):
                    cache = self.host._basin_cache or {}
                    t_years, labels = self.host._resolve_time(cache.get("t"), nt, meta=cache.get("meta", {}) or {})
                    if labels:
                        time_text = f"Time: {labels[0]} -> {labels[-1]} ({len(labels)} samples)"
                page.lbl_basin_time_range.setText(time_text)
            if hasattr(page, "slider_basin_time_index"):
                page.slider_basin_time_index.blockSignals(True)
                page.slider_basin_time_index.setRange(0, max(0, nt - 1))
                page.slider_basin_time_index.setValue(0)
                page.slider_basin_time_index.setEnabled(nt > 1)
                page.slider_basin_time_index.blockSignals(False)
                self._sync_basin_time_slice_label()
            if not page.edit_export_path.text().strip() or page.edit_export_path.text().strip().startswith("./"):
                page.edit_export_path.setText(str(Path(getattr(self.host.cfg.path, "OUTPUT", ROOT_DIR / "output")) / "local" / "basin"))
            if self._basin_boundaries:
                with contextlib.suppress(Exception):
                    lon_vec = np.asarray(self.host._basin_cache.get("lon"), dtype=float).squeeze()
                    lat_vec = np.asarray(self.host._basin_cache.get("lat"), dtype=float).squeeze()
                    self._populate_basin_table_from_boundaries(self._basin_boundaries, lon_vec=lon_vec, lat_vec=lat_vec)
            self.on_log(f"[BASIN] Input loaded: {self.host.var_basin_data.get()}", "stdout")
            with contextlib.suppress(Exception):
                if page.edit_boundary_file.text().strip():
                    self.on_generate_basin_mask_preview()
                else:
                    self.on_refresh_basin_preview(show_errors=False)
        except Exception as exc:
            self.window.page_basin.lbl_basin_info.setText(f"Load failed: {exc}")
            self._show_error("Basin", str(exc))
        self.window.refresh_translations()

    def _ddk_kernel_files(self, ddk_dir: str | Path | None = None) -> list[Path]:
        text = str(ddk_dir or self.window.page_data_paths.edit_ddk_data_dir.text() or "").strip()
        if not text:
            root = Path(DEFAULT_DATA_PATHS["DDK"])
        else:
            root = Path(self._native_path(text, base_dir=ROOT_DIR))
        if not root.exists() or not root.is_dir():
            return []
        return sorted(path for path in root.glob("Wbd_*") if path.is_file())

    def _missing_ddk_kernel_message(self) -> str:
        ddk_dir = self._native_path(self.window.page_data_paths.edit_ddk_data_dir.text(), base_dir=ROOT_DIR)
        return f"DDK kernel files were not found in {ddk_dir}. Expected files matching Wbd_*."

    def on_load_basin_boundary_info(self):
        page = self.window.page_basin
        try:
            boundary_path = page.edit_boundary_file.text().strip() or self.window.page_data_paths.edit_boundary_path.text().strip()
            if not boundary_path:
                raise ValueError("No boundary file configured.")
            boundary_path = self._resolve_basin_boundary_file(boundary_path)
            if page.edit_boundary_file.text().strip() != boundary_path:
                page.edit_boundary_file.setText(boundary_path)
            name_field = self._populate_basin_name_field_options(boundary_path)
            boundaries = basin_read_boundary(boundary_path, name_field=name_field)
            if not boundaries:
                raise ValueError("No basin polygon found in boundary file.")
            self._basin_boundaries = list(boundaries)
            lon_vec = lat_vec = None
            with contextlib.suppress(Exception):
                if self.host._basin_cache is not None:
                    lon_vec = np.asarray(self.host._basin_cache.get("lon"), dtype=float).squeeze()
                    lat_vec = np.asarray(self.host._basin_cache.get("lat"), dtype=float).squeeze()
            self._populate_basin_table_from_boundaries(boundaries, lon_vec=lon_vec, lat_vec=lat_vec)
            if hasattr(page, "lbl_boundary_info"):
                page.lbl_boundary_info.setText(f"Boundary loaded: {len(boundaries)} feature(s)")
            if hasattr(page, "lbl_selected_basin"):
                page.lbl_selected_basin.setText(f"Preview basin: {self._preview_basin_name() or getattr(boundaries[0], 'name', 'basin')}")
            if hasattr(page, "lbl_mask_info"):
                page.lbl_mask_info.setText("Mask: boundary loaded; waiting for grid input" if lon_vec is None or lat_vec is None else "Mask: generating from boundary and grid")
            self.on_log(f"[BASIN] Boundary loaded: {boundary_path} ({len(boundaries)} feature(s))", "stdout")
            with contextlib.suppress(Exception):
                if lon_vec is not None and lat_vec is not None:
                    self.on_generate_basin_mask_preview()
                else:
                    self.on_refresh_basin_preview(show_errors=False)
        except Exception as exc:
            if hasattr(page, "lbl_boundary_info"):
                page.lbl_boundary_info.setText(f"Boundary load failed: {exc}")
            self.on_log(f"[BASIN] Boundary load failed: {exc}", "stderr")
        self.window.refresh_translations()

    def on_generate_basin_mask_preview(self):
        page = self.window.page_basin
        try:
            ctx = self._build_basin_spatial_context(require_boundary=False)
            mask = np.asarray(ctx["mask"], dtype=bool)
            selected_cells = int(np.count_nonzero(mask))
            total_cells = int(mask.size)
            pct = (100.0 * selected_cells / total_cells) if total_cells else 0.0
            if hasattr(page, "lbl_mask_info"):
                page.lbl_mask_info.setText(f"Mask: {selected_cells} / {total_cells} grid cells ({pct:.2f}%)")
            if hasattr(page, "lbl_selected_basin"):
                page.lbl_selected_basin.setText(f"Selected basin: {ctx['basin_name']}")
            page.lbl_series_tool_status.setText(f"Status: mask generated for {ctx['basin_name']}.")
            self.on_log(f"[BASIN] Mask generated: {ctx['basin_name']} cells={selected_cells}/{total_cells}", "stdout")
            self.on_refresh_basin_preview(show_errors=False, context=ctx)
        except Exception as exc:
            if hasattr(page, "lbl_mask_info"):
                page.lbl_mask_info.setText(f"Mask failed: {exc}")
            self._show_error("Basin", str(exc))
        self.window.refresh_translations()

    def on_load_leakage_info(self):
        try:
            self.pull_ui_to_host()
            info = self.host.load_leakage_info()
            shape = info["shape"]
            meta = info.get("meta", {})
            active_var = meta.get("active_var", "ewh")
            page = self.window.page_leakage
            page.lbl_leakage_info.setText(f"{shape[0]} x {shape[1]} x {shape[2]} | {active_var}")
            page.lbl_dataset_shape_value.setText(f"{shape[0]} x {shape[1]} x {shape[2]}")

            lon_vec = np.asarray(self.host._leakage_cache.get("lon"), dtype=float).squeeze()
            lat_vec = np.asarray(self.host._leakage_cache.get("lat"), dtype=float).squeeze()
            data_meta = self.host._leakage_cache.get("meta", {})
            opts = self.host._build_leakage_filter_options(self.host.var_lrc_input.get(), data_meta=data_meta)
            operator = infer_operator_spec(self.host.var_lrc_input.get(), opts, data_meta=data_meta, source="load_info")
            page.lbl_product_type_value.setText(self._leakage_label(operator.product_type))
            page.lbl_operator_value.setText(self._leakage_label(operator.method))
            page.edit_operator_autodetect.setText(operator.method or "Auto")
            page.badge_product.setText(self._leakage_label(operator.product_type))
            page.badge_operator.setText(self._leakage_label(operator.method))

            current_strategy = self._combo_value(page.cmb_correction_strategy)
            family_value = self._combo_value(page.cmb_strategy_family)
            official_mode = self._combo_value(page.cmb_official_mode)
            has_reference = bool(page.edit_reference_input.text().strip())
            if not page.cmb_correction_strategy.isVisible():
                current_strategy = "auto"
                blocker = QSignalBlocker(page.cmb_correction_strategy)
                self._set_combo_value(page.cmb_correction_strategy, "auto")
                del blocker

            if operator.product_type == "mascon_native":
                suggested_family = "official"
            elif operator.product_type in ("official_land_grid", "official_scaling_grid"):
                suggested_family = "official"
            elif bool(getattr(operator, "is_gaussian_equivalent", False)):
                suggested_family = "global_coastal"
            else:
                suggested_family = "global_regularized"

            if current_strategy == "auto" or not family_value:
                blocker = QSignalBlocker(page.cmb_strategy_family)
                self._set_combo_value(page.cmb_strategy_family, suggested_family)
                del blocker
                family_value = suggested_family

            scope_value = "regional" if family_value == "regional" else "global"
            self._set_combo_value(page.cmb_scope, scope_value)

            note_lines = [
                f"产品类型：{self._leakage_label(operator.product_type)}",
                f"滤波识别：{self._leakage_label(operator.method)}",
            ]
            scene_text = "全局模式"
            boundary_status = "不使用区域边界"

            if scope_value == "regional":
                if not page.edit_regional_boundary.text().strip():
                    scope_value = "global"
                    self._set_combo_value(page.cmb_scope, "global")
                    blocker = QSignalBlocker(page.cmb_strategy_family)
                    self._set_combo_value(page.cmb_strategy_family, suggested_family)
                    del blocker
                    family_value = suggested_family
                    note_lines.append("未提供区域边界，已自动切换为全局推荐流程。")
                else:
                    mask = self.host._build_leakage_mask(scope_value, lon_vec, lat_vec)
                    global_land = self.host._build_global_land_mask(lon_vec, lat_vec)
                    scene = classify_leakage_scene(mask, lon_vec, lat_vec, global_land_mask=global_land)
                    scene_text = self._leakage_label(scene.scene)
                    boundary_status = f"已使用区域边界（{int(np.count_nonzero(mask))} 个格点）"
                    requested = resolve_strategy_request(family_value, current_strategy, operator, official_mode=official_mode)
                    recommendation = recommend_correction_method(requested, scene, operator, has_reference_model=has_reference)
                    note_lines.extend([
                        f"场景识别：{scene_text}",
                        f"推荐策略：{self._leakage_label(recommendation)}",
                        "识别依据：",
                        *[f"- {item}" for item in scene.reasoning],
                    ])
            if scope_value != "regional":
                recommendation = resolve_strategy_request(family_value, current_strategy, operator, official_mode=official_mode)
                if recommendation == "AUTO":
                    recommendation = "GLOBAL_COASTAL_GAUSSIAN" if bool(getattr(operator, "is_gaussian_equivalent", False)) else "GLOBAL_REGULARIZED"
                if family_value == "global_coastal" and not bool(getattr(operator, "is_gaussian_equivalent", False)):
                    note_lines.extend([
                        "工作流：全球海岸线",
                        "当前滤波不是 Gaussian 路线，不适用海岸线 Gaussian 算法。",
                        "系统已自动切换为全球正则化恢复。",
                    ])
                else:
                    note_lines.extend([
                        f"工作流：{self._leakage_label(family_value)}",
                        f"推荐策略：{self._leakage_label(recommendation)}",
                    ])

            page.lbl_scene_value.setText(scene_text)
            page.lbl_recommendation_value.setText(self._leakage_label(recommendation))
            page.lbl_boundary_status.setText(boundary_status)
            page.badge_scene.setText(scene_text)
            page.badge_strategy.setText(self._leakage_label(recommendation))
            page.lbl_linkage_status.setText("输入信息已更新，可直接按自动推荐运行。")
            page.txt_leakage_notes.setPlainText("\n".join(note_lines))
            self.on_log(f"[LEAKAGE] Input loaded: {self.host.var_lrc_input.get()}", "stdout")
        except Exception as exc:
            self.window.page_leakage.lbl_leakage_info.setText(f"读取失败：{exc}")
            self.window.page_leakage.lbl_linkage_status.setText("输入读取失败，请检查路径和数据结构。")
            self._show_error("泄漏校正", str(exc))
        self.on_leakage_strategy_changed()
        self.window.refresh_translations()

    def _tool_output_dir(self, tool_name: str) -> Path:
        output_root = self._native_path(getattr(self.host.cfg.path, "OUTPUT", ""), base_dir=ROOT_DIR)
        if not output_root:
            output_root = self._native_path(self.window.page_data_paths.edit_main_output_root.text(), base_dir=ROOT_DIR)
        if not output_root:
            output_root = self._native_path(ROOT_DIR / "output")
        out_dir = Path(output_root) / "local" / "tools" / str(tool_name).strip()
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    @staticmethod
    def _safe_name(text: str, fallback: str) -> str:
        raw = str(text or "").strip()
        if not raw:
            raw = fallback
        return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in raw)

    def _resolve_tool_sh_source(self) -> Path:
        tool_path = self.window.page_processing.edit_sh_tool_source.text().strip()
        if tool_path:
            p = Path(self._native_path(tool_path, base_dir=ROOT_DIR))
            if p.exists() and p.is_file() and p.suffix.lower() in {".gfc", ".mat"}:
                return p
            if p.exists() and p.is_file():
                raise ValueError("SH -> Grid source must be a .gfc or SH-coefficient .mat file.")
        preview_path = self.window.page_preview.edit_dataset_source.text().strip()
        if preview_path:
            p = Path(self._native_path(preview_path, base_dir=ROOT_DIR))
            if p.exists() and p.is_file() and p.suffix.lower() in {".gfc", ".mat"}:
                return p
        gfc_dir = Path(self._native_path(self.window.page_data_paths.edit_gfc_input_dir.text(), base_dir=ROOT_DIR))
        if gfc_dir.exists() and gfc_dir.is_dir():
            candidates = sorted(gfc_dir.glob("*.gfc"))
            if candidates:
                return candidates[0]
        raise FileNotFoundError("No SH source file found. Set a .gfc/.mat source in Preview or configure a valid GFC directory.")

    def _resolve_tool_grid_source(self) -> Path:
        for raw in (
            self.window.page_processing.edit_sh_tool_source.text().strip(),
            self.window.page_preview.edit_dataset_source.text().strip(),
        ):
            if not raw:
                continue
            p = Path(self._native_path(raw, base_dir=ROOT_DIR))
            if p.exists() and p.is_file() and p.suffix.lower() in {".mat", ".nc", ".nc4", ".cdf", ".h5", ".hdf5"}:
                return p
        raise FileNotFoundError("No grid source file found. Set Tool Source or Preview Dataset Source to a MAT/NetCDF/HDF5 grid stack.")

    def _load_sh_from_mat(self, file_path: Path, lmax: int) -> tuple[np.ndarray, np.ndarray, int]:
        payload = loadmat(str(file_path), squeeze_me=True, struct_as_record=False)
        c = payload.get("C")
        s = payload.get("S")
        if c is None or s is None:
            cs = payload.get("cs_grace", payload.get("cs"))
            if isinstance(cs, np.ndarray) and cs.ndim == 3 and cs.shape[2] >= 2:
                c = cs[:, :, 0]
                s = cs[:, :, 1]
        if c is None or s is None:
            raise ValueError("MAT file must contain C/S arrays (or cs(:,:,2)-style coefficients).")
        c_arr = np.asarray(c, dtype=float)
        s_arr = np.asarray(s, dtype=float)
        if c_arr.ndim != 2 or s_arr.ndim != 2:
            raise ValueError("Invalid SH coefficient dimensions in MAT file.")
        lmax_eff = int(min(int(lmax), c_arr.shape[0] - 1, s_arr.shape[0] - 1))
        l1 = lmax_eff + 1
        return c_arr[:l1, :l1], s_arr[:l1, :l1], lmax_eff

    def _read_tool_gfc_anomaly(self, source_path: Path, cfg_dict: dict, lmax: int) -> tuple[np.ndarray, np.ndarray, int, dict]:
        cfg_dict = copy.deepcopy(cfg_dict or {})
        cfg_dict.setdefault("path", {})["GFC"] = str(source_path.parent)
        cfg_dict.setdefault("time", {})["auto_detect_gfc"] = True
        cfg_local = Config(cfg_dict)

        sh0 = read_gfc(str(source_path), lmax)
        ym = str(sh0.meta.get("ym", "") or "").strip()
        if ym:
            time_entry = TimeEntry.from_ym(ym, gfc_file=str(source_path))
            sh = read_gsm_month(cfg_local, time_entry)
        else:
            time_entry = TimeEntry.from_ym("1900-01", gfc_file=str(source_path))
            sh = sh0
        sh = replace_low_degree(cfg_local, sh, time_entry)

        mean_meta = {"removed_mean": False, "mean_months": 0, "mean_mode": "", "source_ym": ym}
        if bool(getattr(cfg_local.inversion, "remove_mean", True)):
            mean_sh = None
            try:
                time_entries = build_time_index(cfg_local)
                mean_sh = compute_mean_sh(cfg_local, time_entries)
            except Exception as exc:
                mean_meta["mean_warning"] = str(exc)
            mean_mode = get_mean_mode(cfg_local)
            mean_for_month = select_mean_sh(mean_sh, time_entry, mean_mode)
            if mean_for_month is not None:
                sh.C = sh.C - mean_for_month.C
                sh.S = sh.S - mean_for_month.S
                mean_meta.update(
                    {
                        "removed_mean": True,
                        "mean_months": int(getattr(mean_for_month, "meta", {}).get("n_months", 0) or 0),
                        "mean_mode": mean_mode,
                    }
                )
        else:
            sh.C = sh.C.copy()
            sh.S = sh.S.copy()
            if sh.C.size:
                sh.C[0, 0] = 0.0
            if sh.C.shape[0] > 1:
                sh.C[1, :] = 0.0
                sh.S[1, :] = 0.0
            mean_meta["mean_warning"] = "Mean removal disabled; degree 0/1 terms were zeroed for display."

        c_arr = np.asarray(sh.C, dtype=float)
        s_arr = np.asarray(sh.S, dtype=float)
        lmax_eff = min(int(lmax), c_arr.shape[0] - 1, s_arr.shape[0] - 1)
        l1 = lmax_eff + 1
        return c_arr[:l1, :l1], s_arr[:l1, :l1], int(lmax_eff), mean_meta

    def on_tool_sh_to_grid(self):
        self.pull_ui_to_host()
        self.window.page_processing.lbl_sh_tool_status.setText("Status: running SH -> Grid synthesis...")

        def _target():
            source_path = self._resolve_tool_sh_source()
            cfg_dict = self.collect_config_dict(copy.deepcopy(getattr(self.host.cfg, "_raw", {}) or {}))
            cfg_local = Config(cfg_dict)
            lon_vec, lat_vec = make_lonlat_vec(cfg_local)
            lmax = int(getattr(cfg_local.inversion, "Lmax", 60))
            tool_meta = {}
            if source_path.suffix.lower() == ".gfc":
                c_arr, s_arr, lmax_eff, tool_meta = self._read_tool_gfc_anomaly(source_path, cfg_dict, lmax)
            else:
                c_arr, s_arr, lmax_eff = self._load_sh_from_mat(source_path, lmax)
                tool_meta = {"removed_mean": False, "source_ym": ""}
            grid = ewh_synthesis(
                c_arr,
                s_arr,
                int(lmax_eff),
                np.asarray(lon_vec, dtype=float),
                np.asarray(lat_vec, dtype=float),
                unit=str(getattr(cfg_local.grid, "unit", "mmEWH")),
            )
            out_dir = self._tool_output_dir("sh_grid")
            out_file = out_dir / f"sh_grid_{self._safe_name(source_path.stem, 'source')}_L{int(lmax_eff)}.mat"
            self.host._safe_savemat(
                str(out_file),
                {
                    "grid_data": np.asarray(grid, dtype=float),
                    "ewh": np.asarray(grid, dtype=float),
                    "lon": np.asarray(lon_vec, dtype=float),
                    "lat": np.asarray(lat_vec, dtype=float),
                    "Lmax": int(lmax_eff),
                    "source_file": str(source_path),
                    "tool_meta": tool_meta,
                },
            )
            self.signals.log.emit(f"[TOOL][SH2GRID] source={source_path}", "stdout")
            if tool_meta:
                self.signals.log.emit(
                    f"[TOOL][SH2GRID] anomaly_removed={tool_meta.get('removed_mean')} mean_months={tool_meta.get('mean_months', 0)}",
                    "stdout",
                )
            self.signals.log.emit(f"[OUTPUT] {out_file}", "stdout")
            self.window.page_processing.lbl_sh_tool_status.setText(f"Status: SH -> Grid completed ({out_file.name}).")

        self._run_in_thread("all", _target, "RUNNING SH -> GRID TOOL")

    def _grid_to_sh_template_gfc(self, source_path: Path, label: str, cfg_local: Config) -> Path | None:
        if source_path.suffix.lower() == ".gfc" and source_path.exists():
            return source_path
        target_ym = self._ym_from_date(str(label))
        gfc_dir = Path(str(getattr(cfg_local.path, "GFC", "") or ""))
        if not target_ym or not gfc_dir.exists():
            return None
        for candidate in sorted(gfc_dir.glob("*.gfc")):
            if extract_ym_from_gfc(str(candidate)) == target_ym:
                return candidate
        return None

    def _write_grid_to_sh_gfc(self, template: Path, target: Path, c_arr: np.ndarray, s_arr: np.ndarray, lmax: int) -> None:
        tmp = target.with_suffix(target.suffix + ".tmp")
        with template.open("r", encoding="utf-8", errors="ignore") as fin, tmp.open("w", encoding="utf-8", newline="\n") as fout:
            for raw in fin:
                line = raw.rstrip("\r\n")
                parts = line.split()
                token = parts[0] if parts else ""
                key = token.lower()
                if (key.startswith("gfc") or key in {"grcof", "grcof2"}) and len(parts) >= 5:
                    try:
                        degree = int(parts[1])
                        order = int(parts[2])
                    except ValueError:
                        fout.write(line + "\n")
                        continue
                    if 0 <= order <= degree <= int(lmax):
                        rest = parts[5:]
                        fout.write(
                            f"{token} {degree:4d} {order:4d} "
                            f"{float(c_arr[degree, order]): .12E} "
                            f"{float(s_arr[degree, order]): .12E}"
                        )
                        if rest:
                            fout.write(" " + " ".join(rest))
                        fout.write("\n")
                    else:
                        fout.write(line + "\n")
                    continue
                stripped = line.strip()
                if stripped.lower().startswith("max_degree"):
                    prefix = line[: len(line) - len(line.lstrip())]
                    fout.write(f"{prefix}max_degree               {int(lmax)}\n")
                else:
                    fout.write(line + "\n")
        tmp.replace(target)

    def on_tool_grid_to_sh(self):
        self.pull_ui_to_host()
        self.window.page_processing.lbl_sh_tool_status.setText("Status: running Grid -> SH analysis...")

        def _target():
            source_path = self._resolve_tool_grid_source()
            stack_data = self.host.get_stack_data(str(source_path), active_var=self.window.page_preview.cmb_data_var.currentText())
            grid3d = np.asarray(stack_data.get("ewh"), dtype=float)
            lon_vec = np.asarray(stack_data.get("lon"), dtype=float).ravel()
            lat_vec = np.asarray(stack_data.get("lat"), dtype=float).ravel()
            if grid3d.ndim == 2:
                grid3d = grid3d[:, :, None]
            grid3d = ensure_latlon_order(grid3d, lon_vec, lat_vec, target_order="lon_lat")
            if grid3d.ndim != 3 or grid3d.shape[0] != lon_vec.size or grid3d.shape[1] != lat_vec.size:
                raise ValueError("Preview grid stack must be shaped [nLon x nLat x Nt] with matching lon/lat vectors.")

            time_index = int(max(0, min(grid3d.shape[2] - 1, self.window.page_preview.slider_time_index.value())))
            cfg_dict = self.collect_config_dict(copy.deepcopy(getattr(self.host.cfg, "_raw", {}) or {}))
            cfg_local = Config(cfg_dict)
            lmax_requested = int(getattr(cfg_local.inversion, "Lmax", 60))
            lmax = int(max(1, min(lmax_requested, lat_vec.size - 1, max(1, (lon_vec.size - 1) // 2))))
            c_arr, s_arr = ewh_analysis(
                grid3d[:, :, time_index],
                lmax,
                lon_vec,
                lat_vec,
                unit=str(getattr(cfg_local.grid, "unit", "mmEWH")),
            )
            _, time_labels = self.host._resolve_time(stack_data.get("t"), grid3d.shape[2], stack_data.get("meta", {}))
            label = time_labels[time_index] if time_index < len(time_labels) else f"{time_index + 1:03d}"

            out_dir = self._tool_output_dir("grid_sh")
            out_file = out_dir / (
                f"grid_sh_{self._safe_name(source_path.stem, 'stack')}_{self._safe_name(label, 'frame')}_L{int(lmax)}.mat"
            )
            self.host._safe_savemat(
                str(out_file),
                {
                    "C": np.asarray(c_arr, dtype=float),
                    "S": np.asarray(s_arr, dtype=float),
                    "lon": lon_vec,
                    "lat": lat_vec,
                    "Lmax": int(lmax),
                    "Lmax_requested": int(lmax_requested),
                    "time_index": int(time_index),
                    "time_label": str(label),
                    "source_file": str(source_path),
                },
            )
            template = self._grid_to_sh_template_gfc(source_path, str(label), cfg_local)
            gfc_file = None
            if template is not None:
                gfc_file = out_file.with_suffix(".gfc")
                self._write_grid_to_sh_gfc(template, gfc_file, np.asarray(c_arr, dtype=float), np.asarray(s_arr, dtype=float), int(lmax))
            self.signals.log.emit(f"[TOOL][GRID2SH] source={source_path} frame={time_index} Lmax={lmax}/{lmax_requested}", "stdout")
            self.signals.log.emit(f"[OUTPUT] {out_file}", "stdout")
            if gfc_file is not None:
                self.signals.log.emit(f"[OUTPUT] {gfc_file}", "stdout")
                self.window.page_processing.lbl_sh_tool_status.setText(f"Status: Grid -> SH completed ({out_file.name}, {gfc_file.name}).")
            else:
                self.window.page_processing.lbl_sh_tool_status.setText(f"Status: Grid -> SH completed ({out_file.name}; no GFC template found).")

        self._run_in_thread("all", _target, "RUNNING GRID -> SH TOOL")

    def on_use_preview_stack_for_leakage(self):
        src = self.window.page_preview.edit_dataset_source.text().strip()
        if not src:
            self._show_warning("Leakage", "Preview dataset source is empty.")
            return
        self.window.page_leakage.edit_lrc_input.setText(self._native_path(src))
        self.window.page_leakage.lbl_linkage_status.setText("Status: leakage input synced from Preview dataset.")
        self.on_log(f"[LINK] Leakage input <- Preview: {src}", "stdout")
        self.window.refresh_translations()

    def on_use_basin_stack_for_leakage(self):
        src = self.window.page_basin.edit_data_file.text().strip()
        if not src:
            self._show_warning("Leakage", "Basin source stack is empty.")
            return
        self.window.page_leakage.edit_lrc_input.setText(self._native_path(src))
        boundary = self.window.page_basin.edit_boundary_file.text().strip()
        if boundary:
            self.window.page_leakage.edit_regional_boundary.setText(self._native_path(boundary))
        self.window.page_leakage.lbl_linkage_status.setText("Status: leakage input synced from Basin page.")
        self.on_log(f"[LINK] Leakage input <- Basin: {src}", "stdout")
        self.window.refresh_translations()

    def _load_leakage_preview_manifest(self) -> dict:
        bundle = getattr(self.host, "_last_leakage_bundle", None)
        manifest_path = ""
        if isinstance(bundle, dict):
            manifest_path = str(bundle.get("preview_manifest", "") or "")
        if not manifest_path:
            return {}
        path = Path(manifest_path)
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _set_leakage_preview_image(self, path_text: str, caption: str = "") -> None:
        page = self.window.page_leakage
        page.preview_image.clear()
        if not path_text:
            page.lbl_preview_status.setText(caption or "尚未生成结果。运行完成后可在 Preview 页查看完整地图和时序结果。")
            return
        path = Path(path_text)
        if path.exists():
            page.lbl_preview_status.setText(caption or f"当前结果：{path.name}。点击按钮可在 Preview 页打开。")
        else:
            page.lbl_preview_status.setText(caption or "结果索引已更新，但目标文件尚不可用。")

    def on_refresh_leakage_preview(self):
        manifest = self._load_leakage_preview_manifest()
        page = self.window.page_leakage
        if not manifest:
            self._set_leakage_preview_image("", "尚未生成结果。本页仅保留结果入口，地图渲染请转到 Preview 页。")
            return

        preview = manifest.get("preview", {})
        figures = preview.get("figures", {}) or {}
        default_key = str(preview.get("default_figure", "representative_map"))
        selected_key = str(page.cmb_preview_figure.currentData() or default_key)
        figure_path = str(figures.get(selected_key) or figures.get(default_key) or next(iter(figures.values()), ""))
        caption = f"当前结果：{manifest.get('method', '校正结果')} | {selected_key}。点击按钮可在 Preview 页查看。"
        self._set_leakage_preview_image(figure_path, caption)

        labels = list(preview.get("time_labels", []) or [])
        blocker = QSignalBlocker(page.cmb_preview_time)
        page.cmb_preview_time.clear()
        page.cmb_preview_time.addItem("全部时次", "all")
        for idx, label in enumerate(labels):
            page.cmb_preview_time.addItem(str(label), idx)
        del blocker

        regions = list(preview.get("regions", []) or ["主区域"])
        blocker = QSignalBlocker(page.cmb_preview_region)
        page.cmb_preview_region.clear()
        for idx, region_name in enumerate(regions):
            page.cmb_preview_region.addItem(str(region_name), idx)
        del blocker


    def on_open_leakage_preview_asset(self):
        manifest = self._load_leakage_preview_manifest()
        if not manifest:
            self._show_warning("Leakage", "No leakage result bundle is available yet.")
            return
        preview = manifest.get("preview", {})
        layer_key = str(self.window.page_leakage.cmb_preview_layer.currentData() or preview.get("default_layer", "corrected"))
        layer_path = str((preview.get("layers", {}) or {}).get(layer_key, "") or "")
        if not layer_path:
            self._show_warning("Leakage", f"Preview layer '{layer_key}' is not available.")
            return
        self.window.set_active_page("preview")
        self.window.page_preview.edit_dataset_source.setText(layer_path)
        self.on_load_stack_info()
        if self.window.page_leakage.cmb_preview_time.currentData() not in (None, "all"):
            try:
                idx = int(self.window.page_leakage.cmb_preview_time.currentData())
                self.window.page_preview.slider_time_index.setValue(idx)
            except Exception:
                pass
        self.on_render_preview()

    def on_open_leakage_preview_corrected(self):
        manifest = self._load_leakage_preview_manifest()
        if not manifest:
            self._show_warning("Leakage", "No leakage result bundle is available yet.")
            return
        preview = manifest.get("preview", {})
        corrected_path = str((preview.get("layers", {}) or {}).get("corrected", "") or "")
        if not corrected_path:
            self._show_warning("Leakage", "Corrected stack is not available in the current bundle.")
            return
        self.window.set_active_page("preview")
        self.window.page_preview.edit_dataset_source.setText(corrected_path)
        self.on_load_stack_info()
        self.on_render_preview()

    def on_leakage_strategy_changed(self, *_args):
        page = self.window.page_leakage
        family = str(page.cmb_strategy_family.currentData() or "global_regularized")
        strategy = str(page.cmb_correction_strategy.currentData() or "auto")
        operator_text = (page.lbl_operator_value.text() or page.edit_operator_autodetect.text() or "").lower()
        gaussian_like = "gaussian" in operator_text
        is_regional = family == "regional"
        is_coastal = family == "global_coastal"
        is_regularized = family == "global_regularized"
        is_official = family == "official"
        allowed_by_family = {
            "regional": {"auto", "basin_scale_factor", "forward_modeling"},
            "global_coastal": {"auto", "global_coastal_gaussian", "global_regularized"},
            "global_regularized": {"auto", "global_regularized"},
            "official": {"auto", "official_land_scaling", "official_ocean_native", "official_mascon_native"},
        }
        allowed = allowed_by_family.get(family, {"auto"})
        if strategy not in allowed:
            blocker = QSignalBlocker(page.cmb_correction_strategy)
            self._set_combo_value(page.cmb_correction_strategy, "auto")
            del blocker
            strategy = "auto"

        if is_regional:
            self._set_combo_value(page.cmb_scope, "regional")
            hint = "区域模式用于流域/湖泊等局地分析，需要提供区域边界。"
        elif is_coastal:
            self._set_combo_value(page.cmb_scope, "global")
            if gaussian_like:
                hint = "全球海岸线模式仅适用于标准 Gaussian 输入。"
            else:
                hint = "当前不是 Gaussian 输入，系统将自动转为全球恢复模式。"
        elif is_regularized:
            self._set_combo_value(page.cmb_scope, "global")
            hint = "全球恢复模式适用于 DDK/FAN/P4M6 等全球格网。"
        else:
            self._set_combo_value(page.cmb_scope, "global")
            hint = "官方/原生模式不重复做球谐泄漏校正。"

        page.lbl_method_hint.setText(hint)
        if hasattr(page, "row_regional_boundary"):
            page.row_regional_boundary.setVisible(is_regional)
        page.cmb_reference_mode.setVisible(not is_official)
        page.cmb_scene_override.setVisible(is_regional)
        page.cmb_official_mode.setVisible(is_official)
        page.params_common_panel.setVisible(not is_official)
        page.params_regional_panel.setVisible(is_regional)
        page.params_coastal_panel.setVisible(is_coastal)
        page.params_regularized_panel.setVisible(is_regularized)
        page.advanced_section.setVisible(True)


    def _read_mask_from_stack_file(self, stack_path: str, lon_vec: np.ndarray, lat_vec: np.ndarray) -> np.ndarray | None:
        path = str(stack_path or "").strip()
        if not path.lower().endswith(".mat"):
            return None
        try:
            payload = loadmat(path, variable_names=["mask"], squeeze_me=True, struct_as_record=False)
        except Exception:
            return None
        if "mask" not in payload:
            return None
        mask = np.asarray(payload.get("mask"), dtype=bool)
        target_shape = (int(np.asarray(lon_vec).size), int(np.asarray(lat_vec).size))
        if mask.shape == target_shape:
            return mask
        if mask.T.shape == target_shape:
            return mask.T
        return None

    def _build_basin_spatial_context(self, require_boundary: bool = True) -> dict:
        stack_path = self.window.page_basin.edit_data_file.text().strip() or self.window.page_preview.edit_dataset_source.text().strip()
        if not stack_path:
            raise ValueError("No stack input set. Please set Basin source stack or Preview dataset.")
        stack_data = self.host.get_stack_data(stack_path)
        grid3d = np.asarray(stack_data.get("ewh"), dtype=float)
        if grid3d.ndim == 2:
            grid3d = grid3d[:, :, None]
        lon_vec = np.asarray(stack_data.get("lon"), dtype=float).squeeze()
        lat_vec = np.asarray(stack_data.get("lat"), dtype=float).squeeze()
        t_arr = stack_data.get("t")
        meta = stack_data.get("meta", {}) if isinstance(stack_data, dict) else {}
        nt = int(grid3d.shape[2])
        t_years, labels = self.host._resolve_time(t_arr, nt, meta=meta)
        boundary_path = self.window.page_basin.edit_boundary_file.text().strip() or self.window.page_data_paths.edit_boundary_path.text().strip()
        stack_mask = self._read_mask_from_stack_file(stack_path, lon_vec, lat_vec)
        if not boundary_path and require_boundary and stack_mask is None:
            raise ValueError("No boundary file configured.")
        basin_obj = None
        basin_name = "stack mask"
        resolved_boundary = ""
        if boundary_path:
            resolved_boundary = self._resolve_basin_boundary_file(boundary_path)
            boundaries = basin_read_boundary(resolved_boundary, name_field=self._basin_name_field())
            if not boundaries:
                raise ValueError("No basin polygon found in boundary file.")
            selected_name = self._preview_basin_name()
            if selected_name:
                filtered = [b for b in boundaries if str(getattr(b, "name", "")).strip().lower() == selected_name.lower()]
                if filtered:
                    boundaries = filtered
            basin_obj = boundaries[0]
            basin_name = str(getattr(basin_obj, "name", "basin")).strip() or "basin"
            mask = basin_make_mask(basin_obj, lon_vec, lat_vec)
        elif stack_mask is not None:
            mask = stack_mask
        else:
            if require_boundary:
                raise ValueError("No boundary file configured.")
            mask = np.ones((lon_vec.size, lat_vec.size), dtype=bool)
            basin_name = "full grid"
        if int(np.count_nonzero(mask)) <= 0:
            raise ValueError("Computed basin mask is empty on current grid.")
        return {
            "stack_path": stack_path,
            "boundary_path": resolved_boundary,
            "basin_name": basin_name,
            "basin": basin_obj,
            "grid3d": grid3d,
            "lon_vec": lon_vec,
            "lat_vec": lat_vec,
            "t_arr": t_arr,
            "meta": meta,
            "labels": labels,
            "t_years": np.asarray(t_years, dtype=float),
            "mask": np.asarray(mask, dtype=bool),
        }

    def _build_series_tool_context(self) -> dict:
        ctx = self._build_basin_spatial_context()
        grid3d = np.asarray(ctx["grid3d"], dtype=float)
        lon_vec = np.asarray(ctx["lon_vec"], dtype=float).squeeze()
        lat_vec = np.asarray(ctx["lat_vec"], dtype=float).squeeze()
        mask = np.asarray(ctx["mask"], dtype=bool)
        nt = int(grid3d.shape[2])
        ts = np.full(nt, np.nan, dtype=float)
        for i in range(nt):
            ts[i] = float(basin_compute_weighted_mean(grid3d[:, :, i], mask, lon_vec, lat_vec))
        ctx["series"] = ts
        return ctx

    def on_refresh_basin_preview(self, show_errors: bool = True, context: dict | None = None):
        page = self.window.page_basin
        try:
            ctx = context or self._build_basin_spatial_context(require_boundary=False)
            grid3d = np.asarray(ctx["grid3d"], dtype=float)
            time_idx = 0
            if grid3d.ndim >= 3 and hasattr(page, "slider_basin_time_index"):
                time_idx = max(0, min(int(page.slider_basin_time_index.value()), int(grid3d.shape[2]) - 1))
            grid2d = np.asarray(grid3d[:, :, time_idx] if grid3d.ndim >= 3 else grid3d, dtype=float)
            self._sync_basin_time_slice_label()
            lon = np.asarray(ctx["lon_vec"], dtype=float).squeeze()
            lat = np.asarray(ctx["lat_vec"], dtype=float).squeeze()
            mask = np.asarray(ctx.get("mask"), dtype=bool) if ctx.get("mask") is not None else None

            lon_plot = lon.copy()
            grid_plot = grid2d.copy()
            mask_plot = mask.copy() if mask is not None else None
            if lon_plot.size and np.nanmax(lon_plot) > 180.0:
                lon_plot = ((lon_plot + 180.0) % 360.0) - 180.0
                order = np.argsort(lon_plot)
                lon_plot = lon_plot[order]
                grid_plot = grid_plot[order, :]
                if mask_plot is not None:
                    mask_plot = mask_plot[order, :]
            if lat.size:
                lat_order = np.argsort(lat)
                lat_plot = lat[lat_order]
                grid_plot = grid_plot[:, lat_order]
                if mask_plot is not None:
                    mask_plot = mask_plot[:, lat_order]
            else:
                lat_plot = lat

            if self._basin_preview_canvas is None or self._basin_preview_figure is None:
                self._mount_basin_preview_canvas()
            fig = self._basin_preview_figure
            fig.clear()
            ax = fig.add_subplot(111)
            self._basin_preview_ax = ax
            ax.set_facecolor("#eef4f8")

            full_extent = [
                float(np.nanmin(lon_plot)),
                float(np.nanmax(lon_plot)),
                float(np.nanmin(lat_plot)),
                float(np.nanmax(lat_plot)),
            ]
            xlim = [full_extent[0], full_extent[1]]
            ylim = [full_extent[2], full_extent[3]]
            bbox_source = ""
            basin = ctx.get("basin")
            parts = getattr(basin, "parts", []) or []
            if not parts and basin is not None:
                lon_b = np.asarray(getattr(basin, "lon", []), dtype=float)
                lat_b = np.asarray(getattr(basin, "lat", []), dtype=float)
                if lon_b.size and lat_b.size:
                    parts = [np.column_stack((lon_b, lat_b))]
            finite_boundary = []
            for part in parts:
                arr = np.asarray(part, dtype=float)
                if arr.ndim == 2 and arr.shape[0] >= 2:
                    finite_boundary.append(arr[np.all(np.isfinite(arr[:, :2]), axis=1), :2])
            if finite_boundary:
                merged = np.vstack([arr for arr in finite_boundary if arr.size])
                if merged.size:
                    xlim = [float(np.nanmin(merged[:, 0])), float(np.nanmax(merged[:, 0]))]
                    ylim = [float(np.nanmin(merged[:, 1])), float(np.nanmax(merged[:, 1]))]
                    bbox_source = "boundary"
            elif mask_plot is not None and np.any(mask_plot):
                idx_lon, idx_lat = np.where(mask_plot)
                if idx_lon.size and idx_lat.size:
                    xlim = [float(np.nanmin(lon_plot[idx_lon])), float(np.nanmax(lon_plot[idx_lon]))]
                    ylim = [float(np.nanmin(lat_plot[idx_lat])), float(np.nanmax(lat_plot[idx_lat]))]
                    bbox_source = "mask"

            if bbox_source:
                lon_span = max(1.0, xlim[1] - xlim[0])
                lat_span = max(1.0, ylim[1] - ylim[0])
                pad_lon = max(2.0, lon_span * 0.45)
                pad_lat = max(2.0, lat_span * 0.45)
                xlim = [max(full_extent[0], xlim[0] - pad_lon), min(full_extent[1], xlim[1] + pad_lon)]
                ylim = [max(full_extent[2], ylim[0] - pad_lat), min(full_extent[3], ylim[1] + pad_lat)]
                if (xlim[1] - xlim[0]) < 8.0:
                    center = 0.5 * (xlim[0] + xlim[1])
                    xlim = [max(full_extent[0], center - 4.0), min(full_extent[1], center + 4.0)]
                if (ylim[1] - ylim[0]) < 8.0:
                    center = 0.5 * (ylim[0] + ylim[1])
                    ylim = [max(full_extent[2], center - 4.0), min(full_extent[3], center + 4.0)]

            lon_roi = (lon_plot >= xlim[0]) & (lon_plot <= xlim[1])
            lat_roi = (lat_plot >= ylim[0]) & (lat_plot <= ylim[1])
            roi = grid_plot[np.ix_(lon_roi, lat_roi)] if np.any(lon_roi) and np.any(lat_roi) else grid_plot
            finite = roi[np.isfinite(roi)]
            if finite.size:
                q = float(np.nanpercentile(np.abs(finite), 98))
                vlim = q if q > 0 else float(np.nanmax(np.abs(finite)) or 1.0)
                im = ax.imshow(grid_plot.T, extent=full_extent, origin="lower", cmap="RdBu_r", vmin=-vlim, vmax=vlim, aspect="auto")
                cbar = fig.colorbar(im, ax=ax, shrink=0.82, pad=0.02)
                cbar.ax.tick_params(labelsize=7)
            if mask_plot is not None:
                mask_img = np.where(mask_plot, 1.0, np.nan)
                ax.imshow(mask_img.T, extent=full_extent, origin="lower", cmap="Blues", alpha=0.38, aspect="auto")
            for part in parts[:8]:
                arr = np.asarray(part, dtype=float)
                if arr.ndim == 2 and arr.shape[0] >= 2:
                    ax.plot(arr[:, 0], arr[:, 1], color="#005db5", linewidth=1.4)
            label = ""
            labels = ctx.get("labels")
            if labels is None:
                labels = []
            if 0 <= time_idx < len(labels):
                label = f" | {labels[time_idx]}"
            ax.set_title(f"{ctx['basin_name']} | {Path(ctx['stack_path']).name}{label}", fontsize=10, loc="left")
            ax.set_xlabel("Longitude")
            ax.set_ylabel("Latitude")
            ax.set_xlim(xlim)
            ax.set_ylim(ylim)
            ax.grid(True, color="#d8e3eb", linewidth=0.6)
            ax.tick_params(labelsize=8)
            fig.tight_layout()

            out_dir = Path(getattr(self.host.cfg.path, "OUTPUT", ROOT_DIR / "output")) / "local" / "gui_review"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / "basin_live_preview.png"
            fig.savefig(str(out_file), dpi=140)
            self._basin_preview_canvas.draw_idle()
            page.lbl_basin_preview_status.setText(
                f"Preview: {ctx['basin_name']} | slice {time_idx + 1} | mask cells={int(np.count_nonzero(mask)) if mask is not None else 0}"
            )
            self.on_log(f"[BASIN] Preview rendered: {out_file}", "stdout")
        except Exception as exc:
            if hasattr(page, "lbl_basin_preview_status"):
                page.lbl_basin_preview_status.setText(f"Preview failed: {exc}")
            if show_errors:
                self._show_error("Basin Preview", str(exc))

    def on_tool_grid_to_series(self):
        self.pull_ui_to_host()
        self.window.page_basin.lbl_series_tool_status.setText("Status: running Grid -> Series...")

        def _target():
            ctx = self._build_series_tool_context()
            out_dir = self._tool_output_dir("series")
            safe_basin = self._safe_name(ctx["basin_name"], "basin")
            safe_src = self._safe_name(Path(ctx["stack_path"]).stem, "stack")
            csv_file = out_dir / f"series_{safe_src}_{safe_basin}.csv"
            lines = ["time,value"]
            for label, value in zip(ctx["labels"], ctx["series"]):
                lines.append(f"{label},{float(value):.9f}")
            self.host._safe_write_text(str(csv_file), lines)
            mat_file = out_dir / f"series_{safe_src}_{safe_basin}.mat"
            self.host._safe_savemat(
                str(mat_file),
                {
                    "time": np.asarray(ctx["labels"], dtype=object),
                    "t_years": np.asarray(ctx["t_years"], dtype=float),
                    "series": np.asarray(ctx["series"], dtype=float),
                    "basin_name": ctx["basin_name"],
                    "stack_file": ctx["stack_path"],
                    "boundary_file": ctx["boundary_path"],
                },
            )
            self.signals.log.emit(f"[TOOL][GRID2SERIES] basin={ctx['basin_name']}", "stdout")
            self.signals.log.emit(f"[OUTPUT] {csv_file}", "stdout")
            self.signals.log.emit(f"[OUTPUT] {mat_file}", "stdout")
            self.window.page_basin.lbl_series_tool_status.setText(
                f"Status: Grid -> Series completed ({safe_basin}, {len(ctx['series'])} samples)."
            )

        self._run_in_thread("all", _target, "RUNNING GRID -> SERIES TOOL")

    def on_tool_harmonic_fit(self):
        self.pull_ui_to_host()
        self.window.page_basin.lbl_series_tool_status.setText("Status: running harmonic analysis...")

        def _target():
            ctx = self._build_series_tool_context()
            stats = basin_fit_seasonal_trend(np.asarray(ctx["t_years"], dtype=float), np.asarray(ctx["series"], dtype=float))
            out_dir = self._tool_output_dir("harmonic")
            safe_basin = self._safe_name(ctx["basin_name"], "basin")
            safe_src = self._safe_name(Path(ctx["stack_path"]).stem, "stack")
            out_txt = out_dir / f"harmonic_{safe_src}_{safe_basin}.txt"
            lines = [
                "metric,value",
                f"trend,{float(stats.get('trend', np.nan)):.9f}",
                f"amp_ann,{float(stats.get('amp_ann', np.nan)):.9f}",
                f"phs_ann,{float(stats.get('phs_ann', np.nan)):.9f}",
                f"amp_semi,{float(stats.get('amp_semi', np.nan)):.9f}",
                f"const,{float(stats.get('const', np.nan)):.9f}",
            ]
            self.host._safe_write_text(str(out_txt), lines)
            out_mat = out_dir / f"harmonic_{safe_src}_{safe_basin}.mat"
            self.host._safe_savemat(
                str(out_mat),
                {
                    "stats": {
                        "trend": float(stats.get("trend", np.nan)),
                        "amp_ann": float(stats.get("amp_ann", np.nan)),
                        "phs_ann": float(stats.get("phs_ann", np.nan)),
                        "amp_semi": float(stats.get("amp_semi", np.nan)),
                        "const": float(stats.get("const", np.nan)),
                    },
                    "time": np.asarray(ctx["labels"], dtype=object),
                    "t_years": np.asarray(ctx["t_years"], dtype=float),
                    "series": np.asarray(ctx["series"], dtype=float),
                    "basin_name": ctx["basin_name"],
                    "stack_file": ctx["stack_path"],
                },
            )
            self.signals.log.emit(f"[TOOL][HARMONIC] basin={ctx['basin_name']}", "stdout")
            self.signals.log.emit(f"[OUTPUT] {out_txt}", "stdout")
            self.signals.log.emit(f"[OUTPUT] {out_mat}", "stdout")
            self.window.page_basin.lbl_series_tool_status.setText(
                f"Status: harmonic analysis completed (trend={float(stats.get('trend', np.nan)):.4f})."
            )

        self._run_in_thread("all", _target, "RUNNING HARMONIC TOOL")

    def on_load_stack_info(self):
        page = self.window.page_preview
        path = page.edit_dataset_source.text().strip()
        if not path:
            self._show_warning("Preview", "Please select a stack file first.")
            return
        try:
            info = self.host.load_stack_info(path)
            shape = tuple(info.get("shape") or ())
            meta = info.get("meta", {}) or {}
            active_var = str(meta.get("active_var") or "ewh").strip() or "ewh"
            var_names = [str(name).strip() for name in meta.get("data_var_names", []) if str(name).strip()]
            if not var_names:
                var_names = [active_var]
            current = page.cmb_data_var.currentText().strip()
            page.cmb_data_var.blockSignals(True)
            page.cmb_data_var.clear()
            page.cmb_data_var.addItems(var_names)
            target_var = active_var if active_var in var_names else (current if current in var_names else var_names[0])
            page.cmb_data_var.setCurrentText(target_var)
            page.cmb_data_var.blockSignals(False)
            nt = int(shape[2]) if len(shape) >= 3 else 1
            page.slider_time_index.blockSignals(True)
            page.slider_time_index.setRange(0, max(0, nt - 1))
            page.slider_time_index.setValue(0)
            page.slider_time_index.blockSignals(False)
            self._sync_preview_time_label(0)
            _t_years, time_labels = self.host._resolve_time(info.get("t"), nt, meta=meta)
            time_summary = ""
            if time_labels:
                first_label = str(time_labels[0])
                last_label = str(time_labels[min(len(time_labels), nt) - 1])
                time_summary = f" | time={first_label}" if first_label == last_label else f" | time={first_label}..{last_label}"
            page.lbl_stack_info.setText(f"{shape[0]} x {shape[1]} x {nt} | active={target_var}{time_summary}")
            self._apply_preview_bbox_from_info(info)
            self.window.refresh_translations()
            self.on_log(f"[PREVIEW] Stack loaded: {path}", "stdout")
        except Exception as exc:
            page.lbl_stack_info.setText(f"Load failed: {exc}")
            self._show_error("Preview", str(exc))

    def on_preview_index_changed(self, idx: int):
        self._sync_preview_time_label(idx)
        self.window.refresh_translations()

    def _sync_preview_time_label(self, idx: int | None = None) -> None:
        page = self.window.page_preview
        idx = int(page.slider_time_index.value() if idx is None else idx)
        total = int(page.slider_time_index.maximum()) + 1
        label = self._preview_time_text(idx)
        suffix = f" | {label}" if label else ""
        page.lbl_time_index.setText(f"{idx + 1} / {max(1, total)}{suffix}")

    def _preview_time_text(self, idx: int) -> str:
        label = ""
        with contextlib.suppress(Exception):
            info = self.host._stack_info_cache or {}
            if info.get("path") == self.window.page_preview.edit_dataset_source.text().strip():
                shape = tuple(info.get("shape") or ())
                nt = int(shape[2]) if len(shape) >= 3 else 1
                _t_years, labels = self.host._resolve_time(info.get("t"), nt, meta=info.get("meta", {}) or {})
                if labels and 0 <= idx < len(labels):
                    label = str(labels[idx])
        if label:
            return label
        with contextlib.suppress(Exception):
            cache = self.host._stack_cache or {}
            shape = np.asarray(cache.get("ewh")).shape
            nt = int(shape[2]) if len(shape) >= 3 else 1
            _t_years, labels = self.host._resolve_time(cache.get("t"), nt, meta=cache.get("meta", {}) or {})
            if labels and 0 <= idx < len(labels):
                label = str(labels[idx])
        return label

    def on_preview_var_changed(self):
        current = self.window.page_preview.lbl_stack_info.text().strip()
        active = self.window.page_preview.cmb_data_var.currentText().strip() or "ewh"
        if "|" in current and "x" in current:
            base = current.split("| active=", 1)[0].strip()
            self.window.page_preview.lbl_stack_info.setText(f"{base} | active={active}")
        elif current and current != "Stack not loaded.":
            self.window.page_preview.lbl_stack_info.setText(f"{current} | active={active}")
        else:
            self.window.page_preview.lbl_stack_info.setText(f"Active variable: {active}")
        self.window.refresh_translations()

    def on_preview_region_mode_changed(self, checked: bool):
        page = self.window.page_preview
        enabled = not bool(checked)
        for widget in (
            page.edit_region_lon_min,
            page.edit_region_lon_max,
            page.edit_region_lat_min,
            page.edit_region_lat_max,
        ):
            widget.setEnabled(enabled)
        if checked:
            detected = False
            with contextlib.suppress(Exception):
                path = page.edit_dataset_source.text().strip()
                if path:
                    info = self.host.load_stack_info(path)
                    detected = self._apply_preview_bbox_from_info(info)
            if not detected:
                for widget in (
                    page.edit_region_lon_min,
                    page.edit_region_lon_max,
                    page.edit_region_lat_min,
                    page.edit_region_lat_max,
                ):
                    widget.setEnabled(True)

    def on_toggle_preview_status(self):
        page = self.window.page_preview
        visible = page.card_status.isVisible()
        page.card_status.setVisible(not visible)
        if visible:
            page.btn_toggle_status.setText("Show Status")
        else:
            page.btn_toggle_status.setText("Hide Status")
        self._apply_preview_main_splitter()
        QTimer.singleShot(0, self.on_preview_home)
        self.window.refresh_translations()

    def on_toggle_preview_sidebar(self):
        page = self.window.page_preview
        visible = page.sidebar_panel.isVisible()
        page.sidebar_panel.setVisible(not visible)
        if visible:
            page.btn_toggle_sidebar.setText("Show Controls")
            page.page_splitter.setSizes([0, max(1180, self.window.width() - 280)])
        else:
            page.btn_toggle_sidebar.setText("Hide Controls")
            self.window._apply_responsive_layout(force=True)
        self._apply_preview_main_splitter()
        QTimer.singleShot(0, self.on_preview_home)
        self.window.refresh_translations()

    def on_toggle_preview_tools(self):
        page = self.window.page_preview
        visible = page.plot_toolbar_host.isVisible()
        page.plot_toolbar_host.setVisible(not visible)
        self._sync_preview_tools_button()

    def _sync_preview_tools_button(self):
        page = self.window.page_preview
        tools_visible = bool(page.plot_toolbar_host.isVisible())
        page.btn_toggle_tools.setText("Hide Tools" if tools_visible else "Tools")
        page.plot_toolbar_host.updateGeometry()
        page.plot_card.updateGeometry()
        self.window.refresh_translations()

    def _sync_preview_overlay_controls(self, *_args):
        page = self.window.page_preview
        boundary_enabled = bool(page.chk_layer_boundaries.isChecked())
        custom_enabled = bool(page.chk_layer_rivers.isChecked())
        for widget in (page.edit_boundary_overlay, page.btn_boundary_overlay_browse):
            widget.setEnabled(boundary_enabled)
        for widget in (page.edit_custom_overlay, page.btn_custom_overlay_browse):
            widget.setEnabled(custom_enabled)

    def _record_preview_view(self, x_data, y_data):
        try:
            x = np.asarray(x_data, dtype=float)
            y = np.asarray(y_data, dtype=float)
            mask = np.isfinite(x) & np.isfinite(y)
            if not np.any(mask):
                self._preview_full_view = None
                return
            xmin = float(np.nanmin(x[mask]))
            xmax = float(np.nanmax(x[mask]))
            ymin = float(np.nanmin(y[mask]))
            ymax = float(np.nanmax(y[mask]))
            xr = max(1.0e-9, xmax - xmin)
            yr = max(1.0e-9, ymax - ymin)
            self._preview_full_view = (
                xmin - 0.03 * xr,
                xmax + 0.03 * xr,
                ymin - 0.08 * yr,
                ymax + 0.04 * yr,
            )
        except Exception:
            self._preview_full_view = None

    def _record_preview_projection_world_view(self, proj, lon0=0.0, lat0=0.0, lat1=30.0, lat2=60.0, x_data=None, y_data=None):
        try:
            lon_eps = 1.0e-3
            lon_edge = np.linspace(-180.0 + lon_eps, 180.0 - lon_eps, 721)
            if proj in {"Mercator", "Miller"}:
                lat_min, lat_max = -85.0, 85.0
            else:
                lat_min, lat_max = -90.0, 90.0
            lat_edge = np.linspace(lat_min, lat_max, 361)
            boundary_parts = [
                (lon_edge, np.full_like(lon_edge, lat_min)),
                (lon_edge, np.full_like(lon_edge, lat_max)),
                (np.full_like(lat_edge, -180.0 + lon_eps), lat_edge),
                (np.full_like(lat_edge, 180.0 - lon_eps), lat_edge),
            ]
            x_parts = []
            y_parts = []
            for lons, lats in boundary_parts:
                xb, yb = self._project(proj, lons, lats, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
                xb = apply_proj_scale(xb, self._proj_scale, self._proj_x0)
                x_parts.append(np.asarray(xb, dtype=float).ravel())
                y_parts.append(np.asarray(yb, dtype=float).ravel())
            if x_data is not None and y_data is not None:
                x_parts.append(np.asarray(x_data, dtype=float).ravel())
                y_parts.append(np.asarray(y_data, dtype=float).ravel())
            x = np.concatenate(x_parts)
            y = np.concatenate(y_parts)
            mask = np.isfinite(x) & np.isfinite(y)
            if not np.any(mask):
                self._preview_full_view = None
                return
            xmin = float(np.nanmin(x[mask]))
            xmax = float(np.nanmax(x[mask]))
            ymin = float(np.nanmin(y[mask]))
            ymax = float(np.nanmax(y[mask]))
            xr = max(1.0e-9, xmax - xmin)
            yr = max(1.0e-9, ymax - ymin)
            self._preview_full_view = (
                xmin - 0.05 * xr,
                xmax + 0.05 * xr,
                ymin - 0.20 * yr,
                ymax + 0.08 * yr,
            )
        except Exception:
            self._preview_full_view = None

    @staticmethod
    def _extend_lat_to_poles(lon, lat, grid):
        try:
            lon_arr = np.asarray(lon, dtype=float).squeeze()
            lat_arr = np.asarray(lat, dtype=float).squeeze()
            grid_arr = np.asarray(grid, dtype=float)
            if lon_arr.ndim != 1 or lat_arr.ndim != 1 or grid_arr.ndim != 2:
                return lon_arr, lat_arr, grid_arr
            if grid_arr.shape != (lon_arr.size, lat_arr.size):
                return lon_arr, lat_arr, grid_arr
            lat_min = float(np.nanmin(lat_arr))
            lat_max = float(np.nanmax(lat_arr))
            if lat_min > -89.999:
                lat_arr = np.concatenate(([-90.0], lat_arr))
                grid_arr = np.concatenate((grid_arr[:, :1], grid_arr), axis=1)
            if lat_max < 89.999:
                lat_arr = np.concatenate((lat_arr, [90.0]))
                grid_arr = np.concatenate((grid_arr, grid_arr[:, -1:]), axis=1)
            return lon_arr, lat_arr, grid_arr
        except Exception:
            return lon, lat, grid

    def on_preview_home(self):
        if self._ax is None or self._preview_full_view is None:
            return
        xmin, xmax, ymin, ymax = self._preview_full_view
        self._ax.set_xlim(xmin, xmax)
        self._ax.set_ylim(ymin, ymax)
        self._canvas.draw_idle()

    def _apply_preview_main_splitter(self):
        page = self.window.page_preview
        total_h = max(page.main.height(), page.main_splitter.height(), 500)
        if page.card_status.isVisible():
            status_h = 64
            plot_h = max(400, total_h - status_h - 6)
            page.main_splitter.setSizes([plot_h, status_h])
        else:
            page.main_splitter.setSizes([max(460, total_h - 6), 0])

    def _apply_preview_bbox_from_info(self, info: dict):
        lon = np.asarray(info.get("lon"), dtype=float).squeeze()
        lat = np.asarray(info.get("lat"), dtype=float).squeeze()
        if lon.size == 0 or lat.size == 0:
            return False
        page = self.window.page_preview
        page.edit_region_lon_min.setText(f"{float(np.nanmin(lon)):.6g}")
        page.edit_region_lon_max.setText(f"{float(np.nanmax(lon)):.6g}")
        page.edit_region_lat_min.setText(f"{float(np.nanmin(lat)):.6g}")
        page.edit_region_lat_max.setText(f"{float(np.nanmax(lat)):.6g}")
        return True

    @staticmethod
    def _is_global_preview_extent(lon: np.ndarray, lat: np.ndarray, lon0: float = 0.0) -> bool:
        try:
            lon_arr = np.asarray(lon, dtype=float).squeeze()
            lat_arr = np.asarray(lat, dtype=float).squeeze()
            if lon_arr.size == 0 or lat_arr.size == 0:
                return False
            lon_span = float(np.nanmax(wrap_delta_lon(lon_arr, lon0)) - np.nanmin(wrap_delta_lon(lon_arr, lon0)))
            lat_min = float(np.nanmin(lat_arr))
            lat_max = float(np.nanmax(lat_arr))
            return lon_span >= 330.0 and lat_min <= -75.0 and lat_max >= 75.0
        except Exception:
            return False

    @staticmethod
    def _resolve_overlay_file(value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        path = Path(raw)
        if path.is_file():
            return str(path)
        if path.is_dir():
            for pattern in ("*.shp", "*.bln", "*.txt"):
                matches = sorted(path.glob(pattern))
                if matches:
                    return str(matches[0])
        return ""

    def on_render_preview(self):
        try:
            start = time.perf_counter()
            path = self.window.page_preview.edit_dataset_source.text().strip()
            active_var = self.window.page_preview.cmb_data_var.currentText().strip() or None
            idx = int(self.window.page_preview.slider_time_index.value())
            frame = self.host.get_stack_frame(path, idx, active_var=active_var)
            grid = np.asarray(frame["grid"], dtype=float)
            lon = np.asarray(frame["lon"], dtype=float).squeeze()
            lat = np.asarray(frame["lat"], dtype=float).squeeze()
            if grid.shape[0] != lon.size and grid.shape[1] == lon.size:
                grid = grid.T
            proj = self._projection_key(self.window.page_preview.cmb_projection.currentText())
            lon_mode = infer_plot_lon_mode(lon)
            bbox = None
            if self.window.page_preview.chk_auto_region.isChecked():
                bbox = (
                    float(np.nanmin(lon)),
                    float(np.nanmax(lon)),
                    float(np.nanmin(lat)),
                    float(np.nanmax(lat)),
                )
                self.window.page_preview.edit_region_lon_min.setText(f"{bbox[0]:.6g}")
                self.window.page_preview.edit_region_lon_max.setText(f"{bbox[1]:.6g}")
                self.window.page_preview.edit_region_lat_min.setText(f"{bbox[2]:.6g}")
                self.window.page_preview.edit_region_lat_max.setText(f"{bbox[3]:.6g}")
            else:
                lon_min_raw = self._safe_float(self.window.page_preview.edit_region_lon_min.text(), -180.0)
                lon_max_raw = self._safe_float(self.window.page_preview.edit_region_lon_max.text(), 180.0)
                lat_min = self._safe_float(self.window.page_preview.edit_region_lat_min.text(), -90.0)
                lat_max = self._safe_float(self.window.page_preview.edit_region_lat_max.text(), 90.0)
                lon_min = lon_min_raw
                lon_max = lon_max_raw
                if lon_mode == "0_360":
                    lon_min = lon_min_raw % 360.0
                    lon_max = lon_max_raw % 360.0
                bbox = (lon_min, lon_max, min(lat_min, lat_max), max(lat_min, lat_max))

            self._figure.clear()
            self._ax = self._figure.add_subplot(111)
            cmap = self.window.page_preview.cmb_cmap.currentText().strip() or "RdBu_r"
            cmin = parse_float(self.window.page_preview.edit_cmin.text())
            cmax = parse_float(self.window.page_preview.edit_cmax.text())
            if bbox is not None:
                lon_min, lon_max, lat_min, lat_max = bbox
                lat_min, lat_max = min(lat_min, lat_max), max(lat_min, lat_max)
                span = lon_max - lon_min
                full_lon = (
                    abs(span) >= 359.0
                    or (abs(lon_min) < 1.0e-6 and abs(lon_max - 360.0) < 1.0e-6)
                    or (abs(lon_min + 180.0) < 1.0e-6 and abs(lon_max - 180.0) < 1.0e-6)
                )
                lon_eval = normalize_lon_for_plot(lon, lon_mode=lon_mode)
                if full_lon:
                    lon_mask = np.ones_like(lon, dtype=bool)
                elif lon_min <= lon_max:
                    lon_mask = (lon_eval >= lon_min) & (lon_eval <= lon_max)
                else:
                    lon_mask = (lon_eval >= lon_min) | (lon_eval <= lon_max)
                lat_mask = (lat >= lat_min) & (lat <= lat_max)
                if not np.any(lon_mask) or not np.any(lat_mask):
                    raise ValueError("Selected region does not overlap the dataset grid.")
                lon = lon[lon_mask]
                lat = lat[lat_mask]
                grid = grid[np.ix_(lon_mask, lat_mask)]
            try:
                first = float(lon[0])
                last = float(lon[-1])
                same_meridian = abs(((last - first + 180.0) % 360.0) - 180.0) <= 1.0e-6
                if same_meridian and lon.size > 2 and grid.shape[0] == lon.size:
                    lon = lon[:-1]
                    grid = grid[:-1, :]
            except Exception:
                pass
            lon2d, lat2d = np.meshgrid(lon, lat)
            grid_plot = grid.T if grid.shape == (lon.size, lat.size) else grid
            if grid_plot.size == 0 or lon2d.size == 0 or lat2d.size == 0:
                raise ValueError("Selected region produced an empty plot.")

            coast_path = self._resolve_coastline_path()
            show_coast = self.window.page_preview.chk_layer_coastlines.isChecked() and bool(coast_path)
            show_grid = self.window.page_preview.chk_layer_grid.isChecked()
            show_boundaries = self.window.page_preview.chk_layer_boundaries.isChecked()
            show_data = self.window.page_preview.chk_layer_data.isChecked()
            boundary_path = self._resolve_boundary_overlay_path()
            custom_overlay_path = self._resolve_custom_overlay_path()
            show_custom_overlay = self.window.page_preview.chk_layer_rivers.isChecked() and bool(custom_overlay_path)
            im = None

            if proj == "PlateCarree":
                if show_data:
                    im = self._ax.pcolormesh(lon2d, lat2d, grid_plot, shading="auto", cmap=cmap, vmin=cmin, vmax=cmax)
                self._ax.set_xlabel("Longitude")
                self._ax.set_ylabel("Latitude")
                self._ax.set_aspect("equal", adjustable="box")
                self._record_preview_view(lon2d, lat2d)
                if show_grid:
                    draw_graticule(self._ax, proj="PlateCarree", lon0=0.0, lat0=0.0, lat1=30.0, lat2=60.0, plot_lon_mode=lon_mode, apply_proj_scale_cb=lambda x: x, plot_line_cb=plot_line, projector_cb=self._project)
                if show_coast:
                    draw_coastlines(
                        self._ax,
                        coast_path=coast_path,
                        proj="PlateCarree",
                        lon0=0.0,
                        lat0=0.0,
                        lat1=30.0,
                        lat2=60.0,
                        bbox=bbox,
                        normalize_lon_for_plot_cb=lambda arr: normalize_lon_for_plot(arr, lon_mode=lon_mode),
                        split_dateline_cb=lambda lons, lats, lon0=0.0: split_dateline(lons, lats, wrap_delta_lon, lon0=lon0),
                        split_plot_lon_segments_cb=lambda lons, lats, plate_carree=False: split_plot_lon_segments(lons, lats, split_dateline, lon0=0.0, plate_carree=plate_carree, lon_mode=lon_mode),
                        apply_proj_scale_cb=lambda xx: xx,
                        plot_line_cb=plot_line,
                        projector_cb=self._project,
                    )
                if show_boundaries and boundary_path and Path(boundary_path).exists():
                    boundaries = read_boundary_file(boundary_path)
                    draw_boundaries(
                        self._ax,
                        boundaries,
                        proj="PlateCarree",
                        lon0=0.0,
                        lat0=0.0,
                        lat1=30.0,
                        lat2=60.0,
                        bbox=bbox,
                        normalize_lon_for_plot_cb=lambda arr: normalize_lon_for_plot(arr, lon_mode=lon_mode),
                        split_dateline_cb=lambda lons, lats, lon0=0.0: split_dateline(lons, lats, wrap_delta_lon, lon0=lon0),
                        split_plot_lon_segments_cb=lambda lons, lats, plate_carree=False: split_plot_lon_segments(lons, lats, split_dateline, lon0=0.0, plate_carree=plate_carree, lon_mode=lon_mode),
                        apply_proj_scale_cb=lambda xx: xx,
                        plot_line_cb=plot_line,
                        projector_cb=self._project,
                    )
                if show_custom_overlay and Path(custom_overlay_path).exists():
                    boundaries = read_boundary_file(custom_overlay_path)
                    draw_boundaries(
                        self._ax,
                        boundaries,
                        proj="PlateCarree",
                        lon0=0.0,
                        lat0=0.0,
                        lat1=30.0,
                        lat2=60.0,
                        bbox=bbox,
                        normalize_lon_for_plot_cb=lambda arr: normalize_lon_for_plot(arr, lon_mode=lon_mode),
                        split_dateline_cb=lambda lons, lats, lon0=0.0: split_dateline(lons, lats, wrap_delta_lon, lon0=lon0),
                        split_plot_lon_segments_cb=lambda lons, lats, plate_carree=False: split_plot_lon_segments(lons, lats, split_dateline, lon0=0.0, plate_carree=plate_carree, lon_mode=lon_mode),
                        apply_proj_scale_cb=lambda xx: xx,
                        plot_line_cb=plot_line,
                        projector_cb=self._project,
                    )
            else:
                lon0, lat0 = get_proj_center(lon, lat)
                lat1, lat2 = get_conic_parallels(float(np.nanmin(lat)), float(np.nanmax(lat)))
                lon_sort_key = wrap_delta_lon(lon, lon0)
                lon_order = np.argsort(lon_sort_key)
                lon = lon[lon_order]
                grid = grid[lon_order, :]
                regional_view = not self._is_global_preview_extent(lon, lat, lon0=lon0)
                if not regional_view:
                    lon, lat, grid = self._extend_lat_to_poles(lon, lat, grid)
                lon2d, lat2d = np.meshgrid(lon, lat)
                grid_plot = grid.T if grid.shape == (lon.size, lat.size) else grid
                x, y = self._project(proj, lon2d, lat2d, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
                x, y, self._proj_scale, self._proj_x0 = scale_projection(x, y, target_ratio=2.0)
                if show_data:
                    im = self._ax.pcolormesh(x, y, grid_plot, shading="auto", cmap=cmap, vmin=cmin, vmax=cmax)
                self._ax.set_axis_off()
                if not regional_view:
                    self._record_preview_projection_world_view(proj, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2, x_data=x, y_data=y)
                else:
                    self._record_preview_view(x, y)
                if show_grid:
                    draw_graticule(self._ax, proj=proj, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2, plot_lon_mode=lon_mode, apply_proj_scale_cb=lambda xx: apply_proj_scale(xx, self._proj_scale, self._proj_x0), plot_line_cb=plot_line, projector_cb=self._project)
                if show_coast:
                    draw_coastlines(
                        self._ax,
                        coast_path=coast_path,
                        proj=proj,
                        lon0=lon0,
                        lat0=lat0,
                        lat1=lat1,
                        lat2=lat2,
                        bbox=bbox,
                        normalize_lon_for_plot_cb=lambda arr: normalize_lon_for_plot(arr, lon_mode=lon_mode),
                        split_dateline_cb=lambda lons, lats, lon0=0.0: split_dateline(lons, lats, wrap_delta_lon, lon0=lon0),
                        split_plot_lon_segments_cb=lambda lons, lats, plate_carree=False: split_plot_lon_segments(lons, lats, split_dateline, lon0=lon0, plate_carree=plate_carree, lon_mode=lon_mode),
                        apply_proj_scale_cb=lambda xx: apply_proj_scale(xx, self._proj_scale, self._proj_x0),
                        plot_line_cb=plot_line,
                        projector_cb=self._project,
                    )
                if show_boundaries and boundary_path and Path(boundary_path).exists():
                    boundaries = read_boundary_file(boundary_path)
                    draw_boundaries(
                        self._ax,
                        boundaries,
                        proj=proj,
                        lon0=lon0,
                        lat0=lat0,
                        lat1=lat1,
                        lat2=lat2,
                        bbox=bbox,
                        normalize_lon_for_plot_cb=lambda arr: normalize_lon_for_plot(arr, lon_mode=lon_mode),
                        split_dateline_cb=lambda lons, lats, lon0=0.0: split_dateline(lons, lats, wrap_delta_lon, lon0=lon0),
                        split_plot_lon_segments_cb=lambda lons, lats, plate_carree=False: split_plot_lon_segments(lons, lats, split_dateline, lon0=lon0, plate_carree=plate_carree, lon_mode=lon_mode),
                        apply_proj_scale_cb=lambda xx: apply_proj_scale(xx, self._proj_scale, self._proj_x0),
                        plot_line_cb=plot_line,
                        projector_cb=self._project,
                    )
                if show_custom_overlay and Path(custom_overlay_path).exists():
                    boundaries = read_boundary_file(custom_overlay_path)
                    draw_boundaries(
                        self._ax,
                        boundaries,
                        proj=proj,
                        lon0=lon0,
                        lat0=lat0,
                        lat1=lat1,
                        lat2=lat2,
                        bbox=bbox,
                        normalize_lon_for_plot_cb=lambda arr: normalize_lon_for_plot(arr, lon_mode=lon_mode),
                        split_dateline_cb=lambda lons, lats, lon0=0.0: split_dateline(lons, lats, wrap_delta_lon, lon0=lon0),
                        split_plot_lon_segments_cb=lambda lons, lats, plate_carree=False: split_plot_lon_segments(lons, lats, split_dateline, lon0=lon0, plate_carree=plate_carree, lon_mode=lon_mode),
                        apply_proj_scale_cb=lambda xx: apply_proj_scale(xx, self._proj_scale, self._proj_x0),
                        plot_line_cb=plot_line,
                        projector_cb=self._project,
                    )
            if im is not None:
                self._figure.colorbar(im, ax=self._ax, shrink=0.84, pad=0.02)
            self._figure.subplots_adjust(left=0.018, right=0.985, top=0.965, bottom=0.03)
            self._apply_preview_main_splitter()
            self.on_preview_home()
            self._preview_pick_state = {
                "x": np.asarray(lon2d if proj == "PlateCarree" else x, dtype=float),
                "y": np.asarray(lat2d if proj == "PlateCarree" else y, dtype=float),
                "lon": np.asarray(lon2d, dtype=float),
                "lat": np.asarray(lat2d, dtype=float),
                "grid": np.asarray(grid_plot, dtype=float),
            }
            self._canvas.draw_idle()
            active_var_name = frame["meta"].get("active_var", "ewh")
            self.window.page_preview.lbl_dataset.setText(f"{Path(path).name} | {active_var_name}")
            finite = np.isfinite(grid)
            if np.any(finite):
                self.window.page_preview.lbl_grid_value.setText(f"{float(np.nanmean(grid[finite])):.3f}")
            else:
                self.window.page_preview.lbl_grid_value.setText("NaN")
            self.window.page_preview.lbl_engine_latency.setText(f"{(time.perf_counter() - start) * 1000.0:.1f} ms")
            time_text = self._preview_time_text(idx)
            title_suffix = f"slice {idx + 1}" + (f" | {time_text}" if time_text else "")
            self.window.page_preview.canvas_preview_title.setText(f"{self.window.page_preview.cmb_projection.currentText()}: {title_suffix}")
            self._apply_preview_main_splitter()
            self.on_log(f"[PREVIEW] Rendered {Path(path).name} [{active_var_name}] idx={idx}", "stdout")
        except Exception as exc:
            self._show_error("Preview", str(exc))

    def on_preview_canvas_event(self, event):
        state = getattr(self, "_preview_pick_state", None)
        if state is None or event is None or event.xdata is None or event.ydata is None:
            return
        x = state["x"].ravel()
        y = state["y"].ravel()
        lon = state["lon"].ravel()
        lat = state["lat"].ravel()
        grid = state["grid"].ravel()
        mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(lon) & np.isfinite(lat)
        if not np.any(mask):
            return
        dx = x[mask] - float(event.xdata)
        dy = y[mask] - float(event.ydata)
        idx = int(np.argmin(dx * dx + dy * dy))
        lon_val = float(lon[mask][idx])
        lat_val = float(lat[mask][idx])
        grid_val = float(grid[mask][idx]) if np.isfinite(grid[mask][idx]) else float("nan")
        ns = "N" if lat_val >= 0 else "S"
        ew = "E" if lon_val >= 0 else "W"
        self.window.page_preview.lbl_cursor_position.setText(f"{abs(lat_val):.2f} {ns}, {abs(lon_val):.2f} {ew}")
        self.window.page_preview.lbl_grid_value.setText(f"{grid_val:.3f}" if np.isfinite(grid_val) else "NaN")

    def on_export_figure(self):
        try:
            self.on_log("[PREVIEW] Export requested", "stdout")
            if self._figure is None or not self._figure.axes:
                self._show_info("Export Figure", "No rendered figure is available. Render Preview first.")
                return
            current_w = int(max(1200, round(self._figure.get_figwidth() * self._figure.dpi), self._canvas.width() * 2))
            current_h = int(max(800, round(self._figure.get_figheight() * self._figure.dpi), self._canvas.height() * 2))
            dialog = QDialog(self.window)
            dialog.setWindowTitle("Export Figure")
            dialog.setModal(True)
            dialog.resize(620, 250)
            layout = QVBoxLayout(dialog)
            form = QFormLayout()
            form.setContentsMargins(0, 0, 0, 0)
            form.setSpacing(10)

            default_path = ROOT_DIR / "output" / "local" / "preview.png"
            row_path = QWidget()
            row_path_layout = QHBoxLayout(row_path)
            row_path_layout.setContentsMargins(0, 0, 0, 0)
            row_path_layout.setSpacing(8)
            path_edit = QLineEdit(str(default_path))
            browse_btn = QPushButton("Browse")
            browse_btn.setObjectName("GhostButton")
            row_path_layout.addWidget(path_edit, 1)
            row_path_layout.addWidget(browse_btn)
            form.addRow("Output File", row_path)

            fmt_combo = QComboBox()
            fmt_combo.addItems(["png", "pdf", "svg"])
            form.addRow("Format", fmt_combo)

            dpi_combo = QComboBox()
            dpi_combo.addItems(["120", "180", "240", "300", "600"])
            dpi_combo.setCurrentText("300")
            form.addRow("DPI", dpi_combo)

            width_spin = QSpinBox()
            width_spin.setRange(640, 10000)
            width_spin.setValue(current_w)
            height_spin = QSpinBox()
            height_spin.setRange(400, 10000)
            height_spin.setValue(current_h)
            size_row = QWidget()
            size_row_layout = QHBoxLayout(size_row)
            size_row_layout.setContentsMargins(0, 0, 0, 0)
            size_row_layout.setSpacing(8)
            size_row_layout.addWidget(width_spin)
            size_row_layout.addWidget(QLabel("x"))
            size_row_layout.addWidget(height_spin)
            size_row_layout.addWidget(QLabel("px"))
            size_row_layout.addStretch(1)
            form.addRow("Size", size_row)

            layout.addLayout(form)
            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            layout.addWidget(buttons)

            def choose_path():
                start = path_edit.text().strip() or str(default_path)
                path, _ = QFileDialog.getSaveFileName(
                    dialog,
                    "Export Figure",
                    start,
                    "PNG (*.png);;PDF (*.pdf);;SVG (*.svg)",
                )
                if path:
                    path_edit.setText(path)

            browse_btn.clicked.connect(choose_path)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)

            if dialog.exec() != QDialog.Accepted:
                self.on_log("[PREVIEW] Export canceled", "stdout")
                return

            out_path = Path(path_edit.text().strip() or str(default_path))
            fmt = fmt_combo.currentText().strip().lower() or out_path.suffix.lstrip(".").lower() or "png"
            if out_path.suffix.lower() != f".{fmt}":
                out_path = out_path.with_suffix(f".{fmt}")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            dpi = int(dpi_combo.currentText())
            width_px = int(width_spin.value())
            height_px = int(height_spin.value())

            old_size = tuple(self._figure.get_size_inches())
            old_dpi = float(self._figure.dpi)
            try:
                self._figure.set_dpi(dpi)
                self._figure.set_size_inches(width_px / dpi, height_px / dpi, forward=True)
                self._figure.savefig(str(out_path), dpi=dpi, format=fmt)
                self._show_info("Export Figure", f"Saved to:\n{out_path}")
                self.on_log(f"[PREVIEW] Figure exported: {out_path} ({fmt}, {width_px}x{height_px}, {dpi} dpi)", "stdout")
            finally:
                self._figure.set_dpi(old_dpi)
                self._figure.set_size_inches(old_size[0], old_size[1], forward=True)
                self._canvas.draw_idle()
        except Exception as exc:
            self._show_error("Export Figure", str(exc))
            self.on_log(f"[PREVIEW] Export failed: {exc}", "stderr")

    def _resolve_coastline_path(self) -> str:
        if DEFAULT_COASTLINE_PATH.exists():
            return str(DEFAULT_COASTLINE_PATH)
        return ""

    def _resolve_boundary_overlay_path(self) -> str:
        page = self.window.page_preview
        explicit = self._resolve_overlay_file(page.edit_boundary_overlay.text())
        if explicit:
            return explicit
        candidates = [
            self.window.page_basin.edit_boundary_file.text().strip(),
            self.window.page_data_paths.edit_boundary_path.text().strip(),
        ]
        for candidate in candidates:
            if not candidate:
                continue
            resolved = self._resolve_overlay_file(candidate)
            if resolved:
                return resolved
        return ""

    def _resolve_custom_overlay_path(self) -> str:
        return self._resolve_overlay_file(self.window.page_preview.edit_custom_overlay.text())

    def _run_in_thread(self, scope: str, target, status_text: str):
        if self.host._active_scope:
            self._show_warning("Run", f"Another task is already running: {self.host._active_scope}")
            return
        pause_event, stop_event = self.host._get_scope_events(scope)
        pause_event.clear()
        stop_event.clear()
        self.host._active_scope = scope
        self._top_status_text = status_text
        self._pending_terminal_status = None
        self._pending_terminal_scope = scope
        self.window.set_top_status(status_text, "warning")
        self.window.set_run_active(True, text="Preparing...", indeterminate=True)
        self.window.set_console_visible(True)
        self.window.page_monitor.lbl_pipeline_status.setText(status_text)
        self.window.page_dashboard.lbl_dashboard_status.setText(status_text)
        self.window.page_dashboard.lbl_dashboard_stage.setText("Preparing execution environment and validating configuration.")
        self.window.page_dashboard.lbl_active_run_name.setText(status_text)
        self.window.page_dashboard.lbl_active_task.setText("Preparing execution environment and validating configuration.")
        self.window.page_dashboard.lbl_active_counts.setText("0 / 0")
        self._sync_monitor_context()
        self.window.refresh_translations()

        def worker():
            err = None
            old_stdout, old_stderr = sys.stdout, sys.stderr
            sys.stdout = SignalLogWriter(self.signals, "stdout")
            sys.stderr = SignalLogWriter(self.signals, "stderr")
            try:
                target()
            except Exception as exc:
                err = exc
            finally:
                with contextlib.suppress(Exception):
                    sys.stdout.flush()
                with contextlib.suppress(Exception):
                    sys.stderr.flush()
                sys.stdout, sys.stderr = old_stdout, old_stderr
                self.host._active_scope = ""
                self._last_completed_scope = scope
                for events in self.host._scope_events.values():
                    events["pause"].clear()
                    events["stop"].clear()
                if err is not None:
                    self._pending_terminal_status = ("ERROR", "danger")
                    self.signals.status.emit("ERROR", "danger")
                    self.signals.message.emit("error", scope.title(), str(err))
                else:
                    self._pending_terminal_status = ("READY", "success")
                    self.signals.status.emit("READY", "success")

        t = threading.Thread(target=worker, daemon=True)
        self._threads[scope] = t
        t.start()

    def on_run_pipeline(self):
        self.pull_ui_to_host()
        pause_event, stop_event = self.host._get_scope_events("all")
        self.window.console_text.clear()
        self.window.filters_text.clear()
        self.window.alerts_text.clear()
        self.window.page_monitor.text_live_logs.clear()
        self.window.page_monitor.bar_overall_progress.setRange(0, 100)
        self.window.page_monitor.bar_overall_progress.setValue(0)
        self.window.page_monitor.lbl_overall_progress.setText("0/0")
        self.window.page_monitor.lbl_current_task.setText("Initializing pipeline")
        self.window.page_monitor.lbl_last_artifact.setText("Latest Artifact: waiting for pipeline outputs.")
        self.window.page_dashboard.lbl_preview_artifact.setText("Latest Artifact: waiting for pipeline outputs.")
        self.window.page_dashboard.lbl_dashboard_counts.setText("0 / 0")
        self.window.page_dashboard.bar_active_run.setValue(0)
        self._set_progress_active(self.window.page_dashboard.bar_active_run, False)
        self.window.page_dashboard.lbl_active_counts.setText("0 / 0")
        self._sync_monitor_context()

        def _progress(done, total, stage="", detail=""):
            detail_text = detail or f"{done}/{total}"
            pct = 0.0 if total <= 0 else (100.0 * float(done) / float(total))
            if "/" in detail_text:
                left, right = detail_text.split("/", 1)
                try:
                    stage_done = float(left.strip())
                    stage_total = float(right.strip())
                    if stage_total > 0:
                        pct = 100.0 * stage_done / stage_total
                except ValueError:
                    pass
            payload = f"{detail_text}::{stage}" if stage else detail_text
            self.signals.progress.emit("all", pct, payload)

        def _target():
            self.on_log("[PIPELINE] Starting full pipeline...", "stdout")
            run_pipeline(self.host.cfg, pause_event=pause_event, stop_event=stop_event, progress_cb=_progress)
            self.on_log("[PIPELINE] Full pipeline finished.", "stdout")

        self._run_in_thread("all", _target, "RUNNING PIPELINE")

    def on_run_basin(self):
        # The Basin page is a scoped analysis entrypoint; keep the hidden
        # pipeline auto-enable flag from disabling an explicit user run.
        self.window.page_basin.chk_basin_enable.setChecked(True)
        self.pull_ui_to_host()
        if not self.host.var_basin_data.get():
            self._show_warning("流域分析", "请先选择输入栈文件。")
            return
        if not self.host.var_basin_file.get():
            self._show_warning("流域分析", "请先选择流域边界文件。")
            return
        self._run_in_thread("basin", self.host.run_basin_analysis, "RUNNING BASIN")

    def on_run_leakage(self):
        self.pull_ui_to_host()
        if not self.host.var_lrc_input.get():
            self._show_warning("泄漏校正", "请先选择输入栈文件。")
            return
        family = self._combo_value(self.window.page_leakage.cmb_strategy_family).lower()
        if family == "regional" and not self.window.page_leakage.edit_regional_boundary.text().strip():
            self._set_combo_value(self.window.page_leakage.cmb_strategy_family, "global_regularized")
            self.on_leakage_strategy_changed()
            self.pull_ui_to_host()
            self.on_log("[LEAKAGE] 区域模式缺少边界文件，已自动切换为全球恢复模式。", "stderr")
        self._run_in_thread("leakage", self.host.run_leakage_correction, "RUNNING LEAKAGE")

    def on_pause_active(self):
        scope = self.host._active_scope or "all"
        self.on_pause_scope(scope)

    def on_pause_scope(self, scope: str):
        if scope not in self.host._scope_events:
            return
        pause_event = self.host._scope_events[scope]["pause"]
        if pause_event.is_set():
            pause_event.clear()
            self.window.set_top_status(self._top_status_text, "warning")
            self.window.set_run_active(True, text="Resuming...", indeterminate=True)
            self.window.set_pause_action_paused(False)
            self.window.page_dashboard.lbl_dashboard_status.setText(self._top_status_text)
            self.window.page_dashboard.lbl_dashboard_stage.setText("Resuming pipeline execution.")
            self.on_log(f"[RUN] Resumed {scope}", "stdout")
        else:
            pause_event.set()
            self.window.set_top_status("PAUSED", "warning")
            self.window.set_run_progress(-1.0, stage="Paused")
            self.window.set_pause_action_paused(True)
            self.window.page_dashboard.lbl_dashboard_status.setText("PAUSED")
            self.window.page_dashboard.lbl_dashboard_stage.setText("Pipeline execution is paused.")
            self.on_log(f"[RUN] Paused {scope}", "stdout")
        self.window.refresh_translations()

    def on_stop_active(self):
        scope = self.host._active_scope or "all"
        self.on_stop_scope(scope)

    def on_stop_scope(self, scope: str):
        if scope not in self.host._scope_events:
            return
        self.host._scope_events[scope]["stop"].set()
        self.window.set_top_status("STOP REQUESTED", "danger")
        self.window.set_run_progress(-1.0, stage="Stopping...")
        self.window.page_dashboard.lbl_dashboard_status.setText("STOP REQUESTED")
        self.window.page_dashboard.lbl_dashboard_stage.setText("Waiting for the running task to stop safely.")
        self.on_log(f"[RUN] Stop requested: {scope}", "stderr")
        self.window.refresh_translations()

    def on_reset_monitor(self):
        self.window.page_monitor.bar_overall_progress.setRange(0, 100)
        self.window.page_monitor.bar_overall_progress.setValue(0)
        self.window.page_monitor.bar_current_task.setRange(0, 100)
        self.window.page_monitor.bar_current_task.setValue(0)
        self.window.page_monitor.lbl_overall_progress.setText("0/0")
        self.window.page_monitor.lbl_current_task.setText("Idle")
        self.window.page_monitor.lbl_last_artifact.setText("Latest Artifact: not generated yet.")
        self.window.page_monitor.text_live_logs.clear()
        self.window.page_dashboard.lbl_preview_artifact.setText("Latest Artifact: not generated yet.")
        self.window.console_text.clear()
        self.window.filters_text.clear()
        self.window.alerts_text.clear()
        self.window.set_top_status("READY", "success")
        self.window.set_run_progress(0.0, detail="0/0", stage="Idle")
        self.window.top_progress_wrap.setVisible(False)
        self.window.set_run_active(False, text="Idle")
        self.window.page_dashboard.badge_summary_state.setText("Ready to Process")
        self.window.page_dashboard.badge_summary_state.setProperty("variant", "success")
        self.window.page_dashboard.badge_summary_state.style().unpolish(self.window.page_dashboard.badge_summary_state)
        self.window.page_dashboard.badge_summary_state.style().polish(self.window.page_dashboard.badge_summary_state)
        self._pending_terminal_status = None
        self._pending_terminal_scope = ""
        self._sync_dashboard_run_summary()
        self._sync_monitor_context()
        self.window.refresh_translations()

    def on_log(self, text: str, tag: str = "stdout"):
        self.window._append_console_line(text, tag=tag)
        self.window.page_monitor.text_live_logs.append(text)
        if text.startswith("[PIPELINE] Full pipeline finished."):
            self.window.page_monitor.lbl_last_artifact.setText("Latest Artifact: pipeline completed, outputs written to configured directories.")
            self.window.page_dashboard.lbl_preview_artifact.setText("Latest Artifact: pipeline completed, outputs written to configured directories.")
        elif text.startswith("[OUTPUT]"):
            self.window.page_monitor.lbl_last_artifact.setText(f"Latest Artifact: {text.replace('[OUTPUT]', '').strip()}")
            self.window.page_dashboard.lbl_preview_artifact.setText(f"Latest Artifact: {text.replace('[OUTPUT]', '').strip()}")
        elif text.startswith("[ERROR]") or text.startswith("[WARN]"):
            self.window.page_monitor.lbl_current_task.setText(text)
        self.window.refresh_translations()

    def on_message(self, level: str, title: str, text: str):
        self.on_log(f"[{str(level).upper()}] {title}: {text}", "stderr" if level == "error" else "stdout")
        if level == "error":
            self._show_error(title, text)
        elif level == "warning":
            self._show_warning(title, text)
        else:
            self._show_info(title, text)

    def on_progress(self, scope: str, pct: float, text: str):
        detail_text = text
        stage_override = ""
        if "::" in text:
            detail_text, stage_override = text.split("::", 1)
        target = self.window.page_monitor.bar_overall_progress if scope == "all" else self.window.page_monitor.bar_current_task
        label = self.window.page_monitor.lbl_overall_progress if scope == "all" else self.window.page_monitor.lbl_current_task
        if pct < 0:
            target.setRange(0, 0)
        else:
            target.setRange(0, 100)
            target.setValue(int(round(pct)))
        label.setText(detail_text if scope == "all" else (stage_override or detail_text))
        if scope == "all":
            self._last_overall_pct = pct
            self._last_overall_detail = detail_text
            stage_text = stage_override or ("Running monthly loop" if pct < 100.0 else "Finalizing outputs")
            self.window.set_run_progress(pct, detail=detail_text, stage=stage_text)
            self.window.page_dashboard.badge_summary_state.setText("Run in Progress")
            self.window.page_dashboard.badge_summary_state.setProperty("variant", "warning")
            self.window.page_dashboard.badge_summary_state.style().unpolish(self.window.page_dashboard.badge_summary_state)
            self.window.page_dashboard.badge_summary_state.style().polish(self.window.page_dashboard.badge_summary_state)
            self.window.page_dashboard.lbl_dashboard_status.setText("RUNNING")
            self.window.page_dashboard.lbl_dashboard_counts.setText(detail_text.replace("/", " / "))
            self.window.page_dashboard.lbl_dashboard_stage.setText(stage_text)
            self.window.page_dashboard.lbl_active_run_name.setText("Running pipeline")
            self.window.page_dashboard.lbl_active_counts.setText(detail_text.replace("/", " / "))
            self.window.page_dashboard.lbl_active_task.setText(stage_text)
            self.window.page_dashboard.bar_active_run.setValue(int(round(max(0.0, min(100.0, pct)))))
            self._set_progress_active(self.window.page_dashboard.bar_active_run, pct > 0.0)
            if pct >= 100.0:
                self.window.set_top_status("FINALIZING OUTPUTS", "warning")
                self.window.page_dashboard.lbl_dashboard_status.setText("FINALIZING")
        elif self.host._active_scope == scope:
            self._last_overall_pct = pct
            self._last_overall_detail = detail_text
            self.window.set_run_progress(pct, detail=detail_text, stage=stage_override or f"{scope.title()} task")
        self.window.refresh_translations()

    def on_status(self, text: str, variant: str):
        self._top_status_text = text
        self._pending_terminal_status = None
        self._pending_terminal_scope = ""
        self.window.set_top_status(text, variant)
        self.window.page_monitor.lbl_pipeline_status.setText(text)
        self.window.page_dashboard.lbl_dashboard_status.setText(text)
        if text == "READY":
            if getattr(self, "_last_completed_scope", "") == "leakage":
                self.on_refresh_leakage_preview()
            completed_scope = getattr(self, "_last_completed_scope", "")
            done_stage = "Download complete" if completed_scope == "download" else "Pipeline complete"
            done_message = "Download finished and local paths were refreshed." if completed_scope == "download" else "Pipeline finished and outputs are available."
            self.window.set_run_progress(100.0, detail=self._last_overall_detail or "0/0", stage=done_stage)
            self.window.page_dashboard.lbl_dashboard_stage.setText(done_message)
            self.window.page_dashboard.lbl_active_run_name.setText("Completed")
            self.window.page_dashboard.lbl_active_counts.setText((self._last_overall_detail or "0/0").replace("/", " / "))
            self.window.page_dashboard.lbl_active_task.setText(done_message)
            self._set_progress_active(self.window.page_dashboard.bar_active_run, True)
            self.window.page_dashboard.badge_summary_state.setText("Run Complete")
            self.window.page_dashboard.badge_summary_state.setProperty("variant", "success")
            self.window.page_dashboard.badge_summary_state.style().unpolish(self.window.page_dashboard.badge_summary_state)
            self.window.page_dashboard.badge_summary_state.style().polish(self.window.page_dashboard.badge_summary_state)
            self.window.page_monitor.lbl_last_artifact.setText("Latest Artifact: pipeline finished, inspect output/local for generated files.")
            self.window.page_dashboard.lbl_preview_artifact.setText("Latest Artifact: pipeline finished, inspect output/local for generated files.")
            QTimer.singleShot(1200, lambda: self.window.set_run_active(False, text="Idle"))
        elif text == "ERROR":
            self.window.set_run_progress(-1.0, detail=self._last_overall_detail or "0/0", stage="Failed")
            self.window.page_dashboard.lbl_dashboard_stage.setText("Run failed. Check Console or the Dashboard output preview for the error trace.")
            self.window.page_dashboard.lbl_active_counts.setText((self._last_overall_detail or "0/0").replace("/", " / "))
            self._set_progress_active(self.window.page_dashboard.bar_active_run, False)
            self.window.page_dashboard.badge_summary_state.setText("Run Failed")
            self.window.page_dashboard.badge_summary_state.setProperty("variant", "danger")
            self.window.page_dashboard.badge_summary_state.style().unpolish(self.window.page_dashboard.badge_summary_state)
            self.window.page_dashboard.badge_summary_state.style().polish(self.window.page_dashboard.badge_summary_state)
            QTimer.singleShot(1200, lambda: self.window.set_run_active(False, text="Idle"))
        self.window.refresh_translations()

    def _show_info(self, title: str, text: str):
        QMessageBox.information(self.window, self.window.translate_text(title), self.window.translate_text(text))

    def _show_warning(self, title: str, text: str):
        QMessageBox.warning(self.window, self.window.translate_text(title), self.window.translate_text(text))

    def _show_error(self, title: str, text: str):
        QMessageBox.critical(self.window, self.window.translate_text(title), self.window.translate_text(text))

    def _ym_from_date(self, text: str) -> str:
        text = str(text or "").strip()
        if len(text) >= 7 and text[4] == "-":
            return text[:7]
        return text

    def _date_from_ym(self, text: str) -> str:
        text = str(text or "").strip()
        if len(text) == 7 and text[4] == "-":
            return f"{text}-01"
        return text

    @staticmethod
    def _safe_float(text: str, default: float) -> float:
        try:
            return float(str(text).strip())
        except Exception:
            return float(default)

    @staticmethod
    def _projection_key(text: str) -> str:
        mapping = {
            "Robinson (Global)": "Robinson",
            "Plate Carree": "PlateCarree",
            "Orthographic": "Orthographic",
            "Mollweide": "Mollweide",
            "Mercator": "Mercator",
            "Miller": "Miller",
            "Sinusoidal": "Sinusoidal",
            "Equal Earth": "EqualEarth",
            "Winkel Tripel": "WinkelTripel",
            "Eckert IV": "EckertIV",
            "Azimuthal Equidistant": "AzimuthalEquidistant",
            "Stereographic": "Stereographic",
            "Lambert Conformal": "LambertConformal",
            "Albers Equal Area": "AlbersEqualArea",
        }
        return mapping.get(text, "PlateCarree")

    @staticmethod
    def _project(proj, lon, lat, lon0=0.0, lat0=0.0, lat1=30.0, lat2=60.0):
        if proj == "Robinson":
            return proj_robinson(lon, lat, lon0=lon0)
        if proj == "Mollweide":
            return proj_mollweide(lon, lat, lon0=lon0)
        if proj == "Mercator":
            return proj_mercator(lon, lat, lon0=lon0)
        if proj == "Miller":
            return proj_miller(lon, lat, lon0=lon0)
        if proj == "Sinusoidal":
            return proj_sinusoidal(lon, lat, lon0=lon0)
        if proj == "EqualEarth":
            return proj_equalearth(lon, lat, lon0=lon0)
        if proj == "WinkelTripel":
            return proj_winkeltripel(lon, lat, lon0=lon0)
        if proj == "EckertIV":
            return proj_eckert4(lon, lat, lon0=lon0)
        if proj == "Orthographic":
            return proj_orthographic(lon, lat, lon0=lon0, lat0=lat0)
        if proj == "AzimuthalEquidistant":
            return proj_aeqd(lon, lat, lon0=lon0, lat0=lat0)
        if proj == "Stereographic":
            return proj_stereographic(lon, lat, lon0=lon0, lat0=lat0)
        if proj == "LambertConformal":
            return proj_lambert_conformal(lon, lat, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
        if proj == "AlbersEqualArea":
            return proj_albers(lon, lat, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
        return lon, lat
