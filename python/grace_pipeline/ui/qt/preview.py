"""Preview data loading and rendering helpers for the Qt shell."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from grace_pipeline.infra.stack.loader import load_stack_any


@dataclass
class PreviewSnapshot:
    """Loaded stack payload for preview/plot rendering."""

    path: str = ""
    ewh: Any = None
    lon: Any = None
    lat: Any = None
    t: Any = None
    meta: dict[str, Any] = None
    active_var: str = ""
    index: int = 0


class PreviewDataLoader:
    """Load stack data for the preview page."""

    def load(self, path: str, *, active_var: Optional[str] = None) -> PreviewSnapshot:
        ewh, lon, lat, t, meta = load_stack_any(path, active_var=active_var)
        if ewh is None or lon is None or lat is None:
            raise ValueError("Preview source does not contain a valid grid.")
        if np.asarray(ewh).ndim == 2:
            ewh = np.asarray(ewh)[:, :, None]
        meta = dict(meta or {})
        return PreviewSnapshot(
            path=str(path or ""),
            ewh=np.asarray(ewh),
            lon=np.asarray(lon).squeeze(),
            lat=np.asarray(lat).squeeze(),
            t=t,
            meta=meta,
            active_var=str(meta.get("active_var") or active_var or ""),
            index=0,
        )

    def summarize(self, snapshot: PreviewSnapshot) -> dict[str, Any]:
        ewh = np.asarray(snapshot.ewh)
        finite = np.isfinite(ewh)
        min_val = float(np.nanmin(ewh[finite])) if finite.any() else float("nan")
        max_val = float(np.nanmax(ewh[finite])) if finite.any() else float("nan")
        shape = tuple(int(v) for v in ewh.shape)
        return {
            "shape": shape,
            "active_var": snapshot.active_var or "ewh",
            "index": snapshot.index,
            "min": min_val,
            "max": max_val,
        }

    def select_index(self, snapshot: PreviewSnapshot, index: int) -> PreviewSnapshot:
        snapshot.index = max(0, min(int(index), max(0, int(np.asarray(snapshot.ewh).shape[2]) - 1)))
        return snapshot
