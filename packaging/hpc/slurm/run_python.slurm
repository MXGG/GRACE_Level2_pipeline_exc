#!/bin/bash
#SBATCH --job-name=grace_py
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --time=04:00:00
#SBATCH --output=outputs/logs/grace_%j.out
#SBATCH --error=outputs/logs/grace_%j.err

set -euo pipefail

ROOT="${GRACE_REMOTE_ROOT:-$(pwd)}"
cd "$ROOT" || exit 1

OUTPUT_ROOT="${GRACE_OUTPUT_ROOT:-$ROOT/outputs}"
mkdir -p "$OUTPUT_ROOT/logs" "$OUTPUT_ROOT/remote"
RUN_DIR="$OUTPUT_ROOT/remote/${SLURM_JOB_ID:-manual}"
mkdir -p "$RUN_DIR"

echo "=========================================="
echo "GRACE pipeline (Python) - SLURM Job Started"
echo "Job ID: ${SLURM_JOB_ID:-manual}"
echo "Node: ${SLURM_NODELIST:-local}"
echo "Start time: $(date)"
echo "Workdir: $(pwd)"
echo "CPUs: ${SLURM_CPUS_PER_TASK:-4}"
echo "=========================================="

if [ -f /etc/profile.d/modules.sh ]; then
  # shellcheck disable=SC1091
  source /etc/profile.d/modules.sh
fi

export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OMP_NUM_THREADS=1
export NUMEXPR_MAX_THREADS=1
export PYTHONUNBUFFERED=1

USER_CONFIG="${GRACE_USER_CONFIG:-configs/hpc.example.json}"
DEFAULT_CONFIG="${GRACE_DEFAULT_CONFIG:-configs/default.json}"
PYTHON_EXEC="${GRACE_PYTHON_BIN:-python3}"

if [ -x "$ROOT/python/.venv-hpc/bin/python" ]; then
  PYTHON_EXEC="$ROOT/python/.venv-hpc/bin/python"
elif [ -x "$ROOT/python/.venv/bin/python" ]; then
  PYTHON_EXEC="$ROOT/python/.venv/bin/python"
fi

export PYTHONPATH="$ROOT/python${PYTHONPATH:+:$PYTHONPATH}"

echo "Runtime: python"
echo "Python: $PYTHON_EXEC"
echo "User config: $USER_CONFIG"
echo "Default config: $DEFAULT_CONFIG"
echo "Output root: $OUTPUT_ROOT"

"$PYTHON_EXEC" -m grace_pipeline.infra.doctor -c "$USER_CONFIG" -d "$DEFAULT_CONFIG"
"$PYTHON_EXEC" -m grace_pipeline.entrypoints run \
  -c "$USER_CONFIG" \
  -d "$DEFAULT_CONFIG" \
  -o "$OUTPUT_ROOT" \
  -j "${SLURM_CPUS_PER_TASK:-4}" \
  -v
