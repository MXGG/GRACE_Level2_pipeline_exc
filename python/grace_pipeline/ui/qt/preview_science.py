"""Scientific-integrity helpers shared by Preview renderers.

The GUI loaders intentionally accept a broad range of research data formats.
This module keeps two pieces of interpretation out of the drawing code:

* calendar-month matching for independent raster stacks; and
* value-unit discovery without inventing a unit when none was supplied.

It also provides one resource-safe entry point for ``pyshp.Reader`` so every
Preview renderer closes the underlying SHP/SHX/DBF handles on Windows.
"""

from __future__ import annotations

import contextlib
import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

import numpy as np

from grace_pipeline.infra.stack.loader import (
    _attribute_case_insensitive,
    _json_metadata,
)


DEFAULT_LAYER_TIME_TOLERANCE_MONTHS = 1


@dataclass(frozen=True, order=True)
class YearMonth:
    """A calendar month with a stable integer distance representation."""

    year: int
    month: int

    def __post_init__(self) -> None:
        if not 1 <= int(self.month) <= 12:
            raise ValueError(f"Invalid calendar month: {self.month}")

    @property
    def ordinal(self) -> int:
        return int(self.year) * 12 + int(self.month) - 1

    def __str__(self) -> str:
        return f"{int(self.year):04d}-{int(self.month):02d}"


@dataclass(frozen=True)
class LayerTimeMatch:
    """Result of selecting one independently timed raster layer slice."""

    index: int | None
    method: str
    target_month: YearMonth | None = None
    matched_month: YearMonth | None = None
    distance_months: int | None = None
    message: str = ""

    @property
    def matched(self) -> bool:
        return self.index is not None


def _decode_scalar(value: Any) -> Any:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, (bytes, bytearray, np.bytes_)):
        return bytes(value).decode("utf-8", errors="replace").strip("\x00 ")
    return value


def _month_from_cf_number(value: float, units: str, calendar: str | None) -> YearMonth | None:
    try:
        from netCDF4 import num2date

        decoded = num2date(value, units=units, calendar=calendar or "standard")
        return YearMonth(int(decoded.year), int(decoded.month))
    except Exception:
        pass

    match = re.match(
        r"^\s*(days?|hours?|minutes?|seconds?|months?)\s+since\s+"
        r"(\d{4})-(\d{1,2})(?:-(\d{1,2}))?",
        str(units or ""),
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    scale, year_text, month_text, day_text = match.groups()
    try:
        origin = datetime(int(year_text), int(month_text), int(day_text or 1))
        scale = scale.lower()
        if scale.startswith("month"):
            month_offset = int(round(float(value)))
            ordinal = origin.year * 12 + origin.month - 1 + month_offset
            return YearMonth(ordinal // 12, ordinal % 12 + 1)
        seconds = float(value)
        if scale.startswith("day"):
            seconds *= 86400.0
        elif scale.startswith("hour"):
            seconds *= 3600.0
        elif scale.startswith("minute"):
            seconds *= 60.0
        decoded = origin + timedelta(seconds=seconds)
        return YearMonth(decoded.year, decoded.month)
    except Exception:
        return None


def month_from_value(value: Any, *, units: str | None = None, calendar: str | None = None) -> YearMonth | None:
    """Interpret a common stack time value as a calendar month.

    Supported values include datetime/cftime objects, ``numpy.datetime64``,
    ``YYYY-MM``/``YYYYMM`` strings, CF numeric coordinates, and decimal years.
    Values that cannot be interpreted are deliberately returned as ``None``.
    """

    value = _decode_scalar(value)
    if value is None:
        return None
    if isinstance(value, np.datetime64):
        if np.isnat(value):
            return None
        text = np.datetime_as_string(value, unit="D")
        match = re.match(r"^(\d{4})-(\d{2})", text)
        return YearMonth(int(match.group(1)), int(match.group(2))) if match else None
    if isinstance(value, (datetime, date)):
        return YearMonth(int(value.year), int(value.month))
    if hasattr(value, "year") and hasattr(value, "month"):
        with contextlib.suppress(Exception):
            return YearMonth(int(value.year), int(value.month))

    if isinstance(value, str):
        text = value.strip().strip("[](){}'\"")
        if not text:
            return None
        match = re.search(r"(?<!\d)(\d{4})[-/_.](\d{1,2})(?!\d)", text)
        if match:
            with contextlib.suppress(ValueError):
                return YearMonth(int(match.group(1)), int(match.group(2)))
        match = re.fullmatch(r"(\d{4})(\d{2})", text)
        if match:
            with contextlib.suppress(ValueError):
                return YearMonth(int(match.group(1)), int(match.group(2)))
        # ISO timestamps and labels normally begin with YYYY-MM.
        match = re.match(r"^(\d{4})-(\d{1,2})", text)
        if match:
            with contextlib.suppress(ValueError):
                return YearMonth(int(match.group(1)), int(match.group(2)))
        with contextlib.suppress(ValueError):
            value = float(text)
        if isinstance(value, str):
            return None

    if isinstance(value, (int, float, np.integer, np.floating)):
        number = float(value)
        if not math.isfinite(number):
            return None
        if units and "since" in str(units).lower():
            return _month_from_cf_number(number, str(units), calendar)
        rounded = int(round(number))
        if abs(number - rounded) < 1.0e-8 and 100001 <= rounded <= 999912:
            year, month = divmod(rounded, 100)
            with contextlib.suppress(ValueError):
                return YearMonth(year, month)
        if 1800.0 <= number < 2501.0:
            year = int(math.floor(number))
            fraction = max(0.0, min(0.999999999, number - year))
            month = min(12, int(math.floor(fraction * 12.0)) + 1)
            return YearMonth(year, month)
    return None


def _flatten_time_values(values: Any) -> list[Any]:
    if values is None:
        return []
    arr = np.asarray(values)
    if arr.ndim == 0:
        return [_decode_scalar(arr.item())]
    # MATLAB character matrices often arrive as one character per cell.
    if arr.ndim == 2 and arr.dtype.kind in {"U", "S"}:
        decoded = np.vectorize(_decode_scalar, otypes=[object])(arr)
        if all(len(str(item)) <= 1 for item in decoded.reshape(-1)):
            return ["".join(str(item) for item in row).strip() for row in decoded]
    return [_decode_scalar(item) for item in arr.reshape(-1)]


def select_layer_time_index(
    target_value: Any,
    layer_values: Any,
    *,
    requested_index: int,
    layer_length: int,
    tolerance_months: int = DEFAULT_LAYER_TIME_TOLERANCE_MONTHS,
    target_units: str | None = None,
    target_calendar: str | None = None,
    layer_units: str | None = None,
    layer_calendar: str | None = None,
) -> LayerTimeMatch:
    """Select an overlay slice without ever clamping to its final frame.

    Calendar matches are exact first, then nearest within ``tolerance_months``.
    A one-frame layer is treated as static. Positional fallback is used only
    when month matching is impossible and the requested index is actually in
    range; it is marked as unverified so renderers can surface that fact.
    """

    length = max(0, int(layer_length))
    requested = int(requested_index)
    tolerance = max(0, int(tolerance_months))
    if length <= 0:
        return LayerTimeMatch(None, "unmatched", message="Layer contains no time slices.")
    if length == 1:
        return LayerTimeMatch(0, "static", message="Single-slice layer treated as static.")

    target_month = month_from_value(target_value, units=target_units, calendar=target_calendar)
    raw_candidates = _flatten_time_values(layer_values)[:length]
    parsed_candidates = [
        month_from_value(item, units=layer_units, calendar=layer_calendar)
        for item in raw_candidates
    ]
    has_parsed_candidate = any(item is not None for item in parsed_candidates)

    if target_month is not None and has_parsed_candidate:
        exact = [i for i, item in enumerate(parsed_candidates) if item == target_month]
        if exact:
            index = exact[0]
            return LayerTimeMatch(index, "exact", target_month, parsed_candidates[index], 0)
        ranked = sorted(
            (
                (abs(item.ordinal - target_month.ordinal), i, item)
                for i, item in enumerate(parsed_candidates)
                if item is not None
            ),
            key=lambda row: (row[0], row[1]),
        )
        if ranked and ranked[0][0] <= tolerance:
            distance, index, matched_month = ranked[0]
            return LayerTimeMatch(index, "nearest", target_month, matched_month, int(distance))
        nearest_text = str(ranked[0][2]) if ranked else "none"
        distance_text = str(ranked[0][0]) if ranked else "unknown"
        return LayerTimeMatch(
            None,
            "unmatched",
            target_month=target_month,
            message=(
                f"No layer month is within {tolerance} month(s) of {target_month}; "
                f"nearest is {nearest_text} ({distance_text} month(s))."
            ),
        )

    if 0 <= requested < length:
        reason = "target month unavailable" if target_month is None else "layer time metadata is not interpretable"
        return LayerTimeMatch(
            requested,
            "positional-unverified",
            target_month=target_month,
            message=f"Using in-range positional slice {requested + 1}/{length}; {reason}.",
        )
    return LayerTimeMatch(
        None,
        "unmatched",
        target_month=target_month,
        message=(
            f"Requested positional slice {requested + 1} is outside the layer's "
            f"1..{length} range; the index was not clamped."
        ),
    )


def _clean_unit(value: Any) -> str:
    value = _decode_scalar(value)
    if value is None:
        return ""
    if isinstance(value, np.ndarray):
        if value.size != 1:
            return ""
        value = _decode_scalar(value.reshape(-1)[0])
    text = str(value).strip().strip("\x00")
    return "" if text.lower() in {"", "none", "null", "unknown", "n/a"} else text


def unit_from_metadata(meta: dict | None, var_name: str = "") -> str:
    """Return a supplied value unit, or an empty string when none is known."""

    if not isinstance(meta, dict):
        return ""
    folded = {str(key).strip().lower(): value for key, value in meta.items()}
    for key in ("units", "unit", "data_units", "ewh_unit", "value_unit"):
        unit = _clean_unit(folded.get(key))
        if unit:
            return unit

    wanted = str(var_name or folded.get("active_var") or "").strip().lower()
    for key in ("var_units", "variable_units", "units_by_variable"):
        mapping = folded.get(key)
        if isinstance(mapping, dict):
            for name, value in mapping.items():
                if not wanted or str(name).strip().lower() == wanted:
                    unit = _clean_unit(value)
                    if unit:
                        return unit

    variables = folded.get("variables") or folded.get("data_variables")
    if isinstance(variables, dict):
        for name, details in variables.items():
            if wanted and str(name).strip().lower() != wanted:
                continue
            if isinstance(details, dict):
                unit = unit_from_metadata(details, str(name))
            else:
                unit = _clean_unit(details)
            if unit:
                return unit

    for key in ("meta", "metadata", "attrs", "attributes"):
        nested = folded.get(key)
        if isinstance(nested, dict) and nested is not meta:
            unit = unit_from_metadata(nested, var_name)
            if unit:
                return unit
    for key in ("meta_json", "metadata_json"):
        nested = _json_metadata(folded.get(key))
        if nested:
            unit = unit_from_metadata(nested, var_name)
            if unit:
                return unit
    return ""


def variable_unit_from_file(path: str, var_name: str) -> str:
    """Read a selected variable's unit attribute without loading its data."""

    p = Path(str(path or "").strip())
    name = str(var_name or "").strip()
    if not name or not p.is_file():
        return ""
    suffix = p.suffix.lower()
    if suffix in {".nc", ".nc4", ".cdf", ".hdf", ".h5", ".hdf5", ".he5"}:
        try:
            import netCDF4 as nc

            with contextlib.closing(nc.Dataset(str(p))) as dataset:
                if name in dataset.variables:
                    variable = dataset.variables[name]
                    for attr in ("units", "unit"):
                        unit = _clean_unit(
                            _attribute_case_insensitive(variable, attr, None)
                        )
                        if unit:
                            return unit
        except Exception:
            pass
    if suffix == ".mat":
        try:
            import scipy.io as sio

            unit_keys = [
                "units",
                "unit",
                "data_units",
                "ewh_unit",
                "value_unit",
                "var_units",
                "variable_units",
                "meta_json",
                "metadata_json",
            ]
            raw = sio.loadmat(
                p,
                squeeze_me=True,
                struct_as_record=False,
                variable_names=["meta", "metadata", *unit_keys],
            )
            supplied = {key: raw[key] for key in unit_keys if key in raw}
            unit = unit_from_metadata(supplied, name)
            if unit:
                return unit
            for key in ("meta", "metadata"):
                meta_value = _decode_scalar(raw.get(key))
                if isinstance(meta_value, str):
                    with contextlib.suppress(Exception):
                        parsed = json.loads(meta_value)
                        unit = unit_from_metadata(parsed, name)
                        if unit:
                            return unit
                if hasattr(meta_value, "_fieldnames"):
                    mapping = {
                        field: getattr(meta_value, field, None)
                        for field in getattr(meta_value, "_fieldnames", [])
                    }
                    unit = unit_from_metadata(mapping, name)
                    if unit:
                        return unit
        except Exception:
            pass
    if suffix in {".h5", ".hdf5", ".hdf", ".he5", ".mat"}:
        try:
            import h5py

            with h5py.File(p, "r") as handle:
                file_meta = _json_metadata(
                    _attribute_case_insensitive(handle, "meta_json", "")
                )
                unit = unit_from_metadata(file_meta, name)
                if unit:
                    return unit
                candidates = [name, f"P/grid/{name}", f"Stack/{name}"]
                for key in candidates:
                    if key not in handle:
                        continue
                    dataset = handle[key]
                    for attr in ("units", "unit"):
                        unit = _clean_unit(
                            _attribute_case_insensitive(dataset, attr, None)
                        )
                        if unit:
                            return unit
        except Exception:
            pass
    return ""


def value_label(var_name: str, unit: str = "") -> str:
    name = str(var_name or "value").strip() or "value"
    clean = _clean_unit(unit)
    return f"{name} ({clean})" if clean else name


@contextlib.contextmanager
def open_shapefile_reader(path: str | Path, *args, **kwargs) -> Iterator[Any]:
    """Open a pyshp reader and always release all of its file handles."""

    import shapefile

    reader = shapefile.Reader(str(path), *args, **kwargs)
    try:
        yield reader
    finally:
        close = getattr(reader, "close", None)
        if callable(close):
            with contextlib.suppress(Exception):
                close()
