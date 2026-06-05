"""
GFC file reader for GRACE/GRACE-FO data.
Reads ICGEM/GRACE Level-2 spherical harmonic coefficient files.
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


def _is_coeff_record(token: str) -> bool:
    """Return True for supported SH coefficient record identifiers."""
    key = str(token or "").strip().lower()
    return key.startswith("gfc") or key in {"grcof", "grcof2"}


def _parse_header_value(stripped: str) -> Optional[Tuple[str, str]]:
    """Parse simple key/value header lines from ICGEM and GRACE YAML-like files."""
    if not stripped or stripped.startswith("#"):
        return None
    if ":" in stripped:
        key, value = stripped.split(":", 1)
        return key.strip().lower(), value.strip()
    parts = stripped.split(None, 1)
    if len(parts) == 2:
        return parts[0].strip().lower(), parts[1].strip()
    return None


def read_gfc(gfc_file: str, Lmax: int) -> SHCoefficients:
    """
    Read ICGEM/GRACE Level-2 .gfc file and return spherical harmonic coefficients.
    
    Args:
        gfc_file: Path to GFC file
        Lmax: Maximum degree to read
    
    Returns:
        SHCoefficients object with C, S matrices
    
    Notes:
        - Supports ICGEM-style records beginning with ``gfc``/``gfct``.
        - Supports GRACE Level-2 SHM records beginning with ``GRCOF``/``GRCOF2``.
        - C and S are stored as [Lmax+1, Lmax+1] with C[l,m] indexing.
    """
    if not Path(gfc_file).exists():
        raise FileNotFoundError(f"GFC file not found: {gfc_file}")
    
    meta = {"file": gfc_file}
    
    # Initialize coefficient matrices
    C = np.zeros((Lmax + 1, Lmax + 1))
    S = np.zeros((Lmax + 1, Lmax + 1))
    coeff_count = 0
    max_degree_seen = -1
    
    with open(gfc_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue

            parts = stripped.split()
            token = parts[0].lower()

            # Parse coefficient lines. CSR/JPL/GFZ RL06 SHM files commonly use
            # GRCOF2 records; ICGEM products use gfc/gfct. Treat both as first
            # class coefficient records. Without GRCOF2 support the reader would
            # silently return all-zero GSM coefficients for standard PO.DAAC
            # GRACE Level-2 files.
            if _is_coeff_record(token) and len(parts) >= 5:
                parsed = _parse_coeff_record(parts)
                if parsed is None:
                    continue
                l, m, clm, slm = parsed

                # Only store coefficients up to Lmax
                if l <= Lmax and m <= l and m >= 0 and l >= 0:
                    C[l, m] = clm
                    S[l, m] = slm
                    coeff_count += 1
                    max_degree_seen = max(max_degree_seen, l)
                continue

            # Parse header key-values when available.
            parsed_header = _parse_header_value(stripped)
            if parsed_header is not None:
                key, value = parsed_header
                if key in {
                    "modelname",
                    "product_type",
                    "earth_gravity_constant",
                    "earth_gravity_param",
                    "radius",
                    "mean_equator_radius",
                    "max_degree",
                    "degree",
                    "order",
                    "norm",
                    "normalization",
                    "tide_system",
                    "permanent_tide_flag",
                    "errors",
                    "time_coverage_start",
                    "time_coverage_end",
                }:
                    meta[key] = value

    meta["coeff_count"] = coeff_count
    meta["max_degree_seen"] = max_degree_seen

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
