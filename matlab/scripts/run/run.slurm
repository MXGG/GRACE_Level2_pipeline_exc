#!/bin/bash
# Compatibility wrapper. Prefer packaging/hpc/slurm/run_matlab.slurm.
set -euo pipefail
ROOT="${GRACE_REMOTE_ROOT:-$(pwd)}"
exec bash "$ROOT/packaging/hpc/slurm/run_matlab.slurm"
