"""
Seasonal and trend fitting for time series.
"""

import numpy as np
from typing import Tuple, Dict

def fit_seasonal_trend(
    t_years: np.ndarray,
    y: np.ndarray,
    period: float = 1.0
) -> Dict[str, float]:
    """Fit trend + annual + semi-annual signal.
    
    Model: y = a + b*t + c*cos(w*t) + d*sin(w*t) + e*cos(2*w*t) + f*sin(2*w*t)
    
    Args:
        t_years: Time vector in years (e.g. 2002.3)
        y: Data vector
        period: Period in years (default 1.0)
        
    Returns:
        Dictionary with trend, amplitude, phase, etc.
    """
    valid = np.isfinite(y)
    if np.sum(valid) < 6:
        return {
            'trend': np.nan,
            'amp_ann': np.nan,
            'phs_ann': np.nan,
            'amp_semi': np.nan,
            'phs_semi': np.nan,
            'residual_rms': np.nan,
            'const': np.nan
        }
        
    t = t_years[valid]
    d = y[valid]
    
    # Reference time to mean to improve conditioning
    t_mean = np.mean(t)
    t_prime = t - t_mean
    
    w = 2 * np.pi / period
    
    # Design matrix
    # [1, t, cos(wt), sin(wt), cos(2wt), sin(2wt)]
    A = np.column_stack((
        np.ones_like(t),
        t_prime,
        np.cos(w * t_prime),
        np.sin(w * t_prime),
        np.cos(2 * w * t_prime),
        np.sin(2 * w * t_prime)
    ))
    
    # Least squares
    try:
        x, residuals, rank, s = np.linalg.lstsq(A, d, rcond=None)
    except np.linalg.LinAlgError:
        return {'trend': np.nan}
        
    const, trend, c1, d1, c2, d2 = x
    
    # Amplitude and Phase
    amp_ann = np.sqrt(c1**2 + d1**2)
    phs_ann = np.arctan2(d1, c1) # Phase relative to t_mean
    
    amp_semi = np.sqrt(c2**2 + d2**2)
    phs_semi = np.arctan2(d2, c2)
    fitted = A @ x
    residual = d - fitted
    residual_rms = float(np.sqrt(np.nanmean(residual ** 2))) if residual.size else np.nan
    
    return {
        'trend': trend,
        'amp_ann': amp_ann,
        'phs_ann': phs_ann,
        'amp_semi': amp_semi,
        'phs_semi': phs_semi,
        'residual_rms': residual_rms,
        'const': const,
        't_mean': t_mean,
        'coef_ann_cos': c1,
        'coef_ann_sin': d1,
        'coef_semi_cos': c2,
        'coef_semi_sin': d2,
    }
