"""Stack loading implementation split from GUI service wrapper."""

import json
from pathlib import Path

import numpy as np


_NC_EXTS = (".nc", ".nc4", ".cdf", ".hdf", ".h5", ".hdf5", ".he5")
_H5_EXTS = (".h5", ".hdf5", ".hdf", ".he5")


def _attribute_case_insensitive(obj, key, default=None):
    """Read a NetCDF/HDF5 attribute without assuming its letter case."""

    try:
        return getattr(obj, key)
    except Exception:
        pass
    try:
        for name in obj.ncattrs():
            if str(name).lower() == str(key).lower():
                return obj.getncattr(name)
    except Exception:
        pass
    try:
        for name in obj.attrs.keys():
            if str(name).lower() == str(key).lower():
                return obj.attrs[name]
    except Exception:
        pass
    return default


def _attribute_text_lower(obj, key):
    value = _attribute_case_insensitive(obj, key, "")
    if isinstance(value, (bytes, bytearray, np.bytes_)):
        value = bytes(value).decode("utf-8", errors="replace")
    return str(value or "").lower()


def _decode_text(value):
    if isinstance(value, (bytes, bytearray, np.bytes_)):
        return bytes(value).decode("utf-8", errors="replace").strip("\x00")
    if isinstance(value, np.ndarray):
        if value.size == 0:
            return ""
        if value.size == 1:
            return _decode_text(value.reshape(-1)[0])
        if value.dtype.kind in {"U", "S"}:
            parts = [_decode_text(item) for item in value.reshape(-1)]
            if all(len(part) <= 1 for part in parts):
                return "".join(parts)
    if isinstance(value, np.generic):
        return _decode_text(value.item())
    return str(value or "").strip("\x00")


def _json_metadata(value):
    text = _decode_text(value).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except Exception:
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


def _time_length(values):
    if values is None:
        return None
    try:
        return int(np.asarray(values).reshape(-1).size)
    except Exception:
        return None


def _infer_stack_axes(shape, lon_size=None, lat_size=None, time_size=None):
    if len(shape) != 3:
        return None
    if lon_size is None or lat_size is None:
        return None
    try:
        lon_size = int(lon_size)
        lat_size = int(lat_size)
    except Exception:
        return None

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
                try:
                    time_size_i = int(time_size)
                except Exception:
                    time_size_i = None
                if time_size_i is not None:
                    if int(shape[time_i]) == time_size_i:
                        score += 6
                    if int(shape[lon_i]) == time_size_i:
                        score -= 2
                    if int(shape[lat_i]) == time_size_i:
                        score -= 2
            candidates.append((score, lon_i, lat_i, time_i))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    _, lon_i, lat_i, time_i = candidates[0]
    return lon_i, lat_i, time_i


def _normalize_stack_to_lon_lat_time(data, lon_arr=None, lat_arr=None, t_arr=None):
    arr = np.asarray(data)
    if arr.ndim == 2:
        return arr[:, :, None]
    if arr.ndim != 3:
        return arr

    lon_size = None
    lat_size = None
    if lon_arr is not None:
        lon_vec = np.asarray(lon_arr).squeeze()
        if lon_vec.ndim == 1:
            lon_size = int(lon_vec.size)
    if lat_arr is not None:
        lat_vec = np.asarray(lat_arr).squeeze()
        if lat_vec.ndim == 1:
            lat_size = int(lat_vec.size)

    axes = _infer_stack_axes(arr.shape, lon_size=lon_size, lat_size=lat_size, time_size=_time_length(t_arr))
    if axes is None:
        return arr
    if axes != (0, 1, 2):
        arr = np.transpose(arr, axes=axes)
    return np.asarray(arr)


def _decode_matlab_h5_cellstr(handle, values):
    """Decode MATLAB v7.3 cellstr/object-reference arrays into Python strings."""
    arr = np.asarray(values)
    if arr.size == 0:
        return arr
    if arr.dtype.kind == "S":
        return np.vectorize(
            lambda item: bytes(item).decode("utf-8", errors="replace").strip("\x00"),
            otypes=[object],
        )(arr)
    if arr.dtype.kind == "U":
        return arr.astype(object)
    if arr.dtype.kind != "O":
        return arr

    decoded = []
    flat = arr.reshape(-1)
    for item in flat:
        text = ""
        if isinstance(item, (bytes, bytearray, np.bytes_)):
            decoded.append(bytes(item).decode("utf-8", errors="replace").strip("\x00"))
            continue
        if isinstance(item, str):
            decoded.append(item.strip("\x00"))
            continue
        try:
            if item:
                target = handle[item]
                raw = np.asarray(target)
                chars = raw.reshape(-1, order="F")
                text = "".join(chr(int(v)) for v in chars if int(v) > 0)
        except Exception:
            text = str(item)
        decoded.append(text)
    return np.asarray(decoded, dtype=object).reshape(arr.shape, order="C")


def _materialize_array(var, selector=None):
    arr = var[:] if selector is None else var[selector]
    if isinstance(arr, np.ma.MaskedArray):
        arr = arr.filled(np.nan)
    arr = np.asarray(arr)
    scale = getattr(var, "scale_factor", None)
    offset = getattr(var, "add_offset", None)
    if scale not in (None, 1, 1.0) or offset not in (None, 0, 0.0):
        scale = 1.0 if scale is None else float(scale)
        offset = 0.0 if offset is None else float(offset)
        arr = arr * scale + offset
    fill = getattr(var, "_FillValue", None)
    if fill is None:
        fill = getattr(var, "missing_value", None)
    if fill is not None:
        try:
            arr = np.where(arr == fill, np.nan, arr)
        except Exception:
            pass
    return np.asarray(arr)


def _normalize_slice_to_lon_lat(data, dims, lon_key, lat_key, lon_arr, lat_arr):
    data = np.asarray(data)
    data = np.squeeze(data)
    if data.ndim != 2:
        raise ValueError("Expected a 2-D slice after time selection.")

    lon_i = dims.index(lon_key) if lon_key in dims else None
    lat_i = dims.index(lat_key) if lat_key in dims else None
    if lon_i is not None and lat_i is not None:
        if (lon_i, lat_i) != (0, 1):
            data = np.transpose(data, axes=(lon_i, lat_i))
    elif lon_arr is not None and lat_arr is not None and data.shape == (lat_arr.size, lon_arr.size):
        data = data.T
    return np.asarray(data)


def _clamp_time_index(index, size):
    if size <= 0:
        return 0
    return max(0, min(int(index), int(size) - 1))


def load_stack_any(path, active_var=None, selection_meta=None, select_nc_variables_cb=None):
    path = path.strip()
    if not path:
        return None, None, None, None, None
    ext = Path(path).suffix.lower()
    is_nc = ext in (".nc", ".nc4", ".cdf", ".hdf", ".h5", ".hdf5", ".he5")
    # Try h5py first for all HDF5-like files, then fallback to NetCDF parser.
    is_h5 = ext in (".h5", ".hdf5", ".hdf", ".he5")
    # Try MATLAB v7 or earlier via scipy.io.loadmat
    try:
        import scipy.io as sio
        known_mat_keys = [
            "ewh", "tws", "grid", "data", "lon", "long", "lat",
            "t", "tag", "ym", "meta", "meta_json", "P",
        ]

        def _load_mat(fast_only: bool):
            kwargs = {"squeeze_me": True, "struct_as_record": False}
            if fast_only:
                kwargs["variable_names"] = known_mat_keys
            return sio.loadmat(path, **kwargs)

        mat = _load_mat(fast_only=True)

        def _pick_key(keys, names):
            for k in keys:
                lk = k.lower()
                if any(n in lk for n in names):
                    return k
            return None

        keys = [k for k in mat.keys() if not k.startswith("__")]
        ewh = None
        lon = None
        lat = None
        t = None

        # Direct keys
        ewh_key = _pick_key(keys, ["ewh", "tws", "grid", "data"])
        lon_key = _pick_key(keys, ["lon", "long"])
        lat_key = _pick_key(keys, ["lat"])
        if ewh_key:
            ewh = mat.get(ewh_key)
        if lon_key:
            lon = mat.get(lon_key)
        if lat_key:
            lat = mat.get(lat_key)
        if "t" in mat:
            t = mat.get("t")

        if (ewh is None or lon is None or lat is None) and "P" not in mat:
            mat = _load_mat(fast_only=False)
            keys = [k for k in mat.keys() if not k.startswith("__")]
            ewh_key = _pick_key(keys, ["ewh", "tws", "grid", "data"])
            lon_key = _pick_key(keys, ["lon", "long"])
            lat_key = _pick_key(keys, ["lat"])
            if ewh_key:
                ewh = mat.get(ewh_key)
            if lon_key:
                lon = mat.get(lon_key)
            if lat_key:
                lat = mat.get(lat_key)
            if "t" in mat:
                t = mat.get("t")

        # Nested struct (e.g., P.grid.ewh)
        if ewh is None or lon is None or lat is None:
            try:
                P = mat.get("P")
                if P is not None and hasattr(P, "grid"):
                    g = P.grid
                    if ewh is None and hasattr(g, "ewh"):
                        ewh = g.ewh
                    if lon is None and hasattr(g, "lon"):
                        lon = g.lon
                    if lat is None and hasattr(g, "lat"):
                        lat = g.lat
                if t is None and P is not None and hasattr(P, "time"):
                    t = P.time
            except Exception:
                pass

        # MATLAB struct variable: Stack.ewh/lon/lat/t
        if ewh is None or lon is None or lat is None:
            try:
                S = mat.get("Stack")
                if S is not None and hasattr(S, "ewh"):
                    if ewh is None:
                        ewh = getattr(S, "ewh", None)
                    if lon is None:
                        lon = getattr(S, "lon", None)
                    if lat is None:
                        lat = getattr(S, "lat", None)
                    if t is None:
                        t = getattr(S, "t", None)
            except Exception:
                pass

        # Select a usable data variable without opening a secondary Tk dialog.
        # The Qt shell exposes variable choice in its own UI; this loader should
        # be deterministic when called from automated workflows or PySide slots.
        if (ewh is None or lon is None or lat is None) and keys:
            if ewh is None:
                preferred = []
                if active_var:
                    preferred.append(str(active_var))
                preferred.extend(["ewh", "tws", "grid", "data", "mean", "trend", "amp_ann", "amplitude", "mask"])
                lower_map = {str(k).lower(): k for k in keys}
                for name in preferred:
                    key = lower_map.get(str(name).lower())
                    if key and key in mat:
                        arr = mat.get(key)
                        if isinstance(arr, np.ndarray) and arr.ndim >= 2:
                            ewh = arr
                            ewh_key = key
                            break
                if ewh is None:
                    candidates = []
                    skip_names = {"lon", "long", "longitude", "lat", "latitude", "t", "time", "ym", "tag", "meta"}
                    for k in keys:
                        if str(k).lower() in skip_names:
                            continue
                        arr = mat.get(k)
                        if isinstance(arr, np.ndarray) and arr.ndim >= 2 and np.issubdtype(arr.dtype, np.number):
                            candidates.append((arr.ndim, arr.size, k))
                    if candidates:
                        candidates.sort(reverse=True)
                        ewh_key = candidates[0][2]
                        ewh = mat.get(ewh_key)
            if lon is None:
                for name in ("lon", "long", "longitude", "x"):
                    k = lower_map.get(name)
                    if k and k in mat:
                        lon = mat.get(k)
                        break
            if lat is None:
                for name in ("lat", "latitude", "y"):
                    k = lower_map.get(name)
                    if k and k in mat:
                        lat = mat.get(k)
                        break
            if t is None:
                for name in ("t", "time", "ym", "date"):
                    k = lower_map.get(name)
                    if k and k in mat:
                        t = mat.get(k)
                        break

        # Fallback: choose largest numeric array
        if ewh is None:
            candidates = []
            for k in keys:
                arr = mat.get(k)
                if isinstance(arr, np.ndarray) and arr.ndim >= 2:
                    candidates.append((arr.size, k))
            if candidates:
                candidates.sort(reverse=True)
                ewh = mat.get(candidates[0][1])

        if ewh is not None:
            ewh = np.asarray(ewh)
            if ewh.ndim == 2:
                ewh = ewh[:, :, None]

        if lon is not None:
            lon = np.asarray(lon).squeeze()
        if lat is not None:
            lat = np.asarray(lat).squeeze()

        if ewh is not None:
            ewh = _normalize_stack_to_lon_lat_time(ewh, lon_arr=lon, lat_arr=lat, t_arr=t)

        # If lon/lat missing, synthesize from grid size
        if ewh is not None and (lon is None or lat is None):
            nlon = ewh.shape[0]
            nlat = ewh.shape[1] if ewh.ndim >= 2 else 0
            if nlon and nlat:
                dlon = 360.0 / nlon
                dlat = 180.0 / nlat
                lon = np.linspace(-180 + 0.5 * dlon, 180 - 0.5 * dlon, nlon)
                lat = np.linspace(-90 + 0.5 * dlat, 90 - 0.5 * dlat, nlat)

        if ewh is not None and lon is not None and lat is not None:
            meta = {}
            meta.update(_json_metadata(mat.get("meta_json")))
            try:
                if "tag" in mat:
                    tag_v = mat.get("tag")
                    if isinstance(tag_v, np.ndarray):
                        tag_v = tag_v.squeeze()
                        if isinstance(tag_v, np.ndarray) and tag_v.dtype.kind in ("U", "S"):
                            tag_v = "".join(tag_v.tolist()) if tag_v.ndim > 0 else str(tag_v.item())
                        elif hasattr(tag_v, "item"):
                            tag_v = tag_v.item()
                    meta["tag"] = str(tag_v)
            except Exception:
                pass
            try:
                if "ym" in mat:
                    ym_v = mat.get("ym")
                    if isinstance(ym_v, np.ndarray):
                        ym_v = ym_v.squeeze()
                        if isinstance(ym_v, np.ndarray) and ym_v.dtype.kind in ("U", "S"):
                            ym_v = "".join(ym_v.tolist()) if ym_v.ndim > 0 else str(ym_v.item())
                        elif hasattr(ym_v, "item"):
                            ym_v = ym_v.item()
                    meta["ym"] = str(ym_v)
            except Exception:
                pass
            try:
                if "meta" in mat:
                    raw_meta = mat.get("meta")
                    if isinstance(raw_meta, np.ndarray):
                        raw_meta = raw_meta.squeeze()
                        if hasattr(raw_meta, "item"):
                            raw_meta = raw_meta.item()
                    if isinstance(raw_meta, dict):
                        meta.update(raw_meta)
                    elif isinstance(raw_meta, str):
                        s = raw_meta.strip()
                        if s.startswith("{") and s.endswith("}"):
                            try:
                                mobj = json.loads(s)
                                if isinstance(mobj, dict):
                                    meta.update(mobj)
                            except Exception:
                                pass
            except Exception:
                pass
            meta.setdefault("active_var", str(ewh_key) if ewh_key else "ewh")
            meta.setdefault("data_var_names", [meta["active_var"]])
            return ewh, lon, lat, t, meta
    except Exception:
        pass

    # Try MATLAB v7.3 or generic HDF5
    if (not is_nc) or is_h5:
        try:
            import h5py
            step = "open"
            with h5py.File(path, "r") as f:
                # Common flat keys
                step = "flat_keys"
                ewh = f["ewh"] if "ewh" in f else None
                lon = f["lon"] if "lon" in f else None
                lat = f["lat"] if "lat" in f else None
                t = f["t"] if "t" in f else None

                # Nested layout: P/grid/ewh, P/grid/lon, P/grid/lat
                if ewh is None or lon is None or lat is None:
                    step = "nested_P_grid"
                    if "P" in f:
                        p = f["P"]
                        if "grid" in p:
                            g = p["grid"]
                            ewh = g["ewh"] if "ewh" in g else None
                            lon = g["lon"] if "lon" in g else None
                            lat = g["lat"] if "lat" in g else None
                        if "time" in p:
                            t = p["time"]

                # Fallback: search any group containing ewh/lon/lat
                if ewh is None or lon is None or lat is None:
                    step = "fallback_visit"
                    found = {}
                    def _visitor(name, obj):
                        if not hasattr(obj, "keys"):
                            return
                        if "ewh" in obj.keys() and "lon" in obj.keys() and "lat" in obj.keys():
                            found["ewh"] = obj["ewh"]
                            found["lon"] = obj["lon"]
                            found["lat"] = obj["lat"]
                            if "t" in obj.keys():
                                found["t"] = obj["t"]
                            elif "time" in obj.keys():
                                found["t"] = obj["time"]
                    f.visititems(_visitor)
                    if found:
                        ewh = found.get("ewh")
                        lon = found.get("lon")
                        lat = found.get("lat")
                        if t is None:
                            t = found.get("t")

                if ewh is None or lon is None or lat is None:
                    step = "missing_keys"
                    return None, None, None, None, None

                step = "materialize_arrays"
                ewh_arr = ewh[()]
                lon_arr = lon[()].squeeze()
                lat_arr = lat[()].squeeze()
                if t is not None and not hasattr(t, "keys"):
                    t_arr = _decode_matlab_h5_cellstr(f, t[()])
                else:
                    t_arr = None
                ewh_arr = _normalize_stack_to_lon_lat_time(ewh_arr, lon_arr=lon_arr, lat_arr=lat_arr, t_arr=t_arr)
                meta = _json_metadata(_attribute_case_insensitive(f, "meta_json", ""))
                data_unit = _attribute_case_insensitive(ewh, "units", None)
                if data_unit is None:
                    data_unit = _attribute_case_insensitive(ewh, "unit", None)
                if data_unit is not None and str(data_unit).strip():
                    meta.setdefault("units", _decode_text(data_unit).strip())
                meta.setdefault("active_var", "ewh")
                meta.setdefault("data_var_names", ["ewh"])
                return ewh_arr, lon_arr, lat_arr, t_arr, meta
        except Exception as e:
            # Preserve error context for v7.3 MAT files.
            if path.lower().endswith(".mat"):
                raise RuntimeError(f"HDF5 (.mat v7.3) load failed at {step}: {e}")
            # For generic .h5/.hdf5, continue to NetCDF/plain-text fallback.
            pass

    # Try NetCDF
    if is_nc:
        try:
            import netCDF4 as nc
            ds = nc.Dataset(path)
            try:
                ds.set_auto_maskandscale(False)
            except Exception:
                pass
            try:
                var_names = list(ds.variables.keys())

                def _score_coord(v, kind):
                    name = v.name.lower()
                    std = _attribute_text_lower(v, "standard_name")
                    long = _attribute_text_lower(v, "long_name")
                    units = _attribute_text_lower(v, "units")
                    axis = _attribute_text_lower(v, "axis")
                    score = 0
                    if kind == "lon":
                        if name in ("lon", "longitude", "x") or name.endswith(("_lon", "_longitude")):
                            score += 3
                        if "longitude" in std or "longitude" in long:
                            score += 3
                        if axis == "x":
                            score += 2
                        if "degree" in units and ("east" in units or "e" == units):
                            score += 2
                    elif kind == "lat":
                        if name in ("lat", "latitude", "y") or name.endswith(("_lat", "_latitude")):
                            score += 3
                        if "latitude" in std or "latitude" in long:
                            score += 3
                        if axis == "y":
                            score += 2
                        if "degree" in units and ("north" in units or "n" == units):
                            score += 2
                    else:
                        if name == "time" or name.endswith("_time") or "time" in name:
                            score += 3
                        if name == "t":
                            score += 1
                        if "bounds" in name:
                            score -= 2
                        if axis == "t":
                            score += 2
                        if "since" in units or "days" in units or "seconds" in units or "hours" in units:
                            score += 2
                        if v.ndim == 1:
                            score += 2
                        elif v.ndim >= 2:
                            score -= 1
                    return score

                def _pick_coord(kind):
                    best = None
                    best_score = -1
                    for n in var_names:
                        v = ds.variables[n]
                        s = _score_coord(v, kind)
                        if s > best_score:
                            best = n
                            best_score = s
                    return best if best_score > 0 else None

                lon_key = _pick_coord("lon")
                lat_key = _pick_coord("lat")
                time_key = _pick_coord("time")

                selected_meta = selection_meta if isinstance(selection_meta, dict) else {}
                selected_lon = selected_meta.get("lon_key")
                selected_lat = selected_meta.get("lat_key")
                selected_time = selected_meta.get("time_key")
                selected_data_keys = selected_meta.get("data_var_names", [])
                selected_active = selected_meta.get("active_var")
                if isinstance(selected_data_keys, str):
                    selected_data_keys = [selected_data_keys]
                if (not selected_data_keys) and selected_active:
                    selected_data_keys = [selected_active]
                selected_data_keys = [
                    str(k)
                    for k in selected_data_keys
                    if str(k) in ds.variables and getattr(ds.variables[str(k)], "ndim", 0) >= 2
                ]
                if selected_lon in ds.variables:
                    lon_key = selected_lon
                if selected_lat in ds.variables:
                    lat_key = selected_lat
                if selected_time in ds.variables:
                    time_key = selected_time

                coord_keys = {k for k in [lon_key, lat_key, time_key] if k}

                def _data_priority(name, var):
                    low = str(name).lower()
                    long = _attribute_text_lower(var, "long_name")
                    units = _attribute_text_lower(var, "units")
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
                    std = _attribute_text_lower(var, "standard_name")
                    long = _attribute_text_lower(var, "long_name")
                    units = _attribute_text_lower(var, "units")
                    dims = tuple(getattr(var, "dimensions", ()))
                    if var.ndim < 2:
                        return False
                    # Exclude common auxiliary/bounds variables that often confuse
                    # monthly products like GLDAS.
                    if low.endswith("_bnds") or low.endswith("_bounds") or "bounds" in low:
                        return False
                    if "bounds" in std or "bounds" in long:
                        return False
                    if low in {"lat_bnds", "lon_bnds", "time_bnds"}:
                        return False
                    # Coordinate-like 2-D arrays should not be treated as data.
                    if lon_key and lat_key and dims == (lat_key, lon_key):
                        return False
                    if lon_key and lat_key and dims == (lon_key, lat_key):
                        if "degree" in units and ("east" in units or "north" in units):
                            return False
                    return True

                candidates = []
                data_candidates = []
                for n in var_names:
                    v = ds.variables[n]
                    if _is_data_candidate(n, v):
                        data_candidates.append(n)
                    if n in coord_keys or v.ndim < 2:
                        continue
                    if not _is_data_candidate(n, v):
                        continue
                    score = 0
                    if lon_key and lon_key in v.dimensions:
                        score += 2
                    if lat_key and lat_key in v.dimensions:
                        score += 2
                    if time_key and time_key in v.dimensions:
                        score += 1
                    score += _data_priority(n, v)
                    candidates.append((score, n))

                data_key = None
                if candidates:
                    candidates.sort(reverse=True)
                    data_key = candidates[0][1]

                if selected_data_keys:
                    data_keys = list(dict.fromkeys(selected_data_keys))
                elif lon_key is None or lat_key is None:
                    # Some HDF/HDF4 products (e.g. TRMM) store lon/lat only in
                    # global metadata. In this case do not force lon/lat UI input.
                    if data_key:
                        data_keys = [data_key]
                    elif data_candidates:
                        data_keys = [data_candidates[0]]
                    else:
                        data_keys = []
                else:
                    has_prior_selection = bool(selected_data_keys)
                    need_select = (data_key is None) and (not has_prior_selection)
                    if need_select:
                        if callable(select_nc_variables_cb):
                            picked = select_nc_variables_cb(ds, lon_key, lat_key, time_key, [data_key] if data_key else None)
                            if picked is None:
                                raise ValueError("NetCDF variable selection cancelled.")
                            lon_key, lat_key, time_key, data_keys = picked
                        else:
                            data_keys = [data_key] if data_key else ([data_candidates[0]] if data_candidates else [])
                    else:
                        data_keys = [data_key] if data_key else []

                if not data_keys:
                    raise ValueError("data variables not specified")
                available_data_keys = list(dict.fromkeys(data_keys))
                if active_var and active_var in available_data_keys:
                    data_keys = [active_var]
                else:
                    data_keys = [available_data_keys[0]]

                def _read_var(v):
                    arr = v[:]
                    if isinstance(arr, np.ma.MaskedArray):
                        arr = arr.filled(np.nan)
                    arr = np.asarray(arr)
                    scale = getattr(v, "scale_factor", None)
                    offset = getattr(v, "add_offset", None)
                    if scale not in (None, 1, 1.0) or offset not in (None, 0, 0.0):
                        scale = 1.0 if scale is None else float(scale)
                        offset = 0.0 if offset is None else float(offset)
                        arr = arr * scale + offset
                    fill = getattr(v, "_FillValue", None)
                    if fill is None:
                        fill = getattr(v, "missing_value", None)
                    if fill is not None:
                        try:
                            arr = np.where(arr == fill, np.nan, arr)
                        except Exception:
                            pass
                    return np.asarray(arr)

                lon_arr = _read_var(ds.variables[lon_key]).squeeze() if lon_key and lon_key in ds.variables else None
                lat_arr = _read_var(ds.variables[lat_key]).squeeze() if lat_key and lat_key in ds.variables else None
                t_arr = None
                t_units = None
                t_cal = None
                if time_key and time_key in ds.variables:
                    try:
                        t_var = ds.variables[time_key]
                        t_units = _attribute_case_insensitive(t_var, "units", None)
                        t_cal = _attribute_case_insensitive(t_var, "calendar", None)
                        t_arr = _read_var(t_var).squeeze()
                        try:
                            b_name = _attribute_case_insensitive(t_var, "bounds", None)
                            if b_name and b_name in ds.variables:
                                tb = _read_var(ds.variables[b_name])
                                tb = np.asarray(tb, dtype=float)
                                if tb.ndim == 2:
                                    if tb.shape[0] == 2:
                                        t_arr = np.nanmean(tb, axis=0)
                                    elif tb.shape[1] == 2:
                                        t_arr = np.nanmean(tb, axis=1)
                        except Exception:
                            pass
                        try:
                            if t_arr is not None and np.asarray(t_arr).ndim == 2:
                                arr2 = np.asarray(t_arr, dtype=float)
                                if arr2.shape[0] == 2:
                                    t_arr = np.nanmean(arr2, axis=0)
                                elif arr2.shape[1] == 2:
                                    t_arr = np.nanmean(arr2, axis=1)
                        except Exception:
                            pass
                        if t_units:
                            try:
                                from netCDF4 import num2date
                                t_arr = num2date(t_arr, t_units, calendar=t_cal or "standard")
                            except Exception:
                                pass
                    except Exception:
                        t_arr = None
                        t_units = None
                        t_cal = None

                def _to_1d(arr):
                    arr = np.asarray(arr)
                    if arr.ndim == 1:
                        return arr
                    if arr.ndim == 2:
                        if arr.shape[0] == 1 or arr.shape[1] == 1:
                            return arr.squeeze()
                        if np.allclose(arr, arr[0, :][None, :], equal_nan=True):
                            return arr[0, :]
                        if np.allclose(arr, arr[:, 0][:, None], equal_nan=True):
                            return arr[:, 0]
                    return None

                lon_1d = _to_1d(lon_arr)
                lat_1d = _to_1d(lat_arr)

                def _coords_from_grid_header(nlon_guess: int, nlat_guess: int):
                    txt = str(getattr(ds, "GridHeader", "") or "")
                    if not txt:
                        return None, None
                    kv = {}
                    for part in txt.split(";"):
                        if "=" not in part:
                            continue
                        k, v = part.split("=", 1)
                        kv[k.strip().lower()] = v.strip()
                    try:
                        west = float(kv.get("westboundingcoordinate"))
                        east = float(kv.get("eastboundingcoordinate"))
                        south = float(kv.get("southboundingcoordinate"))
                        north = float(kv.get("northboundingcoordinate"))
                        dlon = float(kv.get("longituderesolution"))
                        dlat = float(kv.get("latituderesolution"))
                        reg = kv.get("registration", "CENTER").upper()
                        if reg == "CENTER":
                            lon_g = np.linspace(west + 0.5 * dlon, east - 0.5 * dlon, nlon_guess)
                            lat_g = np.linspace(south + 0.5 * dlat, north - 0.5 * dlat, nlat_guess)
                        else:
                            lon_g = np.linspace(west, east, nlon_guess)
                            lat_g = np.linspace(south, north, nlat_guess)
                        return lon_g, lat_g
                    except Exception:
                        return None, None

                if lon_1d is None or lat_1d is None:
                    nlon_guess = 0
                    nlat_guess = 0
                    try:
                        ref_var = ds.variables[data_keys[0]]
                        if ref_var.ndim >= 2:
                            nlon_guess = int(ref_var.shape[0])
                            nlat_guess = int(ref_var.shape[1])
                    except Exception:
                        pass
                    if nlon_guess > 0 and nlat_guess > 0:
                        lon_h, lat_h = _coords_from_grid_header(nlon_guess, nlat_guess)
                        if lon_1d is None and lon_h is not None:
                            lon_1d = lon_h
                        if lat_1d is None and lat_h is not None:
                            lat_1d = lat_h

                def _normalize_nc_data(data, data_var, lon_key, lat_key, time_key, lon_1d, lat_1d, t_arr):
                    if data.ndim > 3:
                        data = np.squeeze(data)

                    dims = list(getattr(data_var, "dimensions", []))
                    lon_i = dims.index(lon_key) if lon_key in dims else None
                    lat_i = dims.index(lat_key) if lat_key in dims else None
                    time_i = dims.index(time_key) if time_key in dims else None

                    if lon_i is None and lon_1d is not None:
                        lon_i = next((i for i, s in enumerate(data.shape) if s == lon_1d.size), None)
                    if lat_i is None and lat_1d is not None:
                        lat_i = next((i for i, s in enumerate(data.shape) if s == lat_1d.size), None)
                    if time_i is None and t_arr is not None:
                        time_i = next((i for i, s in enumerate(data.shape) if s == t_arr.size), None)

                    axes_keep = [i for i in [lon_i, lat_i, time_i] if i is not None]
                    if data.ndim > 3:
                        extra = [i for i in range(data.ndim) if i not in axes_keep]
                        for ax in sorted(extra, reverse=True):
                            data = np.take(data, indices=0, axis=ax)
                            if lon_i is not None and ax < lon_i:
                                lon_i -= 1
                            if lat_i is not None and ax < lat_i:
                                lat_i -= 1
                            if time_i is not None and ax < time_i:
                                time_i -= 1

                    if data.ndim == 2:
                        if lon_i is not None and lat_i is not None:
                            order = [lon_i, lat_i]
                            data = np.transpose(data, axes=order)
                        elif lat_1d is not None and lon_1d is not None and data.shape == (lat_1d.size, lon_1d.size):
                            data = data.transpose(1, 0)
                        data = data[:, :, None]
                    elif data.ndim >= 3:
                        order = []
                        if lon_i is not None:
                            order.append(lon_i)
                        if lat_i is not None and lat_i not in order:
                            order.append(lat_i)
                        if time_i is not None and time_i not in order:
                            order.append(time_i)
                        rest = [i for i in range(data.ndim) if i not in order]
                        order += rest
                        data = np.transpose(data, axes=order)
                        if data.ndim == 2:
                            data = data[:, :, None]
                    return data

                if lon_1d is None and lon_arr is not None:
                    lon_1d = np.unique(lon_arr)
                if lat_1d is None and lat_arr is not None:
                    lat_1d = np.unique(lat_arr)
                if lon_1d is None or lat_1d is None:
                    # Final fallback to a regular global mesh from data shape.
                    try:
                        ref_var = ds.variables[data_keys[0]]
                        nlon_f = int(ref_var.shape[0])
                        nlat_f = int(ref_var.shape[1]) if ref_var.ndim >= 2 else 0
                        if nlon_f > 0 and nlat_f > 0:
                            dlon = 360.0 / nlon_f
                            dlat = 180.0 / nlat_f
                            if lon_1d is None:
                                lon_1d = np.linspace(-180 + 0.5 * dlon, 180 - 0.5 * dlon, nlon_f)
                            if lat_1d is None:
                                lat_1d = np.linspace(-90 + 0.5 * dlat, 90 - 0.5 * dlat, nlat_f)
                    except Exception:
                        pass

                data_vars = {}
                for key in data_keys:
                    if key not in ds.variables:
                        continue
                    data_var = ds.variables[key]
                    data = _read_var(data_var)
                    data = _normalize_nc_data(data, data_var, lon_key, lat_key, time_key, lon_1d, lat_1d, t_arr)
                    data_vars[key] = data

                if lon_1d is None or lat_1d is None:
                    raise ValueError("Unable to infer lon/lat coordinates from file.")
                if not data_vars:
                    raise ValueError("No data variables loaded from NetCDF.")

                active_var = next(iter(data_vars.keys()))
                active_units = _attribute_case_insensitive(
                    ds.variables[active_var], "units", None
                )
                meta = {
                    "data_var_names": list(dict.fromkeys(selected_data_keys or data_candidates or available_data_keys)),
                    "active_var": active_var,
                    "lon_key": lon_key,
                    "lat_key": lat_key,
                    "time_key": time_key,
                    "time_units": t_units,
                    "time_calendar": t_cal,
                }
                if active_units is not None and str(active_units).strip():
                    meta["units"] = _decode_text(active_units).strip()
                return data_vars[active_var], lon_1d, lat_1d, t_arr, meta
            finally:
                try:
                    ds.close()
                except Exception:
                    pass
        except Exception as e:
            raise RuntimeError(f"NetCDF load failed: {e}")

    # Try plain text (lon lat val)
    if path.lower().endswith(".txt"):
        delimiter = None
        with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
            for raw_line in handle:
                sample = raw_line.strip()
                if not sample or sample.startswith("#"):
                    continue
                if "," in sample:
                    delimiter = ","
                elif "\t" in sample:
                    delimiter = "\t"
                break
        data = np.genfromtxt(
            path,
            comments="#",
            delimiter=delimiter,
            dtype=float,
            encoding="utf-8-sig",
            invalid_raise=False,
        )
        data = np.asarray(data, dtype=float)
        if data.ndim == 1:
            data = data.reshape(1, -1)
        if data.ndim != 2 or data.shape[1] < 3:
            raise ValueError("TXT must have at least 3 columns: lon lat val")
        data = data[np.all(np.isfinite(data[:, :3]), axis=1)]
        if data.size == 0:
            raise ValueError("TXT contains no finite lon/lat/value rows")
        lon_vals = np.unique(data[:, 0])
        lat_vals = np.unique(data[:, 1])
        grid = np.full((len(lon_vals), len(lat_vals)), np.nan, dtype=float)
        lon_index = {v: i for i, v in enumerate(lon_vals)}
        lat_index = {v: i for i, v in enumerate(lat_vals)}
        for row in data:
            if len(row) < 3:
                continue
            i = lon_index[row[0]]
            j = lat_index[row[1]]
            grid[i, j] = row[2]
        return grid[:, :, None], lon_vals, lat_vals, None, None

    return None, None, None, None, None


def load_stack_slice_any(path, time_index=0, active_var=None, selection_meta=None):
    """Load a single time slice for Preview without materializing the full stack."""
    path = path.strip()
    if not path:
        return None, None, None, None, None
    ext = Path(path).suffix.lower()
    meta = dict(selection_meta or {})
    data_key = str(active_var or meta.get("active_var") or "").strip()

    h5_sidecar = Path(path).with_suffix(".h5")
    if h5_sidecar.exists() and str(h5_sidecar) != path:
        try:
            from grace_pipeline.io.stack import load_stack_slice_hdf5

            grid, lon_arr, lat_arr, t_val = load_stack_slice_hdf5(str(h5_sidecar), time_index)
            frame_meta = {}
            try:
                import h5py

                with h5py.File(h5_sidecar, "r") as handle:
                    frame_meta.update(
                        _json_metadata(
                            _attribute_case_insensitive(handle, "meta_json", "")
                        )
                    )
            except Exception:
                pass
            frame_meta.update(meta)
            frame_meta["active_var"] = "ewh"
            frame_meta["source"] = "hdf5_sidecar"
            return np.asarray(grid), lon_arr, lat_arr, t_val, frame_meta
        except Exception:
            pass

    if ext in _NC_EXTS and data_key:
        lon_key = meta.get("lon_key")
        lat_key = meta.get("lat_key")
        time_key = meta.get("time_key")
        try:
            import netCDF4 as nc

            ds = nc.Dataset(path)
            try:
                try:
                    ds.set_auto_maskandscale(False)
                except Exception:
                    pass
                if data_key not in ds.variables:
                    raise KeyError(f"{data_key} not found in dataset.")
                lon_arr = _materialize_array(ds.variables[lon_key]).squeeze() if lon_key in ds.variables else None
                lat_arr = _materialize_array(ds.variables[lat_key]).squeeze() if lat_key in ds.variables else None
                t_arr = _materialize_array(ds.variables[time_key]).squeeze() if time_key in ds.variables else None
                data_var = ds.variables[data_key]
                dims = list(getattr(data_var, "dimensions", ()))
                if time_key in dims and data_var.ndim >= 3:
                    time_i = dims.index(time_key)
                    idx = _clamp_time_index(time_index, int(data_var.shape[time_i]))
                    selector = [slice(None)] * data_var.ndim
                    selector[time_i] = idx
                    data = _materialize_array(data_var, tuple(selector))
                    dims.pop(time_i)
                else:
                    idx = 0
                    data = _materialize_array(data_var)
                data = _normalize_slice_to_lon_lat(data, dims, lon_key, lat_key, lon_arr, lat_arr)
                t_val = None
                if t_arr is not None and np.asarray(t_arr).ndim > 0:
                    idx_t = _clamp_time_index(idx, np.asarray(t_arr).size)
                    t_flat = np.asarray(t_arr).reshape(-1)
                    t_val = t_flat[idx_t]
                frame_meta = dict(meta)
                frame_meta["active_var"] = data_key
                data_units = _attribute_case_insensitive(data_var, "units", None)
                if data_units is not None and str(data_units).strip():
                    frame_meta["units"] = _decode_text(data_units).strip()
                if time_key in ds.variables:
                    time_var = ds.variables[time_key]
                    frame_meta["time_units"] = _attribute_case_insensitive(
                        time_var, "units", frame_meta.get("time_units")
                    )
                    frame_meta["time_calendar"] = _attribute_case_insensitive(
                        time_var, "calendar", frame_meta.get("time_calendar")
                    )
                return np.asarray(data), lon_arr, lat_arr, t_val, frame_meta
            finally:
                ds.close()
        except Exception:
            pass

    if ext in _H5_EXTS and data_key:
        try:
            import h5py

            with h5py.File(path, "r") as f:
                if data_key in f:
                    data_var = f[data_key]
                    lon_var = f["lon"] if "lon" in f else None
                    lat_var = f["lat"] if "lat" in f else None
                    t_var = f["t"] if "t" in f else None
                elif "P" in f and "grid" in f["P"] and data_key == "ewh":
                    grid_group = f["P"]["grid"]
                    if "ewh" not in grid_group:
                        raise KeyError("ewh not found in HDF5 grid group.")
                    data_var = grid_group["ewh"]
                    lon_var = grid_group["lon"] if "lon" in grid_group else None
                    lat_var = grid_group["lat"] if "lat" in grid_group else None
                    t_var = f["P"]["time"] if "time" in f["P"] else None
                else:
                    raise KeyError(f"{data_key} not found in HDF5 file.")

                lon_arr = np.asarray(lon_var[()]).squeeze() if lon_var is not None else None
                lat_arr = np.asarray(lat_var[()]).squeeze() if lat_var is not None else None
                t_arr = None
                if t_var is not None and not hasattr(t_var, "keys"):
                    t_arr = np.asarray(_decode_matlab_h5_cellstr(f, t_var[()])).squeeze()
                shape = tuple(int(v) for v in data_var.shape)
                if len(shape) >= 3:
                    axes = _infer_stack_axes(
                        shape,
                        lon_size=(lon_arr.size if isinstance(lon_arr, np.ndarray) and lon_arr.ndim == 1 else None),
                        lat_size=(lat_arr.size if isinstance(lat_arr, np.ndarray) and lat_arr.ndim == 1 else None),
                        time_size=_time_length(t_arr),
                    )
                    if axes is None:
                        axes = (0, 1, 2)
                    lon_i, lat_i, time_i = axes
                    idx = _clamp_time_index(time_index, shape[time_i])
                    selector = [slice(None)] * len(shape)
                    selector[time_i] = idx
                    data = np.asarray(data_var[tuple(selector)])
                    two_d_axes = [lon_i, lat_i]
                    if time_i < lon_i:
                        two_d_axes[0] -= 1
                    if time_i < lat_i:
                        two_d_axes[1] -= 1
                    if tuple(two_d_axes) != (0, 1):
                        data = np.transpose(data, axes=tuple(two_d_axes))
                else:
                    idx = 0
                    data = np.asarray(data_var[()])
                if lon_arr is not None and lat_arr is not None and data.shape == (lat_arr.size, lon_arr.size):
                    data = data.T
                t_val = None
                if t_arr is not None and np.asarray(t_arr).ndim > 0:
                    idx_t = _clamp_time_index(idx, np.asarray(t_arr).size)
                    t_flat = np.asarray(t_arr).reshape(-1)
                    t_val = t_flat[idx_t]
                frame_meta = _json_metadata(
                    _attribute_case_insensitive(f, "meta_json", "")
                )
                frame_meta.update(meta)
                frame_meta["active_var"] = data_key
                data_units = _attribute_case_insensitive(data_var, "units", None)
                if data_units is None:
                    data_units = _attribute_case_insensitive(data_var, "unit", None)
                if data_units is not None and str(data_units).strip():
                    frame_meta.setdefault("units", _decode_text(data_units).strip())
                return np.asarray(data), lon_arr, lat_arr, t_val, frame_meta
        except Exception:
            pass

    ewh, lon_arr, lat_arr, t_arr, meta_out = load_stack_any(
        path,
        active_var=active_var,
        selection_meta=selection_meta,
        select_nc_variables_cb=None,
    )
    if ewh is None:
        return None, None, None, None, None
    idx = _clamp_time_index(time_index, int(ewh.shape[2]) if np.asarray(ewh).ndim >= 3 else 1)
    grid = np.asarray(ewh[:, :, idx] if np.asarray(ewh).ndim >= 3 else np.asarray(ewh))
    t_val = None
    if t_arr is not None:
        t_flat = np.asarray(t_arr).reshape(-1)
        if t_flat.size:
            t_val = t_flat[_clamp_time_index(idx, t_flat.size)]
    return grid, lon_arr, lat_arr, t_val, meta_out



