"""Non-UI algorithm utilities extracted from GUI class."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np


def parse_ym(s: str):
    try:
        s = str(s).strip()
        if not s:
            return None
        if "-" in s:
            parts = s.split("-")
        elif "/" in s:
            parts = s.split("/")
        else:
            parts = [s[:4], s[4:6]]
        y = int(parts[0])
        m = int(parts[1])
        return y, m
    except Exception:
        return None


def build_time_from_fallback(start_ym, step_value, nt: int):
    start = parse_ym(start_ym)
    if not start:
        start = (2002, 4)
    try:
        step = max(1, int(step_value))
    except Exception:
        step = 1
    y, m = start
    labels = []
    t_years = []
    for _ in range(nt):
        labels.append(f"{y:04d}-{m:02d}")
        t_years.append(y + (m - 0.5) / 12.0)
        m += step
        while m > 12:
            m -= 12
            y += 1
    return np.array(t_years, dtype=float), labels


def resolve_time(
    t_arr,
    nt: int,
    *,
    use_file_time: bool,
    fallback_start_ym,
    fallback_step,
    meta: Optional[Dict[str, Any]] = None,
):
    if (not use_file_time) or (t_arr is None):
        return build_time_from_fallback(fallback_start_ym, fallback_step, nt)
    try:
        t = np.asarray(t_arr).squeeze()
        if t.size == 0:
            return build_time_from_fallback(fallback_start_ym, fallback_step, nt)
    except Exception:
        return build_time_from_fallback(fallback_start_ym, fallback_step, nt)
    labels = []
    t_years = []
    try:
        if t.dtype.kind in ("U", "S", "O"):
            for item in t.flatten()[:nt]:
                if hasattr(item, "strftime"):
                    try:
                        y = item.year
                        m = item.month
                        labels.append(f"{y:04d}-{m:02d}")
                        t_years.append(y + (m - 0.5) / 12.0)
                        continue
                    except Exception:
                        pass
                ym = parse_ym(item)
                if ym:
                    y, m = ym
                    labels.append(f"{y:04d}-{m:02d}")
                    t_years.append(y + (m - 0.5) / 12.0)
        else:
            vals = t.astype(float)
            if vals.ndim == 2:
                if vals.shape[0] == 2:
                    vals = np.nanmean(vals, axis=0)
                elif vals.shape[1] == 2:
                    vals = np.nanmean(vals, axis=1)
                else:
                    vals = vals.reshape(-1)
            vals = vals.flatten()
            units = str((meta or {}).get("time_units") or "").strip()
            cal = str((meta or {}).get("time_calendar") or "standard").strip() or "standard"
            if units:
                try:
                    from netCDF4 import num2date

                    dates = num2date(vals[:nt], units, calendar=cal)
                    for dt in np.asarray(dates).flatten():
                        y = int(getattr(dt, "year"))
                        m = int(getattr(dt, "month"))
                        labels.append(f"{y:04d}-{m:02d}")
                        t_years.append(y + (m - 0.5) / 12.0)
                except Exception:
                    pass
            if len(t_years) >= nt:
                return np.array(t_years[:nt], dtype=float), labels[:nt]

            if np.nanmax(vals) > 700000:
                for v in vals[:nt]:
                    try:
                        days = float(v)
                        dt = datetime.fromordinal(int(days)) + timedelta(days=days % 1) - timedelta(days=366)
                        labels.append(f"{dt.year:04d}-{dt.month:02d}")
                        t_years.append(dt.year + (dt.month - 0.5) / 12.0)
                    except Exception:
                        pass
            elif np.nanmax(vals) > 1500 and np.nanmax(vals) < 3000:
                for v in vals[:nt]:
                    y = int(round(v))
                    labels.append(f"{y:04d}-01")
                    t_years.append(float(v))
            elif np.nanmax(vals) < 100000:
                y0m0 = parse_ym(fallback_start_ym) or (2002, 4)
                y0, m0 = y0m0
                base = datetime(y0, m0, 15)
                for v in vals[:nt]:
                    try:
                        dt = base + timedelta(days=float(v))
                        labels.append(f"{dt.year:04d}-{dt.month:02d}")
                        t_years.append(dt.year + (dt.month - 0.5) / 12.0)
                    except Exception:
                        pass
    except Exception:
        labels = []
        t_years = []
    if len(t_years) < nt:
        return build_time_from_fallback(fallback_start_ym, fallback_step, nt)
    return np.array(t_years[:nt], dtype=float), labels[:nt]


def resolve_output_file(out_path: str, in_path: str, suffix: str, ext: str):
    out_path = (out_path or "").strip()
    if out_path.lower().endswith(f".{ext}"):
        out_dir = os.path.dirname(out_path)
        if out_dir:
            Path(out_dir).mkdir(parents=True, exist_ok=True)
        return out_path, out_dir or "."
    if not out_path:
        out_dir = os.path.dirname(in_path) or "."
    else:
        out_dir = out_path
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    fname = f"{Path(in_path).stem}_{suffix}.{ext}"
    return str(Path(out_dir) / fname), out_dir


def infer_time_labels(t_arr, nt):
    labels = []
    try:
        arr = np.asarray(t_arr).ravel()
        if arr.size != nt:
            arr = None
    except Exception:
        arr = None
    if arr is not None:
        for v in arr:
            try:
                if isinstance(v, np.datetime64):
                    s = np.datetime_as_string(v, unit="M")
                    labels.append(s.replace("-", ""))
                    continue
                if hasattr(v, "strftime"):
                    labels.append(v.strftime("%Y%m"))
                    continue
                if isinstance(v, (bytes, str)):
                    s = v.decode() if isinstance(v, bytes) else str(v)
                    digits = "".join(ch for ch in s if ch.isdigit())
                    if len(digits) >= 6:
                        labels.append(digits[:6])
                        continue
                num = float(v)
                if 190001 <= num <= 210012:
                    labels.append(f"{int(num):06d}")
                    continue
            except Exception:
                pass
    if len(labels) != nt:
        labels = [f"{i + 1:06d}" for i in range(nt)]
    return labels


def infer_time_axis_for_rate(t_arr, nt: int) -> np.ndarray:
    if nt <= 1:
        return np.arange(max(1, nt), dtype=float)
    try:
        arr = np.asarray(t_arr).reshape(-1)
    except Exception:
        arr = np.array([], dtype=object)
    if arr.size == nt:
        vals = []
        ok = True
        for v in arr:
            try:
                if isinstance(v, np.datetime64):
                    dt = v.astype("datetime64[M]")
                    y = int(str(dt)[:4])
                    m = int(str(dt)[5:7])
                elif hasattr(v, "year") and hasattr(v, "month"):
                    y = int(v.year)
                    m = int(v.month)
                else:
                    ok = False
                    break
                vals.append(y + (m - 0.5) / 12.0)
            except Exception:
                ok = False
                break
        if ok and len(vals) == nt and np.all(np.isfinite(vals)):
            return np.asarray(vals, dtype=float)
    labels = infer_time_labels(t_arr, nt)
    vals = []
    for lb in labels:
        s = str(lb)
        if len(s) < 6 or (not s[:6].isdigit()):
            vals = []
            break
        y = int(s[:4])
        m = int(s[4:6])
        if m < 1 or m > 12:
            vals = []
            break
        vals.append(y + (m - 0.5) / 12.0)
    if len(vals) == nt and np.all(np.isfinite(vals)):
        return np.asarray(vals, dtype=float)
    return np.arange(nt, dtype=float)


def file_fingerprint(path: str) -> Dict[str, Any]:
    p = Path(path) if path else None
    if p is None or not p.exists():
        return {"path": str(path or ""), "exists": False}
    try:
        st = p.stat()
        return {
            "path": str(p.resolve()),
            "exists": True,
            "size": int(st.st_size),
            "mtime": int(st.st_mtime),
        }
    except Exception:
        return {"path": str(path), "exists": True}


def build_scope_signature(scope: str, payload: Dict[str, Any], cfg_obj) -> str:
    base = {
        "scope": scope,
        "payload": payload,
        "cfg": cfg_obj.to_dict() if hasattr(cfg_obj, "to_dict") else {},
    }
    raw = json.dumps(base, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
