#!/bin/bash
#SBATCH --job-name=grace_py
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --time=04:00:00
#SBATCH --output=outputs/logs/grace_%j.out
#SBATCH --error=outputs/logs/grace_%j.err

# Compatibility wrapper. Prefer packaging/hpc/slurm/run_python.slurm.
set -euo pipefail
ROOT="${GRACE_REMOTE_ROOT:-$(pwd)}"
exec bash "$ROOT/packaging/hpc/slurm/run_python.slurm"
