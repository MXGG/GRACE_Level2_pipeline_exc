"""Non-UI file I/O helpers extracted from GUI class."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np


def sanitize_mat_value(v):
    if v is None:
        return None
    if isinstance(v, dict):
        out = {}
        for k, vv in v.items():
            vv2 = sanitize_mat_value(vv)
            if vv2 is not None:
                out[k] = vv2
        return out
    if isinstance(v, (list, tuple)):
        try:
            v = np.asarray(v, dtype=object)
        except Exception:
            return np.asarray([str(x) for x in v], dtype=object)

    if isinstance(v, np.ndarray):
        arr = v
        if arr.dtype != object:
            return arr
        flat = []
        has_text = False
        for x in arr.ravel():
            if x is None:
                flat.append(np.nan)
                continue
            if isinstance(x, (bytes, str)):
                has_text = True
                flat.append(x.decode("utf-8", errors="ignore") if isinstance(x, bytes) else str(x))
                continue
            if isinstance(x, np.datetime64) or hasattr(x, "strftime"):
                has_text = True
                flat.append(str(x))
                continue
            try:
                flat.append(float(x))
            except Exception:
                has_text = True
                flat.append(str(x))
        if has_text:
            return np.asarray(flat, dtype=object).reshape(arr.shape)
        return np.asarray(flat, dtype=float).reshape(arr.shape)
    return v


def safe_savemat(path, data):
    import scipy.io as sio

    if isinstance(data, dict):
        clean = {}
        for k, v in data.items():
            vv = sanitize_mat_value(v)
            if vv is not None:
                clean[k] = vv
        data = clean
    tmp = path + ".tmp"
    sio.savemat(tmp, data, do_compression=True, appendmat=False)
    os.replace(tmp, path)


def safe_write_text(path, lines):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    os.replace(tmp, path)


def save_grid_txt(path, lon_vec, lat_vec, grid):
    lon = np.asarray(lon_vec, dtype=float).reshape(-1)
    lat = np.asarray(lat_vec, dtype=float).reshape(-1)
    val = np.asarray(grid, dtype=float)
    if val.shape[:2] != (lon.size, lat.size):
        raise ValueError("Grid shape mismatch for TXT export.")
    lon_g, lat_g = np.meshgrid(lon, lat, indexing="ij")
    valid = np.isfinite(val)
    tmp = path + ".tmp"
    if np.any(valid):
        arr = np.column_stack((lon_g[valid], lat_g[valid], val[valid]))
        np.savetxt(tmp, arr, fmt="%.6f %.6f %.6f")
    else:
        Path(tmp).write_text("# no valid data\n", encoding="utf-8")
    os.replace(tmp, path)
