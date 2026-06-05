"""Platform-aware runtime resource detection.

The pipeline can run on a desktop, a frozen Windows installer, or a SLURM/HPC
job. This module centralizes CPU worker detection so CLI and GUI callers do not
mistakenly use the full physical node when only a smaller allocation is granted.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class RuntimeContext:
    platform: str
    frozen: bool
    slurm_job_id: str
    slurm_cpus_per_task: int | None
    slurm_cpus_on_node: int | None
    slurm_ntasks: int | None
    affinity_cpus: int | None
    logical_cpus: int
    available_cpus: int

    @property
    def is_slurm(self) -> bool:
        return bool(self.slurm_job_id)

    def to_dict(self) -> dict:
        return asdict(self)


def _int_env(name: str) -> int | None:
    value = os.environ.get(name)
    if value is None or str(value).strip() == "":
        return None
    try:
        parsed = int(str(value).split(",")[0].strip())
        return parsed if parsed > 0 else None
    except Exception:
        return None


def _affinity_count() -> int | None:
    getter = getattr(os, "sched_getaffinity", None)
    if getter is None:
        return None
    try:
        return max(1, len(getter(0)))
    except Exception:
        return None


def detect_runtime_context() -> RuntimeContext:
    logical = max(1, int(os.cpu_count() or 1))
    slurm_cpt = _int_env("SLURM_CPUS_PER_TASK")
    slurm_node = _int_env("SLURM_CPUS_ON_NODE")
    slurm_ntasks = _int_env("SLURM_NTASKS")
    affinity = _affinity_count()

    candidates = [logical]
    if affinity:
        candidates.append(affinity)
    if slurm_cpt:
        candidates.append(slurm_cpt)
    elif slurm_node:
        candidates.append(slurm_node)

    return RuntimeContext(
        platform=sys.platform,
        frozen=bool(getattr(sys, "frozen", False)),
        slurm_job_id=os.environ.get("SLURM_JOB_ID", ""),
        slurm_cpus_per_task=slurm_cpt,
        slurm_cpus_on_node=slurm_node,
        slurm_ntasks=slurm_ntasks,
        affinity_cpus=affinity,
        logical_cpus=logical,
        available_cpus=max(1, min(candidates)),
    )


def recommend_workers(
    configured_workers: int | str | None = None,
    *,
    task_type: str = "pipeline",
    gui: bool = False,
    frozen_max_workers: int | None = None,
) -> int:
    """Return a conservative worker count for the current execution context."""
    ctx = detect_runtime_context()
    available = max(1, ctx.available_cpus)

    if configured_workers is None or str(configured_workers).strip().lower() in {"", "auto"}:
        configured = available
    else:
        try:
            configured = max(1, int(configured_workers))
        except Exception:
            configured = available

    cap = available
    if ctx.is_slurm:
        cap = available
    elif ctx.frozen:
        cap = max(1, int(frozen_max_workers or 0) or min(available, 8))
    elif gui:
        cap = min(available, 8)
    elif os.name == "nt" and task_type.lower() in {"hsaf", "hsaf_stack", "stack"}:
        cap = min(available, 12)

    return max(1, min(configured, cap))


__all__ = ["RuntimeContext", "detect_runtime_context", "recommend_workers"]
