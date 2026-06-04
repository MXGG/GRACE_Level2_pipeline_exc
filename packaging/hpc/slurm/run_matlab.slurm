#!/bin/bash
#SBATCH --job-name=grace_matlab
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=52
#SBATCH --time=04:00:00
#SBATCH --output=outputs/logs/grace_%j.out
#SBATCH --error=outputs/logs/grace_%j.err

set -euo pipefail

ROOT="${GRACE_REMOTE_ROOT:-$(pwd)}"
cd "$ROOT" || exit 1

OUTPUT_ROOT="${GRACE_OUTPUT_ROOT:-$ROOT/outputs}"
mkdir -p "$OUTPUT_ROOT/logs" "$OUTPUT_ROOT/remote/${SLURM_JOB_ID:-manual}"

echo "=========================================="
echo "GRACE pipeline (MATLAB) - SLURM Job Started"
echo "Job ID: ${SLURM_JOB_ID:-manual}"
echo "Node: ${SLURM_NODELIST:-local}"
echo "Start time: $(date)"
echo "Workdir: $(pwd)"
echo "CPUs: ${SLURM_CPUS_PER_TASK:-52}"
echo "=========================================="

if [ -f /etc/profile.d/modules.sh ]; then
  # shellcheck disable=SC1091
  source /etc/profile.d/modules.sh
fi

if [ -n "${GRACE_MATLAB_MODULE:-}" ]; then
  module load "$GRACE_MATLAB_MODULE"
fi

export MATLAB_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1

USER_CONFIG="${GRACE_USER_CONFIG:-configs/hpc.example.json}"
DEFAULT_CONFIG="${GRACE_DEFAULT_CONFIG:-configs/default.json}"
MATLAB_EXEC="${GRACE_MATLAB_BIN:-matlab}"

echo "Runtime: matlab"
echo "MATLAB: $MATLAB_EXEC"
echo "User config: $USER_CONFIG"
echo "Default config: $DEFAULT_CONFIG"
echo "Output root: $OUTPUT_ROOT"

"$MATLAB_EXEC" -batch "try; setenv('GRACE_USER_CONFIG','$USER_CONFIG'); setenv('GRACE_DEFAULT_CONFIG','$DEFAULT_CONFIG'); setenv('GRACE_L2_OUTPUT','$OUTPUT_ROOT'); run('matlab/src/main/run_oneclick.m'); catch ME; disp(getReport(ME,'extended')); exit(1); end; exit(0);"
