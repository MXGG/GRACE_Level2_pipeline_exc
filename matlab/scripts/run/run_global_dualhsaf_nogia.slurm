#!/bin/bash
#SBATCH --job-name=grace_global_dualhsaf
#SBATCH --partition=cpu-pgmf
#SBATCH --qos=pgmf
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=0
#SBATCH --exclusive
#SBATCH --time=06:00:00
#SBATCH --output=/home/um202370130/GRACE_Level2_pipeline/output/logs/grace_%j.out
#SBATCH --error=/home/um202370130/GRACE_Level2_pipeline/output/logs/grace_%j.err

# Compatibility wrapper:
# This scenario is currently identical to run_global_dualhsaf_gia.slurm.
# Keep this filename for existing automation while delegating to the canonical script.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/run_global_dualhsaf_gia.slurm" "$@"

