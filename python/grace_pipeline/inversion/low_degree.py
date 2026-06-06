"""
Low-degree coefficient replacement for GRACE data.

Handles replacement of:
- Degree-1 geocenter terms from TN-13 (C10/C11/S11)
- C20 from TN-14 SLR
- C30 from TN-14 SLR for GRACE-FO months only
"""

from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
import re
from typing import Dict, Optional, Tuple

import numpy as np


MJD_EPOCH = datetime(1858, 11, 17)


def _as_dict(section) -> dict:
    if isinstance(section, dict):
        return section
    return dict(getattr(section, "__dict__", {}) or {})


def _merge_cfg_dict(base: dict, override: dict) -> dict:
    merged = dict(base or {})
    for key, value in dict(override or {}).items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def _inv_cfg(cfg) -> dict:
    cfg_inv = _as_dict(getattr(cfg, "inversion", {}) or {})
    raw_inv = {}
    if hasattr(cfg, "get"):
        try:
            raw_inv = _as_dict(cfg.get("inversion", {}) or {})
        except Exception:
            raw_inv = {}
    return _merge_cfg_dict(cfg_inv, raw_inv)


def _mjd_to_datetime(value: float) -> datetime:
    return MJD_EPOCH + timedelta(days=float(value))


def _month_key_from_mjd_window(start_mjd: float, end_mjd: float) -> str:
    start_dt = _mjd_to_datetime(start_mjd)
    end_dt = _mjd_to_datetime(end_mjd)
    mid_dt = start_dt + (end_dt - start_dt) / 2
    return f"{mid_dt.year:04d}-{mid_dt.month:02d}"


def _datetime_to_mjd(dt: datetime) -> float:
    return (dt - MJD_EPOCH).total_seconds() / 86400.0


def _month_bounds(ym: str) -> Tuple[datetime, datetime]:
    month_start = datetime(int(ym[:4]), int(ym[5:7]), 1)
    month_end = datetime(month_start.year + int(month_start.month == 12), month_start.month % 12 + 1, 1) - timedelta(days=1)
    return month_start, month_end


def _has_explicit_solution_arc(time_entry) -> bool:
    """
    Return True only when the GSM product exposes a real solution arc.

    HUST/ITSG-style files are named by calendar month (YYYYMM/YYY-MM). For those
    products the low-degree replacement should use the same month key instead of
    borrowing a neighboring TN-13/TN-14 arc by overlap.
    """
    basename = Path(str(getattr(time_entry, "gfc_file", "") or "")).name
    if re.search(r"\d{7}-\d{7}", basename):
        return True

    ym = str(getattr(time_entry, "ym", "") or "")
    start_dt = getattr(time_entry, "start_dt", None)
    end_dt = getattr(time_entry, "end_dt", None)
    if not ym or start_dt is None or end_dt is None:
        return False

    month_start, month_end = _month_bounds(ym)
    return start_dt != month_start or end_dt != month_end


@lru_cache(maxsize=8)
def parse_tn14_slr(filepath: str) -> Dict[str, Dict[str, float]]:
    """
    Parse TN-14 SLR replacement file.

    Returns:
        {"YYYY-MM": {"C20": float, "C30": float}}
    """
    slr_data: Dict[str, Dict[str, float]] = {}
    path = Path(filepath)
    if not path.exists():
        return slr_data

    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("%"):
                continue
            if not (line[0].isdigit() or line[0] in "+-."):
                continue

            parts = line.split()
            if len(parts) < 9:
                continue

            try:
                start_mjd = float(parts[0])
                c20 = float(parts[2])
                c30 = float(parts[5])
                end_mjd = float(parts[8])
            except ValueError:
                continue

            ym = _month_key_from_mjd_window(start_mjd, end_mjd)
            slr_data[ym] = {
                "C20": c20,
                "C30": c30,
            }

    return slr_data


@lru_cache(maxsize=8)
def _parse_tn14_slr_rows(filepath: str) -> Tuple[Dict[str, float], ...]:
    rows: list[Dict[str, float]] = []
    path = Path(filepath)
    if not path.exists():
        return tuple()

    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("%"):
                continue
            if not (line[0].isdigit() or line[0] in "+-."):
                continue

            parts = line.split()
            if len(parts) < 9:
                continue

            try:
                start_mjd = float(parts[0])
                c20 = float(parts[2])
                c30 = float(parts[5])
                end_mjd = float(parts[8])
            except ValueError:
                continue

            rows.append(
                {
                    "mjd_start": start_mjd,
                    "mjd_end": end_mjd,
                    "C20": c20,
                    "C30": c30,
                    "ym": _month_key_from_mjd_window(start_mjd, end_mjd),
                }
            )

    return tuple(rows)


def select_tn14_slr_entry(filepath: str, time_entry) -> Dict[str, float]:
    """Select TN-14 row by maximum overlap with the GSM solution arc."""
    rows = _parse_tn14_slr_rows(filepath)
    if not rows:
        return {}

    ym = str(getattr(time_entry, "ym", "") or "")
    month_entry = parse_tn14_slr(filepath).get(ym, {}) if ym else {}
    if not _has_explicit_solution_arc(time_entry):
        if month_entry:
            out = dict(month_entry)
            out["match_method"] = "month_key"
            return out
        return {}

    month_start = _month_bounds(ym)[0] if ym else getattr(time_entry, "dt", None)
    if month_start is None:
        return {}
    month_end = _month_bounds(ym)[1] if ym else month_start
    start_dt = getattr(time_entry, "start_dt", None) or month_start
    end_dt = getattr(time_entry, "end_dt", None) or month_end
    if end_dt < start_dt:
        start_dt, end_dt = month_start, month_end

    mjd0 = _datetime_to_mjd(start_dt)
    mjd1 = _datetime_to_mjd(end_dt)
    best = None
    best_overlap = float("-inf")
    for row in rows:
        overlap = min(mjd1, row["mjd_end"]) - max(mjd0, row["mjd_start"]) + 1
        if overlap > 0 and overlap > best_overlap:
            best = row
            best_overlap = overlap

    if best is not None:
        out = dict(best)
        out["match_method"] = "mjd_overlap"
        out["overlap_days"] = best_overlap
        return out

    return month_entry


def parse_tn14_c20(filepath: str) -> Dict[str, float]:
    """Compatibility wrapper returning only C20 values from TN-14."""
    return {ym: values.get("C20", np.nan) for ym, values in parse_tn14_slr(filepath).items()}


@lru_cache(maxsize=8)
def parse_tn13_degree1(filepath: str) -> Dict[str, Tuple[float, float, float]]:
    """
    Parse TN-13 degree-1 replacement file.

    Returns:
        {"YYYY-MM": (C10, C11, S11)}
    """
    deg1_data: Dict[str, Tuple[float, float, float]] = {}
    path = Path(filepath)
    if not path.exists():
        return deg1_data

    parsed_rows: Dict[str, list[float]] = {}

    def _month_key_from_date_tokens(start_token: str, end_token: str) -> str:
        start_dt = datetime.strptime(str(start_token)[:8], "%Y%m%d")
        end_dt = datetime.strptime(str(end_token)[:8], "%Y%m%d")
        mid_dt = start_dt + (end_dt - start_dt) / 2
        return f"{mid_dt.year:04d}-{mid_dt.month:02d}"

    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("%"):
                continue
            parts = line.split()
            if len(parts) >= 9 and parts[0].upper().startswith("GRCOF2"):
                try:
                    degree = int(parts[1])
                    order = int(parts[2])
                    c_val = float(parts[3])
                    s_val = float(parts[4])
                    ym = _month_key_from_date_tokens(parts[-2], parts[-1])
                except (ValueError, IndexError):
                    continue
                if degree != 1 or order not in (0, 1):
                    continue
                row = parsed_rows.setdefault(ym, [np.nan, np.nan, np.nan])
                if order == 0:
                    row[0] = c_val
                else:
                    row[1] = c_val
                    row[2] = s_val
                continue

            if len(parts) < 5:
                continue
            try:
                year = int(float(parts[0]))
                month = int(parts[1])
                c10 = float(parts[2])
                c11 = float(parts[3])
                s11 = float(parts[4])
            except (ValueError, IndexError):
                continue

            if year < 100:
                year += 2000 if year < 50 else 1900
            if 1 <= month <= 12:
                parsed_rows[f"{year:04d}-{month:02d}"] = [c10, c11, s11]

    for ym, row in parsed_rows.items():
        if np.isfinite(row[0]) and np.isfinite(row[1]) and np.isfinite(row[2]):
            deg1_data[ym] = (row[0], row[1], row[2])

    return deg1_data


@lru_cache(maxsize=8)
def _parse_tn13_degree1_rows(filepath: str) -> Tuple[Dict[str, float], ...]:
    rows: list[Dict[str, float]] = []
    path = Path(filepath)
    if not path.exists():
        return tuple()

    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("%"):
                continue
            parts = line.split()
            if len(parts) >= 9 and parts[0].upper().startswith("GRCOF2"):
                try:
                    degree = int(parts[1])
                    order = int(parts[2])
                    c_val = float(parts[3])
                    s_val = float(parts[4])
                    start_dt = datetime.strptime(str(parts[-2])[:8], "%Y%m%d")
                    end_exclusive = datetime.strptime(str(parts[-1])[:8], "%Y%m%d")
                except (ValueError, IndexError):
                    continue
                if degree != 1 or order not in (0, 1):
                    continue
                rows.append(
                    {
                        "order": order,
                        "C": c_val,
                        "S": s_val,
                        "start_dt": start_dt,
                        "end_dt": end_exclusive - timedelta(days=1),
                    }
                )

    return tuple(rows)


def select_tn13_degree1_entry(filepath: str, time_entry) -> Optional[Tuple[float, float, float]]:
    """Select TN-13 degree-1 terms by maximum overlap with the calendar month."""
    ym = str(getattr(time_entry, "ym", "") or "")
    if not ym:
        return None

    rows = _parse_tn13_degree1_rows(filepath)
    if not rows:
        return parse_tn13_degree1(filepath).get(ym)

    month_start, month_end = _month_bounds(ym)
    best: dict[int, Tuple[int, Dict[str, float]]] = {}
    for row in rows:
        start_dt = row["start_dt"]
        end_dt = row["end_dt"]
        overlap = (min(month_end, end_dt) - max(month_start, start_dt)).days + 1
        if overlap <= 0:
            continue
        order = int(row["order"])
        current = best.get(order)
        if current is None or overlap > current[0]:
            best[order] = (overlap, row)

    if 0 not in best or 1 not in best:
        return parse_tn13_degree1(filepath).get(ym)
    c10 = float(best[0][1]["C"])
    c11 = float(best[1][1]["C"])
    s11 = float(best[1][1]["S"])
    return c10, c11, s11


def replace_low_degree(sh, cfg, time_entry):
    """
    Replace low-degree coefficients in SHCoefficients object.

    Args:
        sh: SHCoefficients object
        cfg: Configuration object
        time_entry: TimeEntry object

    Returns:
        Modified SHCoefficients object
    """
    inv_cfg = _inv_cfg(cfg)
    lowdeg_cfg = inv_cfg.get("lowdeg", {}) or {}
    gia_cfg = inv_cfg.get("gia", {}) or {}

    if not lowdeg_cfg.get("enable", True):
        return sh

    files_cfg = lowdeg_cfg.get("files", {}) or {}
    ym = time_entry.ym
    center = infer_center_from_gfc(getattr(time_entry, "gfc_file", ""))
    degree1_file = files_cfg.get(f"DEGREE1_{center}") or files_cfg.get("DEGREE1")

    # Replace degree-1 (C10, C11, S11)
    if lowdeg_cfg.get("replace_degree1", lowdeg_cfg.get("replace_C10", True)):
        if degree1_file:
            deg1 = select_tn13_degree1_entry(degree1_file, time_entry)
            if deg1 is not None:
                c10, c11, s11 = deg1
                if sh.C.shape[0] > 1:
                    sh.C[1, 0] = c10
                    sh.C[1, 1] = c11
                    sh.S[1, 1] = s11
                    sh.replaced["C10"] = True
                    sh.replaced["C11"] = True
                    sh.replaced["S11"] = True

    # Replace C20/C30 from TN-14 SLR
    c20_file = files_cfg.get("C20")
    if c20_file:
        slr_entry = select_tn14_slr_entry(c20_file, time_entry)
        if slr_entry:
            if lowdeg_cfg.get("replace_C20", True) and "C20" in slr_entry:
                sh.C[2, 0] = slr_entry["C20"]
                sh.replaced["C20"] = True
                sh.meta["C20_match_method"] = slr_entry.get("match_method", "unknown")
                if "overlap_days" in slr_entry:
                    sh.meta["C20_overlap_days"] = slr_entry["overlap_days"]
                if "mjd_start" in slr_entry:
                    sh.meta["C20_mjd_start"] = slr_entry["mjd_start"]
                    sh.meta["C20_mjd_end"] = slr_entry.get("mjd_end")

            if lowdeg_cfg.get("replace_C30", False) and sh.C.shape[0] > 3 and "C30" in slr_entry and np.isfinite(slr_entry["C30"]):
                sh.C[3, 0] = slr_entry["C30"]
                sh.replaced["C30"] = True

    # Apply GIA correction if enabled
    if gia_cfg.get("enable", False):
        gia_file = gia_cfg.get("file")
        if gia_file and Path(gia_file).exists():
            apply_gia_correction(sh, gia_file, time_entry)

    return sh


def infer_center_from_gfc(gfc_file: str) -> str:
    name = Path(str(gfc_file or "")).name.upper()
    if "UTCSR" in name or "_CSR" in name or name.startswith("CSR"):
        return "CSR"
    if "JPLEM" in name or "_JPL" in name or name.startswith("JPL"):
        return "JPL"
    if "GFZOP" in name or "_GFZ" in name or name.startswith("GFZ"):
        return "GFZ"
    return "UNKNOWN"


def apply_gia_correction(sh, gia_file: str, time_entry):
    """Apply GIA correction to coefficients (placeholder)."""
    # TODO: implement GIA rate subtraction if needed
    return sh


# Backward-compatible aliases
read_tn14_c20 = parse_tn14_c20
read_tn13_degree1 = parse_tn13_degree1
