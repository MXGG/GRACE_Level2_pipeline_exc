"""
GIA (Glacial Isostatic Adjustment) correction for GRACE data.
"""

from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

import numpy as np


@dataclass
class GIAModel:
    """GIA model coefficients."""
    C: np.ndarray  # Cosine coefficients rate [/year]
    S: np.ndarray  # Sine coefficients rate [/year]
    Lmax: int
    meta: Dict[str, Any]


def read_gia_model(filepath: str, Lmax: int) -> GIAModel:
    """
    Read GIA model Stokes coefficients.
    
    Typical format: l m Clm_dot Slm_dot (rates in 1/year)
    
    Args:
        filepath: Path to GIA model file
        Lmax: Maximum degree
    
    Returns:
        GIAModel object
    """
    if not Path(filepath).exists():
        raise FileNotFoundError(f"GIA file not found: {filepath}")
    
    C = np.zeros((Lmax + 1, Lmax + 1))
    S = np.zeros((Lmax + 1, Lmax + 1))
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('%'):
                continue
            
            parts = line.split()
            if len(parts) < 4:
                continue
            
            try:
                l = int(parts[0])
                m = int(parts[1])
                c_dot = float(parts[2])
                s_dot = float(parts[3])
                
                if l <= Lmax and m <= l:
                    C[l, m] = c_dot
                    S[l, m] = s_dot
                    
            except (ValueError, IndexError):
                continue
    
    return GIAModel(
        C=C,
        S=S,
        Lmax=Lmax,
        meta={'file': filepath},
    )


# Cache for GIA model
_gia_cache: Optional[GIAModel] = None
_gia_cache_path: Optional[str] = None


def load_gia_model(cfg) -> Optional[GIAModel]:
    """
    Load GIA model from configuration.
    
    Args:
        cfg: Configuration object
    
    Returns:
        GIAModel or None
    """
    global _gia_cache, _gia_cache_path
    
    inv_cfg = cfg.inversion if hasattr(cfg, 'inversion') else cfg.get('inversion', {})
    gia_cfg = getattr(inv_cfg, 'gia', None) or inv_cfg.get('gia', {})
    
    if not gia_cfg:
        return None
    
    enable = gia_cfg.get('enable', False) if isinstance(gia_cfg, dict) else getattr(gia_cfg, 'enable', False)
    if not enable:
        return None
    
    gia_file = gia_cfg.get('file', '') if isinstance(gia_cfg, dict) else getattr(gia_cfg, 'file', '')
    Lmax = gia_cfg.get('Lmax', 60) if isinstance(gia_cfg, dict) else getattr(gia_cfg, 'Lmax', 60)
    
    if not gia_file or not Path(gia_file).exists():
        return None
    
    # Use cache if same file
    if _gia_cache is not None and _gia_cache_path == gia_file:
        return _gia_cache
    
    _gia_cache = read_gia_model(gia_file, Lmax)
    _gia_cache_path = gia_file
    
    return _gia_cache


def apply_gia(cfg, sh, time_entry=None, reference_epoch: float = 2002.0):
    """
    Apply GIA correction to spherical harmonic coefficients.
    
    The GIA model provides rates (per year). We compute:
    C_corrected = C - C_dot * (t - t_ref)
    
    Args:
        cfg: Configuration object
        sh: SHCoefficients object
        time_entry: TimeEntry for computing time offset
        reference_epoch: Reference epoch year (default: 2002.0)
    
    Returns:
        Corrected SHCoefficients
    """
    gia = load_gia_model(cfg)
    if gia is None:
        return sh
    
    # Compute time offset from reference epoch
    if time_entry is not None:
        # Convert to decimal year
        t = time_entry.year + (time_entry.month - 0.5) / 12.0
    else:
        # Use middle of typical GRACE period
        t = 2010.0
    
    dt = t - reference_epoch
    
    # Apply correction
    Lmax = min(sh.Lmax, gia.Lmax)
    sh.C[:Lmax+1, :Lmax+1] -= gia.C[:Lmax+1, :Lmax+1] * dt
    sh.S[:Lmax+1, :Lmax+1] -= gia.S[:Lmax+1, :Lmax+1] * dt
    
    sh.meta['gia_applied'] = True
    sh.meta['gia_dt'] = dt
    
    return sh
