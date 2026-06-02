"""Canonical NetCDF metadata helpers."""


def var_attr_lower(var, key: str) -> str:
    """Safely read a variable attribute and normalize it to lowercase text."""
    return str(getattr(var, key, "") or "").lower()
