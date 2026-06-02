"""Canonical time-index exports."""

from grace_pipeline.core.time_index import (
    TimeEntry,
    build_time_index,
    detect_gfc_files,
    extract_ym_from_gfc,
    parse_ym_range,
    summarize_time_coverage,
)

__all__ = [
    "TimeEntry",
    "parse_ym_range",
    "detect_gfc_files",
    "extract_ym_from_gfc",
    "build_time_index",
    "summarize_time_coverage",
]
