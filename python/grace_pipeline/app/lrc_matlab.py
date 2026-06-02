"""MATLAB-backed leakage-correction helpers (non-UI)."""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np


def ensure_sf_wrapper(out_dir: Path) -> Path:
    wrapper = out_dir / "lrc_sf_wrapper.m"
    if wrapper.exists():
        return wrapper
    content = (
        "% Auto-generated SF wrapper\n"
        "input = getenv('LRC_SF_INPUT');\n"
        "output = getenv('LRC_SF_OUTPUT');\n"
        "method = getenv('LRC_SF_METHOD');\n"
        "if isempty(method), method = 'Gaussian'; end\n"
        "toolbox = getenv('LRC_SF_TOOLBOX');\n"
        "if ~isempty(toolbox)\n"
        "    addpath(genpath(toolbox));\n"
        "end\n"
        "load(input);\n"
        "if exist('grid_template','var')\n"
        "    mask = grid_template;\n"
        "end\n"
        "grid_interval = str2double(getenv('LRC_SF_GRID_INT')); if isnan(grid_interval), grid_interval=0.5; end\n"
        "Lmax = str2double(getenv('LRC_SF_LMAX')); if isnan(Lmax), Lmax=60; end\n"
        "radius_gaussian = str2double(getenv('LRC_SF_GAUSS_R')); if isnan(radius_gaussian), radius_gaussian=300; end\n"
        "radius_fan_l = str2double(getenv('LRC_SF_FAN_R1')); if isnan(radius_fan_l), radius_fan_l=300; end\n"
        "radius_fan_m = str2double(getenv('LRC_SF_FAN_R2')); if isnan(radius_fan_m), radius_fan_m=300; end\n"
        "ddk_type = getenv('LRC_SF_DDK'); if isempty(ddk_type), ddk_type='DDK4'; end\n"
        "p4_deg = str2double(getenv('LRC_SF_P4_DEG')); if isnan(p4_deg), p4_deg=4; end\n"
        "p4_m = str2double(getenv('LRC_SF_P4_M')); if isnan(p4_m), p4_m=6; end\n"
        "destrip = sprintf('CHENP%dM%d', p4_deg, p4_m);\n"
        "hsa_window = str2double(getenv('LRC_SF_HSA_WINDOW')); if isnan(hsa_window), hsa_window=60; end\n"
        "hsa_p = str2double(getenv('LRC_SF_HSA_P')); if isnan(hsa_p), hsa_p=20; end\n"
        "hsa_order = str2double(getenv('LRC_SF_HSA_ORDER')); if isnan(hsa_order), hsa_order=6; end\n"
        "hsa_buffer = str2double(getenv('LRC_SF_HSA_BUFFER')); if isnan(hsa_buffer), hsa_buffer=10; end\n"
        "hsa_ts = str2double(getenv('LRC_SF_HSA_TS')); if isnan(hsa_ts), hsa_ts=1; end\n"
        "grid_template = double(mask);\n"
        "cs = gmt_grid2cs(grid_template', Lmax);\n"
        "switch upper(method)\n"
        "    case 'GAUSSIAN'\n"
        "        cs_filtered = gmt_gaussian_filter(cs, radius_gaussian);\n"
        "        grid_filtered = gmt_cs2grid(cs_filtered, 0, grid_interval, 'NONE')';\n"
        "    case 'FAN'\n"
        "        cs_filtered = gmt_fan_filter(cs, radius_fan_l, radius_fan_m);\n"
        "        grid_filtered = gmt_cs2grid(cs_filtered, 0, grid_interval, 'NONE')';\n"
        "    case 'GAUSSIAN_DECORRELATION'\n"
        "        cs_destrip = gmt_destriping(cs, destrip);\n"
        "        cs_filtered = gmt_gaussian_filter(cs_destrip, radius_gaussian);\n"
        "        grid_filtered = gmt_cs2grid(cs_filtered, 0, grid_interval, 'NONE')';\n"
        "    case 'FAN_DECORRELATION'\n"
        "        cs_destrip = gmt_destriping(cs, destrip);\n"
        "        cs_filtered = gmt_fan_filter(cs_destrip, radius_fan_l, radius_fan_m);\n"
        "        grid_filtered = gmt_cs2grid(cs_filtered, 0, grid_interval, 'NONE')';\n"
        "    case 'DDK4'\n"
        "        grid_filtered = DDKs_Filter(grid_template, ddk_type, grid_interval);\n"
        "    case 'HANKEL'\n"
        "        grid_dc = gmt_cs2grid(cs, 0, grid_interval, destrip)';\n"
        "        Hankel_Mode = HSA(grid_dc, hsa_ts, hsa_window, hsa_p, hsa_order, hsa_buffer);\n"
        "        grid_filtered = grid_dc - (sum(Hankel_Mode(:,:,1:6),3) - sum(Hankel_Mode(:,:,3:4),3));\n"
        "    otherwise\n"
        "        grid_filtered = grid_template;\n"
        "end\n"
        "filtered_mean = mean(grid_filtered(mask>0), 'omitnan');\n"
        "sf = 1.0 / filtered_mean;\n"
        "save(output, 'sf', 'filtered_mean');\n"
    )
    wrapper.write_text(content, encoding="utf-8")
    return wrapper


def compute_sf_via_matlab(
    boundary_path,
    grid_interval=0.5,
    *,
    output_dir,
    matlab="matlab",
    sf_method="GAUSSIAN",
    sf_gauss=300.0,
    sf_fan_r1=300.0,
    sf_fan_r2=300.0,
    sf_ddk="DDK4",
    sf_p4_deg=4,
    sf_p4_m=6,
    sf_hsa_window=60,
    sf_hsa_p=20,
    sf_hsa_order=6,
    sf_hsa_buffer=10,
    sf_hsa_ts=1,
    sf_toolbox="",
    sf_target_grid_cb=None,
):
    if not boundary_path:
        raise ValueError("Boundary file required for SF auto-compute.")
    if sf_target_grid_cb is None:
        raise ValueError("sf_target_grid_cb is required.")
    try:
        from grace_pipeline.basin import read_boundary, make_mask
    except Exception as e:
        raise RuntimeError(f"Boundary tools unavailable: {e}")

    lon_t, lat_t = sf_target_grid_cb(grid_interval=grid_interval)
    basins = read_boundary(boundary_path)
    if not basins:
        raise ValueError("No basins found in boundary file.")
    mask = np.zeros((lon_t.size, lat_t.size), dtype=bool)
    for b in basins:
        try:
            mask |= make_mask(b, lon_t, lat_t)
        except Exception:
            continue
    if not np.any(mask):
        raise ValueError("Boundary mask is empty.")

    tmp_dir = Path(output_dir) / "local" / f"lrc_sf_tmp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    mat_in = tmp_dir / "sf_mask.mat"
    mat_out = tmp_dir / "sf_out.mat"
    try:
        import scipy.io as sio

        sio.savemat(mat_in, {"grid_template": mask.astype(float)})
    except Exception as e:
        raise RuntimeError(f"Failed to save mask: {e}")

    wrapper = ensure_sf_wrapper(tmp_dir)
    env = os.environ.copy()
    env["LRC_SF_INPUT"] = str(mat_in)
    env["LRC_SF_OUTPUT"] = str(mat_out)
    env["LRC_SF_METHOD"] = str(sf_method).upper()
    env["LRC_SF_GRID_INT"] = str(float(grid_interval))
    env["LRC_SF_GAUSS_R"] = str(float(sf_gauss))
    env["LRC_SF_FAN_R1"] = str(float(sf_fan_r1))
    env["LRC_SF_FAN_R2"] = str(float(sf_fan_r2))
    env["LRC_SF_DDK"] = str(sf_ddk)
    env["LRC_SF_P4_DEG"] = str(int(sf_p4_deg))
    env["LRC_SF_P4_M"] = str(int(sf_p4_m))
    env["LRC_SF_HSA_WINDOW"] = str(int(sf_hsa_window))
    env["LRC_SF_HSA_P"] = str(int(sf_hsa_p))
    env["LRC_SF_HSA_ORDER"] = str(int(sf_hsa_order))
    env["LRC_SF_HSA_BUFFER"] = str(int(sf_hsa_buffer))
    env["LRC_SF_HSA_TS"] = str(int(sf_hsa_ts))
    env["LRC_SF_TOOLBOX"] = str(sf_toolbox or "")

    wrapper_str = str(wrapper).replace("'", "''")
    cmd = [matlab, "-batch", f"run('{wrapper_str}')"]
    subprocess.run(cmd, check=True, env=env)

    try:
        import scipy.io as sio

        out = sio.loadmat(mat_out, squeeze_me=True, struct_as_record=False)
        sf = float(out.get("sf"))
    except Exception as e:
        raise RuntimeError(f"Failed to read SF output: {e}")
    return sf


def run_fm_correction(
    grid3d,
    lon_vec,
    lat_vec,
    t_arr,
    script_path,
    matlab,
    *,
    output_dir,
    infer_time_labels_cb=None,
    fm_target_grid_cb=None,
    regrid_regular_cb=None,
    write_xyz_file_cb=None,
    read_xyz_grid_cb=None,
):
    if infer_time_labels_cb is None:
        raise ValueError("infer_time_labels_cb is required.")
    if fm_target_grid_cb is None:
        raise ValueError("fm_target_grid_cb is required.")
    if regrid_regular_cb is None:
        raise ValueError("regrid_regular_cb is required.")
    if write_xyz_file_cb is None:
        raise ValueError("write_xyz_file_cb is required.")
    if read_xyz_grid_cb is None:
        raise ValueError("read_xyz_grid_cb is required.")

    lon_vec = np.asarray(lon_vec).astype(float).squeeze()
    lat_vec = np.asarray(lat_vec).astype(float).squeeze()
    nt = grid3d.shape[2]
    labels = infer_time_labels_cb(t_arr, nt)

    script = Path(script_path)
    if not script.exists():
        raise FileNotFoundError(f"FM script not found: {script_path}")
    fm_root = script.parent.parent.parent
    param_src = fm_root / "Data" / "Parameter" / "Global_Forward_Modeling_Simulation_Gauss300km.txt"
    coast_src = fm_root / "Data" / "GlobalCoast" / "globalgrid_30min.mat"
    if not param_src.exists() or not coast_src.exists():
        raise FileNotFoundError("FM parameter/coast files not found in root.")

    tmp_root = Path(output_dir) / "local" / f"lrc_fm_tmp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    input_dir = tmp_root / "Data" / "Out" / "Before_Forward_Modeling" / "SLR"
    input_dir.mkdir(parents=True, exist_ok=True)

    param_dst = tmp_root / "Data" / "Parameter"
    coast_dst = tmp_root / "Data" / "GlobalCoast"
    param_dst.mkdir(parents=True, exist_ok=True)
    coast_dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(param_src, param_dst / param_src.name)
    shutil.copy2(coast_src, coast_dst / coast_src.name)

    lon_t, lat_t = fm_target_grid_cb()

    for k in range(nt):
        grid_k = grid3d[:, :, k]
        lon_in = lon_vec.copy()
        if np.nanmin(lon_in) < 0:
            lon_in = (lon_in + 360.0) % 360.0
        grid_re = regrid_regular_cb(lon_in, lat_vec, grid_k, lon_t, lat_t)
        fname = f"Global_SLR_Gau_EWH_{labels[k]}.txt"
        write_xyz_file_cb(input_dir / fname, lon_t, lat_t, grid_re)

    out_dir = tmp_root / "Data" / "Out" / "Forward_Modelling" / "300kmGauss"
    out_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["IM_FM_ROOT"] = str(tmp_root)
    env["IM_FM_OUT"] = str(out_dir)

    script_dir = str(script.parent).replace("'", "''")
    script_file = str(script).replace("'", "''")
    cmd = [matlab, "-batch", f"addpath('{script_dir}'); run('{script_file}');"]
    subprocess.run(cmd, check=True, env=env)

    grids = []
    for label in labels:
        subdir = out_dir / f"{label}_fast_input_300kmGauss"
        gmt_file = subdir / f"gmt_grace_forward_modelling_{label}.txt"
        if not gmt_file.exists():
            raise FileNotFoundError(f"FM output not found: {gmt_file}")
        grid_fm, lon_fm, lat_fm = read_xyz_grid_cb(gmt_file)
        lon_fm = np.asarray(lon_fm, dtype=float)
        if np.nanmin(lon_vec) < 0:
            lon_fm = ((lon_fm + 180.0) % 360.0) - 180.0
        grid_back = regrid_regular_cb(lon_fm, lat_fm, grid_fm, lon_vec, lat_vec)
        grids.append(grid_back)

    out_stack = np.stack(grids, axis=2)
    return out_stack, lon_vec, lat_vec, labels
