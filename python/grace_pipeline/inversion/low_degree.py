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
        if overlap >= 0 and overlap > best_overlap:
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


def infer_center_from_time_entry(time_entry) -> str:
    """Infer solution center (CSR/JPL/GFZ) from file metadata."""
    basename = Path(str(getattr(time_entry, "gfc_file", "") or "")).name.upper()
    if any(token in basename for token in ("_JPL_", " JPL ", "JPLEM", "JPL")):
        return "JPL"
    if any(token in basename for token in ("_GFZ_", "GFZOP", "GFZ")):
        return "GFZ"
    if any(token in basename for token in ("_CSR_", "UTCSR", "CSR")):
        return "CSR"
    return "UNKNOWN"


def load_low_degree_data(cfg, time_entry=None) -> Tuple[Dict[str, Dict[str, float]], Dict[str, Tuple[float, float, float]]]:
    """Load low-degree replacement data from configuration."""
    inv_cfg = _inv_cfg(cfg)
    lowdeg_cfg = _as_dict(inv_cfg.get("lowdeg", {}))
    if not lowdeg_cfg:
        return {}, {}

    files = _as_dict(lowdeg_cfg.get("files", {}))
    slr_data: Dict[str, Dict[str, float]] = {}
    deg1_data: Dict[str, Tuple[float, float, float]] = {}

    c20_file = str(files.get("C20", "") or "").strip()
    if c20_file:
        slr_data = parse_tn14_slr(c20_file)

    center = infer_center_from_time_entry(time_entry) if time_entry is not None else "UNKNOWN"
    center_key = f"DEGREE1_{center}" if center != "UNKNOWN" else ""
    deg1_file = str(files.get(center_key, "") or files.get("DEGREE1", "") or "").strip()
    if deg1_file:
        deg1_data = parse_tn13_degree1(deg1_file)

    return slr_data, deg1_data


def _lowdeg_files(cfg) -> dict:
    inv_cfg = _inv_cfg(cfg)
    lowdeg_cfg = _as_dict(inv_cfg.get("lowdeg", {}))
    return _as_dict(lowdeg_cfg.get("files", {}))


def infer_mission_from_time_entry(time_entry) -> str:
    """Infer GRACE mission family from file metadata and time stamp."""
    basename = Path(str(getattr(time_entry, "gfc_file", "") or "")).name.upper()
    if any(token in basename for token in ("GRFO", "GRACEFO", "GRACE-FO", "GRACE_FO")):
        return "GRACE-FO"
    if "GRAC" in basename:
        return "GRACE"
    year = int(getattr(time_entry, "year", 0) or 0)
    if year >= 2018:
        return "GRACE-FO"
    if year:
        return "GRACE"
    return "UNKNOWN"


def _c30_replacement_applies(lowdeg_cfg: dict, time_entry) -> bool:
    """
    Decide whether TN-14 C30 replacement should be applied.

    Apply C30 replacement with mission-aware scope and start month.
    """
    scope = str(lowdeg_cfg.get("c30_scope", "grace_fo") or "grace_fo").strip().lower().replace("-", "_")
    mission = infer_mission_from_time_entry(time_entry).upper()
    if scope not in ("all", "global"):
        if scope in ("grace_fo", "fo", "grfo") and mission != "GRACE-FO":
            return False
        if scope in ("grace", "grac") and mission != "GRACE":
            return False

    start_ym = str(lowdeg_cfg.get("c30_start_ym", "2018-06") or "2018-06")
    ym = str(getattr(time_entry, "ym", "") or "")
    if ym:
        return ym >= start_ym
    year = int(getattr(time_entry, "year", 0) or 0)
    month = int(getattr(time_entry, "month", 0) or 0)
    if year <= 0 or month <= 0:
        return False
    return f"{year:04d}-{month:02d}" >= start_ym


def replace_low_degree(cfg, sh, time_entry):
    """Replace low-degree coefficients in an SHCoefficients object."""
    inv_cfg = _inv_cfg(cfg)
    lowdeg_cfg = _as_dict(inv_cfg.get("lowdeg", {}))
    if not lowdeg_cfg:
        return sh

    if not bool(lowdeg_cfg.get("enable", True)):
        return sh

    replace_c20 = bool(lowdeg_cfg.get("replace_C20", True))
    replace_degree1 = bool(lowdeg_cfg.get("replace_degree1", lowdeg_cfg.get("replace_C10", True)))
    replace_c30 = bool(lowdeg_cfg.get("replace_C30", True))

    slr_data, deg1_data = load_low_degree_data(cfg, time_entry=time_entry)
    ym = str(getattr(time_entry, "ym", "") or "")
    c20_file = str(_lowdeg_files(cfg).get("C20", "") or "").strip()
    slr_entry = select_tn14_slr_entry(c20_file, time_entry) if c20_file else slr_data.get(ym, {})

    if replace_c20:
        c20_value = slr_entry.get("C20", np.nan)
        if np.isfinite(c20_value):
            original_c20 = sh.C[2, 0]
            sh.C[2, 0] = c20_value
            sh.replaced["C20"] = True
            sh.meta["C20_original"] = original_c20
            sh.meta["C20_replaced"] = c20_value
            if "match_method" in slr_entry:
                sh.meta["C20_match_method"] = slr_entry.get("match_method")
                sh.meta["C20_match_overlap_days"] = slr_entry.get("overlap_days")
                sh.meta["C20_match_mjd_start"] = slr_entry.get("mjd_start")
                sh.meta["C20_match_mjd_end"] = slr_entry.get("mjd_end")

    if replace_c30 and _c30_replacement_applies(lowdeg_cfg, time_entry):
        c30_value = slr_entry.get("C30", np.nan)
        if not np.isfinite(c30_value):
            c30_value = slr_data.get(ym, {}).get("C30", np.nan)
        if np.isfinite(c30_value):
            original_c30 = sh.C[3, 0]
            sh.C[3, 0] = c30_value
            sh.replaced["C30"] = True
            sh.meta["C30_original"] = original_c30
            sh.meta["C30_replaced"] = c30_value

    if replace_degree1 and ym in deg1_data:
        c10, c11, s11 = deg1_data[ym]
        sh.C[1, 0] = c10
        sh.C[1, 1] = c11
        sh.S[1, 1] = s11
        sh.replaced["C10"] = True
        sh.replaced["C11"] = True
        sh.replaced["S11"] = True
        sh.replaced["Degree1"] = True

    return sh


def get_mean_mode(cfg) -> str:
    """Get mean removal mode."""
    inv_cfg = _inv_cfg(cfg)
    mode = str(inv_cfg.get("mean_mode", "fixed_range") or "fixed_range").strip().lower()
    if mode in ("mission", "mission_full", "mission_full_period"):
        return "mission_full_period"
    return "fixed_range"


def select_mean_sh(mean_sh, time_entry, mean_mode: str = "fixed_range"):
    """Select appropriate mean field for a month."""
    if mean_sh is None:
        return None
    if not isinstance(mean_sh, dict):
        return mean_sh
    mode = str(mean_mode or "fixed_range").strip().lower()
    if mode != "mission_full_period":
        return mean_sh.get("DEFAULT", None)
    mission = infer_mission_from_time_entry(time_entry).upper()
    return mean_sh.get(mission) or mean_sh.get("DEFAULT")


def _compute_mean_over_entries(cfg, entries, Lmax: int):
    from grace_pipeline.inversion.gfc_reader import SHCoefficients, read_gsm_month

    C_sum = np.zeros((Lmax + 1, Lmax + 1), dtype=float)
    S_sum = np.zeros((Lmax + 1, Lmax + 1), dtype=float)
    count = 0
    for te in entries:
        try:
            sh = read_gsm_month(cfg, te)
            sh = replace_low_degree(cfg, sh, te)
        except Exception:
            continue
        C_sum += sh.C
        S_sum += sh.S
        count += 1
    if count == 0:
        return None
    return SHCoefficients(
        C=C_sum / count,
        S=S_sum / count,
        Lmax=Lmax,
        meta={"type": "mean", "n_months": count},
    )


def compute_mean_sh(cfg, time_entries):
    """
    Compute mean spherical harmonic coefficients over the configured time period.
    """
    if not time_entries:
        return None

    inv_cfg = _inv_cfg(cfg)
    Lmax = int(inv_cfg.get("Lmax", 60))
    mean_mode = get_mean_mode(cfg)
    mean_start = str(inv_cfg.get("mean_start_ym", inv_cfg.get("mean_start", "")) or "")
    mean_end = str(inv_cfg.get("mean_end_ym", inv_cfg.get("mean_end", "")) or "")

    selected_entries = []
    for te in time_entries:
        if mean_start and te.ym < mean_start:
            continue
        if mean_end and te.ym > mean_end:
            continue
        selected_entries.append(te)

    if not selected_entries:
        return None

    if mean_mode != "mission_full_period":
        return _compute_mean_over_entries(cfg, selected_entries, Lmax=Lmax)

    buckets = {"GRACE": [], "GRACE-FO": []}
    for te in selected_entries:
        mission = infer_mission_from_time_entry(te).upper()
        if mission in buckets:
            buckets[mission].append(te)

    mean_map = {}
    for mission, mission_entries in buckets.items():
        mean_mission = _compute_mean_over_entries(cfg, mission_entries, Lmax=Lmax)
        if mean_mission is not None:
            mean_mission.meta["mission"] = mission
            mean_map[mission] = mean_mission

    if not mean_map:
        return None

    if len(mean_map) == 1:
        return next(iter(mean_map.values()))
    return mean_map
