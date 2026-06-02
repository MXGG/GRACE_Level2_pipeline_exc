"""Stack (3D time series) save/load utilities."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import scipy.io as sio


@dataclass
class Stack:
    """3D stack data structure [nLon, nLat, Nt]."""
    tag: str
    ewh: np.ndarray  # [nLon, nLat, Nt]
    lon: np.ndarray
    lat: np.ndarray
    t: List[str]  # Time labels
    meta: Dict[str, Any] = field(default_factory=dict)


def _mat_to_string(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    if isinstance(value, str):
        return value
    if isinstance(value, np.ndarray):
        if value.size == 1:
            return _mat_to_string(value.item())
        return "".join(_mat_to_string(v) for v in value.flatten())
    if hasattr(value, "item"):
        try:
            return _mat_to_string(value.item())
        except Exception:
            pass
    return str(value)


def _decode_hdf5_time_values(values: np.ndarray) -> List[str]:
    flat = np.asarray(values).reshape(-1)
    return [
        value.decode("utf-8") if isinstance(value, (bytes, np.bytes_)) else str(value)
        for value in flat
    ]


def save_stack(
    stack: Stack,
    output_dir: str,
    suffix: str = '',
    compress: bool = True,
) -> str:
    """
    Save stack to MAT file.
    
    Args:
        stack: Stack object
        output_dir: Output directory
        suffix: Optional suffix for filename
    
    Returns:
        Path to saved file
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    filename = f"{stack.tag}_stack{suffix}.mat"
    filepath = os.path.join(output_dir, filename)
    
    # Use safe save
    temp_path = filepath + '.tmp'
    # Write a MATLAB-friendly struct variable named 'Stack' for compatibility
    # with legacy MATLAB outputs and external tooling.
    stack_payload = {
        "ewh": np.ascontiguousarray(np.asarray(stack.ewh, dtype=np.float32)),
        "lon": np.asarray(stack.lon),
        "lat": np.asarray(stack.lat),
        "t": np.asarray(list(stack.t), dtype=object),
        "tag": str(stack.tag),
    }
    if stack.meta:
        stack_payload["meta_json"] = json.dumps(stack.meta, ensure_ascii=False, default=str)

    # Keep the flat keys too (some downstream tools load these directly).
    payload = dict(stack_payload)
    payload["Stack"] = stack_payload
    sio.savemat(temp_path, payload, do_compression=compress, appendmat=False)

    os.replace(temp_path, filepath)
    
    return filepath


def load_stack(filepath: str) -> Stack:
    """
    Load stack from MAT file.
    
    Args:
        filepath: Path to stack file
    
    Returns:
        Stack object
    """
    data = sio.loadmat(filepath, squeeze_me=True, struct_as_record=False)

    # New format: a top-level struct called 'Stack'
    if "Stack" in data:
        try:
            s = data["Stack"]
            # scipy loads MATLAB structs as objects with attributes
            if hasattr(s, "__dict__") or hasattr(s, "ewh"):
                ewh = getattr(s, "ewh", None)
                lon = getattr(s, "lon", None)
                lat = getattr(s, "lat", None)
                t_data = getattr(s, "t", None)
                tag = getattr(s, "tag", "")
                meta_json = getattr(s, "meta_json", "")
                meta: Dict[str, Any] = {}
                try:
                    meta_text = _mat_to_string(meta_json)
                    if meta_text:
                        meta = json.loads(meta_text)
                except Exception:
                    meta = {}

                if isinstance(t_data, np.ndarray):
                    t = [_mat_to_string(x) for x in t_data.reshape(-1)]
                else:
                    t = list(t_data) if t_data is not None else []

                return Stack(
                    tag=_mat_to_string(tag),
                    ewh=np.array(ewh),
                    lon=np.array(lon).flatten(),
                    lat=np.array(lat).flatten(),
                    t=t,
                    meta=meta,
                )
        except Exception:
            # Fall back to legacy flat keys
            pass
    
    # Handle time array
    t_data = data.get('t', [])
    if isinstance(t_data, np.ndarray):
        t = [_mat_to_string(x) for x in t_data.flatten()]
    else:
        t = list(t_data)
    
    meta: Dict[str, Any] = {}
    if 'meta_json' in data:
        try:
            meta_text = _mat_to_string(data.get('meta_json', ''))
            if meta_text:
                meta = json.loads(meta_text)
        except Exception:
            meta = {}

    return Stack(
        tag=_mat_to_string(data.get('tag', '')) if 'tag' in data else '',
        ewh=np.array(data['ewh']),
        lon=np.array(data['lon']).flatten(),
        lat=np.array(data['lat']).flatten(),
        t=t,
        meta=meta,
    )


def save_stack_hdf5(
    stack: Stack,
    output_dir: str,
    suffix: str = "",
    compress_level: int = 1,
) -> str:
    """Save stack to HDF5 with one time slice per chunk."""
    try:
        import h5py
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("h5py is required for HDF5 stack output.") from exc

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    filename = f"{stack.tag}_stack{suffix}.h5"
    filepath = os.path.join(output_dir, filename)
    temp_path = filepath + ".tmp"

    ewh = np.ascontiguousarray(np.asarray(stack.ewh, dtype=np.float32))
    if ewh.ndim == 2:
        ewh = ewh[:, :, np.newaxis]
    nlon, nlat, _ = ewh.shape

    dataset_kwargs: Dict[str, Any] = {"chunks": (nlon, nlat, 1)}
    if int(compress_level) > 0:
        dataset_kwargs["compression"] = "gzip"
        dataset_kwargs["compression_opts"] = max(1, min(9, int(compress_level)))

    with h5py.File(temp_path, "w") as handle:
        handle.attrs["tag"] = str(stack.tag)
        handle.attrs["format_version"] = 1
        if stack.meta:
            handle.attrs["meta_json"] = json.dumps(stack.meta, ensure_ascii=False, default=str)
        handle.create_dataset("ewh", data=ewh, **dataset_kwargs)
        handle.create_dataset("lon", data=np.asarray(stack.lon, dtype=np.float64))
        handle.create_dataset("lat", data=np.asarray(stack.lat, dtype=np.float64))
        str_dtype = h5py.string_dtype(encoding="utf-8")
        handle.create_dataset("t", data=np.asarray(list(stack.t), dtype=object), dtype=str_dtype)

    os.replace(temp_path, filepath)
    return filepath


def load_stack_hdf5(filepath: str) -> Stack:
    """Load full stack from HDF5 sidecar."""
    try:
        import h5py
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("h5py is required for HDF5 stack input.") from exc

    with h5py.File(filepath, "r") as handle:
        tag = str(handle.attrs.get("tag", ""))
        meta_json = str(handle.attrs.get("meta_json", "") or "")
        ewh = np.asarray(handle["ewh"][()])
        lon = np.asarray(handle["lon"][()]).flatten()
        lat = np.asarray(handle["lat"][()]).flatten()
        t = _decode_hdf5_time_values(handle["t"][()])
    meta: Dict[str, Any] = {}
    if meta_json:
        try:
            meta = json.loads(meta_json)
        except Exception:
            meta = {}
    return Stack(tag=tag, ewh=ewh, lon=lon, lat=lat, t=t, meta=meta)


def load_stack_slice_hdf5(
    filepath: str,
    time_index: int = 0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Optional[str]]:
    """Load a single time slice from HDF5 without materializing the full stack."""
    try:
        import h5py
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("h5py is required for HDF5 stack input.") from exc

    with h5py.File(filepath, "r") as handle:
        ntime = int(handle["ewh"].shape[2])
        index = max(0, min(int(time_index), ntime - 1))
        ewh_slice = np.asarray(handle["ewh"][:, :, index])
        lon = np.asarray(handle["lon"][()]).flatten()
        lat = np.asarray(handle["lat"][()]).flatten()
        times = _decode_hdf5_time_values(handle["t"][()])
    t_val = times[index] if index < len(times) else None
    return ewh_slice, lon, lat, t_val


def find_stack_file(
    output_dir: str,
    tag: str,
    prefer_hdf5: bool = True,
) -> Optional[str]:
    """
    Find most recent stack file for given tag.
    
    Args:
        output_dir: Directory to search
        tag: Product tag
    
    Returns:
        Path to file or None
    """
    base = Path(output_dir)
    if prefer_hdf5:
        hdf5_matches = list(base.glob(f"{tag}_stack*.h5"))
        if hdf5_matches:
            return str(max(hdf5_matches, key=lambda p: p.stat().st_mtime))

    matches: List[Path] = list(base.glob(f"{tag}_stack*.mat"))
    
    if not matches:
        return None
    
    # Return most recent
    return str(max(matches, key=lambda p: p.stat().st_mtime))
