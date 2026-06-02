"""
Time index management for GRACE data processing.
"""

import calendar
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class TimeEntry:
    """Represents a single time point in the GRACE data series."""
    ym: str  # Format: "YYYY-MM"
    yyyymm: str  # Format: "YYYYMM"
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
        """Create TimeEntry from year-month string."""
        # Handle both "YYYY-MM" and "YYYYMM" formats
        if "-" in ym:
            year, month = map(int, ym.split("-"))
            yyyymm = ym.replace("-", "")
        else:
            year = int(ym[:4])
            month = int(ym[4:6])
            yyyymm = ym
            ym = f"{year:04d}-{month:02d}"
        
        dt = datetime(year, month, 1)
        if start_dt is None:
            start_dt = dt
        if end_dt is None:
            end_dt = _increment_month(dt) - timedelta(days=1)
        return cls(
            ym=ym,
            yyyymm=yyyymm,
            year=year,
            month=month,
            dt=dt,
            gfc_file=gfc_file,
            start_dt=start_dt,
            end_dt=end_dt,
        )


def parse_ym_range(start_ym: str, end_ym: str) -> List[Tuple[int, int]]:
    """Generate list of (year, month) tuples between start and end."""
    start = TimeEntry.from_ym(start_ym)
    end = TimeEntry.from_ym(end_ym)
    
    result = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        result.append((year, month))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return result


def detect_gfc_files(gfc_dir: str, product_type: str = "GSM", file_ext: str = ".gfc") -> List[str]:
    """
    Detect available GFC files in directory.
    
    Args:
        gfc_dir: Directory containing GFC files
        product_type: Product type prefix (e.g., "GSM")
        file_ext: File extension (e.g., ".gfc")
    
    Returns:
        List of GFC file paths sorted by date
    """
    gfc_path = Path(gfc_dir)
    if not gfc_path.exists():
        return []
    
    raw_ext = "" if file_ext is None else str(file_ext).strip()
    ext = raw_ext
    if ext and not ext.startswith("."):
        ext = f".{ext}"

    files: list[Path] = []

    # First pass: preserve legacy behavior for product-specific datasets (e.g., GSM*).
    if product_type:
        if ext:
            files = list(gfc_path.glob(f"{product_type}*{ext}"))
        if not files:
            files = list(gfc_path.glob(f"{product_type}*"))

    # Fallback: support non-GSM naming conventions (e.g., IGG-SLR-DORIS_YYYY-MM.gfc).
    if not files:
        if ext:
            files = [p for p in gfc_path.glob(f"*{ext}") if p.is_file()]
        else:
            files = [p for p in gfc_path.glob("*.gfc") if p.is_file()]

    if not files:
        files = [p for p in gfc_path.iterdir() if p.is_file()]

    unique_files = sorted({str(p.resolve()) for p in files})
    return unique_files


def extract_ym_from_gfc(filename: str) -> Optional[str]:
    """
    Extract year-month from GFC filename.
    
    Common formats:
    - GSM-2_2002095-2002120_GRAC_UTCSR_BA01_0600.gfc
    - The first day number (095) represents day-of-year
    """
    window = _parse_gfc_date_range(filename)
    if window is not None:
        start_dt, end_dt = window
        mid_dt = start_dt + (end_dt - start_dt) / 2
        return f"{mid_dt.year:04d}-{mid_dt.month:02d}"

    basename = Path(filename).stem
    match = re.search(r'(?<!\d)(\d{4})[-_]?(\d{2})(?!\d)', basename)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        if 1 <= month <= 12:
            return f"{year:04d}-{month:02d}"

    return None


def _parse_gfc_date_range(filename: str) -> Optional[Tuple[datetime, datetime]]:
    basename = Path(filename).name

    match = re.search(r'(?P<y1>\d{4})(?P<d1>\d{3})-(?P<y2>\d{4})(?P<d2>\d{3})', basename)
    if match:
        start_dt = datetime(int(match.group("y1")), 1, 1) + timedelta(days=int(match.group("d1")) - 1)
        end_dt = datetime(int(match.group("y2")), 1, 1) + timedelta(days=int(match.group("d2")) - 1)
        return start_dt, end_dt

    ym_matches = re.findall(r'(?<!\d)(\d{4})[-_]?(\d{2})(?!\d)', basename)
    if ym_matches:
        valid_months: list[datetime] = []
        for year_s, month_s in ym_matches:
            year = int(year_s)
            month = int(month_s)
            if 1 <= month <= 12:
                valid_months.append(datetime(year, month, 1))

        if valid_months:
            start_dt = valid_months[0]
            end_dt = _increment_month(valid_months[-1]) - timedelta(days=1)
            return start_dt, end_dt

    header_window = _parse_gfc_header_time(filename)
    if header_window is not None:
        return header_window

    return None


def _parse_gfc_header_time(filename: str) -> Optional[Tuple[datetime, datetime]]:
    path = Path(filename)
    if not path.exists() or not path.is_file():
        return None

    start_dt: Optional[datetime] = None
    end_dt: Optional[datetime] = None

    # Time covered in this file: January 1984
    textual_re = re.compile(r'time covered in this file:\s*([A-Za-z]+)\s+(\d{4})', re.IGNORECASE)

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
                        month_name = m.group(1).lower()
                        month_map = {mname.lower(): i for i, mname in enumerate(calendar.month_name) if mname}
                        month = month_map.get(month_name)
                        if month is None:
                            month_map_abbr = {mname.lower(): i for i, mname in enumerate(calendar.month_abbr) if mname}
                            month = month_map_abbr.get(month_name)
                        if month is not None:
                            year = int(m.group(2))
                            start_dt = datetime(year, month, 1)
                            end_dt = _increment_month(start_dt) - timedelta(days=1)

                parts = line.split(None, 1)
                if len(parts) == 2:
                    key = parts[0].lower()
                    value = parts[1].strip()

                    if key == "modelname":
                        ym_match = re.search(r'(?<!\d)(\d{4})[-_](\d{2})(?!\d)', value)
                        if ym_match:
                            y = int(ym_match.group(1))
                            m = int(ym_match.group(2))
                            if 1 <= m <= 12:
                                start_dt = datetime(y, m, 1)
                                end_dt = _increment_month(start_dt) - timedelta(days=1)

                    parsed = _parse_header_date(value)
                    if parsed is not None:
                        if key == "time_coverage_start":
                            start_dt = parsed
                        elif key == "time_coverage_end":
                            end_dt = parsed

                # Guard against malformed files with very long preambles and no header terminator.
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
    # Accept YYYY-MM-DD or YYYY-MM in header fields.
    m = re.search(r'(?<!\d)(\d{4})-(\d{2})(?:-(\d{2}))?(?!\d)', value)
    if not m:
        return None

    year = int(m.group(1))
    month = int(m.group(2))
    day = int(m.group(3) or "1")

    try:
        return datetime(year, month, day)
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


def summarize_time_coverage(time_entries: List[TimeEntry], grace_fo_start_ym: str = "2018-06") -> Dict:
    """
    Summarize available vs missing monthly coverage.

    Missing months are computed against the continuous range between the first and last
    available months.
    """
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

    available_months = sorted({te.ym for te in time_entries if te.ym})
    if not available_months:
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

    start_ym = available_months[0]
    end_ym = available_months[-1]
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


def build_time_index(
    cfg,
    gfc_dir: Optional[str] = None,
) -> List[TimeEntry]:
    """
    Build time index from configuration.
    
    Args:
        cfg: Configuration object with time settings
        gfc_dir: Override GFC directory
    
    Returns:
        List of TimeEntry objects for each available month
    """
    time_cfg = cfg.time if hasattr(cfg, 'time') else cfg.get('time', {})
    path_cfg = cfg.path if hasattr(cfg, 'path') else cfg.get('path', {})
    
    if gfc_dir is None:
        if hasattr(path_cfg, 'GFC'):
            gfc_dir = path_cfg.GFC
        else:
            gfc_dir = path_cfg.get('GFC', '')
    
    auto_detect = getattr(time_cfg, 'auto_detect_gfc', None)
    if auto_detect is None:
        auto_detect = time_cfg.get('auto_detect_gfc', True) if isinstance(time_cfg, dict) else True
    
    if auto_detect and gfc_dir and Path(gfc_dir).exists():
        # Auto-detect from GFC files
        product_type = getattr(time_cfg, 'product_type', None) or time_cfg.get('product_type', 'GSM')
        file_ext = getattr(time_cfg, 'file_ext', None) or time_cfg.get('file_ext', '.gfc')

        gfc_files = detect_gfc_files(gfc_dir, product_type, file_ext)

        time_entries = []
        seen_months: set[str] = set()
        for gfc_file in gfc_files:
            window = _parse_gfc_date_range(gfc_file)
            if window is not None:
                assigned_month = _assign_gfc_month(window[0], window[1], seen_months)
                ym = assigned_month.strftime("%Y-%m")
            else:
                ym = extract_ym_from_gfc(gfc_file)
                if ym is None:
                    continue
                key = ym.replace("-", "")
                if key in seen_months:
                    assigned_month = _assign_gfc_month(TimeEntry.from_ym(ym).dt, TimeEntry.from_ym(ym).dt, seen_months)
                    ym = assigned_month.strftime("%Y-%m")
                else:
                    seen_months.add(key)
            if window is not None:
                time_entries.append(TimeEntry.from_ym(ym, gfc_file, start_dt=window[0], end_dt=window[1]))
            else:
                time_entries.append(TimeEntry.from_ym(ym, gfc_file))

        time_entries.sort(key=lambda x: x.dt)
        return time_entries
    
    # Use configured time range
    start_ym = getattr(time_cfg, 'start_ym', None) or time_cfg.get('start_ym', '2002-04')
    end_ym = getattr(time_cfg, 'end_ym', None) or time_cfg.get('end_ym', '2017-06')
    
    ym_list = parse_ym_range(start_ym, end_ym)
    return [TimeEntry.from_ym(f"{y:04d}-{m:02d}") for y, m in ym_list]
