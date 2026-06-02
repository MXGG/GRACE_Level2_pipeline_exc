"""
GFC file reader for GRACE/GRACE-FO data.
Reads ICGEM format spherical harmonic coefficient files.
"""

import re
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass, field

import numpy as np

from grace_pipeline.core.time_index import extract_ym_from_gfc


@dataclass
class SHCoefficients:
    """Spherical harmonic coefficients structure."""
    C: np.ndarray  # Cosine coefficients [Lmax+1, Lmax+1]
    S: np.ndarray  # Sine coefficients [Lmax+1, Lmax+1]
    Lmax: int  # Maximum degree
    meta: Dict[str, Any] = field(default_factory=dict)
    replaced: Dict[str, bool] = field(default_factory=dict)


def find_gfc_file(cfg, time_entry) -> Optional[str]:
    """
    Find GFC file for a given time entry.
    
    Args:
        cfg: Configuration object
        time_entry: TimeEntry object with ym/yyyymm
    
    Returns:
        Path to GFC file or None
    """
    if time_entry.gfc_file and Path(time_entry.gfc_file).exists():
        return time_entry.gfc_file
    
    gfc_dir = cfg.path.GFC if hasattr(cfg.path, 'GFC') else cfg.path.get('GFC', '')
    if not gfc_dir or not Path(gfc_dir).exists():
        return None
    
    gfc_path = Path(gfc_dir)
    ym = time_entry.ym.replace("-", "")
    
    # Try common patterns
    patterns = [
        f"*{time_entry.ym}*.gfc",
        f"*{ym}*.gfc",
        f"*{time_entry.year}{time_entry.month:02d}*.gfc",
        f"GSM*{ym}*",
    ]
    
    for pattern in patterns:
        matches = list(gfc_path.glob(pattern))
        if matches:
            return str(matches[0])

    # Fallback: parse month from filenames/headers to match non-standard naming.
    target_ym = getattr(time_entry, "ym", "").strip()
    if target_ym:
        for candidate in sorted(gfc_path.glob("*.gfc")):
            parsed_ym = extract_ym_from_gfc(str(candidate))
            if parsed_ym == target_ym:
                return str(candidate)
    
    return None


def read_gfc(gfc_file: str, Lmax: int) -> SHCoefficients:
    """
    Read ICGEM .gfc file and return spherical harmonic coefficients.
    
    Args:
        gfc_file: Path to GFC file
        Lmax: Maximum degree to read
    
    Returns:
        SHCoefficients object with C, S matrices
    
    Notes:
        - Supports lines beginning with 'gfc' or 'gfct'
        - Skips header until 'end_of_head'
        - C and S are stored as [Lmax+1, Lmax+1] with C[l,m] indexing
    """
    if not Path(gfc_file).exists():
        raise FileNotFoundError(f"GFC file not found: {gfc_file}")
    
    meta = {"file": gfc_file}
    
    # Initialize coefficient matrices
    C = np.zeros((Lmax + 1, Lmax + 1))
    S = np.zeros((Lmax + 1, Lmax + 1))
    coeff_count = 0
    
    with open(gfc_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue

            parts = stripped.split()
            token = parts[0].lower()

            # Parse coefficient lines (gfc/gfct/other gfc-prefixed variants).
            if token.startswith('gfc') and len(parts) >= 5:
                parsed = _parse_coeff_record(parts)
                if parsed is None:
                    continue
                l, m, clm, slm = parsed

                # Only store coefficients up to Lmax
                if l <= Lmax and m <= l and m >= 0 and l >= 0:
                    C[l, m] = clm
                    S[l, m] = slm
                    coeff_count += 1
                continue

            # Parse header key-values when available.
            if len(parts) >= 2 and not token.startswith("#"):
                key = parts[0].lower()
                if key in {
                    "modelname",
                    "product_type",
                    "earth_gravity_constant",
                    "radius",
                    "max_degree",
                    "norm",
                    "tide_system",
                    "errors",
                    "time_coverage_start",
                    "time_coverage_end",
                }:
                    meta[key] = stripped.split(None, 1)[1].strip()

    meta["coeff_count"] = coeff_count

    ym = extract_ym_from_gfc(gfc_file)
    if ym:
        meta["ym"] = ym
        meta["yyyymm"] = ym.replace("-", "")
        try:
            meta["year"] = int(ym[:4])
            meta["month"] = int(ym[5:7])
        except ValueError:
            pass

    return SHCoefficients(
        C=C,
        S=S,
        Lmax=Lmax,
        meta=meta,
        replaced={},
    )


def _parse_coeff_record(parts: list[str]) -> Optional[Tuple[int, int, float, float]]:
    try:
        l = int(parts[1])
        m = int(parts[2])
        clm = _safe_float(parts[3])
        slm = _safe_float(parts[4])
    except (ValueError, IndexError):
        return None

    return l, m, clm, slm


def _safe_float(raw: str) -> float:
    token = raw.strip().replace("D", "E").replace("d", "e")
    if token.endswith(","):
        token = token[:-1]
    return float(token)


def read_gsm_month(cfg, time_entry) -> SHCoefficients:
    """
    Read monthly GSM coefficients.
    
    Args:
        cfg: Configuration object
        time_entry: TimeEntry object
    
    Returns:
        SHCoefficients object
    """
    inv_cfg = cfg.inversion if hasattr(cfg, 'inversion') else cfg.get('inversion', {})
    if isinstance(inv_cfg, dict):
        Lmax = inv_cfg.get('Lmax', 60)
    else:
        Lmax = getattr(inv_cfg, 'Lmax', 60)
    gfc_file = find_gfc_file(cfg, time_entry)
    
    if gfc_file is None:
        raise FileNotFoundError(f"No GFC file found for {time_entry.ym}")
    
    sh = read_gfc(gfc_file, Lmax)
    sh.meta['ym'] = time_entry.ym
    sh.meta['yyyymm'] = time_entry.yyyymm
    
    return sh
