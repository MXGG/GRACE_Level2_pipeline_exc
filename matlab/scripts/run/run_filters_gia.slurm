#!/bin/bash
#SBATCH --job-name=grace_filters_gia
#SBATCH --partition=cpu-pgmf
#SBATCH --qos=pgmf
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=36
#SBATCH --mem=0
#SBATCH --exclusive
#SBATCH --time=04:00:00
#SBATCH --output=/home/um202370130/GRACE_Level2_pipeline/output/logs/grace_%j.out
#SBATCH --error=/home/um202370130/GRACE_Level2_pipeline/output/logs/grace_%j.err

set -euo pipefail
ROOT="/home/um202370130/GRACE_Level2_pipeline"
cd "$ROOT"
source /etc/profile.d/modules.sh
module load app/matlab/2023a
export MATLAB_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
cat > /tmp/grace_cfg_gia.json <<"JSON"
{
  "path": {
    "GFC": "${ROOT}/data/GRACE/GSM",
    "OUTPUT": "${ROOT}/output",
    "AUX": "${ROOT}/data/Aux",
    "DDK": "${ROOT}/data/Aux/DDK",
    "BOUNDARY": "${ROOT}/data/Boundary/boundary_cache"
  },
  "time": { "auto_detect_gfc": true },
  "io": {
    "save_monthly_mat": true,
    "save_stack_mat": false,
    "export_txt": false,
    "return_stacks": false,
    "return_metrics": false,
    "return_basin": false,
    "resume": false
  },
  "metrics": { "enable": false },
  "parallel": { "enable": true, "nWorkers": 36 },
  "filter": {
    "pre_hankel_input": "P4M6",
    "gaussian": { "enable": true },
    "p4m6": { "enable": true },
    "fan": { "enable": true },
    "ddk": { "enable": true, "type": "DDK4" },
    "hankel": {
      "stack_mode": true,
      "variant": "global",
      "Ts": 1,
      "params": { "N": 30, "P": 10, "K": 6, "J": 1, "iterations": 1 }
    }
  },
  "basin": { "analysis_enable": false },
  "leakage": { "enable": false },
  "inversion": {
    "Lmax": 60,
    "remove_mean": true,
    "lowdeg": {
      "enable": true,
      "replace_C20": true,
      "replace_C10": true,
      "files": {
        "C20": "${ROOT}/data/GRACE/LowDegree/TN-14_C30_C20_GSFC_SLR.txt",
        "DEGREE1": "${ROOT}/data/GRACE/LowDegree/TN-13_GEOC_CSR_RL06.txt"
      }
    },
    "gia": {
      "enable": true,
      "file": "${ROOT}/data/GRACE/GIA/GIA_Stokes_ICE-6G_D.txt",
      "Lmax": 60
    }
  }
}
JSON
export GRACE_CFG=/tmp/grace_cfg_gia.json
/opt/app/MATLAB_2023a/bin/matlab -nodisplay -nodesktop -nosplash -r "try; run('src/main/run_oneclick_cfg.m'); catch ME; disp(getReport(ME,'extended')); exit(1); end; exit(0);"



