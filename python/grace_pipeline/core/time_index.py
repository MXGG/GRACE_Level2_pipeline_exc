"""Time index management for GRACE data processing."""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class TimeEntry:
    """Represents a single time point in the GRACE data series."""

    ym: str
    yyyymm: str
    year: int
    month: int
    dt: datetime
    gfc_file: Optional[str] = None
    start_dt: Optional[datetime] = None
    end_dt: Optional[datetime] = None

    @classmethod
    def from_ym(
        cls,
        ym: str,
        gfc_file: Optional[str] = None,
        start_dt: Optional[datetime] = None,
        end_dt: Optional[datetime] = None,
    ) -> "TimeEntry":
        if "-" in ym:
            year, month = map(int, ym.split("-"))
            yyyymm = ym.replace("-", "")
        else:
            year = int(ym[:4])
            month = int(ym[4:6])
            yyyymm = ym
            ym = f"{year:04d}-{month:02d}"
        dt = datetime(year, month, 1)
        return cls(
            ym=ym,
            yyyymm=yyyymm,
            year=year,
            month=month,
            dt=dt,
            gfc_file=gfc_file,
            start_dt=start_dt or dt,
            end_dt=end_dt or (_increment_month(dt) - timedelta(days=1)),
        )


def parse_ym_range(start_ym: str, end_ym: str) -> List[Tuple[int, int]]:
    """Generate inclusive (year, month) tuples between start and end."""
    start = TimeEntry.from_ym(start_ym)
    end = TimeEntry.from_ym(end_ym)
    result: List[Tuple[int, int]] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        result.append((year, month))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return result


def detect_gfc_files(gfc_dir: str, product_type: str = "GSM", file_ext: str = ".gfc") -> List[str]:
    """Detect available GFC files in a directory and return sorted absolute paths."""
    gfc_path = Path(gfc_dir)
    if not gfc_path.exists():
        return []
    raw_ext = "" if file_ext is None else str(file_ext).strip()
    ext = raw_ext if not raw_ext or raw_ext.startswith(".") else f".{raw_ext}"

    files: list[Path] = []
    if product_type:
        if ext:
            files = list(gfc_path.glob(f"{product_type}*{ext}"))
        if not files:
            files = list(gfc_path.glob(f"{product_type}*"))
    if not files:
        files = [p for p in gfc_path.glob(f"*{ext or '.gfc'}") if p.is_file()]
    if not files:
        files = [p for p in gfc_path.iterdir() if p.is_file()]
    return sorted({str(p.resolve()) for p in files})


def extract_ym_from_gfc(filename: str) -> Optional[str]:
    """Extract year-month from a GFC filename or header."""
    window = _parse_gfc_date_range(filename)
    if window is not None:
        start_dt, end_dt = window
        mid_dt = start_dt + (end_dt - start_dt) / 2
        return f"{mid_dt.year:04d}-{mid_dt.month:02d}"

    basename = Path(filename).stem
    match = re.search(r"(?<!\d)(\d{4})[-_]?(\d{2})(?!\d)", basename)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        if 1 <= month <= 12:
            return f"{year:04d}-{month:02d}"
    return None


def _parse_gfc_date_range(filename: str) -> Optional[Tuple[datetime, datetime]]:
    basename = Path(filename).name
    match = re.search(r"(?P<y1>\d{4})(?P<d1>\d{3})-(?P<y2>\d{4})(?P<d2>\d{3})", basename)
    if match:
        start_dt = datetime(int(match.group("y1")), 1, 1) + timedelta(days=int(match.group("d1")) - 1)
        end_dt = datetime(int(match.group("y2")), 1, 1) + timedelta(days=int(match.group("d2")) - 1)
        return start_dt, end_dt

    ym_matches = re.findall(r"(?<!\d)(\d{4})[-_]?(\d{2})(?!\d)", basename)
    valid_months: list[datetime] = []
    for year_s, month_s in ym_matches:
        year = int(year_s)
        month = int(month_s)
        if 1 <= month <= 12:
            valid_months.append(datetime(year, month, 1))
    if valid_months:
        return valid_months[0], _increment_month(valid_months[-1]) - timedelta(days=1)

    return _parse_gfc_header_time(filename)


def _parse_gfc_header_time(filename: str) -> Optional[Tuple[datetime, datetime]]:
    path = Path(filename)
    if not path.exists() or not path.is_file():
        return None
    start_dt: Optional[datetime] = None
    end_dt: Optional[datetime] = None
    textual_re = re.compile(r"time covered in this file:\s*([A-Za-z]+)\s+(\d{4})", re.IGNORECASE)
    month_map = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
    month_map.update({name.lower(): i for i, name in enumerate(calendar.month_abbr) if name})

    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for idx, raw_line in enumerate(f):
                line = raw_line.strip()
                if not line:
                    continue
                low = line.lower()
                if "end_of_head" in low:
                    break
                if start_dt is None:
                    m = textual_re.search(line)
                    if m:
                        month = month_map.get(m.group(1).lower())
                        if month is not None:
                            start_dt = datetime(int(m.group(2)), month, 1)
                            end_dt = _increment_month(start_dt) - timedelta(days=1)
                parts = line.split(None, 1)
                if len(parts) == 2:
                    key, value = parts[0].lower(), parts[1].strip()
                    if key == "modelname":
                        ym = re.search(r"(?<!\d)(\d{4})[-_](\d{2})(?!\d)", value)
                        if ym:
                            y, mo = int(ym.group(1)), int(ym.group(2))
                            if 1 <= mo <= 12:
                                start_dt = datetime(y, mo, 1)
                                end_dt = _increment_month(start_dt) - timedelta(days=1)
                    parsed = _parse_header_date(value)
                    if parsed is not None:
                        if key == "time_coverage_start":
                            start_dt = parsed
                        elif key == "time_coverage_end":
                            end_dt = parsed
                if idx >= 400:
                    break
    except OSError:
        return None

    if start_dt is not None and end_dt is not None:
        if end_dt < start_dt:
            end_dt = _increment_month(start_dt) - timedelta(days=1)
        return start_dt, end_dt
    if start_dt is not None:
        return start_dt, _increment_month(start_dt) - timedelta(days=1)
    return None


def _parse_header_date(value: str) -> Optional[datetime]:
    m = re.search(r"(?<!\d)(\d{4})-(\d{2})(?:-(\d{2}))?(?!\d)", value)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3) or "1"))
    except ValueError:
        return None


def _increment_month(dt: datetime) -> datetime:
    if dt.month == 12:
        return datetime(dt.year + 1, 1, 1)
    return datetime(dt.year, dt.month + 1, 1)


def _month_start(dt: datetime) -> datetime:
    return datetime(dt.year, dt.month, 1)


def _assign_gfc_month(start_dt: datetime, end_dt: datetime, seen_months: set[str]) -> datetime:
    mid_dt = start_dt + (end_dt - start_dt) / 2
    current = _month_start(mid_dt)
    key = current.strftime("%Y%m")
    if key in seen_months and (start_dt.year != end_dt.year or start_dt.month != end_dt.month):
        current = _month_start(end_dt)
        key = current.strftime("%Y%m")
    while key in seen_months:
        current = _increment_month(current)
        key = current.strftime("%Y%m")
    seen_months.add(key)
    return current


def _time_value(time_cfg, key: str, default: str = "") -> str:
    if hasattr(time_cfg, key):
        value = getattr(time_cfg, key)
    elif isinstance(time_cfg, dict):
        value = time_cfg.get(key, default)
    else:
        value = default
    return str(value or "").strip()


def _auto_detect(time_cfg) -> bool:
    if hasattr(time_cfg, "auto_detect_gfc"):
        return bool(getattr(time_cfg, "auto_detect_gfc"))
    if isinstance(time_cfg, dict):
        return bool(time_cfg.get("auto_detect_gfc", True))
    return True


def _filter_entries_by_config_range(entries: List[TimeEntry], time_cfg) -> List[TimeEntry]:
    start_ym = _time_value(time_cfg, "start_ym", "")
    end_ym = _time_value(time_cfg, "end_ym", "")
    if not start_ym and not end_ym:
        return entries
    return [entry for entry in entries if (not start_ym or entry.ym >= start_ym) and (not end_ym or entry.ym <= end_ym)]


def summarize_time_coverage(time_entries: List[TimeEntry], grace_fo_start_ym: str = "2018-06") -> Dict:
    """Summarize available and missing monthly coverage."""
    if not time_entries:
        return {
            "has_data": False,
            "start_ym": "",
            "end_ym": "",
            "full_month_count": 0,
            "available_month_count": 0,
            "missing_month_count": 0,
            "grace_fo_start_ym": grace_fo_start_ym,
            "grace_available_count": 0,
            "grace_missing_count": 0,
            "grace_fo_available_count": 0,
            "grace_fo_missing_count": 0,
            "missing_months": [],
            "missing_months_grace": [],
            "missing_months_grace_fo": [],
        }
    available_months = sorted({entry.ym for entry in time_entries if entry.ym})
    if not available_months:
        return summarize_time_coverage([], grace_fo_start_ym)
    start_ym, end_ym = available_months[0], available_months[-1]
    full_months = [f"{y:04d}-{m:02d}" for y, m in parse_ym_range(start_ym, end_ym)]
    available_set = set(available_months)
    missing_months = [ym for ym in full_months if ym not in available_set]
    grace_available = [ym for ym in available_months if ym < grace_fo_start_ym]
    grace_fo_available = [ym for ym in available_months if ym >= grace_fo_start_ym]
    grace_missing = [ym for ym in missing_months if ym < grace_fo_start_ym]
    grace_fo_missing = [ym for ym in missing_months if ym >= grace_fo_start_ym]
    return {
        "has_data": True,
        "start_ym": start_ym,
        "end_ym": end_ym,
        "full_month_count": len(full_months),
        "available_month_count": len(available_months),
        "missing_month_count": len(missing_months),
        "grace_fo_start_ym": grace_fo_start_ym,
        "grace_available_count": len(grace_available),
        "grace_missing_count": len(grace_missing),
        "grace_fo_available_count": len(grace_fo_available),
        "grace_fo_missing_count": len(grace_fo_missing),
        "missing_months": missing_months,
        "missing_months_grace": grace_missing,
        "missing_months_grace_fo": grace_fo_missing,
    }


def build_time_index(cfg, gfc_dir: Optional[str] = None) -> List[TimeEntry]:
    """Build time index from configuration and crop detected files to start/end."""
    time_cfg = cfg.time if hasattr(cfg, "time") else cfg.get("time", {})
    path_cfg = cfg.path if hasattr(cfg, "path") else cfg.get("path", {})
    if gfc_dir is None:
        gfc_dir = getattr(path_cfg, "GFC", "") if hasattr(path_cfg, "GFC") else path_cfg.get("GFC", "")

    if _auto_detect(time_cfg) and gfc_dir and Path(gfc_dir).exists():
        product_type = _time_value(time_cfg, "product_type", "GSM") or "GSM"
        file_ext = _time_value(time_cfg, "file_ext", ".gfc") or ".gfc"
        entries: List[TimeEntry] = []
        seen_months: set[str] = set()
        for gfc_file in detect_gfc_files(gfc_dir, product_type, file_ext):
            window = _parse_gfc_date_range(gfc_file)
            if window is not None:
                assigned_month = _assign_gfc_month(window[0], window[1], seen_months)
                entries.append(TimeEntry.from_ym(assigned_month.strftime("%Y-%m"), gfc_file, start_dt=window[0], end_dt=window[1]))
                continue
            ym = extract_ym_from_gfc(gfc_file)
            if ym is None:
                continue
            key = ym.replace("-", "")
            if key in seen_months:
                assigned = _assign_gfc_month(TimeEntry.from_ym(ym).dt, TimeEntry.from_ym(ym).dt, seen_months)
                ym = assigned.strftime("%Y-%m")
            else:
                seen_months.add(key)
            entries.append(TimeEntry.from_ym(ym, gfc_file))
        entries.sort(key=lambda item: item.dt)
        return _filter_entries_by_config_range(entries, time_cfg)

    start_ym = _time_value(time_cfg, "start_ym", "2002-04") or "2002-04"
    end_ym = _time_value(time_cfg, "end_ym", "2017-06") or "2017-06"
    return [TimeEntry.from_ym(f"{y:04d}-{m:02d}") for y, m in parse_ym_range(start_ym, end_ym)]
