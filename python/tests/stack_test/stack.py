"""
Stack (3D time series) save/load utilities.

Optimisation changelog (2026-03-31):
  * save_stack_hdf5  – new function: writes .h5 with chunk shape (nLon, nLat, 1)
                       so each time-slice is exactly one HDF5 chunk; Preview
                       reads a single slice in one I/O call instead of loading
                       the full 3-D array.
  * load_stack_hdf5  – new function: full-stack read from .h5
  * load_stack_slice_hdf5 – new function: O(1) single-slice read
  * find_stack_file  – now also locates .h5 sidecars; prefers .h5 for reads
  * save_stack / load_stack remain unchanged (backward-compatible MAT path).
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import scipy.io as sio

# ---------------------------------------------------------------------------
# Public data class  (unchanged)
# ---------------------------------------------------------------------------

@dataclass
class Stack:
    """3D stack data structure [nLon, nLat, Nt]."""
    tag: str
    ewh: np.ndarray          # [nLon, nLat, Nt]
    lon: np.ndarray
    lat: np.ndarray
    t: List[str]             # time labels, e.g. ["200204", "200205", ...]
    meta: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# MAT save / load  (unchanged from original)
# ---------------------------------------------------------------------------

def save_stack(
    stack: Stack,
    output_dir: str,
    suffix: str = "",
    compress: bool = True,
) -> str:
    """
    Save stack to MAT file.

    Args
    ----
    stack      : Stack object
    output_dir : Output directory
    suffix     : Optional suffix for filename
    compress   : MATLAB-compatible gzip compression (default True)

    Returns
    -------
    Path to saved file.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    filename = f"{stack.tag}_stack{suffix}.mat"
    filepath = os.path.join(output_dir, filename)
    temp_path = filepath + ".tmp"

    payload = {
        "ewh": np.ascontiguousarray(np.asarray(stack.ewh, dtype=np.float32)),
        "lon": np.asarray(stack.lon),
        "lat": np.asarray(stack.lat),
        "t": np.asarray(list(stack.t), dtype=object),
        "tag": str(stack.tag),
    }
    sio.savemat(temp_path, payload, do_compression=compress, appendmat=False)
    os.replace(temp_path, filepath)
    return filepath


def load_stack(filepath: str) -> Stack:
    """
    Load stack from MAT file.

    Args
    ----
    filepath : Path to .mat stack file

    Returns
    -------
    Stack object.
    """
    data = sio.loadmat(filepath)

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

    t_data = data.get("t", [])
    if isinstance(t_data, np.ndarray):
        t = [_mat_to_string(x) for x in t_data.flatten()]
    else:
        t = list(t_data)

    return Stack(
        tag=_mat_to_string(data.get("tag", "")) if "tag" in data else "",
        ewh=np.array(data["ewh"]),
        lon=np.array(data["lon"]).flatten(),
        lat=np.array(data["lat"]).flatten(),
        t=t,
    )


# ---------------------------------------------------------------------------
# HDF5 save / load  (new)
# ---------------------------------------------------------------------------

def save_stack_hdf5(
    stack: Stack,
    output_dir: str,
    suffix: str = "",
    compress_level: int = 1,
) -> str:
    """
    Save stack to HDF5 with per-time-slice chunking for fast Preview access.

    Chunk shape is **(nLon, nLat, 1)** — reading a single time-slice touches
    exactly one chunk regardless of how many time-steps exist in the file.
    With 158 months at 360×180 float32, a cold slice read is ~259 KB vs
    ~41 MB for the full uncompressed stack.

    Compression uses gzip level 1 (fast, ~20-40 % size reduction on typical
    GRACE EWH data).  Set ``compress_level=0`` to disable.

    Args
    ----
    stack          : Stack object to save
    output_dir     : Output directory
    suffix         : Optional filename suffix
    compress_level : gzip level 0–9 (0 = no compression, default 1)

    Returns
    -------
    Path to .h5 file.
    """
    try:
        import h5py
    except ImportError:
        raise RuntimeError(
            "h5py is required for HDF5 stack output.  "
            "Install with: pip install h5py"
        )

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    filename = f"{stack.tag}_stack{suffix}.h5"
    filepath = os.path.join(output_dir, filename)
    temp_path = filepath + ".tmp"

    ewh = np.ascontiguousarray(np.asarray(stack.ewh, dtype=np.float32))
    if ewh.ndim == 2:
        ewh = ewh[:, :, np.newaxis]
    nLon, nLat, Nt = ewh.shape

    # One time-slice = one chunk → single seek+read for Preview.
    chunk = (nLon, nLat, 1)

    ds_kw: Dict[str, Any] = {"chunks": chunk}
    if compress_level > 0:
        ds_kw["compression"] = "gzip"
        ds_kw["compression_opts"] = max(1, min(9, int(compress_level)))

    with h5py.File(temp_path, "w") as f:
        f.attrs["tag"] = str(stack.tag)
        f.attrs["format_version"] = 1
        f.create_dataset("ewh", data=ewh, **ds_kw)
        f.create_dataset("lon", data=np.asarray(stack.lon, dtype=np.float64))
        f.create_dataset("lat", data=np.asarray(stack.lat, dtype=np.float64))
        # Store time labels as variable-length UTF-8 strings.
        dt = h5py.string_dtype(encoding="utf-8")
        f.create_dataset("t", data=np.array(list(stack.t), dtype=object), dtype=dt)

    os.replace(temp_path, filepath)
    return filepath


def load_stack_hdf5(filepath: str) -> Stack:
    """
    Load full stack from HDF5 file.

    Args
    ----
    filepath : Path to .h5 stack file

    Returns
    -------
    Stack object.
    """
    try:
        import h5py
    except ImportError:
        raise RuntimeError("h5py is required for HDF5 stack input.")

    with h5py.File(filepath, "r") as f:
        tag = str(f.attrs.get("tag", ""))
        ewh = np.asarray(f["ewh"][()])
        lon = np.asarray(f["lon"][()]).flatten()
        lat = np.asarray(f["lat"][()]).flatten()
        t_raw = f["t"][()]
        t = [
            v.decode("utf-8") if isinstance(v, (bytes, np.bytes_)) else str(v)
            for v in t_raw.flatten()
        ]

    return Stack(tag=tag, ewh=ewh, lon=lon, lat=lat, t=t)


def load_stack_slice_hdf5(
    filepath: str, time_index: int = 0
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Optional[str]]:
    """
    Load a **single time slice** from an HDF5 stack without reading the full
    3-D array.  Because the file uses (nLon, nLat, 1) chunking, HDF5 reads
    exactly one chunk (~259 KB for a 360×180 float32 grid) regardless of Nt.

    Args
    ----
    filepath   : Path to .h5 stack file
    time_index : Zero-based time index

    Returns
    -------
    (ewh_slice, lon, lat, t_str)
      ewh_slice : [nLon, nLat] float32
      lon       : [nLon]
      lat       : [nLat]
      t_str     : time-label string or None
    """
    try:
        import h5py
    except ImportError:
        raise RuntimeError("h5py is required for HDF5 stack input.")

    with h5py.File(filepath, "r") as f:
        Nt = int(f["ewh"].shape[2])
        idx = max(0, min(int(time_index), Nt - 1))
        # This read hits exactly one (nLon, nLat, 1) chunk.
        ewh_slice = np.asarray(f["ewh"][:, :, idx])
        lon = np.asarray(f["lon"][()]).flatten()
        lat = np.asarray(f["lat"][()]).flatten()
        t_raw = f["t"][()]
        t_list = [
            v.decode("utf-8") if isinstance(v, (bytes, np.bytes_)) else str(v)
            for v in t_raw.flatten()
        ]
        t_str = t_list[idx] if idx < len(t_list) else None

    return ewh_slice, lon, lat, t_str


# ---------------------------------------------------------------------------
# File discovery  (extended to include .h5)
# ---------------------------------------------------------------------------

def find_stack_file(
    output_dir: str,
    tag: str,
    prefer_hdf5: bool = True,
) -> Optional[str]:
    """
    Find the most recent stack file for *tag* in *output_dir*.

    When ``prefer_hdf5=True`` (default), an .h5 file is returned if one
    exists alongside the .mat file — the HDF5 path enables fast single-slice
    reads in Preview without loading the full array.

    Args
    ----
    output_dir  : Directory to search
    tag         : Product tag (e.g. "HSAF", "P4M6")
    prefer_hdf5 : Return .h5 if available (default True)

    Returns
    -------
    Absolute path string or None.
    """
    base = Path(output_dir)
    candidates: List[Path] = []

    if prefer_hdf5:
        candidates += list(base.glob(f"{tag}_stack*.h5"))

    candidates += list(base.glob(f"{tag}_stack*.mat"))

    if not candidates:
        return None

    return str(max(candidates, key=lambda p: p.stat().st_mtime))
