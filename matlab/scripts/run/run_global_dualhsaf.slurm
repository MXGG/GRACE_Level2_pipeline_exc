#!/bin/bash
#SBATCH --job-name=grace_global_dualhsaf
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
cd "$ROOT"

source /etc/profile.d/modules.sh
module load app/matlab/2023a

export MATLAB_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1

cat > /tmp/grace_cfg_raw.json <<JSON
{
  "__template": "HPC full filters + basin + leakage FM (HSAF global, single-pass, RAW input)",
  "path": {
    "GFC": "/home/um202370130/GRACE_Level2_pipeline/data/GRACE/GSM",
    "OUTPUT": "/home/um202370130/GRACE_Level2_pipeline/output",
    "AUX": "/home/um202370130/GRACE_Level2_pipeline/data/Aux",
    "DDK": "/home/um202370130/GRACE_Level2_pipeline/data/Aux/DDK",
    "BOUNDARY": "/home/um202370130/GRACE_Level2_pipeline/data/Boundary/boundary_cache"
  },
  "time": { "auto_detect_gfc": true },
  "reference": {
    "mascon_dir": "/home/um202370130/GRACE_Level2_pipeline/data/Reference/Mascon",
    "mascon_pattern": "Mascon_{YYYYMM}.nc",
    "allow_nearest_month": true,
    "nearest_month_tolerance_days": 45
  },
  "gldas": { "dir": "" },
  "io": {
    "return_stacks": false,
    "return_metrics": false,
    "return_basin": true,
    "resume": false
  },
  "metrics": { "enable": false },
  "parallel": { "enable": true, "nWorkers": 52 },
  "filter": {
    "pre_hankel_input": "RAW",
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
  "basin": {
    "analysis_enable": true,
    "boundary_file": "/home/um202370130/GRACE_Level2_pipeline/data/Boundary/boundary_cache/LargeBasin.shp",
    "name": "LargeBasin"
  },
  "leakage": {
    "enable": true,
    "method": "FM",
    "apply_to": ["RAW","P4M6","GAUSS","FAN","P4M6_GAUSS","P4M6_FAN","DDK","HSAF"],
    "Lmax": 60,
    "grid_interval": 1,
    "FM": { "nIter": 2 }
  },
  "inversion": {
    "Lmax": 60,
    "remove_mean": true,
    "lowdeg": {
      "enable": true,
      "replace_C20": true,
      "replace_C10": true,
      "replace_S20": false,
      "files": {
        "C20": "/home/um202370130/GRACE_Level2_pipeline/data/GRACE/LowDegree/TN-14_C30_C20_GSFC_SLR.txt",
        "DEGREE1": "/home/um202370130/GRACE_Level2_pipeline/data/GRACE/LowDegree/TN-13_GEOC_CSR_RL06.txt"
      }
    },
    "gia": {
      "enable": true,
      "file": "/home/um202370130/GRACE_Level2_pipeline/data/GRACE/GIA/GIA_Stokes_ICE-6G_D.txt",
      "Lmax": 60
    }
  }
}
JSON

cat > /tmp/grace_cfg_p4m6.json <<JSON
{
  "__template": "HPC full filters + basin + leakage FM (HSAF global, single-pass, P4M6 input)",
  "path": {
    "GFC": "/home/um202370130/GRACE_Level2_pipeline/data/GRACE/GSM",
    "OUTPUT": "/home/um202370130/GRACE_Level2_pipeline/output",
    "AUX": "/home/um202370130/GRACE_Level2_pipeline/data/Aux",
    "DDK": "/home/um202370130/GRACE_Level2_pipeline/data/Aux/DDK",
    "BOUNDARY": "/home/um202370130/GRACE_Level2_pipeline/data/Boundary/boundary_cache"
  },
  "time": { "auto_detect_gfc": true },
  "reference": {
    "mascon_dir": "/home/um202370130/GRACE_Level2_pipeline/data/Reference/Mascon",
    "mascon_pattern": "Mascon_{YYYYMM}.nc",
    "allow_nearest_month": true,
    "nearest_month_tolerance_days": 45
  },
  "gldas": { "dir": "" },
  "io": {
    "return_stacks": false,
    "return_metrics": false,
    "return_basin": true,
    "resume": false
  },
  "metrics": { "enable": false },
  "parallel": { "enable": true, "nWorkers": 52 },
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
  "basin": {
    "analysis_enable": true,
    "boundary_file": "/home/um202370130/GRACE_Level2_pipeline/data/Boundary/boundary_cache/LargeBasin.shp",
    "name": "LargeBasin"
  },
  "leakage": {
    "enable": true,
    "method": "FM",
    "apply_to": ["RAW","P4M6","GAUSS","FAN","P4M6_GAUSS","P4M6_FAN","DDK","HSAF"],
    "Lmax": 60,
    "grid_interval": 1,
    "FM": { "nIter": 2 }
  },
  "inversion": {
    "Lmax": 60,
    "remove_mean": true,
    "lowdeg": {
      "enable": true,
      "replace_C20": true,
      "replace_C10": true,
      "replace_S20": false,
      "files": {
        "C20": "/home/um202370130/GRACE_Level2_pipeline/data/GRACE/LowDegree/TN-14_C30_C20_GSFC_SLR.txt",
        "DEGREE1": "/home/um202370130/GRACE_Level2_pipeline/data/GRACE/LowDegree/TN-13_GEOC_CSR_RL06.txt"
      }
    },
    "gia": {
      "enable": true,
      "file": "/home/um202370130/GRACE_Level2_pipeline/data/GRACE/GIA/GIA_Stokes_ICE-6G_D.txt",
      "Lmax": 60
    }
  }
}
JSON

export GRACE_CFG=/tmp/grace_cfg_raw.json
/opt/app/MATLAB_2023a/bin/matlab -nodisplay -nodesktop -nosplash -r "try; run('src/main/run_oneclick_cfg.m'); catch ME; disp(getReport(ME,'extended')); exit(1); end; exit(0);"

# stash RAW HSAF outputs so the next run (P4M6) does not overwrite
if [ -d "$ROOT/output/monthly_mat/HSAF" ]; then
  mv "$ROOT/output/monthly_mat/HSAF" "$ROOT/output/monthly_mat/HSAF_RAW"
fi
if [ -d "$ROOT/output/monthly_txt/HSAF" ]; then
  mv "$ROOT/output/monthly_txt/HSAF" "$ROOT/output/monthly_txt/HSAF_RAW"
fi
if [ -d "$ROOT/output/stacks" ]; then
  for f in "$ROOT"/output/stacks/*HSAF*; do
    [ -f "$f" ] && mv "$f" "${f%.*}_RAW.${f##*.}"
  done
fi
if [ -d "$ROOT/output/plots" ]; then
  for f in "$ROOT/output/plots/*HSAF*.png"; do
    [ -f "$f" ] && mv "$f" "${f%.png}_RAW.png"
  done
fi

export GRACE_CFG=/tmp/grace_cfg_p4m6.json
/opt/app/MATLAB_2023a/bin/matlab -nodisplay -nodesktop -nosplash -r "try; run('src/main/run_oneclick_cfg.m'); catch ME; disp(getReport(ME,'extended')); exit(1); end; exit(0);"



