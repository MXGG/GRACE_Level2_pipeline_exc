"""Configuration loading and defaults for the GRACE Level-2 pipeline."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Union


# This file is intentionally self-contained.  It is imported by CLI, GUI, and
# HPC wrappers before most optional scientific dependencies are loaded.


def get_root_dir() -> Path:
    """Return the repository/runtime root directory."""
    env_root = os.environ.get("GRACE_L2_HOME")
    if env_root:
        return Path(env_root).expanduser().resolve()
    # python/grace_pipeline/core/config.py -> repo root
    return Path(__file__).resolve().parents[4]


DEFAULT_CONFIG: Dict[str, Any] = {
    "path": {
        "ROOT": "",
        "GFC": "data/GRACE/GSM",
        "OUTPUT": "outputs",
        "AUX": "data/Aux",
        "DDK": "data/DDK",
        "BOUNDARY": "data/Boundary/boundary_cache",
        "LOW_DEGREE": "data/GRACE/LowDegree",
        "GIA": "data/GRACE/GIA",
        "MASCON": "data/Reference/Mascon",
    },
    "time": {
        "auto_detect_gfc": True,
        "start_ym": "2002-04",
        "end_ym": "2017-06",
        "product_type": "GSM",
        "file_ext": ".gfc",
    },
    "grid": {
        "lon": [-179.5, 179.5],
        "lat": [-89.5, 89.5],
        "dlon": 1.0,
        "dlat": 1.0,
        "unit": "mmEWH",
    },
    "inversion": {
        "Lmax": 60,
        "remove_mean": True,
        "mean_start_ym": "2004-01",
        "mean_end_ym": "2009-12",
        "love_numbers": "default",
        "lowdeg": {
            "enable": True,
            "replace_C20": True,
            "replace_degree1": True,
            "replace_C10": True,
            "replace_C30": False,
            "files": {
                "C20": "data/GRACE/LowDegree/TN-14_C30_C20_GSFC_SLR.txt",
                "DEGREE1": "data/GRACE/LowDegree/TN-13_GEOC_CSR_RL06.txt",
            },
        },
        "gia": {
            "enable": False,
            "file": "data/GRACE/GIA/GIA_Stokes_ICE-6G_D.txt",
            "Lmax": 60,
        },
    },
    "filter": {
        "gaussian": {"enable": True, "radius_km": 300},
        "p4m6": {"enable": True, "poly_deg": 4, "m_start": 6},
        "fan": {"enable": False, "radius1_km": 300, "radius2_km": 300},
        "ddk": {"enable": True, "type": "DDK4", "data_dir": "data/DDK"},
        "hankel": {
            "enable": False,
            "variant": "global",
            "engine": "matlab_v3",
            "mode": "profile",
            "params": {"N": 30, "P": 10, "K": 6, "J": 1},
        },
        "pre_hankel_input": "P4M6",
    },
    "basin": {"analysis_enable": False, "boundary_file": "", "name": ""},
    "leakage": {"enable": False},
    "metrics": {"enable": False, "compute_spectrum": False},
    "io": {
        "save_monthly_mat": True,
        "save_stack_mat": True,
        "export_txt": False,
        "resume": False,
        "return_stacks": False,
        "return_basin": False,
        "return_metrics": False,
    },
    "plot": {
        "quicklook": False,
        "metrics_ts": False,
        "metrics_maps": False,
        "stack_mean": False,
        "stack_trend_amp": False,
        "basin_overlay": False,
    },
    "parallel": {"enable": True, "nWorkers": 4},
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep-merge two dictionaries without mutating either input."""
    result = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _to_namespace(value: Any) -> Any:
    if isinstance(value, dict):
        return ConfigNamespace(value)
    if isinstance(value, list):
        return [_to_namespace(item) for item in value]
    return value


class ConfigNamespace:
    """Dictionary wrapper supporting attribute access and dict-like get."""

    def __init__(self, data: Dict[str, Any]):
        self._data = data
        for key, value in data.items():
            setattr(self, key, _to_namespace(value))

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        return self._data

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]


class Config:
    """Top-level runtime configuration wrapper."""

    def __init__(self, cfg: Dict[str, Any]):
        self._raw = cfg
        self.path = ConfigNamespace(cfg.get("path", {}))
        self.time = ConfigNamespace(cfg.get("time", {}))
        self.grid = ConfigNamespace(cfg.get("grid", {}))
        self.inversion = ConfigNamespace(cfg.get("inversion", {}))
        self.filter = ConfigNamespace(cfg.get("filter", {}))
        self.basin = ConfigNamespace(cfg.get("basin", {}))
        self.leakage = ConfigNamespace(cfg.get("leakage", {}))
        self.metrics = ConfigNamespace(cfg.get("metrics", {}))
        self.io = ConfigNamespace(cfg.get("io", {}))
        self.plot = ConfigNamespace(cfg.get("plot", {}))
        self.parallel = ConfigNamespace(cfg.get("parallel", {}))
        self.fm = cfg.get("fm", {})

    def to_dict(self) -> Dict[str, Any]:
        """Convert config back to dictionary."""
        return self._raw

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value by key path (e.g., 'filter.gaussian.radius_km')."""
        keys = key.split(".")
        value = self._raw
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value


def _load_json_file(path: Union[str, Path], label: str) -> Dict[str, Any]:
    path_obj = Path(path).expanduser()
    if not path_obj.exists():
        raise FileNotFoundError(f"Explicit {label} config file not found: {path_obj}")
    # PowerShell 5.1 Set-Content -Encoding UTF8 writes a UTF-8 BOM. Accept it so
    # user-created JSON configs work consistently across Windows PowerShell,
    # PowerShell 7, Notepad, MATLAB, CLI, and GUI workflows.
    with open(path_obj, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_config(
    user_config: Optional[Union[str, Path]] = None,
    default_config: Optional[Union[str, Path]] = None,
    root_dir: Optional[Union[str, Path]] = None,
) -> Config:
    """Load configuration from JSON files.

    A missing explicitly supplied user/default config is an error. This prevents
    silent fallback to defaults when a CLI, GUI, or HPC caller intended to use a
    specific run configuration.
    """
    if root_dir is None:
        root_dir = get_root_dir()
    root_path = Path(root_dir).resolve()
    root_dir_str = str(root_path)

    base_cfg = deepcopy(DEFAULT_CONFIG)
    if default_config is not None:
        base_cfg = _deep_merge(base_cfg, _load_json_file(default_config, "default"))

    user_cfg: Dict[str, Any] = {}
    if user_config is not None:
        user_cfg = _load_json_file(user_config, "user")

    cfg = _deep_merge(base_cfg, user_cfg)
    cfg.setdefault("path", {})
    cfg["path"]["ROOT"] = cfg["path"].get("ROOT") or root_dir_str

    # Normalize important paths relative to ROOT.
    for section_key in ["GFC", "OUTPUT", "AUX", "DDK", "BOUNDARY", "LOW_DEGREE", "GIA", "MASCON"]:
        value = cfg["path"].get(section_key)
        if value and not Path(value).is_absolute():
            cfg["path"][section_key] = str(root_path / value)

    # Keep DDK data_dir in sync when it is omitted or relative.
    ddk_cfg = cfg.setdefault("filter", {}).setdefault("ddk", {})
    ddk_dir = ddk_cfg.get("data_dir") or cfg["path"].get("DDK")
    if ddk_dir and not Path(ddk_dir).is_absolute():
        ddk_dir = str(root_path / ddk_dir)
    if ddk_dir:
        ddk_cfg["data_dir"] = ddk_dir

    # Normalize low-degree and GIA file paths when present.
    inv_cfg = cfg.setdefault("inversion", {})
    lowdeg = inv_cfg.setdefault("lowdeg", {})
    low_files = lowdeg.setdefault("files", {})
    for key, value in list(low_files.items()):
        if value and not Path(value).is_absolute():
            low_files[key] = str(root_path / value)
    gia_cfg = inv_cfg.setdefault("gia", {})
    if gia_cfg.get("file") and not Path(gia_cfg["file"]).is_absolute():
        gia_cfg["file"] = str(root_path / gia_cfg["file"])

    return Config(cfg)
