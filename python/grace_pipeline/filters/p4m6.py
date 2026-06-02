"""
P4M6 destriping filter for spherical harmonic coefficients.

Polynomial decorrelation filter that removes correlated errors
(stripes) by fitting and removing polynomial trends in the
SH coefficient space.
"""

import numpy as np
from typing import Tuple, Dict, Any


def filter_sh_p4m6(
    C: np.ndarray,
    S: np.ndarray,
    Lmax: int,
    poly_deg: int = 4,
    m_start: int = 6,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Apply PnMm decorrelation filter to spherical harmonic coefficients.
    
    For each order m >= m_start, separately for even/odd degrees:
    Fit a polynomial of degree poly_deg to C(l,m) and S(l,m) vs degree l,
    then subtract the fitted trend from the coefficients.
    
    Args:
        C: Cosine coefficients [Lmax+1, Lmax+1] or [Lmax+1, Lmax+1, Nt]
        S: Sine coefficients [Lmax+1, Lmax+1] or [Lmax+1, Lmax+1, Nt]
        Lmax: Maximum degree
        poly_deg: Polynomial degree for fitting (default: 4)
        m_start: Starting order for destriping (default: 6)
    
    Returns:
        Tuple of (C_filtered, S_filtered, metadata)
    """
    C_f = C.copy()
    S_f = S.copy()
    
    is_3d = C.ndim == 3
    if is_3d:
        Nt = C.shape[2]
    else:
        Nt = 1
        C_f = C_f[:, :, np.newaxis]
        S_f = S_f[:, :, np.newaxis]
    
    # Process each time step
    for it in range(Nt):
        C_t = C_f[:, :, it]
        S_t = S_f[:, :, it]
        
        # Process each order m >= m_start
        for m in range(m_start, Lmax + 1):
            # Get degrees for this order
            l_all = np.arange(m, Lmax + 1)
            
            # Even degrees
            l_even = l_all[l_all % 2 == 0]
            if len(l_even) >= poly_deg + 2:
                C_t, S_t = _remove_poly_trend(C_t, S_t, l_even, m, poly_deg)
            
            # Odd degrees
            l_odd = l_all[l_all % 2 == 1]
            if len(l_odd) >= poly_deg + 2:
                C_t, S_t = _remove_poly_trend(C_t, S_t, l_odd, m, poly_deg)
        
        C_f[:, :, it] = C_t
        S_f[:, :, it] = S_t
    
    if not is_3d:
        C_f = C_f[:, :, 0]
        S_f = S_f[:, :, 0]
    
    meta = {
        'type': f'P{poly_deg}M{m_start}',
        'poly_deg': poly_deg,
        'm_start': m_start,
    }
    
    return C_f, S_f, meta


def _remove_poly_trend(
    C: np.ndarray,
    S: np.ndarray,
    l_arr: np.ndarray,
    m: int,
    poly_deg: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Remove polynomial trend from coefficients at given degrees.
    
    Args:
        C, S: Coefficient matrices [Lmax+1, Lmax+1]
        l_arr: Array of degree indices
        m: Order
        poly_deg: Polynomial degree
    
    Returns:
        Modified (C, S) matrices
    """
    x = l_arr.astype(float)
    
    # Process C coefficients
    y_c = C[l_arr, m]
    good_c = np.isfinite(y_c)
    if np.sum(good_c) >= poly_deg + 2:
        x_valid = x[good_c]
        y_valid = y_c[good_c]
        p = np.polyfit(x_valid, y_valid, poly_deg)
        y_fit = np.polyval(p, x_valid)
        l_good = l_arr[good_c]
        C[l_good, m] = C[l_good, m] - y_fit
    
    # Process S coefficients
    y_s = S[l_arr, m]
    good_s = np.isfinite(y_s)
    if np.sum(good_s) >= poly_deg + 2:
        x_valid = x[good_s]
        y_valid = y_s[good_s]
        p = np.polyfit(x_valid, y_valid, poly_deg)
        y_fit = np.polyval(p, x_valid)
        l_good = l_arr[good_s]
        S[l_good, m] = S[l_good, m] - y_fit
    
    return C, S
