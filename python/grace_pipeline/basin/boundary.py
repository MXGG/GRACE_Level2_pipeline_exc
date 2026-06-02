"""
Basin boundary reading and processing.
"""

import os
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

def _is_number(val: str) -> bool:
    try:
        float(val)
        return True
    except Exception:
        return False

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
    boundaries = []
    
    # Check fields
    fields = [f[0] for f in sf.fields[1:]] # Skip DeletionFlag
    name_idx = -1
    
    # Try to find name field (case insensitive)
    for i, f in enumerate(fields):
        if f.lower() == name_field.lower():
            name_idx = i
            break
            
    # Fallback name fields
    if name_idx == -1:
        for candidate in ['NAME', 'Name', 'name', 'Id', 'ID', 'OBJECTID']:
            for i, f in enumerate(fields):
                if f == candidate:
                    name_idx = i
                    break
            if name_idx != -1:
                break
    
    for i, shape in enumerate(sf.shapes()):
        rec = sf.record(i)
        
        # Get name
        if name_idx != -1:
            name = str(rec[name_idx])
        else:
            name = f"poly_{i+1}"
            
        # Extract coordinates
        # shape.points is list of (x, y)
        if not shape.points:
            continue

        points = np.asarray(shape.points, dtype=float)
        if points.ndim != 2 or points.shape[1] < 2:
            continue
        lon_all = wrap_lon(points[:, 0])
        lat_all = points[:, 1]

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
                
    return boundaries

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
