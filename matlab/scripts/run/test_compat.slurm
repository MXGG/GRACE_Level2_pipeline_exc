#!/bin/bash
#SBATCH --job-name=grace_compat
#SBATCH --partition=cpu-pgmf
#SBATCH --qos=pgmf
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --time=00:10:00
#SBATCH --output=/home/um202370130/GRACE_Level2_pipeline/output/logs/compat_%j.out
#SBATCH --error=/home/um202370130/GRACE_Level2_pipeline/output/logs/compat_%j.err

set -euo pipefail

ROOT="/home/um202370130/GRACE_Level2_pipeline"
cd "$ROOT" || exit 1

mkdir -p "$ROOT/output/logs"
RUN_DIR="$ROOT/output/runs/$SLURM_JOB_ID"
mkdir -p "$RUN_DIR"

echo "=========================================="
echo "GRACE compatibility check - SLURM Job"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $SLURM_NODELIST"
echo "Start time: $(date)"
echo "Workdir: $(pwd)"
echo "=========================================="

source /etc/profile.d/modules.sh
module load app/matlab/2023a

export MATLAB_NUM_THREADS=2
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2

/opt/app/MATLAB_2023a/bin/matlab -batch "addpath(genpath(fullfile(pwd,'src'))); test_compatibility"

