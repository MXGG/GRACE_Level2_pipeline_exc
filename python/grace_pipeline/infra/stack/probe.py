from pathlib import Path
from typing import Callable, Optional, Tuple, Any

import numpy as np

from grace_pipeline.infra.io.nc_utils import var_attr_lower


def _time_length(values):
    if values is None:
        return None
    try:
        return int(np.asarray(values).reshape(-1).size)
    except Exception:
        return None


def _normalize_shape_lon_lat_time(shape, lon=None, lat=None, t=None):
    if not shape:
        return shape
    if len(shape) == 2:
        shape = (shape[0], shape[1], 1)
    if len(shape) != 3:
        return shape
    if lon is None or lat is None:
        return shape
    lon_arr = np.asarray(lon).squeeze()
    lat_arr = np.asarray(lat).squeeze()
    if lon_arr.ndim != 1 or lat_arr.ndim != 1:
        return shape

    lon_size = int(lon_arr.size)
    lat_size = int(lat_arr.size)
    time_size = _time_length(t)

    candidates = []
    for lon_i in range(3):
        if int(shape[lon_i]) != lon_size:
            continue
        for lat_i in range(3):
            if lat_i == lon_i or int(shape[lat_i]) != lat_size:
                continue
            time_i = next(i for i in range(3) if i not in (lon_i, lat_i))
            score = 0
            if (lon_i, lat_i, time_i) == (0, 1, 2):
                score += 4
            if time_size is not None:
                if int(shape[time_i]) == int(time_size):
                    score += 6
                if int(shape[lon_i]) == int(time_size):
                    score -= 2
                if int(shape[lat_i]) == int(time_size):
                    score -= 2
            candidates.append((score, lon_i, lat_i, time_i))

    if not candidates:
        return shape
    candidates.sort(key=lambda item: item[0], reverse=True)
    _, lon_i, lat_i, time_i = candidates[0]
    return (int(shape[lon_i]), int(shape[lat_i]), int(shape[time_i]))


def probe_stack_any(
    path: str,
    load_stack_any_cb: Callable[[str], Tuple[Any, Any, Any, Any, Any]],
    select_nc_variables_cb: Optional[Callable[..., Any]] = None,
):
    path = path.strip()
    if not path:
        return None, None, None, None, None
    ext = Path(path).suffix.lower()

    def _pick_key(keys, names):
        for key in keys:
            low = key.lower()
            if any(name in low for name in names):
                return key
        return None

    if ext == ".mat":
        try:
            import scipy.io as sio

            info = sio.whosmat(path)
            names = [name for name, _shape, _cls in info]
            shape_map = {name: tuple(shape) for name, shape, _cls in info}
            ewh_key = _pick_key(names, ["ewh", "tws", "grid", "data"])
            lon_key = _pick_key(names, ["lon", "long"])
            lat_key = _pick_key(names, ["lat"])
            load_keys = [key for key in [lon_key, lat_key, "t", "tag", "ym"] if key]
            mat = sio.loadmat(path, squeeze_me=True, struct_as_record=False, variable_names=load_keys or ["t"])
            if not ewh_key or ewh_key not in shape_map:
                raise ValueError("Unable to locate primary data variable in MAT file.")
            shape = shape_map[ewh_key]
            lon = np.asarray(mat.get(lon_key)).squeeze() if lon_key and lon_key in mat else None
            lat = np.asarray(mat.get(lat_key)).squeeze() if lat_key and lat_key in mat else None
            t = mat.get("t")
            shape = _normalize_shape_lon_lat_time(shape, lon=lon, lat=lat, t=t)
            if lon is None or lat is None:
                nlon = int(shape[0]) if len(shape) > 0 else 0
                nlat = int(shape[1]) if len(shape) > 1 else 0
                if nlon > 0 and nlat > 0:
                    dlon = 360.0 / nlon
                    dlat = 180.0 / nlat
                    lon = np.linspace(-180 + 0.5 * dlon, 180 - 0.5 * dlon, nlon)
                    lat = np.linspace(-90 + 0.5 * dlat, 90 - 0.5 * dlat, nlat)
            meta = {"active_var": ewh_key, "data_var_names": [ewh_key]}
            return shape, lon, lat, t, meta
        except Exception:
            pass

    if ext in (".h5", ".hdf5", ".hdf", ".he5", ".mat"):
        try:
            import h5py

            with h5py.File(path, "r") as f:
                ewh = f["ewh"] if "ewh" in f else None
                lon = f["lon"] if "lon" in f else None
                lat = f["lat"] if "lat" in f else None
                t = f["t"] if "t" in f else None
                if (ewh is None or lon is None or lat is None) and "P" in f and "grid" in f["P"]:
                    g = f["P"]["grid"]
                    ewh = g["ewh"] if "ewh" in g else ewh
                    lon = g["lon"] if "lon" in g else lon
                    lat = g["lat"] if "lat" in g else lat
                if ewh is not None:
                    shape = tuple(int(v) for v in ewh.shape)
                    lon_arr = lon[()].squeeze() if lon is not None else None
                    lat_arr = lat[()].squeeze() if lat is not None else None
                    t_arr = t[()] if t is not None and not hasattr(t, "keys") else None
                    shape = _normalize_shape_lon_lat_time(shape, lon=lon_arr, lat=lat_arr, t=t_arr)
                    meta = {"active_var": "ewh", "data_var_names": ["ewh"]}
                    return shape, lon_arr, lat_arr, t_arr, meta
        except Exception:
            pass

    if ext in (".nc", ".nc4", ".cdf", ".hdf", ".h5", ".hdf5", ".he5"):
        try:
            import netCDF4 as nc

            ds = nc.Dataset(path)
            try:
                var_names = list(ds.variables.keys())

                def _score_coord(v, kind):
                    name = v.name.lower()
                    std = var_attr_lower(v, "standard_name")
                    long = var_attr_lower(v, "long_name")
                    units = var_attr_lower(v, "units")
                    axis = var_attr_lower(v, "axis")
                    score = 0
                    if kind == "lon":
                        if name in ("lon", "longitude", "x") or name.endswith(("_lon", "_longitude")):
                            score += 3
                        if "longitude" in std or "longitude" in long:
                            score += 3
                        if axis == "x":
                            score += 2
                        if "degree" in units and "east" in units:
                            score += 2
                    elif kind == "lat":
                        if name in ("lat", "latitude", "y") or name.endswith(("_lat", "_latitude")):
                            score += 3
                        if "latitude" in std or "latitude" in long:
                            score += 3
                        if axis == "y":
                            score += 2
                        if "degree" in units and "north" in units:
                            score += 2
                    else:
                        if "time" in name:
                            score += 3
                        if axis == "t":
                            score += 2
                    return score

                def _pick_coord(kind):
                    best_name = None
                    best_score = -1
                    for name in var_names:
                        score = _score_coord(ds.variables[name], kind)
                        if score > best_score:
                            best_name = name
                            best_score = score
                    return best_name if best_score > 0 else None

                lon_key = _pick_coord("lon")
                lat_key = _pick_coord("lat")
                time_key = _pick_coord("time")

                def _data_priority(name, var):
                    low = str(name).lower()
                    long = var_attr_lower(var, "long_name")
                    units = var_attr_lower(var, "units")
                    score = 0
                    preferred = (
                        "tws", "ewh", "water", "precip", "rain", "snow",
                        "soilmoi", "soil_moi", "rootmoist", "canop", "evap",
                        "runoff", "qs_", "qsb", "qsm", "swe",
                    )
                    discouraged = (
                        "swdown", "lwdown", "swnet", "lwnet", "qh", "qg",
                        "albedo", "temp", "tair", "psurf", "wind",
                    )
                    if any(tok in low for tok in preferred):
                        score += 6
                    if any(tok in long for tok in preferred):
                        score += 4
                    if any(tok in low for tok in discouraged):
                        score -= 4
                    if any(tok in long for tok in discouraged):
                        score -= 3
                    if "kg m-2" in units or "mm" in units:
                        score += 2
                    return score

                def _is_data_candidate(name, var):
                    low = str(name).lower()
                    std = var_attr_lower(var, "standard_name")
                    long = var_attr_lower(var, "long_name")
                    units = var_attr_lower(var, "units")
                    dims = tuple(getattr(var, "dimensions", ()))
                    if var.ndim < 2:
                        return False
                    if low.endswith("_bnds") or low.endswith("_bounds") or "bounds" in low:
                        return False
                    if "bounds" in std or "bounds" in long:
                        return False
                    if low in {"lat_bnds", "lon_bnds", "time_bnds"}:
                        return False
                    if lon_key and lat_key and dims == (lat_key, lon_key):
                        return False
                    if lon_key and lat_key and dims == (lon_key, lat_key):
                        if "degree" in units and ("east" in units or "north" in units):
                            return False
                    return True

                candidates = []
                data_candidates = []
                for name in var_names:
                    var = ds.variables[name]
                    if _is_data_candidate(name, var):
                        data_candidates.append(name)
                    if var.ndim < 2 or name in {lon_key, lat_key, time_key}:
                        continue
                    if not _is_data_candidate(name, var):
                        continue
                    score = 0
                    if lon_key and lon_key in getattr(var, "dimensions", ()):
                        score += 2
                    if lat_key and lat_key in getattr(var, "dimensions", ()):
                        score += 2
                    if time_key and time_key in getattr(var, "dimensions", ()):
                        score += 1
                    score += _data_priority(name, var)
                    candidates.append((score, name))
                if not candidates and not data_candidates:
                    raise ValueError("No grid-like variable found.")
                data_key = None
                if candidates:
                    candidates.sort(reverse=True)
                    data_key = candidates[0][1]
                if lon_key is None or lat_key is None:
                    if data_key:
                        data_keys = [data_key]
                    elif data_candidates:
                        data_keys = [data_candidates[0]]
                    else:
                        data_keys = []
                else:
                    need_select = data_key is None
                    if need_select and callable(select_nc_variables_cb):
                        picked = select_nc_variables_cb(ds, lon_key, lat_key, time_key, [data_key] if data_key else None)
                        if picked is None:
                            raise ValueError("NetCDF variable selection cancelled.")
                        lon_key, lat_key, time_key, data_keys = picked
                    else:
                        data_keys = [data_key] if data_key else ([data_candidates[0]] if data_candidates else [])
                if not data_keys:
                    raise ValueError("No grid-like variable selected.")
                data_keys = list(dict.fromkeys(data_keys))
                data_key = data_keys[0]
                lon = np.asarray(ds.variables[lon_key][:]).squeeze() if lon_key else None
                lat = np.asarray(ds.variables[lat_key][:]).squeeze() if lat_key else None
                t = np.asarray(ds.variables[time_key][:]).squeeze() if time_key else None
                data_var = ds.variables[data_key]
                dims = list(getattr(data_var, "dimensions", ()))
                shape_raw = tuple(int(v) for v in data_var.shape)
                nlon = shape_raw[dims.index(lon_key)] if lon_key in dims else shape_raw[0]
                nlat = shape_raw[dims.index(lat_key)] if lat_key in dims else shape_raw[1 if len(shape_raw) > 1 else 0]
                nt = shape_raw[dims.index(time_key)] if time_key in dims else 1
                meta = {
                    "active_var": data_key,
                    "data_var_names": data_candidates or data_keys,
                    "lon_key": lon_key,
                    "lat_key": lat_key,
                    "time_key": time_key,
                }
                return (nlon, nlat, nt), lon, lat, t, meta
            finally:
                ds.close()
        except Exception:
            pass

    ewh, lon, lat, t, meta = load_stack_any_cb(path)
    if ewh is None:
        return None, None, None, None, None
    return ewh.shape, lon, lat, t, meta or {}
