"""Application-layer public exports.

Keep this package lightweight so UI imports do not eagerly pull optional
pipeline dependencies.
"""

__all__ = ["PipelineOutput", "run_pipeline"]


def __getattr__(name):
    if name in {"PipelineOutput", "run_pipeline"}:
        from grace_pipeline.app import pipeline as _pipeline

        return getattr(_pipeline, name)
    raise AttributeError(name)
