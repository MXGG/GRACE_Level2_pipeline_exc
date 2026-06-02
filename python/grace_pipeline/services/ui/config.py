"""Compatibility shim for canonical ui.controllers.config."""

from grace_pipeline.ui.controllers.config import _collect_config_dict, _update_config, load_config_file

__all__ = ["load_config_file", "_update_config", "_collect_config_dict"]
