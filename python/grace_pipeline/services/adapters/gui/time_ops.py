"""Compatibility shim for canonical infra.runtime.time_ops."""

from grace_pipeline.infra.runtime.time_ops import (
    build_scope_signature,
    build_time_from_fallback,
    file_fingerprint,
    infer_time_axis_for_rate,
    infer_time_labels,
    parse_ym,
    resolve_output_file,
    resolve_time,
)

__all__ = [
    "parse_ym",
    "build_time_from_fallback",
    "resolve_time",
    "resolve_output_file",
    "infer_time_labels",
    "infer_time_axis_for_rate",
    "file_fingerprint",
    "build_scope_signature",
]
