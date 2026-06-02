"""
Metrics accumulator for time-series aggregation.
"""

from typing import List, Dict, Any, Optional
import numpy as np
from dataclasses import dataclass, field

from grace_pipeline.metrics.evaluate import eval_global

@dataclass
class MetricTimeSeries:
    """Time series of scalar metrics."""
    CC: np.ndarray
    NSC: np.ndarray
    RMSE: np.ndarray
    MAE: np.ndarray
    PSNR: np.ndarray
    SNR: np.ndarray
    Nvalid: np.ndarray
    
    @classmethod
    def create(cls, nt: int) -> 'MetricTimeSeries':
        return cls(
            CC=np.full(nt, np.nan),
            NSC=np.full(nt, np.nan),
            RMSE=np.full(nt, np.nan),
            MAE=np.full(nt, np.nan),
            PSNR=np.full(nt, np.nan),
            SNR=np.full(nt, np.nan),
            Nvalid=np.zeros(nt, dtype=int)
        )
        
    def update(self, index: int, m: Dict[str, float]):
        self.CC[index] = m.get('CC', np.nan)
        self.NSC[index] = m.get('NSC', np.nan)
        self.RMSE[index] = m.get('RMSE', np.nan)
        self.MAE[index] = m.get('MAE', np.nan)
        self.PSNR[index] = m.get('PSNR', np.nan)
        self.SNR[index] = m.get('SNR', np.nan)
        self.Nvalid[index] = m.get('Nvalid', 0)


class MetricsAccumulator:
    """Accumulates metrics over time and space."""
    
    def __init__(
        self,
        methods: List[str],
        nt: int,
        shape: tuple[int, int]
    ):
        self.methods = methods
        self.nt = nt
        self.shape = shape
        
        self.ts: Dict[str, MetricTimeSeries] = {}
        self.sse: Dict[str, np.ndarray] = {}  # Sum of squared errors
        self.nmap: Dict[str, np.ndarray] = {} # Count of valid points
        
        for m in methods:
            self.ts[m] = MetricTimeSeries.create(nt)
            self.sse[m] = np.zeros(shape)
            self.nmap[m] = np.zeros(shape)
            
    def update(
        self,
        t_index: int,
        method: str,
        fo: np.ndarray,
        ft: np.ndarray,
        mask_land: Optional[np.ndarray] = None,
        mask_ocean: Optional[np.ndarray] = None
    ):
        """Update metrics for a single time step."""
        if method not in self.methods:
            return
            
        # Global scalars
        m = eval_global(fo, ft, mask_land, mask_ocean)
        self.ts[method].update(t_index, m)
        
        # Spatial accumulation (SRMSE)
        v = np.isfinite(fo) & np.isfinite(ft)
        d = fo - ft
        d[~v] = 0
        
        self.sse[method] += d**2
        self.nmap[method] += v.astype(float)
        
    def finalize(self) -> Dict[str, Any]:
        """Compute final temporal statistics."""
        results = {
            'ts': {m: self.ts[m].__dict__ for m in self.methods},
            'srmse': {}
        }
        
        for m in self.methods:
            # Compute SRMSE map
            with np.errstate(divide='ignore', invalid='ignore'):
                mse_map = self.sse[m] / self.nmap[m]
                srmse_map = np.sqrt(mse_map)
                srmse_map[self.nmap[m] == 0] = np.nan
                results['srmse'][m] = srmse_map
                
        return results
