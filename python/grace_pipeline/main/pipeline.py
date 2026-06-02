"""Legacy pipeline compatibility shim.

Canonical orchestration now lives in ``grace_pipeline.app.pipeline``.
"""

from grace_pipeline.app.pipeline import OutputPaths, PipelineOutput, run_pipeline

__all__ = ["OutputPaths", "PipelineOutput", "run_pipeline"]
