%% Forward Modelling (SIM) - HPC V3 Corrected (迭代逻辑修正版)
% Changelog from V3:
% 1. FIXED: Added acceleration factor k=1.2 (关键修改)
% 2. FIXED: Convergence criterion using land-weighted mean (收敛判据改进)
% 3. IMPROVED: Iteration logic matches reference code (与参考代码一致)
% 4. MAINTAINED: All GMT output fixes and optimizations

clear; clc;

%% Configuration
SAVE_FINAL_GMT = true;
SAVE_STATS     = true;
USE_PARALLEL   = true;
DIAGNOSE_FIRST_FILE = true;

% Iteration parameters (NEW)
k_acceleration = 1.1;  % 加速因子 (参考代码中的k)
convergence_threshold = 0.01;  % 收敛阈值α (可调)

%% Grid Definition (Global 0.5°)
lonVec = (0.25:0.5:359.75)';  % 720x1
latVec = (-89.75:0.5:89.75)';  % 360x1
nlon   = numel(lonVec);
nlat   = numel(latVec);

%% Paths
ROOT = getenv('IM_FM_ROOT');
OUTR = getenv('IM_FM_OUT');
if isempty(ROOT)
    ROOT = 'G:\code\2Simulation_Global_Signal_No_Error\';
end
if isempty(OUTR)
    OUTR = fullfile(ROOT, 'Data', 'Out', 'Forward_Modelling', '300kmGauss');
end

HIS_EWH_dir = fullfile(ROOT, 'Data', 'Out', 'Before_Forward_Modeling', 'SLR');
HIS_pattern = 'Global_SLR_Gau_EWH_*';
Parameter_address = fullfile(ROOT, 'Data', 'Parameter', 'Global_Forward_Modeling_Simulation_Gauss300km.txt');
CoastMatFile = fullfile(ROOT, 'Data', 'GlobalCoast', 'globalgrid_30min.mat');

sum_iteration = 99;
Lmax_SH = 60;

%% Load Input Files
HIS_file = dir(fullfile(HIS_EWH_dir, HIS_pattern));
assert(~isempty(HIS_file), 'No input files found');
nfiles = numel(HIS_file);
fprintf('Found %d files to process\n\n', nfiles);

%% Load Coastline Mask
S = load(CoastMatFile);
global_coast = build_global_coast(S.globalgrid);
landMask = (global_coast == 1);
oceanMask = ~landMask;

% Compute land weights for convergence criterion
land_weights = double(landMask);
weight_sum = sum(land_weights(:));

%% Load Parameters
params = read_parameter_file(Parameter_address);
[ceta, fir, n_c, n_f, ~, ~, nceta, nfir] = region_grid(...
    params.minlat, params.maxlat, params.minlon, params.maxlon, params.Res_lonlat);

%% Pre-compute ALL Constants
fprintf('Pre-computing constants...\n');
tic;

% Love numbers
loveN_k0 = [0,0.027,-0.303,-0.194,-0.132,-0.104,-0.089,-0.081,-0.076,...
    -0.072,-0.069,-0.064,-0.058,-0.051,-0.040,-0.033,-0.027,-0.020,...
    -0.014,-0.010,-0.007];
n_loveN = [0,1,2,3,4,5,6,7,8,9,10,12,15,20,30,40,50,70,100,150,200];
n = 0:params.Lmax;
loveN_k = interp1(n_loveN, loveN_k0, n);
loveN = (2*n+1)./(1+loveN_k);
loveN = loveN(:).';

% Physical constants
a = 6.378136460E+06;
Pave = 5517.0;
Pwater = 1000.0;
scale = a*Pave/(3.0*Pwater) * 100.0;

% Trigonometric matrices for synthesis
mVec = (0:params.Lmax).';
mfir = mVec * fir(:).';
cosdmf = cosd(mfir);
sindmf = sind(mfir);

% Pnm for synthesis
Pnm_syn = Nlmx_v3(params.Lmax, ceta);

% Pre-compute constants for SH analysis
d_ceta = params.Res_lonlat * pi/180;
d_fir = params.Res_lonlat * pi/180;
analysis_const = 3*Pwater/(4*pi*a*Pave) * d_ceta * d_fir / 100.0;

% Pre-compute Pnm for analysis
Pnm_analysis = Nlmx_v3(Lmax_SH, latVec);

% Pre-compute coordinate arrays
lon_col = repmat(lonVec, nlat, 1);
lat_col = repelem(latVec, nlon);

% Pre-compute sin/cos arrays
m_vals = (0:Lmax_SH)';
lon_grid_all = lon_col(:);
cos_m_lon = cosd(m_vals * lon_grid_all');
sin_m_lon = sind(m_vals * lon_grid_all');
sin_colat = sind(90 - lat_col(:))';

% Pre-compute Love number factors
loveN_k_analysis = interp1(n_loveN, loveN_k0, 0:Lmax_SH);
love_factor = (1 + loveN_k_analysis) ./ (2*(0:Lmax_SH) + 1);

fprintf('Pre-computation complete (%.2f s)\n\n', toc);

%% Initialize Parallel Pool
if USE_PARALLEL
    poolobj = gcp('nocreate');
    if isempty(poolobj)
        parpool('local');
    end
end

%% Main Processing Loop
total_start = tic;

% Create shared data struct
shared_data = struct(...
    'lonVec', lonVec, 'latVec', latVec, 'nlon', nlon, 'nlat', nlat, ...
    'global_coast', global_coast, 'landMask', landMask, 'oceanMask', oceanMask, ...
    'land_weights', land_weights, 'weight_sum', weight_sum, ...
    'sum_iteration', sum_iteration, 'Lmax_SH', Lmax_SH, ...
    'params', params, 'Pnm_syn', Pnm_syn, 'Pnm_analysis', Pnm_analysis, ...
    'loveN', loveN, 'scale', scale, 'cosdmf', cosdmf, 'sindmf', sindmf, ...
    'n_c', n_c, 'n_f', n_f, 'analysis_const', analysis_const, ...
    'lon_col', lon_col, 'lat_col', lat_col, ...
    'cos_m_lon', cos_m_lon, 'sin_m_lon', sin_m_lon, ...
    'sin_colat', sin_colat, 'love_factor', love_factor, ...
    'k_acceleration', k_acceleration, ...
    'convergence_threshold', convergence_threshold, ...
    'SAVE_FINAL_GMT', SAVE_FINAL_GMT, 'SAVE_STATS', SAVE_STATS, ...
    'DIAGNOSE_FIRST_FILE', DIAGNOSE_FIRST_FILE);

if USE_PARALLEL
    parfor fileIdx = 1:nfiles
        process_single_file(fileIdx, HIS_file, HIS_EWH_dir, OUTR, shared_data);
    end
else
    for fileIdx = 1:nfiles
        process_single_file(fileIdx, HIS_file, HIS_EWH_dir, OUTR, shared_data);
    end
end

total_time = toc(total_start);
fprintf('\n========================================\n');
fprintf('ALL FILES PROCESSED\n');
fprintf('Total time: %.1f s (%.2f min)\n', total_time, total_time/60);
fprintf('Average per file: %.1f s\n', total_time/nfiles);
fprintf('========================================\n');

%% ========== PROCESSING FUNCTION (修正版迭代逻辑) ==========
function process_single_file(fileIdx, HIS_file, HIS_EWH_dir, OUTR, shared_data)

% Extract variables
lonVec = shared_data.lonVec;
latVec = shared_data.latVec;
nlon = shared_data.nlon;
nlat = shared_data.nlat;
global_coast = shared_data.global_coast;
landMask = shared_data.landMask;
oceanMask = shared_data.oceanMask;
land_weights = shared_data.land_weights;
weight_sum = shared_data.weight_sum;
sum_iteration = shared_data.sum_iteration;
Lmax_SH = shared_data.Lmax_SH;
params = shared_data.params;
Pnm_syn = shared_data.Pnm_syn;
Pnm_analysis = shared_data.Pnm_analysis;
loveN = shared_data.loveN;
scale = shared_data.scale;
cosdmf = shared_data.cosdmf;
sindmf = shared_data.sindmf;
n_c = shared_data.n_c;
n_f = shared_data.n_f;
analysis_const = shared_data.analysis_const;
lon_col = shared_data.lon_col;
lat_col = shared_data.lat_col;
cos_m_lon = shared_data.cos_m_lon;
sin_m_lon = shared_data.sin_m_lon;
sin_colat = shared_data.sin_colat;
love_factor = shared_data.love_factor;
k_acceleration = shared_data.k_acceleration;
convergence_threshold = shared_data.convergence_threshold;
SAVE_FINAL_GMT = shared_data.SAVE_FINAL_GMT;
SAVE_STATS = shared_data.SAVE_STATS;
DIAGNOSE_FIRST_FILE = shared_data.DIAGNOSE_FIRST_FILE;

file_start = tic;
current_file = HIS_file(fileIdx).name;
filename_in = fullfile(HIS_EWH_dir, current_file);
HIS_time = current_file(20:25);

fprintf('[%d/%d] Processing %s...\n', fileIdx, numel(HIS_file), HIS_time);

%% Load and reshape input
a = load(filename_in);

% Safe reconstruction method
USE_SAFE_METHOD = true;

if USE_SAFE_METHOD
    M_obs = nan(nlat, nlon);
    for i = 1:size(a, 1)
        lon_val = a(i, 1);
        lat_val = a(i, 2);
        val = a(i, 3);

        [~, ilon] = min(abs(lonVec - lon_val));
        [~, ilat] = min(abs(latVec - lat_val));

        M_obs(ilat, ilon) = val;
    end
else
    M_obs = reshape(a(:,3), nlat, nlon);
end

if fileIdx == 1
    fprintf('  Input matrix: %d × %d, Range: [%.4f, %.4f]\n', ...
        size(M_obs, 1), size(M_obs, 2), min(M_obs(:)), max(M_obs(:)));
end

%% CORRECTED ITERATION LOGIC (修正版迭代)
% 按照参考代码的逻辑：
% M_tru = M_obs (初始化)
% for iteration:
%     M_pre = forward_model(M_tru)  // SH分析+合成+滤波
%     ΔM = M_obs - M_pre
%     M_tru = M_tru + k*ΔM
% 最终输出M_tru

M_tru = M_obs;  % 初始化：真实信号 = 观测信号
M_obs_ref = M_obs;  % 保存观测数据作为参考

% Pre-allocate
mean_land_weighted = zeros(sum_iteration, 1);  % 陆地加权平均（收敛判据）
mean_delta_global = zeros(sum_iteration, 1);   % 全局平均（监控）

% Iteration loop
for iteration = 1:sum_iteration

    % Step 1: 处理海洋区域（用陆地平均值填充）
    mean_land_val = mean(M_tru(landMask), 'omitnan') * ...
        nnz(landMask) / numel(M_tru);

    M_tru_masked = M_tru .* global_coast + ...
        mean_land_val * (global_coast - 1);

    % Step 2: 球谐分析 (M_tru → SH coefficients, truncated to Lmax_SH)
    val_col = reshape(M_tru_masked.', [], 1);

    % % %     % OPTIMIZED SH analysis (vectorized)
    % SH_model_mask_v1 = SHanalysis4EWH(val_col, Pnm, Lmax_SH, 0.5);toc;tic;
    % % %
    % % %     SH_model = SHanalysis4EWH_optimized(val_col, Pnm_analysis, Lmax_SH, ...
    % % %         analysis_const, cos_m_lon, sin_m_lon, sin_colat, love_factor, nlon);

    SH_model = SHanalysis4EWH_optimized(val_col, Pnm_analysis, Lmax_SH, ...
        analysis_const, cos_m_lon, sin_m_lon, sin_colat, love_factor, nlon);

    % Convert to matrices
    Dc = zeros(params.Lmax+1, params.Lmax+1);
    Ds = zeros(params.Lmax+1, params.Lmax+1);
    n_idx = SH_model(:,1) + 1;
    m_idx = SH_model(:,2) + 1;
    idx = sub2ind([params.Lmax+1, params.Lmax+1], n_idx, m_idx);
    Dc(idx) = SH_model(:,3);
    Ds(idx) = SH_model(:,4);

    % Step 3: 球谐合成 + 高斯滤波 (SH → M_pre)
    M_pre = synthesize_EWH_fast(Dc, Ds, Pnm_syn, loveN, scale, ...
        cosdmf, sindmf, n_c, n_f, params.Gaussian_r, params.Lmax);

    % Step 4: 计算差值 ΔM = M_obs - M_pre
    delta_M = M_obs_ref - M_pre;

    % Step 5: 计算收敛指标
    % 陆地加权平均（主要收敛判据）

    mean_land_weighted(iteration) = sum(sum(delta_M .* land_weights)) / weight_sum;

    % 全局平均（辅助监控）
    mean_delta_global(iteration) = mean(delta_M(:), 'omitnan');

    % Step 6: 更新 M_tru（关键：添加加速因子k）
    M_tru = M_tru + k_acceleration * delta_M;

    % Progress reporting
    if mod(iteration, 10) == 0 || iteration == 1 || iteration == sum_iteration
        fprintf('  [%s] iter %d/%d | land_weighted_ΔM=%.4g | global_ΔM=%.4g\n', ...
            HIS_time, iteration, sum_iteration, ...
            mean_land_weighted(iteration), mean_delta_global(iteration));
    end

    % Early stopping (可选)
    if abs(mean_land_weighted(iteration)) < convergence_threshold
        fprintf('  [%s] Converged at iteration %d (ΔM=%.4g < %.4g)\n', ...
            HIS_time, iteration, abs(mean_land_weighted(iteration)), convergence_threshold);
        % Truncate arrays
        mean_land_weighted = mean_land_weighted(1:iteration);
        mean_delta_global = mean_delta_global(1:iteration);
        break;
    end
end

%% Final output processing
final_mean_land = mean(M_tru(landMask), 'omitnan');
M_final = M_tru .* global_coast + final_mean_land * (global_coast - 1);

final_global_mean = mean(M_final(:), 'omitnan');
fprintf('  [%s] Final: land_ΔM=%.4g, global_mean=%.4g\n', ...
    HIS_time, mean_land_weighted(end), final_global_mean);

% Create output directory
Output_final_address = fullfile(OUTR, [HIS_time, '_fast_input_300kmGauss']);
if ~exist(Output_final_address, 'dir')
    mkdir(Output_final_address);
end

%% Diagnostics
if fileIdx == 1 && DIAGNOSE_FIRST_FILE
    diagnose_data_structure(M_final, lonVec, latVec);

    % Plot convergence
    fprintf('\n  Convergence history:\n');
    fprintf('    First 5 iterations: ');
    fprintf('%.4g ', mean_land_weighted(1:min(5,end)));
    fprintf('\n    Last 5 iterations: ');
    fprintf('%.4g ', mean_land_weighted(max(1,end-4):end));
    fprintf('\n\n');
end

%% Save outputs
if SAVE_FINAL_GMT
    filename_gmt = fullfile(Output_final_address, ...
        ['gmt_grace_forward_modelling_', HIS_time, '.txt']);
    write_gmt_xyz_v3(filename_gmt, M_final, lonVec, latVec);
end

if SAVE_STATS
    % Save land-weighted convergence metric (主要收敛指标)
    write_two_col_fast(fullfile(Output_final_address, ...
        ['convergence_land_weighted_', HIS_time, '.txt']), ...
        (1:length(mean_land_weighted))', mean_land_weighted);

    % Save global mean for reference
    write_two_col_fast(fullfile(Output_final_address, ...
        ['convergence_global_mean_', HIS_time, '.txt']), ...
        (1:length(mean_delta_global))', mean_delta_global);
end

fprintf('  [%s] Complete in %.1f s\n\n', HIS_time, toc(file_start));
end

%% ========== SH ANALYSIS (VECTORIZED) ==========
function SH_model = SHanalysis4EWH_optimized(val_col, Pnm_analysis, Lmax, ...
    analysis_const, cos_m_lon, sin_m_lon, sin_colat, love_factor, nlon)

num_coeffs = (Lmax+1)*(Lmax+2)/2;
nn = zeros(num_coeffs, 1);
mm = zeros(num_coeffs, 1);
Cnm = zeros(num_coeffs, 1);
Snm = zeros(num_coeffs, 1);

idx = 1;
for n = 0:Lmax
    for m = 0:n
        Pnm_slice = squeeze(Pnm_analysis(n+1, m+1, :));
        Pnm_all = repelem(Pnm_slice, nlon);
        Pnm_all = Pnm_all';

        integrand_C = Pnm_all .* val_col' .* cos_m_lon(m+1,:) .* sin_colat;
        integrand_S = Pnm_all .* val_col' .* sin_m_lon(m+1,:) .* sin_colat;

        nn(idx) = n;
        mm(idx) = m;
        Cnm(idx) = analysis_const * sum(integrand_C) * love_factor(n+1);
        Snm(idx) = analysis_const * sum(integrand_S) * love_factor(n+1);

        idx = idx + 1;
    end
end

SH_model = [nn, mm, Cnm, Snm];
end

%% ========== SYNTHESIS ==========
function sumg = synthesize_EWH_fast(Dc, Ds, Pnm_syn, loveN, scale, ...
    cosdmf, sindmf, n_c, n_f, gaussian_r, Lmax)

if gaussian_r > 0
    [Dc, Ds] = apply_gaussian_filter(gaussian_r, Lmax, Dc, Ds);
end

sumg = zeros(n_c, n_f);
for nn = 1:n_c
    Pnm_slice = Pnm_syn(:,:,nn);
    A = Pnm_slice .* Dc;
    B = Pnm_slice .* Ds;
    T = A*cosdmf + B*sindmf;
    sumg(nn,:) = scale * (loveN * T);
end
end

%% ========== GAUSSIAN FILTER ==========
function [Dc_w, Ds_w] = apply_gaussian_filter(radius, Lmax, Dc, Ds)
a = 6.378136460E+06;
r1 = radius * 1000;
b1 = log(2) / (1 - cos(r1/a));

w1 = zeros(1, Lmax+1);
w1(1) = 1;
w1(2) = (1 + exp(-2*b1)) / (1 - exp(-2*b1)) - 1/b1;
for l = 1:(Lmax-1)
    w1(l+2) = -(2*l+1)/b1 * w1(l+1) + w1(l);
end

wcol = reshape(w1(:), [Lmax+1, 1]);
Dc_w = Dc .* wcol;
Ds_w = Ds .* wcol;
end

%% ========== LEGENDRE FUNCTIONS ==========
function mNLegendre = Nlmx_v3(Lmax, x)
kk = length(x);
Theta = 90 - x;

mNLegendre = zeros(Lmax+1, Lmax+1, kk);
mx = zeros(Lmax+1, 1);
mx(1) = 1;

for l = 0:Lmax
    cy = legendre(l, cosd(Theta), 'norm');
    for m = 0:l
        mNLegendre(l+1, m+1, :) = Nlegendre_v3(l, m, cy, mx);
    end
end
end

function y = Nlegendre_v3(n, m, cy, mx)
y = cy' * mzeros_v3(n+1, m+1) * sqrt(2 * (2 - mx(m+1)));
end

function y = mzeros_v3(n, m)
y = zeros(n, 1);
y(m) = 1;
end

%% ========== REGION GRID ==========
function [ceta, fir, n_c, n_f, cetax, firx, nceta, nfir] = ...
    region_grid(minlat, maxlat, minlon, maxlon, Res_lonlat)

ceta = (minlat:Res_lonlat:maxlat)';
fir = (minlon:Res_lonlat:maxlon)';
n_c = length(ceta);
n_f = length(fir);

[firx, cetax] = meshgrid(fir, ceta);
nceta = repmat((1:n_c)', 1, n_f);
nfir = repmat(1:n_f, n_c, 1);
end



function write_two_col_fast(outFile, x, y)
fid = fopen(outFile, 'w');
fprintf(fid, '%d %.10g\n', [x(:), y(:)].');
fclose(fid);
end


% %% ========== FILE I/O (lon-fast, match your Fig.3) ==========
function write_gmt_xyz_v3(outFile, M, lonVec, latVec)

nlat = numel(latVec);
nlon = numel(lonVec);

if ~isequal(size(M), [nlat, nlon])
    error('Dimension mismatch! M should be (%d,%d) but is (%d,%d)', ...
        nlat, nlon, size(M,1), size(M,2));
end

% nlat × nlon, lon changes along columns
[LonGrid, LatGrid] = meshgrid(lonVec, latVec);

% --- lon-fast order: flatten row-wise via transpose then (:)
LonT = LonGrid.';   % 或者 LonT = transpose(LonGrid);
LatT = LatGrid.';   % 或者 LatT = transpose(LatGrid);
MT   = M.';         % 或者 MT   = transpose(M);

lon_col = LonT(:);
lat_col = LatT(:);
val_col = MT(:);


% ⚠️ 不建议删 NaN：一旦删了，读回 reshape 就无法还原网格
% 如果你必须处理 NaN，可考虑写成 NaN 字符串（fprintf 会输出 NaN）
fid = fopen(outFile, 'wt');
if fid == -1
    error('Cannot open file: %s', outFile);
end

fprintf(fid, '%.6f %.6f %.10g\n', [lon_col, lat_col, val_col].');
fclose(fid);
end






%% ========== DIAGNOSTICS ==========
function diagnose_data_structure(M, lonVec, latVec)
fprintf('\n========== DATA DIAGNOSTICS ==========\n');
fprintf('Matrix dimensions: %d × %d\n', size(M, 1), size(M, 2));
fprintf('Expected: %d × %d (nlat × nlon)\n', length(latVec), length(lonVec));
fprintf('Data range: [%.6f, %.6f]\n', min(M(:)), max(M(:)));

mid_lat_idx = round(length(latVec)/2);
mid_lon_idx = round(length(lonVec)/2);

fprintf('\nAlong longitude (lat≈%.1f°): ', latVec(mid_lat_idx));
fprintf('%.4g ', M(mid_lat_idx, 1:min(5, size(M,2))));
fprintf('\n');

fprintf('Along latitude (lon≈%.1f°): ', lonVec(mid_lon_idx));
fprintf('%.4g ', M(1:min(5, size(M,1)), mid_lon_idx)');
fprintf('\n');

lon_var = std(M, 0, 2);
lat_var = std(M, 0, 1);

fprintf('\nVariation check:\n');
fprintf('  Along longitude: mean_std=%.4g, range=[%.4g, %.4g]\n', ...
    mean(lon_var), min(lon_var), max(lon_var));
fprintf('  Along latitude: mean_std=%.4g, range=[%.4g, %.4g]\n', ...
    mean(lat_var), min(lat_var), max(lat_var));

if min(lon_var) < 1e-10 || min(lat_var) < 1e-10
    warning('Suspicious: Some slices have near-zero variation!');
end

fprintf('======================================\n\n');
end

%% ========== COASTLINE ==========
function global_coast = build_global_coast(globalgrid)
global_coast_new = zeros(360, 720);
global_coast = zeros(360, 720);
global_coast_new(1:359, 1:719) = flipud(globalgrid);
global_coast(:, 1:360) = global_coast_new(:, 361:720);
global_coast(:, 361:720) = global_coast_new(:, 1:360);
end

%% ========== PARAMETER READER ==========
function params = read_parameter_file(fname)
fid = fopen(fname, 'r');
assert(fid ~= -1, 'Cannot open file: %s', fname);

lines = {};
while ~feof(fid)
    line = fgetl(fid);
    if ischar(line)
        lines{end+1} = strtrim(line);
    end
end
fclose(fid);

params = struct();
i = 1;

while i <= length(lines)
    line = lines{i};
    if isempty(line)
        i = i + 1;
        continue;
    end

    if contains(line, 'Research region')
        params.minlon = str2double(lines{i+1});
        params.maxlon = str2double(lines{i+2});
        params.minlat = str2double(lines{i+3});
        params.maxlat = str2double(lines{i+4});
        i = i + 5;
    elseif contains(line, 'Resolution of longitude')
        params.Res_lonlat = str2double(lines{i+1});
        i = i + 2;
    elseif contains(line, 'Maximum degree of GRACE')
        params.Lmax = str2double(lines{i+1});
        i = i + 2;
    elseif contains(line, 'Radius of Gaussian')
        params.Gaussian_r = str2double(lines{i+1});
        i = i + 2;
    else
        i = i + 1;
    end
end

fprintf('Parameters: Lmax=%d, Gaussian_r=%d km, k_accel=1.2\n', ...
    params.Lmax, params.Gaussian_r);
end