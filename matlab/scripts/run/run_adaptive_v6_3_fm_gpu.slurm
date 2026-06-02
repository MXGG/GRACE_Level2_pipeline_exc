#!/bin/bash
#SBATCH --job-name=grace_adapt_v6
#SBATCH --partition=gpu-pgmf
#SBATCH --qos=gpu-pgmf
#SBATCH --gres=gpu:1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --time=05:00:00
#SBATCH --output=/home/um202370130/GRACE_Level2_pipeline/output/logs/grace_%j.out
#SBATCH --error=/home/um202370130/GRACE_Level2_pipeline/output/logs/grace_%j.err

set -euo pipefail

ROOT="/home/um202370130/GRACE_Level2_pipeline"
cd "$ROOT" || exit 1

mkdir -p "$ROOT/output/logs"
RUN_DIR="$ROOT/output/remote/$SLURM_JOB_ID"
mkdir -p "$RUN_DIR"

export GRACE_CFG="cfg/user_run_adaptive_v6_3_fm.json"

echo "=========================================="
echo "GRACE pipeline - SLURM Job Started"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $SLURM_NODELIST"
echo "Start time: $(date)"
echo "Workdir: $(pwd)"
echo "CPUs: 32"
echo "GPU: 1"
echo "Config: $GRACE_CFG"
echo "=========================================="

source /etc/profile.d/modules.sh
module load app/matlab/2023a

export MATLAB_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1

/opt/app/MATLAB_2023a/bin/matlab -nodisplay -nodesktop -nosplash -r "try; run('src/main/run_oneclick_cfg.m'); catch ME; disp(getReport(ME,'extended')); exit(1); end; exit(0);"

