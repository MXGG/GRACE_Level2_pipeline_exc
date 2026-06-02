#!/bin/bash
#SBATCH --job-name=plot_gia
#SBATCH --partition=cpu-pgmf
#SBATCH --qos=pgmf
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --time=00:15:00
#SBATCH --output=/home/um202370130/GRACE_Level2_pipeline/output/logs/plot_gia_%j.out
#SBATCH --error=/home/um202370130/GRACE_Level2_pipeline/output/logs/plot_gia_%j.err

set -euo pipefail
cd /home/um202370130/GRACE_Level2_pipeline
source /etc/profile.d/modules.sh
module load app/matlab/2023a
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export MATLAB_NUM_THREADS=1
/opt/app/MATLAB_2023a/bin/matlab -batch "cd('/home/um202370130/GRACE_Level2_pipeline'); addpath('cfg'); addpath(genpath('src')); run('tmp_plot_gia_diff_map.m');"

