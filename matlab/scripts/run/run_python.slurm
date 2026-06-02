#!/bin/bash
#SBATCH --job-name=grace_py
#SBATCH --partition=cpu-pgmf
#SBATCH --qos=pgmf
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=52
#SBATCH --time=04:00:00
#SBATCH --output=/home/um202370130/GRACE_Level2_pipeline/output/logs/grace_%j.out
#SBATCH --error=/home/um202370130/GRACE_Level2_pipeline/output/logs/grace_%j.err

set -euo pipefail

ROOT="/home/um202370130/GRACE_Level2_pipeline"
cd "$ROOT" || exit 1

mkdir -p "$ROOT/output/logs"
RUN_DIR="$ROOT/output/remote/$SLURM_JOB_ID"
mkdir -p "$RUN_DIR"

echo "=========================================="
echo "GRACE pipeline (Python) - SLURM Job Started"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $SLURM_NODELIST"
echo "Start time: $(date)"
echo "Workdir: $(pwd)"
echo "CPUs: ${SLURM_CPUS_PER_TASK:-52}"
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

USER_CONFIG="${GRACE_USER_CONFIG:-$ROOT/matlab/cfg/user.json}"
DEFAULT_CONFIG="${GRACE_DEFAULT_CONFIG:-$ROOT/matlab/cfg/default.json}"
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

"$PYTHON_EXEC" -m grace_pipeline.cli run \
  -c "$USER_CONFIG" \
  -d "$DEFAULT_CONFIG" \
  -j "${SLURM_CPUS_PER_TASK:-52}" \
  -v
