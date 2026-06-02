"""Map overlay drawing helpers extracted from GUI class."""

from __future__ import annotations

import os

import numpy as np


def draw_coastlines(
    ax,
    *,
    coast_path: str,
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
    if not coast_path:
        return
    if normalize_lon_for_plot_cb is None or split_dateline_cb is None or split_plot_lon_segments_cb is None:
        raise ValueError("Missing longitude/segment callbacks.")
    if apply_proj_scale_cb is None or plot_line_cb is None or projector_cb is None:
        raise ValueError("Missing projection/draw callbacks.")

    try:
        import shapefile

        shp_path = coast_path
        if os.path.isdir(shp_path):
            for f in os.listdir(shp_path):
                if f.lower().endswith(".shp"):
                    shp_path = os.path.join(shp_path, f)
                    break
        r = shapefile.Reader(shp_path)
        use_bbox = False
        if bbox is not None:
            try:
                lon_min_b, lon_max_b, lat_min_b, lat_max_b = bbox
                lon_span = lon_max_b - lon_min_b
                full_lon = (
                    abs(lon_span) >= 359.0
                    or (abs(lon_min_b) < 1.0e-6 and abs(lon_max_b - 360.0) < 1.0e-6)
                    or (abs(lon_min_b + 180.0) < 1.0e-6 and abs(lon_max_b - 180.0) < 1.0e-6)
                )
                full_lat = abs(lat_min_b + 90.0) < 1.0 and abs(lat_max_b - 90.0) < 1.0
                use_bbox = not (full_lon and full_lat)
            except Exception:
                use_bbox = False
        for shape in r.shapes():
            pts = shape.points
            parts = list(shape.parts) + [len(pts)]
            for i in range(len(parts) - 1):
                seg = pts[parts[i] : parts[i + 1]]
                if not seg:
                    continue
                seg = np.array(seg)
                lons = seg[:, 0]
                lats = seg[:, 1]
                if use_bbox:
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
                        plot_line_cb(ax, x, y, color="#1f3547", linewidth=0.65, alpha=0.95)
                    else:
                        ax.plot(lons_seg, lats_seg, color="#1f3547", linewidth=0.65, alpha=0.95)
    except Exception:
        return


def draw_graticule(
    ax,
    *,
    proj="PlateCarree",
    lon0=0.0,
    lat0=0.0,
    lat1=30.0,
    lat2=60.0,
    plot_lon_mode="-180_180",
    apply_proj_scale_cb=None,
    plot_line_cb=None,
    projector_cb=None,
):
    if apply_proj_scale_cb is None or plot_line_cb is None or projector_cb is None:
        raise ValueError("Missing projection/draw callbacks.")

    try:
        if proj == "PlateCarree":
            try:
                xmin, xmax = ax.get_xlim()
                ymin, ymax = ax.get_ylim()
            except Exception:
                xmin, xmax = (-180, 180)
                ymin, ymax = (-90, 90)
            if plot_lon_mode == "0_360":
                lo = max(0, int(np.floor(xmin / 60.0)) * 60)
                hi = min(360, int(np.ceil(xmax / 60.0)) * 60)
                ax.set_xticks(np.arange(lo, hi + 1, 60))
            else:
                lo = int(np.floor(xmin / 60.0)) * 60
                hi = int(np.ceil(xmax / 60.0)) * 60
                ax.set_xticks(np.arange(lo, hi + 1, 60))
            lo_y = int(np.floor(ymin / 30.0)) * 30
            hi_y = int(np.ceil(ymax / 30.0)) * 30
            ax.set_yticks(np.arange(lo_y, hi_y + 1, 30))
            ax.grid(True, color="#cccccc", linewidth=0.4, linestyle="--")
            return

        lon_lines = np.arange(-180, 181, 60)
        lat_lines = np.arange(-60, 61, 30)
        for lat in lat_lines:
            lons = np.linspace(-180, 180, 361)
            lats = np.full_like(lons, lat, dtype=float)
            x, y = projector_cb(proj, lons, lats, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
            x = apply_proj_scale_cb(x)
            plot_line_cb(ax, x, y, color="#cccccc", linewidth=0.4, linestyle="--", alpha=0.7)
        for lon in lon_lines:
            lats = np.linspace(-85, 85, 341)
            lons = np.full_like(lats, lon, dtype=float)
            x, y = projector_cb(proj, lons, lats, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
            x = apply_proj_scale_cb(x)
            plot_line_cb(ax, x, y, color="#cccccc", linewidth=0.4, linestyle="--", alpha=0.7)
    except Exception:
        return
