"""
Basin boundary reading and processing.
"""

import os
import contextlib
import math
import re
from collections import OrderedDict
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

try:
    import shapefile
except ImportError:
    shapefile = None

@dataclass
class BasinBoundary:
    """Basin boundary polygon."""
    name: str
    lon: np.ndarray
    lat: np.ndarray
    # Optional multi-part geometry, each item is [N x 2] lon/lat polygon.
    parts: List[np.ndarray] = field(default_factory=list)

def wrap_lon(lon: np.ndarray) -> np.ndarray:
    """Wrap longitude to [-180, 180]."""
    return ((lon + 180) % 360) - 180


_NAME_FIELD_CANDIDATES = [
    "NAME",
    "Name",
    "name",
    "BASIN",
    "BASIN_NAME",
    "BasinName",
    "HYBAS_NAME",
    "whymap_r_2",
    "whymap_riv",
    "river_name",
    "RiverName",
    "Id",
    "ID",
    "OBJECTID",
]

def read_boundary(file_path: str, name_field: str = 'Name') -> List[BasinBoundary]:
    """Read basin boundary from .shp/.txt/.bln file.
    
    Args:
        file_path: Path to file
        name_field: Field name for basin name (for shapefiles)
        
    Returns:
        List of BasinBoundary objects
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Boundary file not found: {file_path}")
        
    ext = path.suffix.lower()
    
    if ext == '.shp':
        return read_shapefile(str(path), name_field)
    if ext == '.bln':
        return read_bln(str(path))
    return read_txt_poly(str(path))


def resolve_shapefile_name_field(file_path: str, name_field: str = "Name") -> str:
    """Return the field that should be used as the basin display name."""
    if shapefile is None:
        raise ImportError("pyshp is required to read shapefiles. Install with: pip install pyshp")
    sf = shapefile.Reader(file_path)
    try:
        fields = [f[0] for f in sf.fields[1:]]
    finally:
        with contextlib.suppress(Exception):
            sf.close()
    requested = str(name_field or "").strip()
    if requested:
        for field in fields:
            if field.lower() == requested.lower():
                return field
    for candidate in _NAME_FIELD_CANDIDATES:
        for field in fields:
            if field.lower() == candidate.lower():
                return field
    return fields[0] if fields else ""


def _record_display_name(rec, fields: list[str], preferred_idx: int, fallback: str) -> str:
    order: list[int] = []
    if preferred_idx >= 0:
        order.append(preferred_idx)
    lower_fields = {field.lower(): idx for idx, field in enumerate(fields)}
    for candidate in _NAME_FIELD_CANDIDATES:
        idx = lower_fields.get(candidate.lower())
        if idx is not None and idx not in order:
            order.append(idx)
    for idx in order:
        try:
            value = str(rec[idx]).strip()
        except Exception:
            value = ""
        if value and value.lower() not in {"none", "nan", "null"}:
            return value
    return fallback

def _is_number(val: str) -> bool:
    try:
        float(val)
        return True
    except Exception:
        return False


def _generated_boundary_name(name: str) -> bool:
    return str(name or "").strip().lower().startswith("poly_")


def _merge_duplicate_named_boundaries(boundaries: List[BasinBoundary]) -> List[BasinBoundary]:
    """Merge multipart shapefile records that share one basin name."""

    groups: "OrderedDict[str, List[BasinBoundary]]" = OrderedDict()
    generated: List[BasinBoundary] = []
    for boundary in boundaries:
        name = str(boundary.name or "").strip()
        if not name or _generated_boundary_name(name):
            generated.append(boundary)
            continue
        groups.setdefault(name, []).append(boundary)

    named_count = sum(len(items) for items in groups.values())
    has_duplicates = any(len(items) > 1 for items in groups.values())
    if not groups or not has_duplicates:
        return boundaries

    merged: List[BasinBoundary] = []
    for name, items in groups.items():
        parts: List[np.ndarray] = []
        lon_cat: List[float] = []
        lat_cat: List[float] = []
        for item in items:
            item_parts = item.parts or [
                np.column_stack(
                    (
                        np.asarray(item.lon, dtype=float),
                        np.asarray(item.lat, dtype=float),
                    )
                )
            ]
            for part in item_parts:
                arr = np.asarray(part, dtype=float)
                if arr.ndim != 2 or arr.shape[0] < 3 or arr.shape[1] < 2:
                    continue
                clean = arr[:, :2]
                parts.append(clean)
                if lon_cat:
                    lon_cat.append(np.nan)
                    lat_cat.append(np.nan)
                lon_cat.extend(clean[:, 0].tolist())
                lat_cat.extend(clean[:, 1].tolist())
        if parts:
            merged.append(
                BasinBoundary(
                    name=name,
                    lon=np.asarray(lon_cat, dtype=float),
                    lat=np.asarray(lat_cat, dtype=float),
                    parts=parts,
                )
            )

    # Some regional boundary products store hundreds of unnamed fragments next
    # to a small set of named basins. In that case the named field is the user's
    # intended grouping key, so keeping generated poly_* rows makes the UI noisy.
    if generated and len(generated) <= max(3, len(merged)) and named_count <= len(merged) * 3:
        merged.extend(generated)
    return merged or boundaries


def _wkt_param(text: str, name: str, default: float) -> float:
    match = re.search(rf'PARAMETER\["{re.escape(name)}",\s*([-+0-9.eE]+)\]', text or "")
    return float(match.group(1)) if match else float(default)


def _wkt_spheroid(text: str) -> tuple[float, float]:
    match = re.search(r'SPHEROID\["[^"]+",\s*([-+0-9.eE]+),\s*([-+0-9.eE]+)\]', text or "")
    if not match:
        return 6378137.0, 298.257223563
    return float(match.group(1)), float(match.group(2))


def _albers_q(phi: np.ndarray | float, e: float, e2: float):
    sin_phi = np.sin(phi)
    if abs(e) < 1.0e-14:
        return 2.0 * sin_phi
    return (1.0 - e2) * (
        sin_phi / (1.0 - e2 * sin_phi * sin_phi)
        - (1.0 / (2.0 * e)) * np.log((1.0 - e * sin_phi) / (1.0 + e * sin_phi))
    )


def _inverse_albers_points(points: np.ndarray, prj_text: str) -> np.ndarray:
    a, inv_f = _wkt_spheroid(prj_text)
    f = 1.0 / inv_f if inv_f else 0.0
    e2 = max(0.0, 2.0 * f - f * f)
    e = math.sqrt(e2)
    lon0 = math.radians(_wkt_param(prj_text, "Central_Meridian", 0.0))
    lat0 = math.radians(_wkt_param(prj_text, "Latitude_Of_Origin", 0.0))
    lat1 = math.radians(_wkt_param(prj_text, "Standard_Parallel_1", 0.0))
    lat2 = math.radians(_wkt_param(prj_text, "Standard_Parallel_2", 0.0))
    false_easting = _wkt_param(prj_text, "False_Easting", 0.0)
    false_northing = _wkt_param(prj_text, "False_Northing", 0.0)

    def m(phi):
        return math.cos(phi) / math.sqrt(max(1.0e-30, 1.0 - e2 * math.sin(phi) ** 2))

    q0 = float(_albers_q(lat0, e, e2))
    q1 = float(_albers_q(lat1, e, e2))
    q2 = float(_albers_q(lat2, e, e2))
    m1 = m(lat1)
    m2 = m(lat2)
    if abs(lat1 - lat2) < 1.0e-12:
        n = math.sin(lat1)
    else:
        n = (m1 * m1 - m2 * m2) / (q2 - q1)
    c = m1 * m1 + n * q1
    rho0 = a * math.sqrt(max(0.0, c - n * q0)) / n

    x = np.asarray(points[:, 0], dtype=float) - false_easting
    y = np.asarray(points[:, 1], dtype=float) - false_northing
    rho = np.sign(n) * np.sqrt(x * x + (rho0 - y) * (rho0 - y))
    theta = np.arctan2(x, rho0 - y)
    q = (c - (rho * n / a) ** 2) / n

    # Newton solve authalic latitude from q(phi).
    phi = np.arcsin(np.clip(q / 2.0, -1.0, 1.0))
    for _ in range(12):
        current = _albers_q(phi, e, e2)
        delta = 1.0e-7
        deriv = (_albers_q(phi + delta, e, e2) - _albers_q(phi - delta, e, e2)) / (2.0 * delta)
        step = np.where(np.abs(deriv) > 1.0e-12, (current - q) / deriv, 0.0)
        phi = np.clip(phi - step, -math.pi / 2.0, math.pi / 2.0)
        if float(np.nanmax(np.abs(step))) < 1.0e-12:
            break

    lon = np.degrees(lon0 + theta / n)
    lat = np.degrees(phi)
    return np.column_stack((lon, lat))


def _shape_points_to_lonlat(file_path: str, points: np.ndarray) -> np.ndarray:
    arr = np.asarray(points, dtype=float)
    if arr.ndim != 2 or arr.shape[1] < 2:
        return arr
    if (
        np.nanmin(arr[:, 0]) >= -180.0
        and np.nanmax(arr[:, 0]) <= 360.0
        and np.nanmin(arr[:, 1]) >= -90.0
        and np.nanmax(arr[:, 1]) <= 90.0
    ):
        return np.column_stack((wrap_lon(arr[:, 0]), arr[:, 1]))
    prj_path = Path(file_path).with_suffix(".prj")
    prj_text = prj_path.read_text(encoding="utf-8", errors="ignore") if prj_path.exists() else ""
    if 'PROJECTION["Albers"]' in prj_text or 'PROJECTION["Albers_Conic_Equal_Area"]' in prj_text:
        projected = _inverse_albers_points(arr[:, :2], prj_text)
        return np.column_stack((wrap_lon(projected[:, 0]), projected[:, 1]))
    return np.column_stack((wrap_lon(arr[:, 0]), arr[:, 1]))

def read_bln(file_path: str) -> List[BasinBoundary]:
    """Read Surfer BLN boundary file.

    Format: each polygon starts with a header line "N, name" or "N, flag",
    followed by N lines of lon/lat pairs.
    """
    boundaries: List[BasinBoundary] = []
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = [ln.strip() for ln in f.readlines()]

    i = 0
    count = 1
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith("#"):
            i += 1
            continue
        parts = line.replace(",", " ").split()
        if len(parts) < 1 or not _is_number(parts[0]):
            # Not a BLN header -> fallback to txt poly format
            return read_txt_poly(file_path)
        try:
            npts = int(round(float(parts[0])))
        except Exception:
            return read_txt_poly(file_path)
        name = f"poly_{count}"
        if len(parts) >= 2 and parts[1]:
            if not _is_number(parts[1]):
                name = parts[1].strip().strip("\"'") or name
        coords = []
        i += 1
        for _ in range(npts):
            if i >= len(lines):
                break
            row = lines[i].replace(",", " ").split()
            i += 1
            if len(row) < 2:
                continue
            try:
                lon = float(row[0])
                lat = float(row[1])
            except Exception:
                continue
            coords.append((lon, lat))
        if coords:
            arr = np.array(coords, dtype=float)
            boundaries.append(BasinBoundary(name=name, lon=wrap_lon(arr[:, 0]), lat=arr[:, 1]))
            count += 1
    if not boundaries:
        return read_txt_poly(file_path)
    return boundaries

def read_shapefile(file_path: str, name_field: str) -> List[BasinBoundary]:
    """Read ESRI Shapefile."""
    if shapefile is None:
        raise ImportError("pyshp is required to read shapefiles. Install with: pip install pyshp")
        
    sf = shapefile.Reader(file_path)
    try:
        boundaries = []

        # Check fields
        fields = [f[0] for f in sf.fields[1:]] # Skip DeletionFlag
        name_idx = -1
        resolved_name_field = resolve_shapefile_name_field(file_path, name_field)

        # Try to find name field (case insensitive)
        for i, f in enumerate(fields):
            if f.lower() == resolved_name_field.lower():
                name_idx = i
                break

        for i, shape in enumerate(sf.shapes()):
            rec = sf.record(i)

            name = _record_display_name(rec, fields, name_idx, f"poly_{i+1}")

            # Extract coordinates
            # shape.points is list of (x, y)
            if not shape.points:
                continue

            points = np.asarray(shape.points, dtype=float)
            if points.ndim != 2 or points.shape[1] < 2:
                continue
            lonlat = _shape_points_to_lonlat(file_path, points)
            lon_all = lonlat[:, 0]
            lat_all = lonlat[:, 1]

            # Keep one basin per shape-record. Multipart polygons are retained as
            # one logical basin (fixes 112-basin shapefile being split to 124).
            part_starts = list(shape.parts) if shape.parts is not None else [0]
            if not part_starts:
                part_starts = [0]
            part_starts.append(len(points))

            part_polys: List[np.ndarray] = []
            lon_cat: List[float] = []
            lat_cat: List[float] = []
            for k in range(len(part_starts) - 1):
                start = int(part_starts[k])
                end = int(part_starts[k + 1])
                if end - start < 3:
                    continue
                sub_lon = lon_all[start:end]
                sub_lat = lat_all[start:end]
                poly = np.column_stack((sub_lon, sub_lat))
                part_polys.append(poly)
                if lon_cat:
                    lon_cat.append(np.nan)
                    lat_cat.append(np.nan)
                lon_cat.extend(sub_lon.tolist())
                lat_cat.extend(sub_lat.tolist())

            if not part_polys:
                continue

            boundaries.append(
                BasinBoundary(
                    name=name,
                    lon=np.asarray(lon_cat, dtype=float),
                    lat=np.asarray(lat_cat, dtype=float),
                    parts=part_polys,
                )
            )

        return _merge_duplicate_named_boundaries(boundaries)
    finally:
        with contextlib.suppress(Exception):
            sf.close()

def read_txt_poly(file_path: str) -> List[BasinBoundary]:
    """Read polygon from text file (lon lat columns)."""
    try:
        data = np.loadtxt(file_path)
    except ValueError:
        # Try skipping header
        data = np.loadtxt(file_path, skiprows=1)
        
    if data.shape[1] < 2:
        raise ValueError("Text file must have at least 2 columns (lon, lat)")
        
    lon = wrap_lon(data[:, 0])
    lat = data[:, 1]
    
    # Split by NaNs
    nan_mask = np.isnan(lon) | np.isnan(lat)
    
    boundaries = []
    if not np.any(nan_mask):
        boundaries.append(BasinBoundary(name="poly_1", lon=lon, lat=lat))
    else:
        # Split logic
        indices = np.where(nan_mask)[0]
        start = 0
        count = 1
        
        # Add end if not present
        if indices[-1] != len(lon) - 1:
            indices = np.append(indices, len(lon))
            
        for idx in indices:
            if idx > start:
                sub_lon = lon[start:idx]
                sub_lat = lat[start:idx]
                boundaries.append(BasinBoundary(name=f"poly_{count}", lon=sub_lon, lat=sub_lat))
                count += 1
            start = idx + 1
            
    return boundaries
