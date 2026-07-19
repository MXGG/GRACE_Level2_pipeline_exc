"""Adapters for moving data between Qt widgets and canonical config objects."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Callable, Optional

from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QSlider

from grace_pipeline.infra.config import Config, get_root_dir, load_config


class ValueProxy:
    """Uniform getter/setter bridge around Qt widgets."""

    def __init__(self, getter: Callable[[], Any], setter: Optional[Callable[[Any], None]] = None):
        self._getter = getter
        self._setter = setter

    def get(self):
        return self._getter()

    def set(self, value):
        if self._setter is not None:
            self._setter(value)


def proxy_line_edit(widget: Optional[QLineEdit]) -> Optional[ValueProxy]:
    if widget is None:
        return None
    return ValueProxy(widget.text, widget.setText)


def proxy_combo(widget: Optional[QComboBox]) -> Optional[ValueProxy]:
    if widget is None:
        return None
    return ValueProxy(widget.currentText, widget.setCurrentText)


def proxy_check(widget: Optional[QCheckBox]) -> Optional[ValueProxy]:
    if widget is None:
        return None
    return ValueProxy(widget.isChecked, widget.setChecked)


def proxy_slider(widget: Optional[QSlider]) -> Optional[ValueProxy]:
    if widget is None:
        return None
    return ValueProxy(widget.value, widget.setValue)


class QtConfigAdapter:
    """Load/save config files and synchronize config fields with page widgets."""

    def __init__(self, root_dir: Optional[str] = None):
        self.root_dir = str(Path(root_dir or get_root_dir()).resolve())

    def load(self, path: str) -> Config:
        return load_config(user_config=path, root_dir=self.root_dir)

    def save(self, config: Config, path: str):
        payload = copy.deepcopy(getattr(config, "_raw", {}))
        if not isinstance(payload, dict):
            payload = {}
        tmp = str(path) + ".tmp"
        Path(tmp).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, str(path))

    def sync_config_to_pages(self, pages: dict[str, Any], config: Config):
        self._sync_dashboard(pages.get("dashboard"), config)
        self._sync_data_paths(pages.get("data_paths"), config)
        self._sync_processing(pages.get("processing"), config)
        self._sync_leakage(pages.get("leakage"), config)
        self._sync_basin(pages.get("basin"), config)
        self._sync_preview(pages.get("preview"), config)

    def sync_pages_to_config(self, pages: dict[str, Any], config: Config) -> Config:
        self._collect_data_paths(pages.get("data_paths"), config)
        self._collect_processing(pages.get("processing"), config)
        self._collect_leakage(pages.get("leakage"), config)
        self._collect_basin(pages.get("basin"), config)
        self._collect_preview(pages.get("preview"), config)
        return config

    def _section(self, config: Config, name: str) -> dict[str, Any]:
        raw = getattr(config, "_raw", None)
        if not isinstance(raw, dict):
            raw = {}
            config._raw = raw
        section = raw.get(name)
        if not isinstance(section, dict):
            section = {}
            raw[name] = section
        return section

    @staticmethod
    def _safe_float(text: Any, default: float) -> float:
        try:
            return float(str(text).strip())
        except Exception:
            return float(default)

    @staticmethod
    def _safe_int(text: Any, default: int) -> int:
        try:
            return int(float(str(text).strip()))
        except Exception:
            return int(default)

    def _sync_dashboard(self, page, config: Config):
        if page is None:
            return
        title = Path(getattr(config.path, "OUTPUT", self.root_dir) or self.root_dir).name or "Untitled"
        if getattr(page, "project_name_label", None) is not None:
            page.project_name_label.setText(title)
        if getattr(page, "output_root_label", None) is not None:
            page.output_root_label.setText(getattr(config.path, "OUTPUT", ""))

    def _sync_data_paths(self, page, config: Config):
        if page is None:
            return
        if getattr(page, "gfc_dir_edit", None) is not None:
            page.gfc_dir_edit.setText(getattr(config.path, "GFC", ""))
        if getattr(page, "ddk_dir_edit", None) is not None:
            page.ddk_dir_edit.setText(getattr(config.path, "DDK", ""))
        if getattr(page, "output_root_edit", None) is not None:
            page.output_root_edit.setText(getattr(config.path, "OUTPUT", ""))
        if getattr(page, "logs_dir_edit", None) is not None:
            page.logs_dir_edit.setText(str(Path(getattr(config.path, "OUTPUT", self.root_dir)) / "logs"))
        if getattr(page, "aux_edit", None) is not None:
            page.aux_edit.setText(getattr(config.path, "AUX", ""))
        if getattr(page, "boundary_edit", None) is not None:
            page.boundary_edit.setText(getattr(config.path, "BOUNDARY", ""))
        if getattr(page, "low_degree_edit", None) is not None:
            lowdeg = getattr(config.inversion, "lowdeg", {}) or {}
            page.low_degree_edit.setText(str(lowdeg.get("files", {}).get("C20", "")) if isinstance(lowdeg, dict) else "")
        if getattr(page, "gia_edit", None) is not None:
            gia = getattr(config.inversion, "gia", {}) or {}
            page.gia_edit.setText(str(gia.get("file", "")) if isinstance(gia, dict) else "")
        if getattr(page, "mascon_ref_edit", None) is not None:
            ref = getattr(config, "reference", {}) or {}
            page.mascon_ref_edit.setText(str(ref.get("mascon_dir", "")) if isinstance(ref, dict) else "")

    def _collect_data_paths(self, page, config: Config):
        if page is None:
            return
        if getattr(page, "gfc_dir_edit", None) is not None:
            config.path.GFC = page.gfc_dir_edit.text().strip()
            self._section(config, "path")["GFC"] = config.path.GFC
        if getattr(page, "ddk_dir_edit", None) is not None:
            config.path.DDK = page.ddk_dir_edit.text().strip()
            self._section(config, "path")["DDK"] = config.path.DDK
        if getattr(page, "output_root_edit", None) is not None:
            config.path.OUTPUT = page.output_root_edit.text().strip()
            self._section(config, "path")["OUTPUT"] = config.path.OUTPUT
        if getattr(page, "aux_edit", None) is not None:
            config.path.AUX = page.aux_edit.text().strip()
            self._section(config, "path")["AUX"] = config.path.AUX
        if getattr(page, "boundary_edit", None) is not None:
            config.path.BOUNDARY = page.boundary_edit.text().strip()
            self._section(config, "path")["BOUNDARY"] = config.path.BOUNDARY
        if getattr(page, "remote_sync_toggle", None) is not None:
            self._section(config, "perf")["remote_sync"] = bool(page.remote_sync_toggle.isChecked())

    def _sync_processing(self, page, config: Config):
        if page is None:
            return
        if getattr(page, "start_date_edit", None) is not None:
            page.start_date_edit.setText(getattr(config.time, "start_ym", ""))
        if getattr(page, "end_date_edit", None) is not None:
            page.end_date_edit.setText(getattr(config.time, "end_ym", ""))
        if getattr(page, "step_days_edit", None) is not None:
            page.step_days_edit.setText(str(getattr(config.time, "step_days", 30)))
        if getattr(page, "resolution_edit", None) is not None:
            page.resolution_edit.setText(str(getattr(config.grid, "dlon", 1.0)))
        if getattr(page, "lat_min_edit", None) is not None:
            page.lat_min_edit.setText(str(getattr(config.grid, "lat", (-89.5, 89.5))[0]))
        if getattr(page, "lat_max_edit", None) is not None:
            page.lat_max_edit.setText(str(getattr(config.grid, "lat", (-89.5, 89.5))[1]))
        if getattr(page, "lon_min_edit", None) is not None:
            page.lon_min_edit.setText(str(getattr(config.grid, "lon", (-179.5, 179.5))[0]))
        if getattr(page, "lon_max_edit", None) is not None:
            page.lon_max_edit.setText(str(getattr(config.grid, "lon", (-179.5, 179.5))[1]))
        if getattr(page, "lmax_slider", None) is not None:
            page.lmax_slider.setValue(int(getattr(config.inversion, "Lmax", 60)))
        if getattr(page, "static_field_edit", None) is not None:
            lowdeg = getattr(config.inversion, "lowdeg", {}) or {}
            page.static_field_edit.setText(str(lowdeg.get("files", {}).get("C20", "")) if isinstance(lowdeg, dict) else "")
        if getattr(page, "gaussian_enable", None) is not None:
            page.gaussian_enable.setChecked(bool(getattr(config.filter.gaussian, "enable", False)))
        if getattr(page, "gaussian_radius_edit", None) is not None:
            page.gaussian_radius_edit.setText(str(getattr(config.filter.gaussian, "radius_km", 300.0)))
        if getattr(page, "p4m6_enable", None) is not None:
            page.p4m6_enable.setChecked(bool(getattr(config.filter.p4m6, "enable", False)))
        if getattr(page, "p4_deg_edit", None) is not None:
            page.p4_deg_edit.setText(str(getattr(config.filter.p4m6, "poly_deg", 4)))
        if getattr(page, "p4_m_edit", None) is not None:
            page.p4_m_edit.setText(str(getattr(config.filter.p4m6, "m_start", 6)))
        if getattr(page, "ddk_enable", None) is not None:
            page.ddk_enable.setChecked(bool(getattr(config.filter.ddk, "enable", False)))
        if getattr(page, "ddk_type_combo", None) is not None:
            page.ddk_type_combo.setCurrentText(getattr(config.filter.ddk, "type", "DDK4"))
        if getattr(page, "fan_enable", None) is not None:
            page.fan_enable.setChecked(bool(config.filter.fan.get("enable", False)))
        if getattr(page, "fan_r1_edit", None) is not None:
            page.fan_r1_edit.setText(str(config.filter.fan.get("radius1_km", 300.0)))
        if getattr(page, "fan_r2_edit", None) is not None:
            page.fan_r2_edit.setText(str(config.filter.fan.get("radius2_km", 300.0)))
        if getattr(page, "hsaf_enable", None) is not None:
            page.hsaf_enable.setChecked(bool(getattr(config.filter.hankel, "enable", False)))
        if getattr(page, "hsaf_variant_combo", None) is not None:
            page.hsaf_variant_combo.setCurrentText(getattr(config.filter.hankel, "variant", "global"))
        if getattr(page, "hsaf_input_combo", None) is not None:
            page.hsaf_input_combo.setCurrentText(getattr(config.filter, "pre_hankel_input", "P4M6"))
        params = getattr(config.filter.hankel, "params", {}) or {}
        if getattr(page, "hsaf_N_edit", None) is not None:
            page.hsaf_N_edit.setText(str(params.get("N", 30)))
        if getattr(page, "hsaf_P_edit", None) is not None:
            page.hsaf_P_edit.setText(str(params.get("P", 10)))
        if getattr(page, "hsaf_K_edit", None) is not None:
            page.hsaf_K_edit.setText(str(params.get("K", 6)))
        if getattr(page, "hsaf_J_edit", None) is not None:
            page.hsaf_J_edit.setText(str(params.get("J", 1)))
        if getattr(page, "hsaf_tol_edit", None) is not None:
            page.hsaf_tol_edit.setText(str(config.perf.get("hsaf_tol", 1e-7)))
        if getattr(page, "hsaf_iter_edit", None) is not None:
            page.hsaf_iter_edit.setText(str(config.perf.get("hsaf_iter", 500)))

    def _collect_processing(self, page, config: Config):
        if page is None:
            return
        if getattr(page, "start_date_edit", None) is not None:
            config.time.start_ym = page.start_date_edit.text().strip()
            self._section(config, "time")["start_ym"] = config.time.start_ym
        if getattr(page, "end_date_edit", None) is not None:
            config.time.end_ym = page.end_date_edit.text().strip()
            self._section(config, "time")["end_ym"] = config.time.end_ym
        if getattr(page, "step_days_edit", None) is not None:
            self._section(config, "time")["step_days"] = self._safe_int(page.step_days_edit.text(), 30)
        if getattr(page, "resolution_edit", None) is not None:
            d = self._safe_float(page.resolution_edit.text(), 1.0)
            config.grid.dlon = d
            config.grid.dlat = d
            self._section(config, "grid")["dlon"] = d
            self._section(config, "grid")["dlat"] = d
        if getattr(page, "lat_min_edit", None) is not None and getattr(page, "lat_max_edit", None) is not None:
            lat = (self._safe_float(page.lat_min_edit.text(), -89.5), self._safe_float(page.lat_max_edit.text(), 89.5))
            config.grid.lat = lat
            self._section(config, "grid")["lat"] = list(lat)
        if getattr(page, "lon_min_edit", None) is not None and getattr(page, "lon_max_edit", None) is not None:
            lon = (self._safe_float(page.lon_min_edit.text(), -179.5), self._safe_float(page.lon_max_edit.text(), 179.5))
            config.grid.lon = lon
            self._section(config, "grid")["lon"] = list(lon)
        if getattr(page, "lmax_slider", None) is not None:
            config.inversion.Lmax = int(page.lmax_slider.value())
            self._section(config, "inversion")["Lmax"] = config.inversion.Lmax
        if getattr(page, "static_field_edit", None) is not None:
            lowdeg = self._section(config, "inversion").setdefault("lowdeg", {})
            lowdeg.setdefault("files", {})["C20"] = page.static_field_edit.text().strip()
        if getattr(page, "gaussian_enable", None) is not None:
            self._section(config, "filter").setdefault("gaussian", {})["enable"] = bool(page.gaussian_enable.isChecked())
            config.filter.gaussian.enable = bool(page.gaussian_enable.isChecked())
        if getattr(page, "gaussian_radius_edit", None) is not None:
            r = self._safe_float(page.gaussian_radius_edit.text(), 300.0)
            self._section(config, "filter").setdefault("gaussian", {})["radius_km"] = r
            config.filter.gaussian.radius_km = r
        if getattr(page, "p4m6_enable", None) is not None:
            self._section(config, "filter").setdefault("p4m6", {})["enable"] = bool(page.p4m6_enable.isChecked())
            config.filter.p4m6.enable = bool(page.p4m6_enable.isChecked())
        if getattr(page, "p4_deg_edit", None) is not None:
            v = self._safe_int(page.p4_deg_edit.text(), 4)
            self._section(config, "filter").setdefault("p4m6", {})["poly_deg"] = v
            config.filter.p4m6.poly_deg = v
        if getattr(page, "p4_m_edit", None) is not None:
            v = self._safe_int(page.p4_m_edit.text(), 6)
            self._section(config, "filter").setdefault("p4m6", {})["m_start"] = v
            config.filter.p4m6.m_start = v
        if getattr(page, "ddk_enable", None) is not None:
            v = bool(page.ddk_enable.isChecked())
            self._section(config, "filter").setdefault("ddk", {})["enable"] = v
            config.filter.ddk.enable = v
        if getattr(page, "ddk_type_combo", None) is not None:
            v = page.ddk_type_combo.currentText()
            self._section(config, "filter").setdefault("ddk", {})["type"] = v
            config.filter.ddk.type = v
        if getattr(page, "fan_enable", None) is not None:
            fan = self._section(config, "filter").setdefault("fan", {})
            fan["enable"] = bool(page.fan_enable.isChecked())
            config.filter.fan["enable"] = bool(page.fan_enable.isChecked())
        if getattr(page, "fan_r1_edit", None) is not None:
            v = self._safe_float(page.fan_r1_edit.text(), 300.0)
            self._section(config, "filter").setdefault("fan", {})["radius1_km"] = v
            config.filter.fan["radius1_km"] = v
        if getattr(page, "fan_r2_edit", None) is not None:
            v = self._safe_float(page.fan_r2_edit.text(), 300.0)
            self._section(config, "filter").setdefault("fan", {})["radius2_km"] = v
            config.filter.fan["radius2_km"] = v
        if getattr(page, "hsaf_enable", None) is not None:
            self._section(config, "filter").setdefault("hankel", {})["enable"] = bool(page.hsaf_enable.isChecked())
            config.filter.hankel.enable = bool(page.hsaf_enable.isChecked())
        if getattr(page, "hsaf_variant_combo", None) is not None:
            v = page.hsaf_variant_combo.currentText()
            self._section(config, "filter").setdefault("hankel", {})["variant"] = v
            config.filter.hankel.variant = v
        if getattr(page, "hsaf_input_combo", None) is not None:
            v = page.hsaf_input_combo.currentText() or "P4M6"
            self._section(config, "filter")["pre_hankel_input"] = v
            config.filter.pre_hankel_input = v
        params = self._section(config, "filter").setdefault("hankel", {}).setdefault("params", {})
        if getattr(page, "hsaf_N_edit", None) is not None:
            params["N"] = self._safe_int(page.hsaf_N_edit.text(), 30)
        if getattr(page, "hsaf_P_edit", None) is not None:
            params["P"] = self._safe_int(page.hsaf_P_edit.text(), 10)
        if getattr(page, "hsaf_K_edit", None) is not None:
            params["K"] = self._safe_int(page.hsaf_K_edit.text(), 6)
        if getattr(page, "hsaf_J_edit", None) is not None:
            params["J"] = self._safe_int(page.hsaf_J_edit.text(), 1)
        self._section(config, "perf")["hsaf_tol"] = self._safe_float(getattr(page, "hsaf_tol_edit", QLineEdit("1e-7")).text() if getattr(page, "hsaf_tol_edit", None) is not None else "1e-7", 1e-7)
        self._section(config, "perf")["hsaf_iter"] = self._safe_int(getattr(page, "hsaf_iter_edit", QLineEdit("500")).text() if getattr(page, "hsaf_iter_edit", None) is not None else "500", 500)

    def _sync_basin(self, page, config: Config):
        if page is None:
            return
        if getattr(page, "enable_toggle", None) is not None:
            page.enable_toggle.setChecked(bool(config.basin.get("analysis_enable", False)))
        if getattr(page, "boundary_edit", None) is not None:
            page.boundary_edit.setText(config.basin.get("boundary_file", ""))
        if getattr(page, "data_file_edit", None) is not None:
            page.data_file_edit.setText(config.basin.get("data_file", ""))
        if getattr(page, "output_path_edit", None) is not None:
            page.output_path_edit.setText(config.basin.get("output_dir", ""))
        if getattr(page, "prefix_edit", None) is not None:
            page.prefix_edit.setText(config.basin.get("prefix", "basin"))
        if getattr(page, "tag_edit", None) is not None:
            page.tag_edit.setText(config.basin.get("tag", "DATA"))
        if getattr(page, "name_edit", None) is not None:
            page.name_edit.setText(config.basin.get("name", ""))
        if getattr(page, "name_field_edit", None) is not None:
            page.name_field_edit.setText(config.basin.get("name_field", "Name"))

    def _collect_basin(self, page, config: Config):
        if page is None:
            return
        basin = self._section(config, "basin")
        if getattr(page, "enable_toggle", None) is not None:
            basin["analysis_enable"] = bool(page.enable_toggle.isChecked())
            config.basin["analysis_enable"] = basin["analysis_enable"]
        if getattr(page, "boundary_edit", None) is not None:
            basin["boundary_file"] = page.boundary_edit.text().strip()
        if getattr(page, "data_file_edit", None) is not None:
            basin["data_file"] = page.data_file_edit.text().strip()
        if getattr(page, "output_path_edit", None) is not None:
            basin["output_dir"] = page.output_path_edit.text().strip()
        if getattr(page, "prefix_edit", None) is not None:
            basin["prefix"] = page.prefix_edit.text().strip()
        if getattr(page, "tag_edit", None) is not None:
            basin["tag"] = page.tag_edit.text().strip()
        if getattr(page, "name_edit", None) is not None:
            basin["name"] = page.name_edit.text().strip()
        if getattr(page, "name_field_edit", None) is not None:
            basin["name_field"] = page.name_field_edit.text().strip() or "Name"
        if getattr(page, "save_ts_txt_toggle", None) is not None:
            basin["save_ts_txt"] = bool(page.save_ts_txt_toggle.isChecked())
        if getattr(page, "save_ts_mat_toggle", None) is not None:
            basin["save_ts_mat"] = bool(page.save_ts_mat_toggle.isChecked())
        if getattr(page, "save_grid_txt_toggle", None) is not None:
            basin["save_grid_txt"] = bool(page.save_grid_txt_toggle.isChecked())
        if getattr(page, "save_grid_mat_toggle", None) is not None:
            basin["save_grid_mat"] = bool(page.save_grid_mat_toggle.isChecked())
        if getattr(page, "do_ts_toggle", None) is not None:
            basin["do_ts"] = bool(page.do_ts_toggle.isChecked())
        if getattr(page, "do_stats_toggle", None) is not None:
            basin["do_stats"] = bool(page.do_stats_toggle.isChecked())
        if getattr(page, "do_grid_toggle", None) is not None:
            basin["do_grid"] = bool(page.do_grid_toggle.isChecked())

    def _sync_leakage(self, page, config: Config):
        if page is None:
            return
        leak_cfg = getattr(config, "leakage", {}) or {}
        scope_default = str(leak_cfg.get("scope", "global")).lower()
        family_default = str(leak_cfg.get("strategy_family", "")).lower()
        if not family_default:
            family_default = "global_regularized"
        strategy_default = str(leak_cfg.get("correction_strategy", "")).lower()
        if not strategy_default:
            legacy_method = str(leak_cfg.get("method", "SF")).upper()
            strategy_default = "forward_modeling" if (legacy_method == "FM" and scope_default == "regional") else "auto"
        if getattr(page, "chk_leakage_enable", None) is not None:
            page.chk_leakage_enable.setChecked(bool(config.leakage.get("enable", False)))
        if getattr(page, "cmb_scope", None) is not None:
            idx = page.cmb_scope.findData(scope_default)
            page.cmb_scope.setCurrentIndex(idx if idx >= 0 else 0)
        if getattr(page, "cmb_strategy_family", None) is not None:
            idx = page.cmb_strategy_family.findData(family_default)
            page.cmb_strategy_family.setCurrentIndex(idx if idx >= 0 else 0)
        if getattr(page, "rb_method_fm", None) is not None:
            method = str(config.leakage.get("method", "SF")).upper()
            page.rb_method_fm.setChecked(method == "FM")
            page.rb_method_sf.setChecked(method != "FM")
        if getattr(page, "cmb_correction_strategy", None) is not None:
            strategy = strategy_default
            if strategy == "scale_factor":
                strategy = "basin_scale_factor"
            idx = page.cmb_correction_strategy.findData(strategy)
            page.cmb_correction_strategy.setCurrentIndex(idx if idx >= 0 else 0)
        if getattr(page, "cmb_scene_override", None) is not None:
            idx = page.cmb_scene_override.findData(str(config.leakage.get("scene_override", "auto")))
            page.cmb_scene_override.setCurrentIndex(idx if idx >= 0 else 0)
        if getattr(page, "cmb_reference_mode", None) is not None:
            idx = page.cmb_reference_mode.findData(str(config.leakage.get("reference_mode", "trend")))
            page.cmb_reference_mode.setCurrentIndex(idx if idx >= 0 else 0)
        if getattr(page, "cmb_official_mode", None) is not None:
            idx = page.cmb_official_mode.findData(str(config.leakage.get("official_mode", "auto")))
            page.cmb_official_mode.setCurrentIndex(idx if idx >= 0 else 0)
        if getattr(page, "edit_lrc_input", None) is not None:
            page.edit_lrc_input.setText(config.leakage.get("input", ""))
        if getattr(page, "edit_reference_input", None) is not None:
            page.edit_reference_input.setText(config.leakage.get("reference_input", ""))
        if getattr(page, "edit_lrc_output", None) is not None:
            page.edit_lrc_output.setText(config.leakage.get("output", ""))
        if getattr(page, "cmb_lrc_format", None) is not None:
            idx = page.cmb_lrc_format.findData(str(config.leakage.get("format", "mat")))
            page.cmb_lrc_format.setCurrentIndex(idx if idx >= 0 else 0)
        if getattr(page, "edit_regional_boundary", None) is not None:
            page.edit_regional_boundary.setText(config.leakage.get("boundary_file", ""))
        if getattr(page, "edit_lrc_sf_factor", None) is not None:
            page.edit_lrc_sf_factor.setText(str(config.leakage.get("sf_factor", 1.0)))
        if getattr(page, "edit_operator_autodetect", None) is not None:
            page.edit_operator_autodetect.setText(str(config.leakage.get("sf_method", "Auto")))
        if getattr(page, "edit_ddk_type", None) is not None:
            page.edit_ddk_type.setText(str(config.leakage.get("sf_ddk_type", "DDK4")))
        if getattr(page, "edit_lrc_gaussian_km", None) is not None:
            page.edit_lrc_gaussian_km.setText(str(config.leakage.get("sf_gauss_km", 300.0)))
        if getattr(page, "edit_fm_iteration_count", None) is not None:
            page.edit_fm_iteration_count.setText(str(config.leakage.get("fm_max_iter", 40)))
        if getattr(page, "edit_fm_convergence_threshold", None) is not None:
            page.edit_fm_convergence_threshold.setText(str(config.leakage.get("fm_tol", 0.01)))
        if getattr(page, "edit_fm_acceleration", None) is not None:
            page.edit_fm_acceleration.setText(str(config.leakage.get("fm_accel", 1.1)))
        if getattr(page, "edit_fm_patience", None) is not None:
            page.edit_fm_patience.setText(str(config.leakage.get("fm_patience", 8)))
        if getattr(page, "edit_fm_min_improve", None) is not None:
            page.edit_fm_min_improve.setText(str(config.leakage.get("fm_min_improve", 1.0e-4)))
        if getattr(page, "edit_coastal_buffer_cells", None) is not None:
            page.edit_coastal_buffer_cells.setText(str(config.leakage.get("coastal_buffer_cells", 3)))
        if getattr(page, "edit_coastal_attenuation_gain", None) is not None:
            page.edit_coastal_attenuation_gain.setText(str(config.leakage.get("coastal_attenuation_gain", 1.0)))
        if getattr(page, "edit_regularized_lambda", None) is not None:
            page.edit_regularized_lambda.setText(str(config.leakage.get("regularized_lambda", 0.18)))
        if getattr(page, "edit_regularized_step_size", None) is not None:
            page.edit_regularized_step_size.setText(str(config.leakage.get("regularized_step_size", 0.9)))
        if getattr(page, "edit_regularized_sigma", None) is not None:
            page.edit_regularized_sigma.setText(str(config.leakage.get("regularized_sigma", 1.2)))
        if getattr(page, "edit_regularized_iter", None) is not None:
            page.edit_regularized_iter.setText(str(config.leakage.get("regularized_iter", 10)))

    def _collect_leakage(self, page, config: Config):
        if page is None:
            return
        leak = self._section(config, "leakage")
        if getattr(page, "chk_leakage_enable", None) is not None:
            leak["enable"] = bool(page.chk_leakage_enable.isChecked())
            config.leakage["enable"] = leak["enable"]
        if getattr(page, "cmb_scope", None) is not None:
            leak["scope"] = str(page.cmb_scope.currentData() or page.cmb_scope.currentText()).lower()
            config.leakage["scope"] = leak["scope"]
        if getattr(page, "cmb_strategy_family", None) is not None:
            leak["strategy_family"] = str(page.cmb_strategy_family.currentData() or page.cmb_strategy_family.currentText()).lower()
            config.leakage["strategy_family"] = leak["strategy_family"]
        if getattr(page, "cmb_correction_strategy", None) is not None:
            leak["correction_strategy"] = str(page.cmb_correction_strategy.currentData() or page.cmb_correction_strategy.currentText()).strip().lower()
            config.leakage["correction_strategy"] = leak["correction_strategy"]
            leak["method"] = "FM" if leak["correction_strategy"] == "forward_modeling" else "SF"
            config.leakage["method"] = leak["method"]
        if getattr(page, "cmb_scene_override", None) is not None:
            leak["scene_override"] = str(page.cmb_scene_override.currentData() or page.cmb_scene_override.currentText()).strip().lower()
            config.leakage["scene_override"] = leak["scene_override"]
        if getattr(page, "cmb_reference_mode", None) is not None:
            leak["reference_mode"] = str(page.cmb_reference_mode.currentData() or page.cmb_reference_mode.currentText()).strip().lower()
            config.leakage["reference_mode"] = leak["reference_mode"]
        if getattr(page, "cmb_official_mode", None) is not None:
            leak["official_mode"] = str(page.cmb_official_mode.currentData() or page.cmb_official_mode.currentText()).strip().lower()
            config.leakage["official_mode"] = leak["official_mode"]
        if getattr(page, "edit_lrc_input", None) is not None:
            leak["input"] = page.edit_lrc_input.text().strip()
            config.leakage["input"] = leak["input"]
        if getattr(page, "edit_reference_input", None) is not None:
            leak["reference_input"] = page.edit_reference_input.text().strip()
            config.leakage["reference_input"] = leak["reference_input"]
        if getattr(page, "edit_lrc_output", None) is not None:
            leak["output"] = page.edit_lrc_output.text().strip()
            config.leakage["output"] = leak["output"]
        if getattr(page, "cmb_lrc_format", None) is not None:
            leak["format"] = page.cmb_lrc_format.currentText().strip().lower()
            config.leakage["format"] = leak["format"]
        if getattr(page, "edit_regional_boundary", None) is not None:
            leak["boundary_file"] = page.edit_regional_boundary.text().strip()
            config.leakage["boundary_file"] = leak["boundary_file"]
        if getattr(page, "edit_lrc_sf_factor", None) is not None:
            leak["sf_factor"] = self._safe_float(page.edit_lrc_sf_factor.text(), 1.0)
            config.leakage["sf_factor"] = leak["sf_factor"]
        if getattr(page, "edit_operator_autodetect", None) is not None:
            leak["sf_method"] = page.edit_operator_autodetect.text().strip() or "Auto"
            config.leakage["sf_method"] = leak["sf_method"]
        if getattr(page, "edit_ddk_type", None) is not None:
            leak["sf_ddk_type"] = page.edit_ddk_type.text().strip() or "DDK4"
            config.leakage["sf_ddk_type"] = leak["sf_ddk_type"]
        if getattr(page, "edit_lrc_gaussian_km", None) is not None:
            leak["sf_gauss_km"] = self._safe_float(page.edit_lrc_gaussian_km.text(), 300.0)
            config.leakage["sf_gauss_km"] = leak["sf_gauss_km"]
        if getattr(page, "edit_fm_iteration_count", None) is not None:
            leak["fm_max_iter"] = self._safe_int(page.edit_fm_iteration_count.text(), 40)
            config.leakage["fm_max_iter"] = leak["fm_max_iter"]
        if getattr(page, "edit_fm_convergence_threshold", None) is not None:
            leak["fm_tol"] = self._safe_float(page.edit_fm_convergence_threshold.text(), 0.01)
            config.leakage["fm_tol"] = leak["fm_tol"]
        if getattr(page, "edit_fm_acceleration", None) is not None:
            leak["fm_accel"] = self._safe_float(page.edit_fm_acceleration.text(), 1.1)
            config.leakage["fm_accel"] = leak["fm_accel"]
        if getattr(page, "edit_fm_patience", None) is not None:
            leak["fm_patience"] = self._safe_int(page.edit_fm_patience.text(), 8)
            config.leakage["fm_patience"] = leak["fm_patience"]
        if getattr(page, "edit_fm_min_improve", None) is not None:
            leak["fm_min_improve"] = self._safe_float(page.edit_fm_min_improve.text(), 1.0e-4)
            config.leakage["fm_min_improve"] = leak["fm_min_improve"]
        if getattr(page, "edit_coastal_buffer_cells", None) is not None:
            leak["coastal_buffer_cells"] = self._safe_int(page.edit_coastal_buffer_cells.text(), 3)
            config.leakage["coastal_buffer_cells"] = leak["coastal_buffer_cells"]
        if getattr(page, "edit_coastal_attenuation_gain", None) is not None:
            leak["coastal_attenuation_gain"] = self._safe_float(page.edit_coastal_attenuation_gain.text(), 1.0)
            config.leakage["coastal_attenuation_gain"] = leak["coastal_attenuation_gain"]
        if getattr(page, "edit_regularized_lambda", None) is not None:
            leak["regularized_lambda"] = self._safe_float(page.edit_regularized_lambda.text(), 0.18)
            config.leakage["regularized_lambda"] = leak["regularized_lambda"]
        if getattr(page, "edit_regularized_step_size", None) is not None:
            leak["regularized_step_size"] = self._safe_float(page.edit_regularized_step_size.text(), 0.9)
            config.leakage["regularized_step_size"] = leak["regularized_step_size"]
        if getattr(page, "edit_regularized_sigma", None) is not None:
            leak["regularized_sigma"] = self._safe_float(page.edit_regularized_sigma.text(), 1.2)
            config.leakage["regularized_sigma"] = leak["regularized_sigma"]
        if getattr(page, "edit_regularized_iter", None) is not None:
            leak["regularized_iter"] = self._safe_int(page.edit_regularized_iter.text(), 10)
            config.leakage["regularized_iter"] = leak["regularized_iter"]

    def _sync_preview(self, page, config: Config):
        if page is None:
            return
        if getattr(page, "dataset_edit", None) is not None:
            page.dataset_edit.setText(config.plot.get("stack_file", ""))
        if getattr(page, "projection_combo", None) is not None:
            page.projection_combo.setCurrentText(config.plot.get("projection", "Robinson"))
        if getattr(page, "time_index_slider", None) is not None:
            page.time_index_slider.setValue(int(config.plot.get("time_index", 0) or 0))
        if getattr(page, "cmap_combo", None) is not None:
            page.cmap_combo.setCurrentText(config.plot.get("cmap", "RdBu_r"))
        if getattr(page, "cmin_edit", None) is not None:
            page.cmin_edit.setText(str(config.plot.get("cmin", "")))
        if getattr(page, "cmax_edit", None) is not None:
            page.cmax_edit.setText(str(config.plot.get("cmax", "")))
        if getattr(page, "save_path_edit", None) is not None:
            page.save_path_edit.setText(config.plot.get("save_path", ""))
        if getattr(page, "save_dpi_edit", None) is not None:
            page.save_dpi_edit.setText(str(config.plot.get("save_dpi", 300)))
        if getattr(page, "save_fmt_combo", None) is not None:
            page.save_fmt_combo.setCurrentText(config.plot.get("save_fmt", "png"))

    def _collect_preview(self, page, config: Config):
        if page is None:
            return
        plot = self._section(config, "plot")
        if getattr(page, "dataset_edit", None) is not None:
            plot["stack_file"] = page.dataset_edit.text().strip()
        if getattr(page, "projection_combo", None) is not None:
            plot["projection"] = page.projection_combo.currentText()
        if getattr(page, "time_index_slider", None) is not None:
            plot["time_index"] = int(page.time_index_slider.value())
        if getattr(page, "cmap_combo", None) is not None:
            plot["cmap"] = page.cmap_combo.currentText()
        if getattr(page, "cmin_edit", None) is not None:
            plot["cmin"] = page.cmin_edit.text().strip()
        if getattr(page, "cmax_edit", None) is not None:
            plot["cmax"] = page.cmax_edit.text().strip()
        if getattr(page, "save_path_edit", None) is not None:
            plot["save_path"] = page.save_path_edit.text().strip()
        if getattr(page, "save_dpi_edit", None) is not None:
            plot["save_dpi"] = self._safe_int(page.save_dpi_edit.text(), 300)
        if getattr(page, "save_fmt_combo", None) is not None:
            plot["save_fmt"] = page.save_fmt_combo.currentText().strip().lower()
