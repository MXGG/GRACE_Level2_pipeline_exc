"""Compatibility shim for canonical infra.stack.state."""

from grace_pipeline.infra.stack.state import _get_stack_data, _on_stack_var_change, _set_stack_var_options, load_stack_info

__all__ = ["load_stack_info", "_set_stack_var_options", "_on_stack_var_change", "_get_stack_data"]
