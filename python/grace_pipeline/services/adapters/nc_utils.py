"""Shared NetCDF metadata helpers for stack services."""


def var_attr_lower(var, key: str) -> str:
    """Safely read variable attribute and normalize to lowercase text."""
    return str(getattr(var, key, "") or "").lower()
