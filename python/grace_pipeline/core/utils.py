"""
Utility functions for GRACE pipeline.
"""

import os
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional, Union


def ensure_dir(path: Union[str, Path]) -> Path:
    """
    Ensure directory exists, creating if necessary.
    
    Args:
        path: Directory path
    
    Returns:
        Path object for the directory
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def merge_struct(base: Dict, override: Dict) -> Dict:
    """
    Merge two dictionaries (shallow merge).
    
    Args:
        base: Base dictionary
        override: Dictionary with override values
    
    Returns:
        Merged dictionary
    """
    result = base.copy()
    if override:
        result.update(override)
    return result


def deep_merge(base: Dict, override: Dict) -> Dict:
    """
    Deep merge two dictionaries.
    
    Args:
        base: Base dictionary
        override: Dictionary with override values
    
    Returns:
        Deep merged dictionary
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def cfg_hash(cfg: Union[Dict, object], keys: Optional[list] = None) -> str:
    """
    Compute a hash of configuration for caching/checkpointing.
    
    Args:
        cfg: Configuration dictionary or object
        keys: Specific keys to include in hash
    
    Returns:
        MD5 hash string
    """
    if hasattr(cfg, 'to_dict'):
        cfg_dict = cfg.to_dict()
    elif hasattr(cfg, '_raw'):
        cfg_dict = cfg._raw
    else:
        cfg_dict = cfg
    
    if keys:
        cfg_dict = {k: cfg_dict.get(k) for k in keys if k in cfg_dict}
    
    # Sort keys for consistent hashing
    cfg_str = json.dumps(cfg_dict, sort_keys=True, default=str)
    return hashlib.md5(cfg_str.encode()).hexdigest()[:12]


class ProgressBar:
    """Simple progress bar for console output."""
    
    def __init__(self, total: int, tag: str = "Progress", width: int = 40):
        self.total = max(total, 1)
        self.tag = tag
        self.width = width
        self.current = 0
        self.substep = ""
    
    def update(self, n: int, substep: str = ""):
        """Update progress bar."""
        self.current = min(n, self.total)
        self.substep = substep
        self._display()
    
    def _display(self):
        """Display progress bar."""
        pct = self.current / self.total
        filled = int(self.width * pct)
        bar = "=" * filled + "-" * (self.width - filled)
        substep_str = f" {self.substep}" if self.substep else ""
        print(f"\r[{self.tag}] [{bar}] {pct*100:5.1f}%{substep_str}", end="", flush=True)
    
    def finish(self):
        """Complete progress bar."""
        self.current = self.total
        self._display()
        print()  # New line


def progress_bar(action: str, *args, **kwargs):
    """
    Factory function for progress bar operations.
    
    Args:
        action: 'create', 'update', or 'finish'
    """
    if action == "create":
        total = args[0] if args else kwargs.get("total", 100)
        tag = kwargs.get("Tag", "Progress")
        return ProgressBar(total, tag)
    elif action == "update":
        pb = args[0]
        n = args[1] if len(args) > 1 else kwargs.get("n", 0)
        substep = kwargs.get("substep", "")
        pb.update(n, substep)
        return pb
    elif action == "finish":
        pb = args[0]
        pb.finish()
        return pb


def safe_save(data: Any, filepath: Union[str, Path], save_func=None):
    """
    Safely save data by writing to temp file first, then moving.
    Helps avoid corruption on crash.
    
    Args:
        data: Data to save
        filepath: Target file path
        save_func: Function to call for saving (default: pickle)
    """
    import tempfile
    import shutil
    
    filepath = Path(filepath)
    ensure_dir(filepath.parent)
    
    # Write to temp file
    fd, tmp_path = tempfile.mkstemp(
        suffix=filepath.suffix,
        prefix=filepath.stem + "_",
        dir=filepath.parent
    )
    os.close(fd)
    
    try:
        if save_func:
            save_func(data, tmp_path)
        else:
            import pickle
            with open(tmp_path, 'wb') as f:
                pickle.dump(data, f)
        
        # Move to final location
        shutil.move(tmp_path, filepath)
    except Exception as e:
        # Clean up temp file on error
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise e
