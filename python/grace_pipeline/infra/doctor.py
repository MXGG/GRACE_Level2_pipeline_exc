"""Runtime health checks for GRACE Pipeline entrypoints."""

from __future__ import annotations

import importlib.util
import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    required: bool = True


CORE_MODULES = [
    "numpy",
    "scipy",
    "matplotlib",
    "netCDF4",
    "h5py",
    "click",
    "tqdm",
    "yaml",
    "joblib",
    "shapefile",
]

GUI_MODULES = ["PySide6"]


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _path_check(name: str, value: Optional[str], required: bool = True, writable: bool = False) -> CheckResult:
    if not value:
        return CheckResult(name, not required, "not configured", required=required)
    path = Path(value).expanduser()
    if writable:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".grace_write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return CheckResult(name, True, str(path.resolve()), required=required)
        except Exception as exc:
            return CheckResult(name, False, f"not writable: {path} ({exc})", required=required)
    return CheckResult(name, path.exists() or not required, str(path), required=required)


def run_doctor(cfg=None, default_config: Optional[str] = None, check_gui: bool = False) -> list[CheckResult]:
    """Return runtime health-check results without starting the pipeline."""
    from grace_pipeline.infra.config import find_default_config, get_root_dir

    root = get_root_dir()
    results: list[CheckResult] = []

    results.append(CheckResult("python.version", sys.version_info >= (3, 9), sys.version.split()[0]))
    results.append(CheckResult("platform", True, f"{platform.system()} {platform.release()} ({platform.machine()})"))
    results.append(CheckResult("runtime.root", root.exists(), str(root)))
    results.append(CheckResult("runtime.frozen", True, str(bool(getattr(sys, "frozen", False))), required=False))

    for module_name in CORE_MODULES:
        results.append(CheckResult(f"module.{module_name}", _module_available(module_name), "importable" if _module_available(module_name) else "missing"))

    for module_name in GUI_MODULES:
        required = check_gui
        results.append(CheckResult(f"module.{module_name}", _module_available(module_name) or not required, "importable" if _module_available(module_name) else "missing; install with .[gui]", required=required))

    default_path = Path(default_config).expanduser() if default_config else find_default_config(root)
    results.append(CheckResult("config.default", bool(default_path and Path(default_path).exists()), str(default_path) if default_path else "not found"))

    if cfg is not None:
        results.append(_path_check("config.path.GFC", getattr(cfg.path, "GFC", ""), required=False))
        results.append(_path_check("config.path.DDK", getattr(cfg.path, "DDK", ""), required=False))
        results.append(_path_check("config.path.BOUNDARY", getattr(cfg.path, "BOUNDARY", ""), required=False))
        results.append(_path_check("config.path.OUTPUT", getattr(cfg.path, "OUTPUT", ""), required=True, writable=True))

    return results


def print_doctor(results: Iterable[CheckResult]) -> int:
    """Print a compact doctor report. Return 0 when required checks pass."""
    failures = 0
    for result in results:
        marker = "OK" if result.ok else ("FAIL" if result.required else "WARN")
        print(f"[{marker:4}] {result.name}: {result.detail}")
        if result.required and not result.ok:
            failures += 1
    return 1 if failures else 0
