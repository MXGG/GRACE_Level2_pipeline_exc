"""
Basin mask generation.
"""

import numpy as np
from matplotlib.path import Path as MplPath

from grace_pipeline.basin.boundary import BasinBoundary


def _split_parts(boundary: BasinBoundary):
    if getattr(boundary, "parts", None):
        out = []
        for poly in boundary.parts:
            arr = np.asarray(poly, dtype=float)
            if arr.ndim == 2 and arr.shape[1] >= 2 and arr.shape[0] >= 3:
                out.append(arr[:, :2])
        if out:
            return out

    lon = np.asarray(boundary.lon, dtype=float).ravel()
    lat = np.asarray(boundary.lat, dtype=float).ravel()
    if lon.size != lat.size or lon.size < 3:
        return []

    nan = np.isnan(lon) | np.isnan(lat)
    if not np.any(nan):
        return [np.column_stack((lon, lat))]

    parts = []
    start = 0
    for idx in np.where(nan)[0]:
        if idx - start >= 3:
            parts.append(np.column_stack((lon[start:idx], lat[start:idx])))
        start = idx + 1
    if lon.size - start >= 3:
        parts.append(np.column_stack((lon[start:], lat[start:])))
    return parts


def make_mask(
    boundary: BasinBoundary,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray
) -> np.ndarray:
    """Create binary mask for a basin boundary.
    
    Args:
        boundary: BasinBoundary object
        lon_vec: Longitude vector
        lat_vec: Latitude vector
        
    Returns:
        Boolean mask [nLon, nLat]
    """
    nLon = len(lon_vec)
    nLat = len(lat_vec)
    
    # Create grid mesh
    lon_grid, lat_grid = np.meshgrid(lon_vec, lat_vec, indexing='ij')
    
    # Flatten grid points
    points = np.column_stack((lon_grid.flatten(), lat_grid.flatten()))
    
    mask_flat = np.zeros(points.shape[0], dtype=bool)
    parts = _split_parts(boundary)
    for poly_points in parts:
        if poly_points.shape[0] < 3:
            continue
        # Quick bbox reject to reduce expensive point-in-polygon calls.
        min_lon = float(np.nanmin(poly_points[:, 0]))
        max_lon = float(np.nanmax(poly_points[:, 0]))
        min_lat = float(np.nanmin(poly_points[:, 1]))
        max_lat = float(np.nanmax(poly_points[:, 1]))
        cand = (
            (points[:, 0] >= min_lon)
            & (points[:, 0] <= max_lon)
            & (points[:, 1] >= min_lat)
            & (points[:, 1] <= max_lat)
        )
        if not np.any(cand):
            continue
        cand_idx = np.where(cand)[0]
        path = MplPath(poly_points)
        cand_points = points[cand_idx]
        inside = path.contains_points(cand_points, radius=0.0) | path.contains_points(cand_points, radius=-1e-9)
        if np.any(inside):
            mask_flat[cand_idx[inside]] = True
    
    mask = mask_flat.reshape(nLon, nLat)
    
    return mask
