"""Stack loading implementation split from GUI service wrapper.

Optimisation changelog (2026-03-31):
  load_stack_slice_any – before falling back to full-stack materialisation,
    now checks for an HDF5 sidecar (.h5 file with the same stem).  If found,
    delegates to load_stack_slice_hdf5 which reads a single (nLon, nLat, 1)
    chunk — typically 259 KB instead of 41 MB for a 158-month stack.
  load_stack_any – passes variable_names to loadmat to avoid deserialising
    internal scipy MATLAB metadata arrays that are never used downstream.
"""

import json
from pathlib import Path

import numpy as np
from tkinter import simpledialog

from grace_pipeline.infra.io.nc_utils import var_attr_lower


_NC_EXTS = (".nc", ".nc4", ".cdf", ".hdf", ".h5", ".hdf5", ".he5")
_H5_EXTS = (".h5", ".hdf5", ".hdf", ".he5")


# ---------------------------------------------------------------------------
# Internal helpers  (unchanged)
# ---------------------------------------------------------------------------

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
    elif (
        lon_arr is not None
        and lat_arr is not None
        and data.shape == (lat_arr.size, lon_arr.size)
    ):
        data = data.T
    return np.asarray(data)


def _clamp_time_index(index, size):
    if size <= 0:
        return 0
    return max(0, min(int(index), int(size) - 1))


# ---------------------------------------------------------------------------
# load_stack_any  (minor: variable_names optimisation for MAT path)
# ---------------------------------------------------------------------------

def load_stack_any(
    path, active_var=None, selection_meta=None, select_nc_variables_cb=None
):
    """Load a full stack from any supported format (MAT / HDF5 / NetCDF / TXT).

    Changes vs original
    -------------------
    * MAT path: passes ``variable_names`` to loadmat so scipy skips
      deserialising all keys except the five we actually read.  This has
      marginal effect on total I/O time (the large ewh array dominates) but
      avoids scanning internal metadata arrays in structured MAT files.
    """
    path = path.strip()
    if not path:
        return None, None, None, None, None
    ext = Path(path).suffix.lower()
    is_nc = ext in (".nc", ".nc4", ".cdf", ".hdf", ".h5", ".hdf5", ".he5")
    is_h5 = ext in (".h5", ".hdf5", ".hdf", ".he5")

    # ── MAT v5/v6 via scipy ──────────────────────────────────────────────
    try:
        import scipy.io as sio

        # OPT: only deserialise the keys we actually use to skip internal
        # scipy metadata in large structured MAT files.
        _KNOWN_MAT_KEYS = ["ewh", "tws", "grid", "data", "lon", "long", "lat", "t", "tag", "ym", "meta", "P"]
        mat = sio.loadmat(
            path,
            squeeze_me=True,
            struct_as_record=False,
            variable_names=_KNOWN_MAT_KEYS,
        )

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

        if (ewh is None or lon is None or lat is None) and keys:
            def _ask_var(title, role):
                choices = ", ".join(keys)
                return simpledialog.askstring(
                    title,
                    f"Available variables: {choices}\nPlease input {role} variable name:",
                )
            if ewh is None:
                k = _ask_var("Select Data Variable", "data/grid")
                if k and k in mat:
                    ewh = mat.get(k)
            if lon is None:
                k = _ask_var("Select Longitude Variable", "lon")
                if k and k in mat:
                    lon = mat.get(k)
            if lat is None:
                k = _ask_var("Select Latitude Variable", "lat")
                if k and k in mat:
                    lat = mat.get(k)
            if t is None:
                k = _ask_var("Select Time Variable (optional)", "time")
                if k and k in mat:
                    t = mat.get(k)

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

        if (
            ewh is not None
            and lon is not None
            and lat is not None
            and ewh.ndim == 3
            and lon.ndim == 1
            and lat.ndim == 1
            and ewh.shape[0] == lat.size
            and ewh.shape[1] == lon.size
        ):
            ewh = ewh.transpose(1, 0, 2)

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
            try:
                if "tag" in mat:
                    tag_v = mat.get("tag")
                    if isinstance(tag_v, np.ndarray):
                        tag_v = tag_v.squeeze()
                        if isinstance(tag_v, np.ndarray) and tag_v.dtype.kind in ("U", "S"):
                            tag_v = (
                                "".join(tag_v.tolist()) if tag_v.ndim > 0 else str(tag_v.item())
                            )
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
                            ym_v = (
                                "".join(ym_v.tolist()) if ym_v.ndim > 0 else str(ym_v.item())
                            )
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

    # ── HDF5 / MAT v7.3 via h5py ─────────────────────────────────────────
    if (not is_nc) or is_h5:
        try:
            import h5py

            step = "open"
            with h5py.File(path, "r") as f:
                step = "flat_keys"
                ewh = f["ewh"] if "ewh" in f else None
                lon = f["lon"] if "lon" in f else None
                lat = f["lat"] if "lat" in f else None
                t = f["t"] if "t" in f else None

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

                if ewh is None or lon is None or lat is None:
                    step = "fallback_visit"
                    found = {}

                    def _visitor(name, obj):
                        if not hasattr(obj, "keys"):
                            return
                        if (
                            "ewh" in obj.keys()
                            and "lon" in obj.keys()
                            and "lat" in obj.keys()
                        ):
                            found["ewh"] = obj["ewh"]
                            found["lon"] = obj["lon"]
                            found["lat"] = obj["lat"]

                    f.visititems(_visitor)
                    if found:
                        ewh = found.get("ewh")
                        lon = found.get("lon")
                        lat = found.get("lat")

                if ewh is None or lon is None or lat is None:
                    step = "missing_keys"
                    return None, None, None, None, None

                step = "materialize_arrays"
                ewh_arr = ewh[()]
                if ewh_arr.ndim == 2:
                    ewh_arr = ewh_arr[:, :, None]
                lon_arr = lon[()].squeeze()
                lat_arr = lat[()].squeeze()
                if (
                    ewh_arr.ndim == 3
                    and lon_arr.ndim == 1
                    and lat_arr.ndim == 1
                    and ewh_arr.shape[0] == lat_arr.size
                    and ewh_arr.shape[1] == lon_arr.size
                ):
                    ewh_arr = ewh_arr.transpose(1, 0, 2)
                if t is not None and not hasattr(t, "keys"):
                    t_arr = t[()]
                else:
                    t_arr = None
                return (
                    ewh_arr,
                    lon_arr,
                    lat_arr,
                    t_arr,
                    {"active_var": "ewh", "data_var_names": ["ewh"]},
                )
        except Exception as e:
            if path.lower().endswith(".mat"):
                raise RuntimeError(f"HDF5 (.mat v7.3) load failed at {step}: {e}")
            pass

    # ── NetCDF ───────────────────────────────────────────────────────────
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
                    if str(k) in ds.variables
                    and getattr(ds.variables[str(k)], "ndim", 0) >= 2
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
                    return score

                available_data_keys = [
                    n for n in var_names
                    if n not in coord_keys
                    and getattr(ds.variables[n], "ndim", 0) >= 2
                ]
                if not selected_data_keys:
                    scored = sorted(
                        available_data_keys,
                        key=lambda n: _data_priority(n, ds.variables[n]),
                        reverse=True,
                    )
                    if select_nc_variables_cb and len(scored) > 1:
                        selected_data_keys = select_nc_variables_cb(scored) or [scored[0]]
                    else:
                        selected_data_keys = [scored[0]] if scored else []

                data_candidates = selected_data_keys or available_data_keys

                lon_1d = (
                    _materialize_array(ds.variables[lon_key]).squeeze()
                    if lon_key and lon_key in ds.variables
                    else None
                )
                lat_1d = (
                    _materialize_array(ds.variables[lat_key]).squeeze()
                    if lat_key and lat_key in ds.variables
                    else None
                )
                t_arr = None
                t_units = None
                t_cal = None
                if time_key and time_key in ds.variables:
                    t_var = ds.variables[time_key]
                    t_arr = _materialize_array(t_var).squeeze()
                    t_units = getattr(t_var, "units", None)
                    t_cal = getattr(t_var, "calendar", None)

                def _read_var(var):
                    return _materialize_array(var)

                def _normalize_nc_data(data, var, lon_key, lat_key, time_key, lon_1d, lat_1d, t_arr):
                    data = np.asarray(data)
                    dims = list(getattr(var, "dimensions", ()))
                    if data.ndim == 3 and time_key in dims:
                        time_i = dims.index(time_key)
                        if time_i != 0:
                            axes = list(range(data.ndim))
                            axes.pop(time_i)
                            data = np.transpose(data, [time_i] + axes)
                        data = np.moveaxis(data, 0, -1)
                        dims.pop(time_i)
                    elif data.ndim == 2:
                        data = data[:, :, None]
                    lon_i = dims.index(lon_key) if lon_key in dims else None
                    lat_i = dims.index(lat_key) if lat_key in dims else None
                    if (
                        lon_i is not None
                        and lat_i is not None
                        and (lon_i, lat_i) != (0, 1)
                    ):
                        axes_2d = [lon_i, lat_i, 2] if data.ndim == 3 else [lon_i, lat_i]
                        data = np.transpose(data, axes_2d)
                    elif (
                        lon_1d is not None
                        and lat_1d is not None
                        and data.ndim == 3
                        and data.shape[0] == lat_1d.size
                        and data.shape[1] == lon_1d.size
                    ):
                        data = data.transpose(1, 0, 2)
                    return data

                if lon_1d is None and lon_key:
                    try:
                        lon_arr_2d = _materialize_array(ds.variables[lon_key])
                        if lon_arr_2d.ndim == 2:
                            lon_1d = np.unique(lon_arr_2d)
                    except Exception:
                        pass
                if lat_1d is None and lat_key:
                    try:
                        lat_arr_2d = _materialize_array(ds.variables[lat_key])
                        if lat_arr_2d.ndim == 2:
                            lat_1d = np.unique(lat_arr_2d)
                    except Exception:
                        pass

                def _fallback_lonlat(data):
                    nonlocal lon_1d, lat_1d
                    if lon_1d is None or lat_1d is None:
                        try:
                            nlon_f = int(data.shape[0])
                            nlat_f = int(data.shape[1]) if data.ndim >= 2 else 0
                            if nlon_f > 0 and nlat_f > 0:
                                dlon = 360.0 / nlon_f
                                dlat = 180.0 / nlat_f
                                if lon_1d is None:
                                    lon_1d = np.linspace(-180 + 0.5 * dlon, 180 - 0.5 * dlon, nlon_f)
                                if lat_1d is None:
                                    lat_1d = np.linspace(-90 + 0.5 * dlat, 90 - 0.5 * dlat, nlat_f)
                        except Exception:
                            pass
                    return data

                if lon_1d is None and lon_key and lon_key in ds.variables:
                    lon_arr_raw = _materialize_array(ds.variables[lon_key])
                    if lon_arr_raw.ndim == 1:
                        lon_1d = lon_arr_raw.squeeze()
                if lat_1d is None and lat_key and lat_key in ds.variables:
                    lat_arr_raw = _materialize_array(ds.variables[lat_key])
                    if lat_arr_raw.ndim == 1:
                        lat_1d = lat_arr_raw.squeeze()

                if lon_1d is None and lon_key:
                    try:
                        lon_arr_2 = _materialize_array(ds.variables[lon_key])
                        if lon_arr_2.ndim == 2:
                            lon_1d = np.unique(lon_arr_2)
                    except Exception:
                        pass
                if lat_1d is None and lat_key:
                    try:
                        lat_arr_2 = _materialize_array(ds.variables[lat_key])
                        if lat_arr_2.ndim == 2:
                            lat_1d = np.unique(lat_arr_2)
                    except Exception:
                        pass

                if lon_1d is None and lon_key is None and lat_1d is None and lat_key is None:
                    if data_candidates:
                        try:
                            ref_var = ds.variables[data_candidates[0]]
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
                for key in data_candidates:
                    if key not in ds.variables:
                        continue
                    data_var = ds.variables[key]
                    data = _read_var(data_var)
                    data = _normalize_nc_data(
                        data, data_var, lon_key, lat_key, time_key, lon_1d, lat_1d, t_arr
                    )
                    data = _fallback_lonlat(data)
                    data_vars[key] = data

                if lon_1d is None or lat_1d is None:
                    raise ValueError("Unable to infer lon/lat coordinates from file.")
                if not data_vars:
                    raise ValueError("No data variables loaded from NetCDF.")

                active_var = next(iter(data_vars.keys()))
                meta = {
                    "data_var_names": list(
                        dict.fromkeys(
                            selected_data_keys or data_candidates or available_data_keys
                        )
                    ),
                    "active_var": active_var,
                    "lon_key": lon_key,
                    "lat_key": lat_key,
                    "time_key": time_key,
                    "time_units": t_units,
                    "time_calendar": t_cal,
                }
                return data_vars[active_var], lon_1d, lat_1d, t_arr, meta
            finally:
                try:
                    ds.close()
                except Exception:
                    pass
        except Exception as e:
            raise RuntimeError(f"NetCDF load failed: {e}")

    # ── Plain text (lon lat val) ──────────────────────────────────────────
    if path.lower().endswith(".txt"):
        data = np.genfromtxt(path, comments="#", delimiter=None)
        if data.shape[1] < 3:
            raise ValueError("TXT must have at least 3 columns: lon lat val")
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


# ---------------------------------------------------------------------------
# load_stack_slice_any  (HDF5 sidecar fast-path added)
# ---------------------------------------------------------------------------

def load_stack_slice_any(
    path, time_index=0, active_var=None, selection_meta=None
):
    """Load a single time slice for Preview without materialising the full stack.

    Fast-path priority
    ------------------
    1. **HDF5 sidecar** (.h5 alongside the .mat/.nc) — reads one
       (nLon, nLat, 1) chunk, typically ~259 KB for 360×180 float32.
    2. Native .h5 / .hdf5 slice via h5py with time-dim indexing.
    3. NetCDF slice via netCDF4 with time-dim indexing.
    4. Full-stack fallback via load_stack_any then slice in memory
       (for MAT v5 where partial reads are not possible).

    The sidecar path is the key optimisation for Preview in stack-mode runs:
    once the pipeline has written P4M6_stack.h5 alongside P4M6_stack.mat,
    every subsequent single-month Preview browse loads ~259 KB instead of
    the full ~41 MB array.
    """
    path = path.strip()
    if not path:
        return None, None, None, None, None
    ext = Path(path).suffix.lower()
    meta = dict(selection_meta or {})
    data_key = str(active_var or meta.get("active_var") or "").strip()

    # ── 1. HDF5 sidecar (.h5 next to the requested file) ─────────────────
    h5_sidecar = Path(path).with_suffix(".h5")
    if h5_sidecar.exists() and str(h5_sidecar) != path:
        try:
            from grace_pipeline.io.stack import load_stack_slice_hdf5

            ewh_slice, lon_arr, lat_arr, t_val = load_stack_slice_hdf5(
                str(h5_sidecar), time_index
            )
            frame_meta = dict(meta)
            frame_meta["active_var"] = "ewh"
            frame_meta["source"] = "hdf5_sidecar"
            return np.asarray(ewh_slice), lon_arr, lat_arr, t_val, frame_meta
        except Exception:
            pass  # fall through to next path

    # ── 2. Native NetCDF slice ────────────────────────────────────────────
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
                lon_arr = (
                    _materialize_array(ds.variables[lon_key]).squeeze()
                    if lon_key in ds.variables
                    else None
                )
                lat_arr = (
                    _materialize_array(ds.variables[lat_key]).squeeze()
                    if lat_key in ds.variables
                    else None
                )
                t_arr = (
                    _materialize_array(ds.variables[time_key]).squeeze()
                    if time_key in ds.variables
                    else None
                )
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
                data = _normalize_slice_to_lon_lat(
                    data, dims, lon_key, lat_key, lon_arr, lat_arr
                )
                t_val = None
                if t_arr is not None and np.asarray(t_arr).ndim > 0:
                    idx_t = _clamp_time_index(idx, np.asarray(t_arr).size)
                    t_flat = np.asarray(t_arr).reshape(-1)
                    t_val = t_flat[idx_t]
                frame_meta = dict(meta)
                frame_meta["active_var"] = data_key
                return np.asarray(data), lon_arr, lat_arr, t_val, frame_meta
            finally:
                ds.close()
        except Exception:
            pass

    # ── 3. Native HDF5 slice ──────────────────────────────────────────────
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

                lon_arr = (
                    np.asarray(lon_var[()]).squeeze() if lon_var is not None else None
                )
                lat_arr = (
                    np.asarray(lat_var[()]).squeeze() if lat_var is not None else None
                )
                t_arr = (
                    np.asarray(t_var[()]).squeeze()
                    if t_var is not None and not hasattr(t_var, "keys")
                    else None
                )
                shape = tuple(int(v) for v in data_var.shape)
                if len(shape) >= 3:
                    idx = _clamp_time_index(time_index, shape[2])
                    data = np.asarray(data_var[:, :, idx])
                else:
                    idx = 0
                    data = np.asarray(data_var[()])
                if (
                    lon_arr is not None
                    and lat_arr is not None
                    and data.shape == (lat_arr.size, lon_arr.size)
                ):
                    data = data.T
                t_val = None
                if t_arr is not None and np.asarray(t_arr).ndim > 0:
                    idx_t = _clamp_time_index(idx, np.asarray(t_arr).size)
                    t_flat = np.asarray(t_arr).reshape(-1)
                    t_val = t_flat[idx_t]
                frame_meta = dict(meta)
                frame_meta["active_var"] = data_key
                return np.asarray(data), lon_arr, lat_arr, t_val, frame_meta
        except Exception:
            pass

    # ── 4. Full-stack fallback (MAT v5 has no partial-read API) ──────────
    ewh, lon_arr, lat_arr, t_arr, meta_out = load_stack_any(
        path,
        active_var=active_var,
        selection_meta=selection_meta,
        select_nc_variables_cb=None,
    )
    if ewh is None:
        return None, None, None, None, None
    idx = _clamp_time_index(
        time_index, int(ewh.shape[2]) if np.asarray(ewh).ndim >= 3 else 1
    )
    grid = np.asarray(
        ewh[:, :, idx] if np.asarray(ewh).ndim >= 3 else np.asarray(ewh)
    )
    t_val = None
    if t_arr is not None:
        t_flat = np.asarray(t_arr).reshape(-1)
        if t_flat.size:
            t_val = t_flat[_clamp_time_index(idx, t_flat.size)]
    return grid, lon_arr, lat_arr, t_val, meta_out
