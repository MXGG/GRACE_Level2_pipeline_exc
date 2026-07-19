"""Canonical time-index exports with configuration-aware filtering."""

from __future__ import annotations

from typing import Optional

from grace_pipeline.core.time_index import (
    TimeEntry,
    build_time_index as _core_build_time_index,
    detect_gfc_files,
    extract_ym_from_gfc,
    parse_ym_range,
    summarize_time_coverage,
)


def _get_time_value(time_cfg, name: str, default: Optional[str] = None) -> Optional[str]:
    if hasattr(time_cfg, name):
        value = getattr(time_cfg, name)
    elif isinstance(time_cfg, dict):
        value = time_cfg.get(name, default)
    else:
        value = default
    if value is None:
        return default
    value = str(value).strip()
    return value or default


def _get_auto_detect(time_cfg) -> bool:
    if hasattr(time_cfg, "auto_detect_gfc"):
        return bool(getattr(time_cfg, "auto_detect_gfc"))
    if isinstance(time_cfg, dict):
        return bool(time_cfg.get("auto_detect_gfc", True))
    return True


def build_time_index(cfg, gfc_dir: Optional[str] = None) -> list[TimeEntry]:
    """Build a time index and respect configured ``start_ym``/``end_ym``.

    The legacy auto-detect path returned every detectable GFC month. For a
    processing configuration, auto-detection should find available files first
    and then crop to the user-specified span. Empty start/end values keep the
    corresponding side open.
    """
    entries = _core_build_time_index(cfg, gfc_dir=gfc_dir)
    time_cfg = cfg.time if hasattr(cfg, "time") else cfg.get("time", {})

    if not _get_auto_detect(time_cfg):
        return entries

    start_ym = _get_time_value(time_cfg, "start_ym", "")
    end_ym = _get_time_value(time_cfg, "end_ym", "")
    if not start_ym and not end_ym:
        return entries

    filtered = []
    for entry in entries:
        if start_ym and entry.ym < start_ym:
            continue
        if end_ym and entry.ym > end_ym:
            continue
        filtered.append(entry)
    return filtered


__all__ = [
    "TimeEntry",
    "parse_ym_range",
    "detect_gfc_files",
    "extract_ym_from_gfc",
    "build_time_index",
    "summarize_time_coverage",
]
