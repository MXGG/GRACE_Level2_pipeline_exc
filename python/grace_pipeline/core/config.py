"""
Configuration management for GRACE pipeline.
Handles loading JSON configs with placeholder resolution and merging.
"""

import configparser
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Union


def _path_value(value: Optional[str]) -> Optional[Path]:
    """Return an expanded path value without requiring the path to exist."""
    if not value:
        return None
    try:
        return Path(value).expanduser().resolve()
    except Exception:
        return None


def _existing_path(value: Optional[str]) -> Optional[Path]:
    if not value:
        return None
    try:
        path = Path(value).expanduser()
        if path.exists():
            return path.resolve()
    except Exception:
        return None
    return None


def _read_install_ini(start: Optional[Path] = None) -> Dict[str, str]:
    """Read installer path hints from grace-l2.ini when present."""
    starts = []
    if start is not None:
        starts.extend([start, *start.parents])
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        starts.extend([exe_dir, *exe_dir.parents])

    seen = set()
    for base in starts:
        if base in seen:
            continue
        seen.add(base)
        ini_path = base / "grace-l2.ini"
        if not ini_path.exists():
            continue
        parser = configparser.ConfigParser()
        try:
            parser.read(ini_path, encoding="utf-8")
            if parser.has_section("Paths"):
                return {k.lower(): v for k, v in parser.items("Paths")}
        except Exception:
            continue
    return {}


def get_bundle_dir() -> Path:
    """Return the PyInstaller bundle directory, or a sensible source fallback."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass).resolve()
    return get_root_dir()


def _looks_like_repo_root(path: Path) -> bool:
    return (
        (path / "configs").is_dir()
        or (path / "python" / "grace_pipeline").is_dir()
        or (path / "matlab" / "src").is_dir()
        or (path / "grace-l2.ini").exists()
    )


def get_root_dir() -> Path:
    """
    Return the active project/install root.

    Frozen installer layout:
        <root>/dist/grace-pipeline-gui.exe
        <root>/configs
        <root>/data
        <root>/outputs

    Source layout:
        repository root containing configs/, python/, and matlab/.
    """
    env_root = _existing_path(os.environ.get("GRACE_L2_HOME"))
    if env_root:
        return env_root

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        ini = _read_install_ini(exe_dir)
        ini_root = _existing_path(ini.get("homedir"))
        if ini_root:
            return ini_root

        candidates = [exe_dir.parent, exe_dir] if exe_dir.name.lower() == "dist" else [exe_dir, exe_dir.parent]
        for candidate in candidates:
            if _looks_like_repo_root(candidate):
                return candidate.resolve()
        return candidates[0].resolve()

    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        if _looks_like_repo_root(candidate):
            return candidate.resolve()
    return cwd


def get_data_dir(root_dir: Optional[Union[str, Path]] = None) -> Path:
    """Return the active data directory for source or installed runs."""
    root = Path(root_dir).resolve() if root_dir is not None else get_root_dir()
    env_data = _existing_path(os.environ.get("GRACE_L2_DATA"))
    if env_data:
        return env_data
    ini_data = _existing_path(_read_install_ini(root).get("datadir"))
    if ini_data:
        return ini_data
    bundle_data = get_bundle_dir() / "data" if getattr(sys, "frozen", False) else None
    if bundle_data and bundle_data.exists():
        return bundle_data
    return root / "data"


def get_output_dir(root_dir: Optional[Union[str, Path]] = None) -> Path:
    """Return the active output directory for source or installed runs.

    Unlike input/data directories, output paths are allowed to be absent at
    startup. The pipeline or doctor command can create them later.
    """
    root = Path(root_dir).resolve() if root_dir is not None else get_root_dir()
    env_output = _path_value(os.environ.get("GRACE_L2_OUTPUT"))
    if env_output:
        return env_output
    ini_output = _path_value(_read_install_ini(root).get("outputdir"))
    if ini_output:
        return ini_output
    return root / "outputs"


def get_config_dir(root_dir: Optional[Union[str, Path]] = None) -> Path:
    """Return the canonical user-facing config directory."""
    root = Path(root_dir).resolve() if root_dir is not None else get_root_dir()
    env_cfg = _existing_path(os.environ.get("GRACE_L2_CONFIG"))
    if env_cfg:
        return env_cfg
    ini_cfg = _existing_path(_read_install_ini(root).get("configdir"))
    if ini_cfg:
        return ini_cfg
    for candidate in [root / "configs", root / "cfg", root / "matlab" / "cfg"]:
        if candidate.exists():
            return candidate.resolve()
    return root / "configs"


def find_default_config(root_dir: Optional[Union[str, Path]] = None) -> Optional[Path]:
    """Find default.json in canonical, installed, bundled, or legacy layouts."""
    root = Path(root_dir).resolve() if root_dir is not None else get_root_dir()
    bundle = get_bundle_dir()
    config_dir = get_config_dir(root)
    candidates = [
        config_dir / "default.json",
        root / "configs" / "default.json",
        root / "cfg" / "default.json",
        root / "matlab" / "cfg" / "default.json",
        bundle / "configs" / "default.json",
        bundle / "cfg" / "default.json",
        bundle / "matlab" / "cfg" / "default.json",
    ]
    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            return candidate.resolve()
    return None


def resolve_placeholders(obj: Any, root_dir: str) -> Any:
    """Recursively resolve ${ROOT} and other environment placeholders."""
    if isinstance(obj, str):
        obj = obj.replace("${ROOT}", root_dir)
        pattern = r"\$\{([^}]+)\}"
        for match in re.findall(pattern, obj):
            env_val = os.environ.get(match, "")
            obj = obj.replace(f"${{{match}}}", env_val)
        return obj
    if isinstance(obj, dict):
        return {k: resolve_placeholders(v, root_dir) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve_placeholders(item, root_dir) for item in obj]
    return obj


def remap_root_paths(obj: Any, source_root: str, target_root: str) -> Any:
    """Remap absolute paths rooted at source_root to target_root recursively."""
    if not source_root or not target_root:
        return obj

    src_win = source_root.replace("/", "\\").rstrip("\\")
    src_posix = source_root.replace("\\", "/").rstrip("/")
    dst = str(Path(target_root).resolve())

    if isinstance(obj, str):
        s = obj
        replaced = False
        for src in (src_win, src_posix):
            if src and src in s:
                s = s.replace(src, dst)
                replaced = True
        if replaced and os.name != "nt":
            s = s.replace("\\", "/")
        return s
    if isinstance(obj, dict):
        return {k: remap_root_paths(v, source_root, target_root) for k, v in obj.items()}
    if isinstance(obj, list):
        return [remap_root_paths(item, source_root, target_root) for item in obj]
    return obj


def merge_configs(base: Dict, override: Dict) -> Dict:
    """Deep merge override config into base config."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    return result


@dataclass
class PathConfig:
    """Path configuration."""
    ROOT: str = ""
    GFC: str = ""
    OUTPUT: str = ""
    AUX: str = ""
    DDK: str = ""
    BOUNDARY: str = ""
    TOOLBOX: Dict[str, str] = field(default_factory=dict)


@dataclass
class TimeConfig:
    """Time range configuration."""
    auto_detect_gfc: bool = True
    start_ym: str = "2002-04"
    end_ym: str = "2017-06"
    product_type: str = "GSM"
    file_ext: str = ".gfc"


@dataclass
class GridConfig:
    """Output grid configuration."""
    lon: tuple = (-179.5, 179.5)
    lat: tuple = (-89.5, 89.5)
    dlon: float = 1.0
    dlat: float = 1.0
    unit: str = "mmEWH"


@dataclass
class InversionConfig:
    """Spherical harmonic inversion parameters."""
    Lmax: int = 60
    remove_mean: bool = True
    mean_start_ym: str = ""
    mean_end_ym: str = ""
    lowdeg: Dict = field(default_factory=dict)
    gia: Dict = field(default_factory=dict)


@dataclass
class GaussianFilterConfig:
    """Gaussian filter settings."""
    enable: bool = True
    radius_km: float = 300.0


@dataclass
class P4M6FilterConfig:
    """P4M6 destriping filter settings."""
    enable: bool = True
    poly_deg: int = 4
    m_start: int = 6


@dataclass
class DDKFilterConfig:
    """DDK filter settings."""
    enable: bool = True
    type: str = "DDK4"
    data_dir: str = ""


@dataclass
class HSAFFilterConfig:
    """HSAF (Hankel-SVD Adaptive Filter) settings."""
    enable: bool = True
    variant: str = "global"
    mode: str = "profile"
    engine: str = "matlab_v3"
    params: Dict = field(default_factory=lambda: {"N": 30, "P": 10, "K": 6, "J": 1})
    adaptive: list = field(default_factory=list)
    stack_mode: bool = False


@dataclass
class FilterConfig:
    """All filter configurations."""
    gaussian: GaussianFilterConfig = field(default_factory=GaussianFilterConfig)
    p4m6: P4M6FilterConfig = field(default_factory=P4M6FilterConfig)
    fan: Dict = field(default_factory=dict)
    ddk: DDKFilterConfig = field(default_factory=DDKFilterConfig)
    hankel: HSAFFilterConfig = field(default_factory=HSAFFilterConfig)
    pre_hankel_input: str = "P4M6"
    combinations: Dict = field(default_factory=dict)


@dataclass
class IOConfig:
    """Input/output settings."""
    save_monthly_mat: bool = True
    save_stack_mat: bool = True
    save_stack_hdf5: bool = False
    export_txt: bool = False
    txt_format: str = "lonlatval"
    resume: bool = False
    return_stacks: bool = False
    return_basin: bool = False
    return_metrics: bool = False


@dataclass
class ParallelConfig:
    """Parallel processing settings."""
    enable: bool = True
    n_workers: int = 4


class Config:
    """Main configuration class for GRACE pipeline."""

    def __init__(self, config_dict: Dict[str, Any]):
        self._raw = config_dict
        self._parse_config(config_dict)

    def _parse_config(self, cfg: Dict):
        """Parse configuration dictionary into typed attributes."""
        path_cfg = cfg.get("path", {})
        self.path = PathConfig(
            ROOT=path_cfg.get("ROOT", ""),
            GFC=path_cfg.get("GFC", ""),
            OUTPUT=path_cfg.get("OUTPUT", ""),
            AUX=path_cfg.get("AUX", ""),
            DDK=path_cfg.get("DDK", ""),
            BOUNDARY=path_cfg.get("BOUNDARY", ""),
            TOOLBOX=path_cfg.get("TOOLBOX", {}),
        )

        time_cfg = cfg.get("time", {})
        self.time = TimeConfig(
            auto_detect_gfc=time_cfg.get("auto_detect_gfc", True),
            start_ym=time_cfg.get("start_ym", "2002-04"),
            end_ym=time_cfg.get("end_ym", "2017-06"),
            product_type=time_cfg.get("product_type", "GSM"),
            file_ext=time_cfg.get("file_ext", ".gfc"),
        )

        grid_cfg = cfg.get("grid", {})
        self.grid = GridConfig(
            lon=tuple(grid_cfg.get("lon", [-179.5, 179.5])),
            lat=tuple(grid_cfg.get("lat", [-89.5, 89.5])),
            dlon=grid_cfg.get("dlon", 1.0),
            dlat=grid_cfg.get("dlat", 1.0),
            unit=grid_cfg.get("unit", "mmEWH"),
        )

        inv_cfg = cfg.get("inversion", {})
        self.inversion = InversionConfig(
            Lmax=inv_cfg.get("Lmax", 60),
            remove_mean=inv_cfg.get("remove_mean", True),
            mean_start_ym=inv_cfg.get("mean_start_ym", inv_cfg.get("mean_start", "")),
            mean_end_ym=inv_cfg.get("mean_end_ym", inv_cfg.get("mean_end", "")),
            lowdeg=inv_cfg.get("lowdeg", {}),
            gia=inv_cfg.get("gia", {}),
        )

        filter_cfg = cfg.get("filter", {})
        self.filter = FilterConfig(
            pre_hankel_input=filter_cfg.get("pre_hankel_input", "P4M6"),
            combinations=filter_cfg.get("combinations", {}),
        )
        if "gaussian" in filter_cfg:
            g = filter_cfg["gaussian"]
            self.filter.gaussian = GaussianFilterConfig(
                enable=g.get("enable", True), radius_km=g.get("radius_km", 300.0)
            )
        if "p4m6" in filter_cfg:
            p = filter_cfg["p4m6"]
            self.filter.p4m6 = P4M6FilterConfig(
                enable=p.get("enable", True), poly_deg=p.get("poly_deg", 4), m_start=p.get("m_start", 6)
            )
        if "ddk" in filter_cfg:
            d = filter_cfg["ddk"]
            self.filter.ddk = DDKFilterConfig(
                enable=d.get("enable", True), type=d.get("type", "DDK4"), data_dir=d.get("data_dir", "")
            )
        if "hankel" in filter_cfg:
            h = filter_cfg["hankel"]
            self.filter.hankel = HSAFFilterConfig(
                enable=h.get("enable", True),
                variant=h.get("variant", "global"),
                mode=h.get("mode", "profile"),
                engine=h.get("engine", "matlab_v3"),
                params=h.get("params", {"N": 30, "P": 10, "K": 6, "J": 1}),
                adaptive=h.get("adaptive", []),
                stack_mode=h.get("stack_mode", False),
            )
        self.filter.fan = filter_cfg.get("fan", {})

        io_cfg = cfg.get("io", {})
        self.io = IOConfig(
            save_monthly_mat=io_cfg.get("save_monthly_mat", True),
            save_stack_mat=io_cfg.get("save_stack_mat", True),
            save_stack_hdf5=io_cfg.get("save_stack_hdf5", False),
            export_txt=io_cfg.get("export_txt", False),
            txt_format=io_cfg.get("txt_format", "lonlatval"),
            resume=io_cfg.get("resume", False),
            return_stacks=io_cfg.get("return_stacks", False),
            return_basin=io_cfg.get("return_basin", False),
            return_metrics=io_cfg.get("return_metrics", False),
        )

        par_cfg = cfg.get("parallel", {})
        self.parallel = ParallelConfig(
            enable=par_cfg.get("enable", True),
            n_workers=par_cfg.get("nWorkers", par_cfg.get("n_workers", 4)),
        )

        self.reference = cfg.get("reference", {})
        self.gldas = cfg.get("gldas", {})
        self.basin = cfg.get("basin", {})
        self.leakage = cfg.get("leakage", {})
        self.metrics = cfg.get("metrics", {})
        self.plot = cfg.get("plot", {})
        self.perf = cfg.get("perf", {})
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
    with open(path_obj, "r", encoding="utf-8") as f:
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
    data_dir = get_data_dir(root_path)
    output_dir = get_output_dir(root_path)

    if default_config is None:
        default_config = find_default_config(root_path)

    base_cfg: Dict[str, Any] = {}
    if default_config:
        base_cfg = _load_json_file(default_config, "default")

    user_cfg: Dict[str, Any] = {}
    if user_config:
        user_cfg = _load_json_file(user_config, "user")

    merged = merge_configs(base_cfg, user_cfg)
    resolved = resolve_placeholders(merged, root_dir_str)

    current_root = str(root_path)
    configured_root = str(resolved.get("path", {}).get("ROOT", "") or "")
    if configured_root and configured_root != current_root:
        resolved = remap_root_paths(resolved, configured_root, current_root)

    if not resolved.get("path"):
        resolved["path"] = {}

    path_cfg = resolved["path"]
    if not path_cfg.get("ROOT"):
        path_cfg["ROOT"] = root_dir_str
    if not path_cfg.get("GFC"):
        path_cfg["GFC"] = str(data_dir / "GRACE" / "GSM")
    if not path_cfg.get("OUTPUT"):
        path_cfg["OUTPUT"] = str(output_dir)
    if not path_cfg.get("DDK"):
        path_cfg["DDK"] = str(data_dir / "DDK")
    if not path_cfg.get("BOUNDARY"):
        path_cfg["BOUNDARY"] = str(data_dir / "Boundary")

    if "filter" not in resolved:
        resolved["filter"] = {}
    if "ddk" not in resolved["filter"]:
        resolved["filter"]["ddk"] = {}
    if not resolved["filter"]["ddk"].get("data_dir"):
        resolved["filter"]["ddk"]["data_dir"] = path_cfg["DDK"]

    return Config(resolved)
