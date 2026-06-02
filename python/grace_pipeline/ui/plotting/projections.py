"""Map/projection math utilities extracted from GUI class."""

from __future__ import annotations

import numpy as np


def infer_plot_lon_mode(lon):
    try:
        lon_arr = np.asarray(lon, dtype=float).squeeze()
        if lon_arr.size == 0:
            return "-180_180"
        lon_min = float(np.nanmin(lon_arr))
        lon_max = float(np.nanmax(lon_arr))
        lon_span = lon_max - lon_min
        if lon_min >= -1e-6 and lon_max > 180.0 and lon_span > 180.0:
            return "0_360"
    except Exception:
        pass
    return "-180_180"


def normalize_lon_for_plot(lons, lon_mode="-180_180"):
    lon_arr = np.asarray(lons, dtype=float)
    if lon_mode == "0_360":
        return np.mod(lon_arr, 360.0)
    return ((lon_arr + 180.0) % 360.0) - 180.0


def split_plot_lon_segments(lons, lats, split_dateline_cb, lon0=0.0, plate_carree=False, lon_mode="-180_180"):
    if plate_carree:
        lons_plot = normalize_lon_for_plot(lons, lon_mode=lon_mode)
        return split_dateline_cb(lons_plot, lats, lon0=None)
    return split_dateline_cb(lons, lats, lon0=lon0)


def normalize_lon_input(val):
    try:
        v = float(val) % 360.0
        if abs(v - 180.0) < 1e-6:
            return 180.0
        if v > 180.0:
            v -= 360.0
        return v
    except Exception:
        return float(val)


def region_is_custom(lon_min, lon_max, lat_min, lat_max):
    try:
        lon_min = float(lon_min)
        lon_max = float(lon_max)
        lat_min = float(lat_min)
        lat_max = float(lat_max)
    except Exception:
        return False
    if lat_min > lat_max:
        lat_min, lat_max = lat_max, lat_min
    full_lon = abs((lon_max - lon_min)) >= 359.0
    full_lat = abs((lat_max - lat_min)) >= 179.0
    return not (full_lon and full_lat)


def parse_float(s):
    try:
        s = str(s).strip()
        if not s:
            return None
        return float(s)
    except Exception:
        return None


def wrap_delta_lon(lon_deg, lon0):
    lon = np.asarray(lon_deg, dtype=float)
    return ((lon - lon0 + 180.0) % 360.0) - 180.0


def get_proj_center(lon, lat):
    try:
        lon_arr = np.asarray(lon, dtype=float)
        lat_arr = np.asarray(lat, dtype=float)
        lon_rad = np.deg2rad(lon_arr)
        lon0 = np.rad2deg(np.arctan2(np.nanmean(np.sin(lon_rad)), np.nanmean(np.cos(lon_rad))))
        if np.isnan(lon0):
            lon0 = 0.0
        lat0 = float(np.nanmean([np.nanmin(lat_arr), np.nanmax(lat_arr)]))
        if np.isnan(lat0):
            lat0 = 0.0
        return lon0, lat0
    except Exception:
        return 0.0, 0.0


def get_conic_parallels(lat_min, lat_max):
    try:
        if lat_min > lat_max:
            lat_min, lat_max = lat_max, lat_min
        span = max(5.0, abs(lat_max - lat_min))
        p1 = lat_min + 0.25 * span
        p2 = lat_min + 0.75 * span
        p1 = float(np.clip(p1, -80.0, 80.0))
        p2 = float(np.clip(p2, -80.0, 80.0))
        if abs(p2 - p1) < 1.0:
            p2 = p1 + 1.0
        return p1, p2
    except Exception:
        return 30.0, 60.0


def scale_projection(x, y, target_ratio=2.0):
    try:
        xr = float(np.nanmax(x) - np.nanmin(x))
        yr = float(np.nanmax(y) - np.nanmin(y))
        if not np.isfinite(xr) or not np.isfinite(yr) or xr <= 0 or yr <= 0:
            return x, y, None, None
        ratio = xr / yr
        if not np.isfinite(target_ratio) or target_ratio <= 0:
            target_ratio = ratio
        scale = target_ratio / ratio
        if 0.85 <= scale <= 1.15:
            return x, y, None, None
        x0 = 0.5 * (np.nanmin(x) + np.nanmax(x))
        x_scaled = (x - x0) * scale + x0
        return x_scaled, y, scale, x0
    except Exception:
        return x, y, None, None


def apply_proj_scale(x, proj_scale=None, proj_x0=None):
    try:
        if proj_scale is None:
            return x
        x0 = 0.0 if proj_x0 is None else proj_x0
        return (np.asarray(x) - x0) * float(proj_scale) + x0
    except Exception:
        return x


def proj_robinson(lon_deg, lat_deg, lon0=0.0):
    x = np.array([1.0000, 0.9986, 0.9954, 0.9900, 0.9822, 0.9730, 0.9600,
                  0.9427, 0.9216, 0.8962, 0.8679, 0.8350, 0.7986, 0.7597,
                  0.7186, 0.6732, 0.6213, 0.5722, 0.5322])
    y = np.array([0.0000, 0.0620, 0.1240, 0.1860, 0.2480, 0.3100, 0.3720,
                  0.4340, 0.4958, 0.5571, 0.6176, 0.6769, 0.7346, 0.7903,
                  0.8435, 0.8936, 0.9394, 0.9761, 1.0000])
    lon = np.deg2rad(wrap_delta_lon(lon_deg, lon0))
    lat = np.asarray(lat_deg)
    sign = np.sign(lat)
    alat = np.abs(lat)
    valid = np.isfinite(alat)
    alat = np.where(valid, np.clip(alat, 0, 90), 0.0)
    idx = alat / 5.0
    i0 = np.floor(idx).astype(int)
    i1 = np.clip(i0 + 1, 0, len(x) - 1)
    f = idx - i0
    xk = x[i0] + (x[i1] - x[i0]) * f
    yk = y[i0] + (y[i1] - y[i0]) * f
    x_out = xk * lon
    y_out = yk * sign
    x_out = np.where(valid, x_out, np.nan)
    y_out = np.where(valid, y_out, np.nan)
    return x_out, y_out


def proj_mollweide(lon_deg, lat_deg, lon0=0.0):
    lon = np.deg2rad(wrap_delta_lon(lon_deg, lon0))
    lat = np.deg2rad(lat_deg)
    theta = lat.copy()
    for _ in range(6):
        delta = (2 * theta + np.sin(2 * theta) - np.pi * np.sin(lat)) / (2 + 2 * np.cos(2 * theta))
        theta = theta - delta
    x = 2 * np.sqrt(2) / np.pi * lon * np.cos(theta)
    y = np.sqrt(2) * np.sin(theta)
    return x, y


def proj_mercator(lon_deg, lat_deg, lon0=0.0):
    lon = np.deg2rad(wrap_delta_lon(lon_deg, lon0))
    lat = np.deg2rad(lat_deg)
    lat = np.clip(lat, np.deg2rad(-85.0), np.deg2rad(85.0))
    x = lon
    y = np.log(np.tan(np.pi / 4.0 + lat / 2.0))
    return x, y


def proj_miller(lon_deg, lat_deg, lon0=0.0):
    lon = np.deg2rad(wrap_delta_lon(lon_deg, lon0))
    lat = np.deg2rad(lat_deg)
    lat = np.clip(lat, np.deg2rad(-85.0), np.deg2rad(85.0))
    x = lon
    y = 1.25 * np.log(np.tan(np.pi / 4.0 + 0.4 * lat))
    return x, y


def proj_sinusoidal(lon_deg, lat_deg, lon0=0.0):
    lon = np.deg2rad(wrap_delta_lon(lon_deg, lon0))
    lat = np.deg2rad(lat_deg)
    x = lon * np.cos(lat)
    y = lat
    return x, y


def proj_equalearth(lon_deg, lat_deg, lon0=0.0):
    lon = np.deg2rad(wrap_delta_lon(lon_deg, lon0))
    lat = np.deg2rad(lat_deg)
    a1, a2, a3, a4 = 1.340264, -0.081106, 0.000893, 0.003796
    theta = np.arcsin((np.sqrt(3) / 2) * np.sin(lat))
    denom = a1 + 3 * a2 * theta**2 + 7 * a3 * theta**6 + 9 * a4 * theta**8
    x = (2 * np.sqrt(3) / 3) * lon * np.cos(theta) / denom
    y = a1 * theta + a2 * theta**3 + a3 * theta**7 + a4 * theta**9
    return x, y


def proj_winkeltripel(lon_deg, lat_deg, lon0=0.0):
    lon = np.deg2rad(wrap_delta_lon(lon_deg, lon0))
    lat = np.deg2rad(lat_deg)
    phi1 = np.arccos(2 / np.pi)
    alpha = np.arccos(np.cos(lat) * np.cos(lon / 2))
    sinc = np.ones_like(alpha)
    mask = alpha != 0
    sinc[mask] = np.sin(alpha[mask]) / alpha[mask]
    x = 2 * np.cos(lat) * np.sin(lon / 2) / sinc
    y = np.sin(lat) / sinc
    x = (x + lon * np.cos(phi1)) / 2
    y = (y + lat) / 2
    return x, y


def proj_eckert4(lon_deg, lat_deg, lon0=0.0):
    lon = np.deg2rad(wrap_delta_lon(lon_deg, lon0))
    lat = np.deg2rad(lat_deg)
    theta = lat.copy()
    for _ in range(6):
        delta = (theta + np.sin(theta) - (2 + np.pi / 2) * np.sin(lat)) / (1 + np.cos(theta))
        theta = theta - delta
    a = 2 / np.sqrt(4 * np.pi + np.pi**2)
    b = 2 * np.sqrt(np.pi / (4 + np.pi))
    x = a * lon * (1 + np.cos(theta))
    y = b * np.sin(theta)
    return x, y


def proj_orthographic(lon_deg, lat_deg, lon0=0.0, lat0=0.0):
    lon = np.deg2rad(wrap_delta_lon(lon_deg, lon0))
    lat = np.deg2rad(lat_deg)
    lat0 = np.deg2rad(lat0)
    cosc = np.sin(lat0) * np.sin(lat) + np.cos(lat0) * np.cos(lat) * np.cos(lon)
    x = np.cos(lat) * np.sin(lon)
    y = np.cos(lat0) * np.sin(lat) - np.sin(lat0) * np.cos(lat) * np.cos(lon)
    x = np.where(cosc >= 0, x, np.nan)
    y = np.where(cosc >= 0, y, np.nan)
    return x, y


def proj_aeqd(lon_deg, lat_deg, lon0=0.0, lat0=0.0):
    lon = np.deg2rad(wrap_delta_lon(lon_deg, lon0))
    lat = np.deg2rad(lat_deg)
    lat0 = np.deg2rad(lat0)
    cosc = np.sin(lat0) * np.sin(lat) + np.cos(lat0) * np.cos(lat) * np.cos(lon)
    cosc = np.clip(cosc, -1, 1)
    c = np.arccos(cosc)
    sinc = np.ones_like(c)
    mask = c != 0
    sinc[mask] = c[mask] / np.sin(c[mask])
    x = sinc * np.cos(lat) * np.sin(lon)
    y = sinc * (np.cos(lat0) * np.sin(lat) - np.sin(lat0) * np.cos(lat) * np.cos(lon))
    return x, y


def proj_stereographic(lon_deg, lat_deg, lon0=0.0, lat0=0.0):
    lon = np.deg2rad(wrap_delta_lon(lon_deg, lon0))
    lat = np.deg2rad(lat_deg)
    lat0 = np.deg2rad(lat0)
    k = 2 / (1 + np.sin(lat0) * np.sin(lat) + np.cos(lat0) * np.cos(lat) * np.cos(lon))
    x = k * np.cos(lat) * np.sin(lon)
    y = k * (np.cos(lat0) * np.sin(lat) - np.sin(lat0) * np.cos(lat) * np.cos(lon))
    return x, y


def proj_lambert_conformal(lon_deg, lat_deg, lon0=0.0, lat0=0.0, lat1=30.0, lat2=60.0):
    lon = np.deg2rad(wrap_delta_lon(lon_deg, lon0))
    lat = np.deg2rad(lat_deg)
    lat0 = np.deg2rad(lat0)
    lat1 = np.deg2rad(lat1)
    lat2 = np.deg2rad(lat2)
    n = np.log(np.cos(lat1) / np.cos(lat2)) / np.log(np.tan(np.pi / 4 + lat2 / 2) / np.tan(np.pi / 4 + lat1 / 2))
    f = np.cos(lat1) * (np.tan(np.pi / 4 + lat1 / 2) ** n) / n
    rho = f / (np.tan(np.pi / 4 + lat / 2) ** n)
    rho0 = f / (np.tan(np.pi / 4 + lat0 / 2) ** n)
    x = rho * np.sin(n * lon)
    y = rho0 - rho * np.cos(n * lon)
    return x, y


def proj_albers(lon_deg, lat_deg, lon0=0.0, lat0=0.0, lat1=30.0, lat2=60.0):
    lon = np.deg2rad(wrap_delta_lon(lon_deg, lon0))
    lat = np.deg2rad(lat_deg)
    lat0 = np.deg2rad(lat0)
    lat1 = np.deg2rad(lat1)
    lat2 = np.deg2rad(lat2)
    n = 0.5 * (np.sin(lat1) + np.sin(lat2))
    c = np.cos(lat1) ** 2 + 2 * n * np.sin(lat1)
    rho = np.sqrt(np.maximum(0.0, c - 2 * n * np.sin(lat))) / n
    rho0 = np.sqrt(np.maximum(0.0, c - 2 * n * np.sin(lat0))) / n
    x = rho * np.sin(n * lon)
    y = rho0 - rho * np.cos(n * lon)
    return x, y
