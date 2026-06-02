"""
Evaluation metrics for GRACE products.
"""

import numpy as np
from typing import Dict, Any, Optional

def eval_global(
    fo: np.ndarray,
    ft: np.ndarray,
    mask_land: Optional[np.ndarray] = None,
    mask_ocean: Optional[np.ndarray] = None
) -> Dict[str, float]:
    """Compute global scalar metrics between test (fo) and reference (ft).
    
    Args:
        fo: Test grid (mmEWH)
        ft: Reference grid (mmEWH)
        mask_land: Boolean mask for land (optional, for SNR)
        mask_ocean: Boolean mask for ocean (optional, for SNR)
        
    Returns:
        Dictionary with CC, NSC, RMSE, MAE, PSNR, SNR, Nvalid
    """
    fo_flat = fo.flatten()
    ft_flat = ft.flatten()
    
    # Valid mask
    v = np.isfinite(fo_flat) & np.isfinite(ft_flat)
    N = np.sum(v)
    
    metrics = {
        'CC': np.nan,
        'NSC': np.nan,
        'RMSE': np.nan,
        'MAE': np.nan,
        'PSNR': np.nan,
        'SNR': np.nan,
        'Nvalid': int(N)
    }
    
    if N < 5:
        return metrics
        
    fo_v = fo_flat[v]
    ft_v = ft_flat[v]
    
    mfo = np.mean(fo_v)
    mft = np.mean(ft_v)
    
    # CC (Pearson)
    num = np.sum((fo_v - mfo) * (ft_v - mft))
    den = np.sqrt(np.sum((fo_v - mfo)**2) * np.sum((ft_v - mft)**2))
    if den > 0:
        metrics['CC'] = num / den
        
    # NSC (Nash-Sutcliffe)
    numN = np.sum((fo_v - ft_v)**2)
    denN = np.sum((ft_v - mft)**2)
    if denN > 0:
        metrics['NSC'] = 1 - numN / denN
        
    # RMSE / MAE
    mse = np.mean((fo_v - ft_v)**2)
    metrics['RMSE'] = np.sqrt(mse)
    metrics['MAE'] = np.mean(np.abs(fo_v - ft_v))
    
    # PSNR
    maxFt2 = np.max(ft_v)**2
    metrics['PSNR'] = 10 * np.log10(maxFt2 / (mse + np.finfo(float).eps))
    
    # SNR (Land/Ocean RMS ratio)
    if mask_land is not None and mask_ocean is not None:
        land = fo[mask_land & np.isfinite(fo)]
        ocean = fo[mask_ocean & np.isfinite(fo)]
        
        if len(land) > 0 and len(ocean) > 0:
            rms_land = np.sqrt(np.mean(land**2))
            rms_ocean = np.sqrt(np.mean(ocean**2))
            
            if rms_ocean > 0:
                metrics['SNR'] = 10 * np.log10(rms_land / (rms_ocean + np.finfo(float).eps))
                
    return metrics
