"""
Correlation analysis for GRACE product stacks.
"""

import numpy as np
from typing import Optional

def compute_cc_map(
    A: np.ndarray,
    B: np.ndarray,
    min_count: int = 10
) -> np.ndarray:
    """Compute temporal correlation map between two 3D stacks [nLon, nLat, Nt].
    
    Args:
        A: First stack (nLon, nLat, Nt)
        B: Second stack (nLon, nLat, Nt)
        min_count: Minimum valid points required to compute correlation
        
    Returns:
        Correlation map (nLon, nLat)
    """
    if A.shape != B.shape:
        raise ValueError(f"Shape mismatch: {A.shape} vs {B.shape}")
        
    nLon, nLat, Nt = A.shape
    
    # Reshape to [pixels, time]
    a = A.reshape(-1, Nt)
    b = B.reshape(-1, Nt)
    
    # Identify valid points
    v = np.isfinite(a) & np.isfinite(b)
    n = np.sum(v, axis=1)
    
    cc = np.full(n.shape, np.nan)
    
    # Process pixels with enough data
    ok = n >= min_count
    
    if np.any(ok):
        # Apply mask (zeros where invalid, but v handles count)
        # Note: We must operate carefully to handle NaNs correctly
        # Instead of replacing NaNs with 0, we use masked arrays or explicit math
        
        # Explicit math with zeroing invalid entries
        a_valid = np.where(v, a, 0)
        b_valid = np.where(v, b, 0)
        
        sum_a = np.sum(a_valid, axis=1)
        sum_b = np.sum(b_valid, axis=1)
        sum_a2 = np.sum(a_valid**2, axis=1)
        sum_b2 = np.sum(b_valid**2, axis=1)
        sum_ab = np.sum(a_valid * b_valid, axis=1)
        
        # Calculate moments on valid subset
        n_ok = n[ok]
        mu_a = sum_a[ok] / n_ok
        mu_b = sum_b[ok] / n_ok
        
        denom = np.maximum(n_ok - 1, 1)
        
        # Covariance
        cov_ab = (sum_ab[ok] - n_ok * mu_a * mu_b) / denom
        var_a = (sum_a2[ok] - n_ok * mu_a**2) / denom
        var_b = (sum_b2[ok] - n_ok * mu_b**2) / denom
        
        # Correlation
        cc[ok] = cov_ab / (np.sqrt(var_a * var_b) + np.finfo(float).eps)
        
    return cc.reshape(nLon, nLat)
