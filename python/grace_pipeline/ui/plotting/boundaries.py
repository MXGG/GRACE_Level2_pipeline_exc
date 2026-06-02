"""Boundary plotting/data helpers extracted from GUI class."""

from __future__ import annotations

import numpy as np


def plot_line(ax, x, y, **kwargs):
    try:
        x = np.asarray(x)
        y = np.asarray(y)
        if x.size < 2:
            return
        x2 = x.astype(float).copy()
        y2 = y.astype(float).copy()
        mask = np.isfinite(x2) & np.isfinite(y2)
        if not np.any(mask):
            return
        xr = np.nanmax(x2[mask]) - np.nanmin(x2[mask])
        if xr > 0:
            jumps = np.where(np.abs(np.diff(x2)) > 0.5 * xr)[0]
            if jumps.size > 0:
                x2[jumps + 1] = np.nan
                y2[jumps + 1] = np.nan
        ax.plot(x2, y2, **kwargs)
    except Exception:
        return


def split_dateline(lons, lats, wrap_delta_lon_cb, threshold=180.0, lon0=None):
    try:
        lons = np.asarray(lons)
        lats = np.asarray(lats)
        if lons.size < 2:
            return [(lons, lats)]
        lons_eval = lons
        if lon0 is not None:
            try:
                lons_eval = wrap_delta_lon_cb(lons, lon0)
            except Exception:
                lons_eval = lons
        jumps = np.where(np.abs(np.diff(lons_eval)) > threshold)[0]
        if jumps.size == 0:
            return [(lons, lats)]
        segs = []
        start = 0
        for j in jumps:
            segs.append((lons[start : j + 1], lats[start : j + 1]))
            start = j + 1
        if start < lons.size:
            segs.append((lons[start:], lats[start:]))
        return segs
    except Exception:
        return [(lons, lats)]


def read_boundary_file(path: str, name_field: str = "Name"):
    try:
        from grace_pipeline.basin import read_boundary

        return read_boundary(path, name_field=name_field)
    except Exception as e:
        raise RuntimeError(f"Boundary read failed: {e}")


def boundary_bbox(boundaries):
    try:
        lons = np.concatenate([np.asarray(b.lon).astype(float) for b in boundaries if b is not None])
        lats = np.concatenate([np.asarray(b.lat).astype(float) for b in boundaries if b is not None])
        if lons.size == 0 or lats.size == 0:
            return None
        lon_min = float(np.nanmin(lons))
        lon_max = float(np.nanmax(lons))
        lat_min = float(np.nanmin(lats))
        lat_max = float(np.nanmax(lats))
        return (lon_min, lon_max, lat_min, lat_max)
    except Exception:
        return None


def draw_boundaries(
    ax,
    boundaries,
    *,
    proj="PlateCarree",
    lon0=0.0,
    lat0=0.0,
    lat1=30.0,
    lat2=60.0,
    bbox=None,
    normalize_lon_for_plot_cb=None,
    split_dateline_cb=None,
    split_plot_lon_segments_cb=None,
    apply_proj_scale_cb=None,
    plot_line_cb=None,
    projector_cb=None,
):
    if normalize_lon_for_plot_cb is None or split_dateline_cb is None or split_plot_lon_segments_cb is None:
        raise ValueError("Missing longitude/segment callbacks.")
    if apply_proj_scale_cb is None or plot_line_cb is None or projector_cb is None:
        raise ValueError("Missing projection/draw callbacks.")

    try:
        for b in boundaries:
            lons = np.asarray(b.lon, dtype=float)
            lats = np.asarray(b.lat, dtype=float)
            if lons.size < 2:
                continue
            if bbox is not None:
                try:
                    lon_min_b, lon_max_b, lat_min_b, lat_max_b = bbox
                    lons_eval = normalize_lon_for_plot_cb(lons)
                    in_lat = (lats >= lat_min_b) & (lats <= lat_max_b)
                    if lon_min_b <= lon_max_b:
                        in_lon = (lons_eval >= lon_min_b) & (lons_eval <= lon_max_b)
                    else:
                        in_lon = (lons_eval >= lon_min_b) | (lons_eval <= lon_max_b)
                    if not np.any(in_lon & in_lat):
                        continue
                except Exception:
                    pass

            if proj in (
                "Robinson",
                "Mollweide",
                "EqualEarth",
                "WinkelTripel",
                "EckertIV",
                "Mercator",
                "Miller",
                "Sinusoidal",
                "Orthographic",
                "AzimuthalEquidistant",
                "Stereographic",
                "LambertConformal",
                "AlbersEqualArea",
            ):
                segments = split_dateline_cb(lons, lats, lon0=lon0)
            else:
                segments = split_plot_lon_segments_cb(lons, lats, plate_carree=True)

            for lons_seg, lats_seg in segments:
                if proj in (
                    "Robinson",
                    "Mollweide",
                    "EqualEarth",
                    "WinkelTripel",
                    "EckertIV",
                    "Mercator",
                    "Miller",
                    "Sinusoidal",
                    "Orthographic",
                    "AzimuthalEquidistant",
                    "Stereographic",
                    "LambertConformal",
                    "AlbersEqualArea",
                ):
                    x, y = projector_cb(
                        proj,
                        lons_seg,
                        lats_seg,
                        lon0=lon0,
                        lat0=lat0,
                        lat1=lat1,
                        lat2=lat2,
                    )
                    x = apply_proj_scale_cb(x)
                    plot_line_cb(ax, x, y, color="#b00020", linewidth=0.8, alpha=0.8)
                else:
                    ax.plot(lons_seg, lats_seg, color="#b00020", linewidth=0.8, alpha=0.8)
    except Exception:
        return
