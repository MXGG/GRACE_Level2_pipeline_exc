"""
Grid utilities for GRACE data processing.
"""

import numpy as np
from typing import Tuple, Union


def make_lonlat_vec(cfg) -> Tuple[np.ndarray, np.ndarray]:
    """
    Create longitude and latitude vectors from configuration.
    
    Args:
        cfg: Configuration object with grid settings
    
    Returns:
        Tuple of (lon_vec, lat_vec) as 1D numpy arrays
    """
    grid_cfg = cfg.grid if hasattr(cfg, 'grid') else cfg.get('grid', {})
    
    # Get grid parameters
    if hasattr(grid_cfg, 'lon'):
        lon_range = grid_cfg.lon
        lat_range = grid_cfg.lat
        dlon = grid_cfg.dlon
        dlat = grid_cfg.dlat
    else:
        lon_range = grid_cfg.get('lon', [-179.5, 179.5])
        lat_range = grid_cfg.get('lat', [-89.5, 89.5])
        dlon = grid_cfg.get('dlon', 1.0)
        dlat = grid_cfg.get('dlat', 1.0)
    
    # Create vectors
    lon_vec = np.arange(lon_range[0], lon_range[1] + dlon/2, dlon)
    lat_vec = np.arange(lat_range[0], lat_range[1] + dlat/2, dlat)
    
    return lon_vec, lat_vec


def ensure_latlon_order(
    grid: np.ndarray, 
    lon_vec: np.ndarray, 
    lat_vec: np.ndarray,
    target_order: str = "lon_lat"
) -> np.ndarray:
    """
    Ensure grid data is in the expected dimension order.
    
    The pipeline uses [nLon x nLat x Nt] consistently.
    
    Args:
        grid: 2D or 3D grid data
        lon_vec: Longitude vector
        lat_vec: Latitude vector
        target_order: Target dimension order ('lon_lat' or 'lat_lon')
    
    Returns:
        Grid with correct dimension ordering
    """
    nLon = len(lon_vec)
    nLat = len(lat_vec)
    
    if grid.ndim == 2:
        # 2D case
        if grid.shape == (nLon, nLat):
            return grid if target_order == "lon_lat" else grid.T
        elif grid.shape == (nLat, nLon):
            return grid.T if target_order == "lon_lat" else grid
        else:
            # Unknown dimensions, return as-is
            return grid
    
    elif grid.ndim == 3:
        # 3D case [nLon, nLat, Nt] or [nLat, nLon, Nt]
        if grid.shape[0] == nLon and grid.shape[1] == nLat:
            return grid if target_order == "lon_lat" else np.transpose(grid, (1, 0, 2))
        elif grid.shape[0] == nLat and grid.shape[1] == nLon:
            return np.transpose(grid, (1, 0, 2)) if target_order == "lon_lat" else grid
        else:
            return grid
    
    return grid


def compute_grid_area(lon_vec: np.ndarray, lat_vec: np.ndarray) -> np.ndarray:
    """
    Compute area weight for each grid cell (in km^2 or relative).
    
    Args:
        lon_vec: Longitude vector in degrees
        lat_vec: Latitude vector in degrees
    
    Returns:
        2D array of cell areas [nLon, nLat]
    """
    # Earth radius in km
    R = 6371.0
    
    dlon = np.abs(np.mean(np.diff(lon_vec))) if len(lon_vec) > 1 else 1.0
    dlat = np.abs(np.mean(np.diff(lat_vec))) if len(lat_vec) > 1 else 1.0
    
    # Convert to radians
    dlon_rad = np.deg2rad(dlon)
    dlat_rad = np.deg2rad(dlat)
    
    # Area = R^2 * dlon * (sin(lat2) - sin(lat1))
    lat_rad = np.deg2rad(lat_vec)
    
    # For each latitude band
    area_lat = R**2 * dlon_rad * (
        np.sin(lat_rad + dlat_rad/2) - np.sin(lat_rad - dlat_rad/2)
    )
    
    # Broadcast to 2D [nLon, nLat]
    nLon = len(lon_vec)
    area = np.tile(area_lat, (nLon, 1))
    
    return np.abs(area)


def latlon_to_index(
    lon: Union[float, np.ndarray],
    lat: Union[float, np.ndarray],
    lon_vec: np.ndarray,
    lat_vec: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Convert lon/lat coordinates to grid indices.
    
    Args:
        lon: Longitude value(s)
        lat: Latitude value(s)
        lon_vec: Longitude vector
        lat_vec: Latitude vector
    
    Returns:
        Tuple of (lon_idx, lat_idx) arrays
    """
    lon = np.atleast_1d(lon)
    lat = np.atleast_1d(lat)
    
    dlon = lon_vec[1] - lon_vec[0] if len(lon_vec) > 1 else 1.0
    dlat = lat_vec[1] - lat_vec[0] if len(lat_vec) > 1 else 1.0
    
    lon_idx = np.round((lon - lon_vec[0]) / dlon).astype(int)
    lat_idx = np.round((lat - lat_vec[0]) / dlat).astype(int)
    
    # Clip to valid range
    lon_idx = np.clip(lon_idx, 0, len(lon_vec) - 1)
    lat_idx = np.clip(lat_idx, 0, len(lat_vec) - 1)
    
    return lon_idx, lat_idx
