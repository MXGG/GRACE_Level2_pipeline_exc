"""Runtime helpers shared by CLI and pipeline."""

import os


def limit_blas_threads() -> None:
    """Reduce thread oversubscription and memory spikes in frozen/GUI usage."""
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("NUMEXPR_MAX_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
