"""Non-UI grid/xyz helpers extracted from GUI class."""

from __future__ import annotations

import numpy as np
from scipy.interpolate import RegularGridInterpolator


def fm_target_grid():
    lon = np.arange(0.25, 360.0, 0.5)
    lat = np.arange(-89.75, 90.0, 0.5)
    return lon, lat


def sf_target_grid(grid_interval=0.5):
    step = float(grid_interval)
    lon = np.arange(-180 + step / 2, 180, step)
    lat = np.arange(-90 + step / 2, 90, step)
    return lon, lat


def regrid_regular(lon_in, lat_in, grid_in, lon_out, lat_out):
    lon = np.asarray(lon_in, dtype=float).copy()
    lat = np.asarray(lat_in, dtype=float).copy()
    grid = np.asarray(grid_in)
    if grid.ndim >= 2 and grid.shape[0] == lat.size and grid.shape[1] == lon.size:
        grid = grid.T
    if lon.ndim != 1 or lat.ndim != 1:
        raise ValueError("Regrid requires 1D lon/lat.")

    lon_order = np.argsort(lon)
    lat_order = np.argsort(lat)
    lon = lon[lon_order]
    lat = lat[lat_order]
    grid = grid[lon_order, :]
    grid = grid[:, lat_order]

    lon_out = np.asarray(lon_out, dtype=float)
    lat_out = np.asarray(lat_out, dtype=float)
    lon_grid, lat_grid = np.meshgrid(lon_out, lat_out, indexing="ij")
    pts = np.column_stack([lon_grid.ravel(), lat_grid.ravel()])

    interp = RegularGridInterpolator((lon, lat), grid, bounds_error=False, fill_value=np.nan)
    return interp(pts).reshape(lon_out.size, lat_out.size)


def write_xyz_file(path, lon_vec, lat_vec, grid):
    lon_vec = np.asarray(lon_vec)
    lat_vec = np.asarray(lat_vec)
    grid = np.asarray(grid)
    if grid.shape[0] != lon_vec.size or grid.shape[1] != lat_vec.size:
        raise ValueError("Grid shape mismatch for xyz write.")
    lon_col = np.repeat(lon_vec, lat_vec.size)
    lat_col = np.tile(lat_vec, lon_vec.size)
    val_col = grid.reshape(lon_vec.size, lat_vec.size).reshape(-1)
    arr = np.column_stack([lon_col, lat_col, val_col])
    np.savetxt(path, arr, fmt="%.6f")


def read_xyz_grid(path):
    data = np.loadtxt(path)
    if data.ndim != 2 or data.shape[1] < 3:
        raise ValueError("Invalid xyz format")
    lon = np.unique(data[:, 0])
    lat = np.unique(data[:, 1])
    grid = np.full((lon.size, lat.size), np.nan, dtype=float)
    lon_idx = {v: i for i, v in enumerate(lon)}
    lat_idx = {v: i for i, v in enumerate(lat)}
    for row in data:
        i = lon_idx.get(row[0])
        j = lat_idx.get(row[1])
        if i is None or j is None:
            continue
        grid[i, j] = row[2]
    return grid, lon, lat
