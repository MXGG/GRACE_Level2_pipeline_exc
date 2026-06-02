"""
GRACE Level-2 Satellite Gravity Data Processing Pipeline

A comprehensive Python toolkit for processing GRACE/GRACE-FO satellite gravity data,
including spherical harmonic inversion, filtering, leakage correction, and basin analysis.
"""

__version__ = "1.0.0"
__author__ = "GRACE Pipeline Team"

__all__ = [
    "__version__",
    "Config",
    "load_config",
    "run_pipeline",
    "start_gui",
]


def Config(*args, **kwargs):
    """Lazy import wrapper to avoid heavy imports at package import time."""
    from grace_pipeline.infra.config import Config as _Config
    return _Config(*args, **kwargs)


def load_config(*args, **kwargs):
    """Lazy import wrapper to avoid heavy imports at package import time."""
    from grace_pipeline.infra.config import load_config as _load_config
    return _load_config(*args, **kwargs)


def run_pipeline(*args, **kwargs):
    """Lazy import wrapper to avoid heavy imports at package import time."""
    from grace_pipeline.app.pipeline import run_pipeline as _run_pipeline
    return _run_pipeline(*args, **kwargs)


def start_gui(*args, **kwargs):
    """Lazy GUI entrypoint."""
    from grace_pipeline.gui import start_gui as _start_gui
    return _start_gui(*args, **kwargs)
