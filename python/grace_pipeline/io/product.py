"""Product save/load utilities."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import scipy.io as sio


@dataclass
class Product:
    """GRACE product data structure."""
    tag: str  # Product identifier (e.g., 'GAUSS', 'P4M6')
    ym: str  # Year-month string
    ewh: np.ndarray  # EWH grid [nLon, nLat]
    lon: np.ndarray
    lat: np.ndarray
    meta: Dict[str, Any] = field(default_factory=dict)


def save_product(
    product: Product,
    output_dir: str,
    format: str = 'mat',
) -> str:
    """
    Save product to file.
    
    Args:
        product: Product object
        output_dir: Output directory
        format: 'mat' or 'txt'
    
    Returns:
        Path to saved file
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    if format == 'mat':
        filename = f"{product.tag}_{product.ym}.mat"
        filepath = os.path.join(output_dir, filename)
        
        # Use safe save (temp file then move)
        temp_path = filepath + '.tmp'
        sio.savemat(temp_path, {
            'ewh': product.ewh,
            'lon': product.lon,
            'lat': product.lat,
            'tag': product.tag,
            'ym': product.ym,
            'meta': str(product.meta),
        }, do_compression=True, appendmat=False)

        os.replace(temp_path, filepath)
        
    elif format == 'txt':
        filename = f"{product.tag}_{product.ym}.txt"
        filepath = os.path.join(output_dir, filename)
        
        # Stream rows by longitude to avoid building a full lon/lat mesh in memory.
        with open(filepath, 'w') as f:
            f.write(f"# {product.tag} {product.ym}\n")
            f.write("# lon lat ewh_mm\n")
            val = np.asarray(product.ewh, dtype=float)
            lon = np.asarray(product.lon, dtype=float).reshape(-1)
            lat = np.asarray(product.lat, dtype=float).reshape(-1)
            for i in range(min(val.shape[0], lon.size)):
                row = val[i, :]
                valid = np.isfinite(row)
                if not np.any(valid):
                    continue
                arr = np.column_stack((
                    np.full(np.count_nonzero(valid), lon[i], dtype=float),
                    lat[valid],
                    row[valid],
                ))
                np.savetxt(f, arr, fmt="%.2f %.2f %.4f")
    else:
        raise ValueError(f"Unknown format: {format}")
    
    return filepath


def load_product(filepath: str) -> Product:
    """
    Load product from file.
    
    Args:
        filepath: Path to product file
    
    Returns:
        Product object
    """
    if filepath.endswith('.mat'):
        data = sio.loadmat(filepath)
        return Product(
            tag=str(data.get('tag', [''])[0]),
            ym=str(data.get('ym', [''])[0]),
            ewh=np.array(data['ewh']),
            lon=np.array(data['lon']).flatten(),
            lat=np.array(data['lat']).flatten(),
            meta={},
        )
    else:
        raise ValueError(f"Unsupported file format: {filepath}")


def find_product_file(
    output_dir: str,
    tag: str,
    ym: str,
) -> Optional[str]:
    """
    Find product file in output directory.
    
    Args:
        output_dir: Directory to search
        tag: Product tag
        ym: Year-month string
    
    Returns:
        Path to file or None
    """
    patterns = [
        f"{tag}_{ym}.mat",
        f"{tag}_{ym.replace('-', '')}.mat",
    ]
    
    for pattern in patterns:
        filepath = os.path.join(output_dir, pattern)
        if os.path.exists(filepath):
            return filepath
    
    return None
