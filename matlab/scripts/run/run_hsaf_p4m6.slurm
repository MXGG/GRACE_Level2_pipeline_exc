#!/bin/bash
#SBATCH --job-name=grace_hsaf_p4m6
#SBATCH --partition=cpu-pgmf
#SBATCH --qos=pgmf
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --time=04:00:00
#SBATCH --output=/home/um202370130/GRACE_Level2_pipeline/output/logs/grace_%j.out
#SBATCH --error=/home/um202370130/GRACE_Level2_pipeline/output/logs/grace_%j.err

set -euo pipefail

ROOT="/home/um202370130/GRACE_Level2_pipeline"
cd "$ROOT" || exit 1

mkdir -p "$ROOT/output/logs"
RUN_DIR="$ROOT/output/runs/$SLURM_JOB_ID"
mkdir -p "$RUN_DIR"

echo "=========================================="
echo "GRACE pipeline - SLURM Job Started"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $SLURM_NODELIST"
echo "Start time: $(date)"
echo "Workdir: $(pwd)"
echo "CPUs: 32"
echo "=========================================="

source /etc/profile.d/modules.sh
module load app/matlab/2023a

export MATLAB_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1

/opt/app/MATLAB_2023a/bin/matlab -nodisplay -nodesktop -nosplash -r "try; addpath(fullfile('$ROOT','cfg')); addpath(genpath(fullfile('$ROOT','src'))); addpath(fullfile('$ROOT','src','tools')); addpath(genpath(fullfile('$ROOT','src','tools')),'-end'); cfg=cfg_load(fullfile('$ROOT','cfg','user_hsaf_p4m6.json'), fullfile('$ROOT','cfg','default.json')); setup_env(cfg); run_pipeline(cfg); catch ME; disp(getReport(ME,'extended')); exit(1); end; exit(0);"

