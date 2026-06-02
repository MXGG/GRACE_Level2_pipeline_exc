"""Parse GRACE GNV1B orbit files and build monthly ground-track bundle templates."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple
import tarfile
from urllib.error import HTTPError

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import hilbert

from grace_pipeline.app.grace_l1b_fetch import build_gfz_target, download_target


GNV_RECORD_DTYPE = np.dtype(
    [
        ("gps_time", ">i4"),
        ("grace_id", "S1"),
        ("coord_ref", "S1"),
        ("xpos", ">f8"),
        ("ypos", ">f8"),
        ("zpos", ">f8"),
        ("xpos_err", ">f8"),
        ("ypos_err", ">f8"),
        ("zpos_err", ">f8"),
        ("xvel", ">f8"),
        ("yvel", ">f8"),
        ("zvel", ">f8"),
        ("xvel_err", ">f8"),
        ("yvel_err", ">f8"),
        ("zvel_err", ">f8"),
        ("qualflg", "u1"),
    ],
    align=False,
)


@dataclass(frozen=True)
class GroundTrackBundle:
    month: str
    density: np.ndarray
    lon: np.ndarray
    lat: np.ndarray
    counts: int
    archive_path: Path
    meta: Dict[str, float]


def _read_header_length(blob: bytes) -> int:
    line_len = 81
    end_marker = b"END OF HEADER"
    pos = blob.find(end_marker)
    if pos < 0:
        raise ValueError("END OF HEADER marker not found in GNV1B file.")
    line_start = pos - (pos % line_len)
    return line_start + line_len


def parse_gnv1b_bytes(blob: bytes) -> np.ndarray:
    header_len = _read_header_length(blob)
    payload = memoryview(blob)[header_len:]
    nrec = len(payload) // GNV_RECORD_DTYPE.itemsize
    if nrec <= 0:
        return np.zeros(0, dtype=GNV_RECORD_DTYPE)
    payload = payload[: nrec * GNV_RECORD_DTYPE.itemsize]
    return np.frombuffer(payload, dtype=GNV_RECORD_DTYPE, count=nrec)


def _ecef_to_geodetic_deg(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    a = 6378137.0
    e2 = 6.69437999014e-3
    lon = np.degrees(np.arctan2(y, x))
    p = np.sqrt(x * x + y * y)
    lat = np.arctan2(z, p * (1.0 - e2))
    for _ in range(5):
        sin_lat = np.sin(lat)
        n = a / np.sqrt(1.0 - e2 * sin_lat * sin_lat)
        h = p / np.maximum(np.cos(lat), np.finfo(float).eps) - n
        lat = np.arctan2(z, p * (1.0 - e2 * n / np.maximum(n + h, np.finfo(float).eps)))
    return ((lon + 180.0) % 360.0) - 180.0, np.degrees(lat)


def _grid_edges(vec: np.ndarray) -> np.ndarray:
    v = np.asarray(vec, dtype=float).ravel()
    if v.size < 2:
        return np.asarray([v[0] - 0.5, v[0] + 0.5], dtype=float)
    dv = np.diff(v)
    edges = np.empty(v.size + 1, dtype=float)
    edges[1:-1] = 0.5 * (v[:-1] + v[1:])
    edges[0] = v[0] - 0.5 * dv[0]
    edges[-1] = v[-1] + 0.5 * dv[-1]
    return edges


def _build_density_from_lonlat(lon: np.ndarray, lat: np.ndarray, lon_vec: np.ndarray, lat_vec: np.ndarray) -> np.ndarray:
    lon_edges = _grid_edges(lon_vec)
    lat_edges = _grid_edges(lat_vec)
    hist, _, _ = np.histogram2d(lon, lat, bins=[lon_edges, lat_edges])
    return hist.astype(float)


def _row_normalize(density: np.ndarray) -> np.ndarray:
    out = np.asarray(density, dtype=float).copy()
    for j in range(out.shape[1]):
        row = out[:, j]
        if not np.any(np.isfinite(row)):
            continue
        row = row - np.nanmean(row)
        std = float(np.nanstd(row))
        if std > 0:
            out[:, j] = row / std
        else:
            out[:, j] = 0.0
    return out


def _bandpass_rowwise(grid: np.ndarray, center: float, width: float) -> np.ndarray:
    arr = np.asarray(grid, dtype=float)
    out = np.zeros_like(arr)
    nlon = arr.shape[0]
    freqs = np.fft.rfftfreq(nlon, d=1.0)
    band = np.abs(freqs - float(center)) <= max(1.5 * float(width), 1.0 / max(8, nlon))
    if not np.any(band):
        band[int(np.argmin(np.abs(freqs - float(center))))] = True
    for j in range(arr.shape[1]):
        row = arr[:, j] - float(np.nanmean(arr[:, j]))
        spec = np.fft.rfft(row)
        filt = np.zeros_like(spec)
        filt[band] = spec[band]
        out[:, j] = np.fft.irfft(filt, n=nlon)
    return out


def build_bundle_template_from_density(
    density: np.ndarray,
    center: float,
    width: float,
    *,
    lat_smooth: int = 5,
    lon_smooth: int = 9,
) -> np.ndarray:
    norm = _row_normalize(density)
    band = _bandpass_rowwise(norm, center=center, width=width)
    if lon_smooth > 1:
        band = uniform_filter1d(band, size=int(max(1, lon_smooth)), axis=0, mode="wrap")
    if lat_smooth > 1:
        band = uniform_filter1d(band, size=int(max(1, lat_smooth)), axis=1, mode="nearest")
    return _row_normalize(band)


def build_bundle_phase_unit(template: np.ndarray) -> np.ndarray:
    arr = np.asarray(template, dtype=float)
    unit = np.ones(arr.shape, dtype=complex)
    for j in range(arr.shape[1]):
        row = arr[:, j] - float(np.nanmean(arr[:, j]))
        if not np.any(np.isfinite(row)) or float(np.nanstd(row)) <= 0:
            continue
        analytic = hilbert(row)
        mag = np.maximum(np.abs(analytic), np.finfo(float).eps)
        unit[:, j] = analytic / mag
    return unit


def build_bundle_order_scores(
    template: np.ndarray,
    lmax: int,
    *,
    smooth_window: int = 5,
    m_start: int = 6,
) -> np.ndarray:
    arr = np.asarray(template, dtype=float)
    if arr.ndim != 2 or arr.size == 0:
        return np.zeros(int(lmax) + 1, dtype=float)
    spec = np.abs(np.fft.rfft(arr, axis=0)) ** 2
    if spec.ndim != 2 or spec.shape[0] == 0:
        return np.zeros(int(lmax) + 1, dtype=float)
    lat_weight = np.nanstd(arr, axis=0)
    if not np.any(np.isfinite(lat_weight)) or float(np.nansum(lat_weight)) <= 0:
        lat_weight = np.ones(arr.shape[1], dtype=float)
    avg_power = np.average(spec, axis=1, weights=np.asarray(lat_weight, dtype=float))
    scores = np.zeros(int(lmax) + 1, dtype=float)
    limit = min(int(lmax), int(avg_power.size) - 1)
    if limit >= 0:
        scores[: limit + 1] = np.asarray(avg_power[: limit + 1], dtype=float)
    if smooth_window > 1:
        scores = uniform_filter1d(scores, size=int(max(1, smooth_window)), mode="nearest")
    scores[: max(0, int(m_start))] = 0.0
    taper = np.linspace(0.0, 1.0, scores.size, dtype=float) ** 0.5
    scores = scores * taper
    finite = np.isfinite(scores)
    if not np.any(finite):
        return np.zeros_like(scores)
    maxv = float(np.nanmax(scores))
    if maxv > 0:
        scores = scores / maxv
    return np.clip(scores, 0.0, 1.0)


def build_monthly_groundtrack_bundle(
    *,
    month: str,
    lon_vec: Sequence[float],
    lat_vec: Sequence[float],
    cache_dir: Path,
    release: str = "RL03",
    satellites: Iterable[str] = ("A", "B"),
) -> GroundTrackBundle:
    cache_dir.mkdir(parents=True, exist_ok=True)
    lon_arr = np.asarray(lon_vec, dtype=float)
    lat_arr = np.asarray(lat_vec, dtype=float)
    key = f"bundle_{release.lower()}_{month}_{len(lon_arr)}x{len(lat_arr)}.npz"
    cache_path = cache_dir / key
    if cache_path.exists():
        data = np.load(cache_path, allow_pickle=True)
        return GroundTrackBundle(
            month=month,
            density=np.asarray(data["density"], dtype=float),
            lon=np.asarray(data["lon"], dtype=float),
            lat=np.asarray(data["lat"], dtype=float),
            counts=int(data["counts"]),
            archive_path=Path(str(data["archive_path"])),
            meta=dict(data["meta"].item()),
        )

    target = build_gfz_target(release=release, month=month)
    archive_path = download_target(target, cache_dir)
    satellites = tuple(str(s).upper() for s in satellites)
    density = np.zeros((lon_arr.size, lat_arr.size), dtype=float)
    total_points = 0
    file_count = 0
    with tarfile.open(archive_path, "r:gz") as tar:
        for member in tar.getmembers():
            name = Path(member.name).name.upper()
            if not name.startswith("GNV1B_") or not name.endswith(".DAT"):
                continue
            if satellites and not any(f"_{sat}_" in name for sat in satellites):
                continue
            fobj = tar.extractfile(member)
            if fobj is None:
                continue
            records = parse_gnv1b_bytes(fobj.read())
            if records.size == 0:
                continue
            mask = records["coord_ref"] == b"E"
            if not np.any(mask):
                continue
            lon, lat = _ecef_to_geodetic_deg(records["xpos"][mask], records["ypos"][mask], records["zpos"][mask])
            density += _build_density_from_lonlat(lon, lat, lon_arr, lat_arr)
            total_points += int(lon.size)
            file_count += 1
    meta = {
        "file_count": float(file_count),
        "release": 3.0 if str(release).upper() == "RL03" else 2.0,
    }
    np.savez_compressed(
        cache_path,
        density=density,
        lon=lon_arr,
        lat=lat_arr,
        counts=int(total_points),
        archive_path=str(archive_path),
        meta=np.asarray(meta, dtype=object),
    )
    return GroundTrackBundle(
        month=month,
        density=density,
        lon=lon_arr,
        lat=lat_arr,
        counts=total_points,
        archive_path=archive_path,
        meta=meta,
    )


def _sample_days_for_month(month: str, sample_days: int) -> List[str]:
    year = int(str(month)[:4])
    mon = int(str(month)[5:7])
    ndays = calendar.monthrange(year, mon)[1]
    k = max(1, int(sample_days))
    if k == 1:
        picks = [max(1, min(ndays, int(round((ndays + 1) / 2.0))))]
    else:
        picks = sorted(set(int(round(v)) for v in np.linspace(1, ndays, k)))
        picks = [max(1, min(ndays, d)) for d in picks]
    return [f"{year:04d}-{mon:02d}-{day:02d}" for day in picks]


def _nearby_days(day: str, max_offset: int = 2) -> List[str]:
    dt = datetime.strptime(day, "%Y-%m-%d")
    out = [dt.strftime("%Y-%m-%d")]
    for offset in range(1, int(max_offset) + 1):
        out.append((dt + timedelta(days=offset)).strftime("%Y-%m-%d"))
        out.append((dt - timedelta(days=offset)).strftime("%Y-%m-%d"))
    # preserve order but deduplicate
    seen = set()
    ordered = []
    for item in out:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def build_monthly_groundtrack_bundle_rl02_sampled(
    *,
    month: str,
    lon_vec: Sequence[float],
    lat_vec: Sequence[float],
    cache_dir: Path,
    sample_days: int = 1,
    satellites: Iterable[str] = ("A", "B"),
) -> GroundTrackBundle:
    """Approximate a monthly bundle using sampled RL02 daily GNV1B files."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    lon_arr = np.asarray(lon_vec, dtype=float)
    lat_arr = np.asarray(lat_vec, dtype=float)
    key = f"bundle_rl02samp_{month}_{int(sample_days)}d_{len(lon_arr)}x{len(lat_arr)}.npz"
    cache_path = cache_dir / key
    if cache_path.exists():
        data = np.load(cache_path, allow_pickle=True)
        counts = int(data["counts"])
        if counts > 0:
            return GroundTrackBundle(
                month=month,
                density=np.asarray(data["density"], dtype=float),
                lon=np.asarray(data["lon"], dtype=float),
                lat=np.asarray(data["lat"], dtype=float),
                counts=counts,
                archive_path=Path(str(data["archive_path"])),
                meta=dict(data["meta"].item()),
            )

    satellites = tuple(str(s).upper() for s in satellites)
    density = np.zeros((lon_arr.size, lat_arr.size), dtype=float)
    total_points = 0
    file_count = 0
    sampled_days = _sample_days_for_month(month, sample_days)
    last_archive: Path | None = None
    for day in sampled_days:
        archive_path = None
        chosen_day = None
        for candidate in _nearby_days(day, max_offset=2):
            try:
                target = build_gfz_target(release="RL02", day=candidate)
                archive_path = download_target(target, cache_dir)
                chosen_day = candidate
                break
            except HTTPError:
                continue
        if archive_path is None:
            continue
        last_archive = archive_path
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar.getmembers():
                name = Path(member.name).name.upper()
                if not name.startswith("GNV1B_") or not name.endswith(".DAT"):
                    continue
                if satellites and not any(f"_{sat}_" in name for sat in satellites):
                    continue
                fobj = tar.extractfile(member)
                if fobj is None:
                    continue
                records = parse_gnv1b_bytes(fobj.read())
                if records.size == 0:
                    continue
                mask = records["coord_ref"] == b"E"
                if not np.any(mask):
                    continue
                lon, lat = _ecef_to_geodetic_deg(records["xpos"][mask], records["ypos"][mask], records["zpos"][mask])
                density += _build_density_from_lonlat(lon, lat, lon_arr, lat_arr)
                total_points += int(lon.size)
                file_count += 1
                if chosen_day is not None and chosen_day != day:
                    break
    meta = {
        "file_count": float(file_count),
        "release": 2.0,
        "sample_days": float(sample_days),
        "sampled_days": sampled_days,
    }
    archive_ref = last_archive if last_archive is not None else cache_dir
    np.savez_compressed(
        cache_path,
        density=density,
        lon=lon_arr,
        lat=lat_arr,
        counts=int(total_points),
        archive_path=str(archive_ref),
        meta=np.asarray(meta, dtype=object),
    )
    return GroundTrackBundle(
        month=month,
        density=density,
        lon=lon_arr,
        lat=lat_arr,
        counts=total_points,
        archive_path=archive_ref,
        meta=meta,
    )
