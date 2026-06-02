"""Non-UI progress cache helpers extracted from GUI class."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


def scope_cache_dir(output_path: str, root_dir: str) -> Path:
    out_dir = (output_path or "").strip()
    if not out_dir:
        out_dir = str(Path(root_dir) / "output")
    d = Path(out_dir) / "local" / "CACHE" / "progress"
    d.mkdir(parents=True, exist_ok=True)
    return d


def scope_cache_file(scope: str, output_path: str, root_dir: str) -> Path:
    return scope_cache_dir(output_path, root_dir) / f"{scope}.json"


def load_scope_progress(scope: str, signature: str, output_path: str, root_dir: str) -> Optional[Dict[str, Any]]:
    f = scope_cache_file(scope, output_path, root_dir)
    if not f.exists():
        return None
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        if str(data.get("signature", "")) != str(signature):
            return None
        return data
    except Exception:
        return None


def save_scope_progress(
    scope: str,
    signature: str,
    state: Dict[str, Any],
    progress_cache_last_save: Dict[str, float],
    output_path: str,
    root_dir: str,
):
    f = scope_cache_file(scope, output_path, root_dir)
    payload = {
        "scope": scope,
        "signature": signature,
        "updated": datetime.now().isoformat(timespec="seconds"),
        "state": state,
    }
    tmp = str(f) + ".tmp"
    Path(tmp).write_text(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":")),
        encoding="utf-8",
    )
    os.replace(tmp, str(f))
    progress_cache_last_save[scope] = time.time()


def save_scope_progress_throttled(
    scope: str,
    signature: str,
    state: Dict[str, Any],
    progress_cache_last_save: Dict[str, float],
    output_path: str,
    root_dir: str,
    *,
    min_interval_s: float = 1.5,
    force: bool = False,
):
    now = time.time()
    last = float(progress_cache_last_save.get(scope, 0.0))
    if force or (now - last) >= max(0.0, float(min_interval_s)):
        save_scope_progress(
            scope,
            signature,
            state,
            progress_cache_last_save,
            output_path,
            root_dir,
        )


def clear_scope_progress(
    scope: str,
    progress_cache_last_save: Dict[str, float],
    output_path: str,
    root_dir: str,
):
    f = scope_cache_file(scope, output_path, root_dir)
    if f.exists():
        f.unlink()
    progress_cache_last_save.pop(scope, None)
    if scope == "leakage":
        d = scope_cache_dir(output_path, root_dir) / "leakage_monthly"
        if d.exists():
            try:
                for p in d.glob("*.npy"):
                    p.unlink()
            except Exception:
                pass
