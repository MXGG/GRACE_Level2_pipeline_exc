#!/bin/bash
#SBATCH --job-name=grace_run_nogia
#SBATCH --partition=cpu-pgmf
#SBATCH --qos=pgmf
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=52
#SBATCH --time=04:00:00
#SBATCH --output=/home/um202370130/GRACE_Level2_pipeline/output/logs/grace_nogia_%j.out
#SBATCH --error=/home/um202370130/GRACE_Level2_pipeline/output/logs/grace_nogia_%j.err

set -euo pipefail
ROOT="/home/um202370130/GRACE_Level2_pipeline"
cd "$ROOT" || exit 1

mkdir -p "$ROOT/output/logs"
RUN_DIR="$ROOT/output/remote/$SLURM_JOB_ID"
mkdir -p "$RUN_DIR"

echo "=========================================="
echo "GRACE pipeline - SLURM Job Started (NO GIA)"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $SLURM_NODELIST"
echo "Start time: $(date)"
echo "Workdir: $(pwd)"
echo "CPUs: 52"
echo "=========================================="

source /etc/profile.d/modules.sh
module load app/matlab/2023a

export MATLAB_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1

/opt/app/MATLAB_2023a/bin/matlab -nodisplay -nodesktop -nosplash -r "try; addpath(genpath('src')); run_oneclick_cfg('cfg/user_nogia.json'); catch ME; disp(getReport(ME,'extended')); exit(1); end; exit(0);"
