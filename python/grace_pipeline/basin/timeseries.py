"""
Basin time series analysis.
"""

import numpy as np
from typing import Dict, Optional, Tuple

from grace_pipeline.core.grid import compute_grid_area

def compute_weighted_mean(
    grid: np.ndarray,
    mask: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray
) -> float:
    """Compute area-weighted mean of grid over mask.
    
    Args:
        grid: Data grid [nLon, nLat]
        mask: Boolean mask [nLon, nLat]
        lon_vec: Longitude vector
        lat_vec: Latitude vector
        
    Returns:
        Weighted mean value
    """
    area = compute_grid_area(lon_vec, lat_vec)
    
    # Apply mask
    weights = area * mask
    values = grid * mask
    
    # Handle NaNs in grid
    valid = np.isfinite(values) & (mask > 0)
    
    if not np.any(valid):
        return np.nan
        
    w = weights[valid]
    v = values[valid]
    
    return np.sum(v * w) / np.sum(w)

def extract_basin_ts(
    stacks: Dict[str, np.ndarray],
    mask: np.ndarray,
    lon_vec: np.ndarray,
    lat_vec: np.ndarray
) -> Dict[str, np.ndarray]:
    """Extract time series for all products in stacks over a basin mask.
    
    Args:
        stacks: Dictionary of 3D stacks {tag: [nLon, nLat, Nt]}
        mask: Basin mask
        lon_vec, lat_vec: Grid vectors
        
    Returns:
        Dictionary {tag: 1D_array_of_means}
    """
    area = compute_grid_area(lon_vec, lat_vec)
    weights = area * mask
    total_weight = np.sum(weights)
    
    if total_weight == 0:
        return {tag: np.full(stack.shape[2], np.nan) for tag, stack in stacks.items()}
        
    results = {}
    
    for tag, stack in stacks.items():
        Nt = stack.shape[2]
        ts = np.zeros(Nt)

        # Loop by month to keep memory stable on large stacks.
        for t in range(Nt):
            grid = stack[:, :, t]
            valid = np.isfinite(grid) & (mask > 0)
            
            if np.any(valid):
                w = weights[valid]
                v = grid[valid]
                ts[t] = np.sum(v * w) / np.sum(w)
            else:
                ts[t] = np.nan
                
        results[tag] = ts
        
    return results
