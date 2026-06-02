#!/bin/bash
#SBATCH --job-name=grace_run
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
echo "GRACE pipeline - SLURM Job Started"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $SLURM_NODELIST"
echo "Start time: $(date)"
echo "Workdir: $(pwd)"
echo "CPUs: 52"
echo "=========================================="

# Initialize environment modules for non-login shells.
source /etc/profile.d/modules.sh

# Load MATLAB (update the module name if your cluster differs).
module load app/matlab/2023a

# MEMORY OPTIMIZATION: Limit MATLAB parallel threads to avoid oversubscription
export MATLAB_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1

# MEMORY OPTIMIZATION: Set MATLAB heap memory limit (optional, adjust as needed)
# export MATLAB_JAVA="-Xmx4g"

# Run entrypoint.
/opt/app/MATLAB_2023a/bin/matlab -nodisplay -nodesktop -nosplash -r "try; run('matlab/src/main/run_oneclick.m'); catch ME; disp(getReport(ME,'extended')); exit(1); end; exit(0);"

