#!/bin/bash
#SBATCH --job-name=grace_matlab
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=52
#SBATCH --time=04:00:00
#SBATCH --output=outputs/logs/grace_%j.out
#SBATCH --error=outputs/logs/grace_%j.err

# Compatibility wrapper. Prefer packaging/hpc/slurm/run_matlab.slurm.
set -euo pipefail
ROOT="${GRACE_REMOTE_ROOT:-$(pwd)}"
exec bash "$ROOT/packaging/hpc/slurm/run_matlab.slurm"
