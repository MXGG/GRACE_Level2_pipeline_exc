"""Compatibility exports for the legacy main package."""

from grace_pipeline.app.pipeline import PipelineOutput, run_pipeline

__all__ = [
    "run_pipeline",
    "PipelineOutput",
]
