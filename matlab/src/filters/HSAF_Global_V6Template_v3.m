%% ========================================================================
%% HSAF_Global_V6Template_v3.m
%% ========================================================================
%  Purpose:
%    1) Keep the ORIGINAL global-parameter HSAF workflow (same core filtering logic as HSAF.m)
%    2) Make OUTPUT + PROGRESS + QC/STATISTICS consistent with HSAF_V6_3.m style:
%       - Unified banners + config summary
%       - Timestamped output folder + diary log
%       - Progress report with ETA (PARFOR-safe)
%       - Quality assessment module (global metrics + SRMSE/CC maps + basin RMSE + exports)
%
%  Dependencies (same as your project):
%    - HSA(), DDKs_Filter(), plot_map()
%    - Basin_Analysis(), gmt_harmonic(), mkmask(), (optional) gmt_grid2cs(), Function_GeoidErrorRealEGM()
%
%  Author: HSAF_Improve (refactor)
%  Date: 2026-01-12
%% ========================================================================

%% ========================================================================
%% PART 1) ENVIRONMENT INITIALIZATION (V6 STYLE)
%% ========================================================================
clc; clear; close all; warning('off','verbose');

fprintf('\n╔══════════════════════════════════════════════════════════════╗\n');
fprintf('║  HSAF Global (Fixed-Params) - V6 Output & QC Template (v3)   ║\n');
fprintf('║  Core filter: ORIGINAL HSAF.m (global common params)         ║\n');
fprintf('╚══════════════════════════════════════════════════════════════╝\n');
fprintf('Start time: %s\n', datestr(now,'yyyy-mm-dd HH:MM:SS'));

is_cluster = ~usejava('desktop');
if is_cluster
    fprintf('[ENV] Running on HPC cluster (nodisplay)\n');
    set(0,'DefaultFigureVisible','off');
else
    fprintf('[ENV] Running on local workstation\n');
end

%% ========================================================================
%% PART 2) USER CONFIG (PLEASE EDIT)
%% ========================================================================
opt = struct();

% ---- Project paths ----
opt.base_path   = '/home/um202370130/HSAF';      % <<< EDIT ME
opt.data_path   = fullfile(opt.base_path,'Data');
opt.script_path = fullfile(opt.base_path,'Software');

% ---- Dataset ----
% 1 = CSR (2004.01-2016.01), 2 = HIS (2003.01-2007.12)
opt.data_choice = 1;

% ---- Time range ----
opt.use_index_range = true;
opt.t0 = 19;     % used if use_index_range=true
opt.t1 = 150;    % used if use_index_range=true

% ---- Global HSAF parameters (same meaning as your HSAF.m) ----
opt.Ts          = 1;
opt.window_size = 30;   % <<< fill with your best global setting
opt.p           = 10;   % <<< fill with your best global setting
opt.order       = 6;    % <<< fill with your best global setting
opt.buffer      = 1;    % <<< fill with your best global setting

% ---- Other methods for comparison ----
opt.DDK_version = 'DDK4';

% ---- Parallel ----
opt.max_workers = 56;

% ---- Output ----
opt.output_base    = fullfile(opt.data_path,'EWH_Output','HSAF_Global');
opt.save_png_dpi   = 600;
opt.save_mat_v73   = true;
opt.save_snapshot  = true;

% ---- Quality Control / Statistics (V6_3-like) ----
opt.qc = struct();
opt.qc.enable           = true;
opt.qc.do_basin         = true;   % basin RMSE + time series extraction (heavy)
opt.qc.do_cc_map        = true;   % global correlation map (heavy)
opt.qc.do_srmse_map     = true;   % spatial RMSE map
opt.qc.cc_map_min_valid = 10;     % min valid samples for per-grid corr
opt.qc.max_basins       = 112;    % cap
opt.qc.do_shc_geoid     = false;  % optional/slow; requires gmt_grid2cs + Function_GeoidErrorRealEGM
opt.qc.plot_methods = {'Hankel', opt.DDK_version, 'Gaussian', 'Fan_Decorrelation', 'Mascon'};

%% ========================================================================
%% PART 3) PATHS + OUTPUT DIR + LOG (V6 STYLE)
%% ========================================================================
addpath(fullfile(opt.script_path,'Tool_Functions','gmt'));
addpath(fullfile(opt.script_path,'Tool_Functions','m_map'));
addpath(fullfile(opt.script_path,'Tool_Functions'));
addpath(fullfile(opt.script_path,'Tool_Functions','GRACE-filter-master','src','matlab'));
addpath(fullfile(opt.script_path,'HSA_Filter'));
addpath(opt.script_path);

timestamp  = datestr(now,'yyyymmdd_HHMMSS');
output_dir = fullfile(opt.output_base, timestamp, ...
    sprintf('global_win%d_p%d_order%d_buf%d', opt.window_size, opt.p, opt.order, opt.buffer));
ensure_dir(output_dir);

stats_dir = fullfile(output_dir,'Statistics');
fig_dir   = fullfile(stats_dir,'Figures');
ensure_dir(stats_dir);
ensure_dir(fig_dir);

fprintf('[DIR] Output: %s\n', output_dir);

log_file = fullfile(output_dir,'hsaf_global.log');
diary(log_file); diary on;

%% Print CONFIG summary (V6 style)
fprintf('\n[CONFIG] ═══════════════════════════════════════\n');
fprintf('         Global Parameter Configuration\n');
fprintf('         ═══════════════════════════════════════\n');
fprintf('Data choice: %d (1=CSR, 2=HIS)\n', opt.data_choice);
fprintf('Time range: use_index_range=%d | t0=%d | t1=%d\n', opt.use_index_range, opt.t0, opt.t1);
fprintf('HSAF params: Ts=%g | window=%d | p=%d | order=%d | buffer=%d\n', ...
    opt.Ts, opt.window_size, opt.p, opt.order, opt.buffer);
fprintf('DDK version: %s\n', opt.DDK_version);
fprintf('Parallel: max_workers=%d\n', opt.max_workers);
fprintf('QC: enable=%d | basin=%d | cc_map=%d | srmse_map=%d | shc_geoid=%d\n', ...
    opt.qc.enable, opt.qc.do_basin, opt.qc.do_cc_map, opt.qc.do_srmse_map, opt.qc.do_shc_geoid);
fprintf('═══════════════════════════════════════════════\n\n');

safe_save_struct(fullfile(output_dir,'config_opt.mat'), false, struct('opt', opt));

%% ========================================================================
%% PART 4) LOAD DATA (KEEP CONSISTENT WITH HSAF.m)
%% ========================================================================
fprintf('[LOAD] Loading auxiliary data...\n');

aux_path = fullfile(opt.data_path,'Auxiliary_Data');
load(fullfile(aux_path,'land_mask.mat'));
load(fullfile(aux_path,'date.mat'));
load(fullfile(aux_path,'time.mat'));
load(fullfile(aux_path,'rivers1.mat'));

% land mask 300 km
[~, ~, bool] = textread(fullfile(aux_path,'msk_300.xyz'), '%f %f %u', 'headerlines', 0);
msk = reshape(bool, [360, 180]);
land_mask_300_r(1:180, :) = msk(181:360, :);
land_mask_300_r(181:360, :) = msk(1:180, :);
land_mask_300_r = fliplr(land_mask_300_r);
land_mask_r_300_025 = ones(360, 180);
land_mask_r_300_025(land_mask_300_r == 0) = NaN;

fprintf('[LOAD] Loading GRACE/HIS data...\n');
EWH_data_address = fullfile(opt.data_path,'EWH_Output');

if opt.data_choice == 1
    load(fullfile(EWH_data_address,'CSR_EWH_data.mat'));
    load(fullfile(EWH_data_address,'CSR_CGS_EWH_data.mat'));
    EWH = CSR_EWH;
    EWH.CGS = CSR_CGS_EWH.None;
    data_type = 'CSR';
    start_year = 2004; start_month = 1;
    end_year   = 2016; end_month   = 1;
    fprintf('[LOAD] ✓ CSR loaded (2004.01-2016.01)\n');
elseif opt.data_choice == 2
    load(fullfile(EWH_data_address,'HIS_EWH_data.mat'));
    EWH = HIS_EWH;
    data_type = 'HIS';
    years = years';
    start_year = 2003; start_month = 1;
    end_year   = 2007; end_month   = 12;
    fprintf('[LOAD] ✓ HIS loaded (2003.01-2007.12)\n');
else
    error('[ERROR] Invalid opt.data_choice');
end

% lon/lat inference (robust)
[grid_lon, grid_lat] = infer_lonlat();

% time indices
if opt.use_index_range
    start_idx = opt.t0; end_idx = opt.t1;
else
    start_idx = find(year(dateTime)==start_year & month(dateTime)==start_month, 1);
    end_idx   = find(year(dateTime)==end_year   & month(dateTime)==end_month,   1);
end
time_size = end_idx - start_idx + 1;
dates = dateTime(start_idx:end_idx);

fprintf('[DATA] Period: %s to %s (%d months)\n', ...
    datestr(dates(1),'yyyy-mm'), datestr(dates(end),'yyyy-mm'), time_size);

%% ========================================================================
%% PART 5) PRE-FILTER (DDK) + GLOBAL HSAF FILTERING (ORIGINAL CORE)
%% ========================================================================
fprintf('\n[FILTER] Applying DDK (%s)...\n', opt.DDK_version);
EWH.(opt.DDK_version) = DDKs_Filter(EWH.None, opt.DDK_version, 1);
fprintf('[FILTER] ✓ DDK done\n');

% IMPORTANT: use the SAME input channel as your best legacy-global results.
% Legacy HSAF.m typically uses EWH.Decorrelation as Hankel input.
if isfield(EWH,'Decorrelation')
    X_in_all = EWH.Decorrelation;
    fprintf('[FILTER] Input channel: EWH.Decorrelation\n');
else
    warning('[WARN] EWH.Decorrelation not found. Using EWH.None as input.');
    X_in_all = EWH.None;
end

% X_in = X_in_all(:,:,start_idx:end_idx);  % unify time range for QC
X_in = EWH.None(:,:,start_idx:end_idx);  % unify time range for QC
%% 5.1) Parallel pool (V6 style)
fprintf('\n[PARALLEL] Configuring parallel pool...\n');
poolobj = gcp('nocreate');
if isempty(poolobj)
    try
        parpool('local', min(opt.max_workers, feature('numcores')));
        fprintf('[PARALLEL] ✓ Started %d workers\n', gcp().NumWorkers);
    catch ME
        warning('[WARN] Parallel pool failed: %s', ME.message);
        fprintf('[PARALLEL] Running in serial mode\n');
    end
else
    fprintf('[PARALLEL] ✓ Using existing pool (%d workers)\n', poolobj.NumWorkers);
end

%% 5.2) Hankel filtering (global fixed parameters)
fprintf('\n[FILTER] Running GLOBAL HSAF (fixed params)...\n');
batch_size  = 30;
num_batches = ceil(time_size / batch_size);
fprintf('[FILTER] Total months: %d | batch_size=%d | batches=%d\n', time_size, batch_size, num_batches);

t_filt_start = tic;
Hankel_out = zeros(size(X_in,1), size(X_in,2), time_size, 'like', X_in);

% Progress reporter (PARFOR-safe)
clear updateProgressHSAF;
dq = parallel.pool.DataQueue;
afterEach(dq, @(tidx) updateProgressHSAF(tidx, time_size, t_filt_start, '[FILTER]', 20));

for batch = 1:num_batches
    b0 = (batch-1)*batch_size + 1;
    b1 = min(batch*batch_size, time_size);
    idx_list = b0:b1;

    fprintf('[FILTER] Batch %d/%d (months %d-%d)\n', batch, num_batches, b0, b1);

    tmp = cell(numel(idx_list),1);

    parfor ii = 1:numel(idx_list)
        t = idx_list(ii);

        Hankel_Mode = HSA(X_in(:,:,t), ...
            opt.Ts, opt.window_size, opt.p, opt.order, opt.buffer);

        % SAME noise-mode selection logic as legacy HSAF.m
        switch opt.order
            case 3
                Y_noise = Hankel_Mode(:,:,1) + Hankel_Mode(:,:,3);
            case 4
                Y_noise = Hankel_Mode(:,:,1) + Hankel_Mode(:,:,4);
            case 5
                Y_noise = sum(Hankel_Mode(:,:, [1:2 4:5]), 3);
            case 6
                Y_noise = sum(Hankel_Mode(:,:, [1:2 5:6]), 3);
            case 7
                Y_noise = sum(Hankel_Mode(:,:, [1:2 6:7]), 3);
            case 8
                Y_noise = sum(Hankel_Mode(:,:, [1:3 6:8]), 3);
            case 9
                Y_noise = sum(Hankel_Mode(:,:, [1:3 7:9]), 3);
            case 10
                Y_noise = sum(Hankel_Mode(:,:, [1:3 8:10]), 3);
            otherwise
                error('Order %d not supported', opt.order);
        end

        tmp{ii} = X_in(:,:,t) - Y_noise;
        send(dq, t);
    end

    for ii = 1:numel(idx_list)
        Hankel_out(:,:,idx_list(ii)) = tmp{ii};
    end
end

EWH.Hankel = Hankel_out;
t_filt = toc(t_filt_start);
fprintf('[FILTER] ✓ Completed in %.1f sec (%.2f sec/month)\n', t_filt, t_filt/max(time_size,1));

%% Save filtered data
mat_file = fullfile(output_dir, sprintf('%s_EWH_HSAF_Global.mat', data_type));
S = struct('EWH', EWH, 'dates', dates, 'time_size', time_size, 'start_idx', start_idx, 'end_idx', end_idx, 'opt', opt);
safe_save_struct(mat_file, opt.save_mat_v73, S);
fprintf('[SAVE] Filtered data: %s\n', mat_file);

%% ========================================================================
%% PART 6) QUICK CHECK PLOTS (V6 STYLE)
%% ========================================================================
fprintf('\n[PLOT] Generating quick-check plots...\n');
t_check = max(1, round(time_size/2));

fig = figure('Visible','off','Position',[100 100 1200 420]);
tiledlayout(1,3,'TileSpacing','compact','Padding','compact');

nexttile;
plot_map(X_in(:,:,t_check), grid_lon, grid_lat, 1);
title('Before (Input to HSAF)','FontWeight','bold');

nexttile;
plot_map(EWH.Hankel(:,:,t_check), grid_lon, grid_lat, 1);
title('After (HSAF Global)','FontWeight','bold');

nexttile;
plot_map(X_in(:,:,t_check)-EWH.Hankel(:,:,t_check), grid_lon, grid_lat, 1);
title('Residual (Before - After)','FontWeight','bold');

cb = colorbar; cb.Layout.Tile='east'; cb.Label.String='EWH (cm)';
check_png = fullfile(fig_dir, sprintf('check_global_%s.png', datestr(dates(t_check),'yyyymm')));
print(fig, check_png, '-dpng', sprintf('-r%d', opt.save_png_dpi));
close(fig);
fprintf('[PLOT] ✓ Check plot saved: %s\n', check_png);

%% ========================================================================
%% PART 7) QUALITY CONTROL & STATISTICS (V6_3-LIKE)
%% ========================================================================
if opt.qc.enable
    fprintf('\n[QC] ═══════════════════════════════════════\n');
    fprintf('     Quality Control & Statistics Module\n');
    fprintf('     ═══════════════════════════════════════\n');

    % 7.1) Build unified evaluation struct (all methods share time dimension)
    EWH_eval = struct();
    EWH_eval.Input = X_in;
    if isfield(EWH,'None'), EWH_eval.None = EWH.None(:,:,start_idx:end_idx); end
    if isfield(EWH,opt.DDK_version), EWH_eval.(opt.DDK_version) = EWH.(opt.DDK_version)(:,:,start_idx:end_idx); end
    if isfield(EWH,'Gaussian'), EWH_eval.Gaussian = EWH.Gaussian(:,:,start_idx:end_idx); end
    if isfield(EWH,'Fan_Decorrelation'), EWH_eval.Fan_Decorrelation = EWH.Fan_Decorrelation(:,:,start_idx:end_idx); end
    if isfield(EWH,'Mascon'), EWH_eval.Mascon = EWH.Mascon(:,:,start_idx:end_idx); end
    EWH_eval.Hankel = EWH.Hankel; % already time_size

    fprintf('[QC] Methods prepared:\n');
    mlist = fieldnames(EWH_eval);
    for i = 1:numel(mlist)
        fprintf('      - %s\n', mlist{i});
    end

    has_ref = isfield(EWH_eval,'Mascon');
    if ~has_ref
        warning('[QC] Reference field "Mascon" not found -> skip reference-based metrics (CC/RMSE/...)');
    end

    % 7.2) Residual RMS diagnosis (Input vs Hankel)
    [rms_tbl_monthly, rms_tbl_single] = qc_rms_diagnosis(EWH_eval, dates, t_check);
    writetable(rms_tbl_monthly, fullfile(stats_dir, 'rms_monthly.csv'));
    writetable(rms_tbl_single,  fullfile(stats_dir, sprintf('rms_stats_check_%s.csv', datestr(dates(t_check),'yyyymm'))));
    safe_save_struct(fullfile(stats_dir,'rms_diagnosis.mat'), true, struct('rms_tbl_monthly', rms_tbl_monthly, 'rms_tbl_single', rms_tbl_single, 't_check', t_check));

    fprintf('[QC] RMS diagnosis saved:\n      - %s\n      - %s\n', ...
        fullfile(stats_dir,'rms_monthly.csv'), fullfile(stats_dir, sprintf('rms_stats_check_%s.csv', datestr(dates(t_check),'yyyymm'))));

    % 7.3) Global metrics vs reference (Mascon), SRMSE map
    if has_ref
        t_metrics = tic;
        [CC_results,SNR_results,RMSE_results,PSNR_results,MAE_results,NSC_results,SRMSE_results] = ...
            qc_global_metrics(EWH_eval, land_mask_r_300_025);

        metrics_file = fullfile(stats_dir,'metrics_global.mat');
        safe_save_struct(metrics_file, true, struct('CC_results', CC_results, 'SNR_results', SNR_results, 'RMSE_results', RMSE_results, 'PSNR_results', PSNR_results, 'MAE_results', MAE_results, 'NSC_results', NSC_results, 'SRMSE_results', SRMSE_results, 'dates', dates));
        fprintf('[QC] Metrics MAT: %s\n', metrics_file);

        % Mean table
        Tmean = qc_metrics_mean_table(CC_results,SNR_results,RMSE_results,PSNR_results,MAE_results,NSC_results);
        writetable(Tmean, fullfile(stats_dir,'metrics_mean.csv'));
        fprintf('[QC] Metrics mean CSV: %s\n', fullfile(stats_dir,'metrics_mean.csv'));

        % Time-series plots (same 2×3 layout)
        fig = qc_plot_metrics_timeseries(dates, CC_results,SNR_results,RMSE_results,PSNR_results,MAE_results,NSC_results, opt.qc.plot_methods);
        png_metrics = fullfile(fig_dir,'Global_Statistics_TimeSeries.png');
        print(fig, png_metrics, '-dpng', sprintf('-r%d', opt.save_png_dpi));
        close(fig);
        fprintf('[QC] ✓ Metrics time-series plot: %s\n', png_metrics);

        fprintf('[QC] ✓ Global metrics done in %.1f sec\n', toc(t_metrics));

        % 7.4) SRMSE maps
        if opt.qc.do_srmse_map
            qc_plot_srmse_maps(SRMSE_results, grid_lon, grid_lat, opt.qc.plot_methods, fig_dir, opt.save_png_dpi);
        end

        % 7.5) Global CC maps
        if opt.qc.do_cc_map
            qc_plot_cc_maps(EWH_eval, grid_lon, grid_lat, opt.qc.plot_methods, opt.qc.cc_map_min_valid, fig_dir, opt.save_png_dpi);
        end
    end

    % 7.6) Basin-scale RMSE (optional; heavy)
    if has_ref && opt.qc.do_basin && exist('mkmask','file')==2 && exist('Basin_Analysis','file')==2
        try
            qc_basin_metrics(EWH_eval, grid_lon, grid_lat, rivers_new, years, dates, stats_dir, opt.qc.max_basins);
        catch ME
            warning('[QC] Basin metrics failed: %s (%s)', ME.message, ME.identifier);
        end
    else
        if opt.qc.do_basin
            fprintf('[QC] Basin module skipped (missing reference / functions / disabled)\n');
        end
    end

    % 7.7) Optional: SHC + geoid degree errors (slow)
    if has_ref && opt.qc.do_shc_geoid
        qc_shc_geoid(EWH_eval, dates, stats_dir);
    end
end

%% ========================================================================
%% PART 8) SAVE SNAPSHOT + RUN SUMMARY (V6 STYLE)
%% ========================================================================
if opt.save_snapshot
    try
        src = mfilename('fullpath');
        if ~endsWith(src,'.m'); src = [src '.m']; end
        dst = fullfile(output_dir, 'HSAF_Global_snapshot.m');
        txt = fileread(src);
        fid = fopen(dst,'w'); assert(fid>0, 'Cannot open dst: %s', dst);
        fwrite(fid, txt, 'char'); fclose(fid);
        fprintf('[SNAP] Script snapshot saved: %s\n', dst);
    catch ME
        warning('[WARN] Failed to save script snapshot: %s', ME.message);
    end
end

fprintf('\n════════════════════════════════════════════\n');
fprintf('   HSAF Global Run Summary\n');
fprintf('════════════════════════════════════════════\n');
fprintf('End time:        %s\n', datestr(now, 'yyyy-mm-dd HH:MM:SS'));
fprintf('Filtering:       %.1f sec (%.2f sec/month)\n', t_filt, t_filt/max(time_size,1));
fprintf('Output dir:      %s\n', output_dir);
fprintf('Log file:        %s\n', log_file);
fprintf('Statistics dir:  %s\n', stats_dir);
fprintf('════════════════════════════════════════════\n\n');

fprintf('[DONE] All finished.\n');
diary off;

%% ========================================================================
%% LOCAL UTILITIES (V6 STYLE)
%% ========================================================================

function ensure_dir(d)
    if ~exist(d,'dir'), mkdir(d); end
end

function [lon,lat] = infer_lonlat()
% infer_lonlat - try common variable names; fallback to 0.25° grid
    lon = [];
    lat = [];
    candidates_lon = {'csr_lon','lon','LON','longitude','grid_lon','his_lon'};
    candidates_lat = {'csr_lat','lat','LAT','latitude','grid_lat','his_lat'};

    for k = 1:numel(candidates_lon)
        if evalin('base', sprintf('exist(''%s'',''var'')', candidates_lon{k}))
            lon = evalin('base', candidates_lon{k});
            break;
        end
    end
    for k = 1:numel(candidates_lat)
        if evalin('base', sprintf('exist(''%s'',''var'')', candidates_lat{k}))
            lat = evalin('base', candidates_lat{k});
            break;
        end
    end

    if isempty(lon) || isempty(lat)
        lon = (0.125:0.25:359.875)';
        lat = (-89.875:0.25:89.875)';
        fprintf('[WARN] lon/lat not found in workspace. Using default 0.25° grid.\n');
    end
end

function updateProgressHSAF(~, N_total, tStart, tag, every)
% updateProgressHSAF - V6_3-style progress reporter for PARFOR loops
%   Prints full lines (HPC-log friendly).
    persistent count
    if isempty(count), count = 0; end
    count = count + 1;

    if nargin < 5 || isempty(every), every = 20; end
    if nargin < 4 || isempty(tag),   tag   = '[FILTER]'; end

    if (mod(count, every) == 0) || (count == 1) || (count == N_total)
        elapsed = toc(tStart);
        eta = elapsed / max(count,1) * max(N_total - count, 0);
        fprintf('%s Month %3d/%d (%.1f%%) | ETA: %.1f min\n', ...
            tag, count, N_total, 100*count/max(N_total,1), eta/60);
    end
end

function [tbl_monthly, tbl_check] = qc_rms_diagnosis(EWH_eval, dates, t_check)
% RMS diagnostics like HSAF_V6_3: Original/Filtered/Residual (Input vs Hankel)
    X = EWH_eval.Input;
    Y = EWH_eval.Hankel;
    R = X - Y;

    Nt = size(X,3);
    rmsX = zeros(Nt,1); rmsY = zeros(Nt,1); rmsR = zeros(Nt,1); pct = zeros(Nt,1);

    for t = 1:Nt
        rmsX(t) = sqrt(mean(X(:,:,t).^2, 'all', 'omitnan'));
        rmsY(t) = sqrt(mean(Y(:,:,t).^2, 'all', 'omitnan'));
        rmsR(t) = sqrt(mean(R(:,:,t).^2, 'all', 'omitnan'));
        pct(t)  = 100*rmsR(t) / max(rmsX(t), eps);
    end

    tbl_monthly = table(dates(:), rmsX, rmsY, rmsR, pct, ...
        'VariableNames', {'Date','Input_RMS_cm','Filtered_RMS_cm','Residual_RMS_cm','Residual_pct_of_input'});

    tbl_check = table(rmsX(t_check), rmsY(t_check), rmsR(t_check), pct(t_check), ...
        'VariableNames', {'Input_RMS_cm','Filtered_RMS_cm','Residual_RMS_cm','Residual_pct_of_input'});
end

function [CC,SNR,RMSE,PSNR,MAE,NSC,SRMSE] = qc_global_metrics(EWH_eval, land_mask_r_300_025)
% Compute global metrics vs Mascon + SRMSE map (time-avg)
    methods = fieldnames(EWH_eval);
    methods(strcmp(methods,'Mascon')) = [];
    Nt = size(EWH_eval.Mascon,3);

    CC=struct(); SNR=struct(); RMSE=struct(); PSNR=struct(); MAE=struct(); NSC=struct();
    SRMSE_acc=struct(); SRMSE=struct();

    for i = 1:numel(methods)
        m = methods{i};
        CC.(m)   = zeros(Nt,1);
        SNR.(m)  = zeros(Nt,1);
        RMSE.(m) = zeros(Nt,1);
        PSNR.(m) = zeros(Nt,1);
        MAE.(m)  = zeros(Nt,1);
        NSC.(m)  = zeros(Nt,1);
        SRMSE_acc.(m) = zeros(size(EWH_eval.Mascon,1), size(EWH_eval.Mascon,2));
    end

    for t = 1:Nt
        Ft = EWH_eval.Mascon(:,:,t);
        mean_Ft = mean(Ft(:),'omitnan');
        denom_Ft = sqrt(sum((Ft(:)-mean_Ft).^2,'omitnan'));
        max_Ft2 = max(Ft(:),[],'omitnan')^2;

        for i = 1:numel(methods)
            m = methods{i};
            Fo = EWH_eval.(m)(:,:,t);

            mean_Fo = mean(Fo(:),'omitnan');
            num = sum((Fo(:)-mean_Fo).*(Ft(:)-mean_Ft),'omitnan');
            den = sqrt(sum((Fo(:)-mean_Fo).^2,'omitnan')) * denom_Ft;
            CC.(m)(t) = num / max(den, eps);

            numN = sum((Fo(:)-Ft(:)).^2,'omitnan');
            denN = sum((Ft(:)-mean_Ft).^2,'omitnan');
            NSC.(m)(t) = 1 - numN / max(denN, eps);

            RMSE.(m)(t) = sqrt(mean((Fo(:)-Ft(:)).^2,'omitnan'));
            MAE.(m)(t)  = mean(abs(Fo(:)-Ft(:)),'omitnan');
            PSNR.(m)(t) = 10*log10(max_Ft2 / (RMSE.(m)(t)^2 + eps));

            SRMSE_acc.(m) = SRMSE_acc.(m) + (Fo - Ft).^2;

            land_EWH  = Fo(land_mask_r_300_025 == 1);
            ocean_EWH = Fo(isnan(land_mask_r_300_025));
            RMS_land  = sqrt(mean(land_EWH.^2,'omitnan'));
            RMS_ocean = sqrt(mean(ocean_EWH.^2,'omitnan'));
            SNR.(m)(t) = 10*log10(RMS_land / (RMS_ocean + eps));
        end

        if mod(t,20)==0 || t==1 || t==Nt
            fprintf('[QC] Metrics: %3d/%d months (%.1f%%)\n', t, Nt, 100*t/Nt);
        end
    end

    for i = 1:numel(methods)
        m = methods{i};
        SRMSE.(m) = sqrt(SRMSE_acc.(m) / Nt);
    end
end

function Tmean = qc_metrics_mean_table(CC,SNR,RMSE,PSNR,MAE,NSC)
% Create mean metrics table
    methods = fieldnames(CC);
    rows = cell(0,7);
    for i = 1:numel(methods)
        m = methods{i};
        rows(end+1,:) = {m, mean(CC.(m),'omitnan'), mean(NSC.(m),'omitnan'), ...
            mean(RMSE.(m),'omitnan'), mean(MAE.(m),'omitnan'), mean(SNR.(m),'omitnan'), mean(PSNR.(m),'omitnan')}; %#ok<AGROW>
    end
    Tmean = cell2table(rows, 'VariableNames', {'Method','CC','NSC','RMSE_cm','MAE_cm','SNR_dB','PSNR_dB'});
end

function fig = qc_plot_metrics_timeseries(dates, CC,SNR,RMSE,PSNR,MAE,NSC, plot_methods)
% V6_3-like 2×3 tiled plot
    fig = figure('Visible','off','Position',[100 100 1600 900]);
    tiledlayout(2,3,'TileSpacing','compact','Padding','compact');

    plot_one(CC,'CC','Correlation Coefficient',1);
    plot_one(SNR,'SNR','SNR (dB)',2);
    plot_one(RMSE,'RMSE','RMSE (cm)',3);
    plot_one(PSNR,'PSNR','PSNR (dB)',4);
    plot_one(MAE,'MAE','MAE (cm)',5);
    plot_one(NSC,'NSC','NSC',6);

    sgtitle('Global Statistical Metrics Time Series','FontWeight','bold');

    function plot_one(S, title_txt, ylab, tile)
        nexttile(tile); hold on;
        for k = 1:numel(plot_methods)
            m = plot_methods{k};
            if isfield(S,m)
                plot(dates, S.(m), 'DisplayName', sprintf('%s (μ=%.3g)', m, mean(S.(m),'omitnan')));
            end
        end
        grid on; ylabel(ylab); xtickformat('yyyy-MM');
        legend('Location','best','Interpreter','none');
        title(title_txt);
    end
end

function qc_plot_srmse_maps(SRMSE, lon, lat, plot_methods, fig_dir, dpi)
% Plot SRMSE maps for selected methods
    methods = plot_methods;
    for k = 1:numel(methods)
        m = methods{k};
        if strcmp(m,'Mascon'), continue; end
        if ~isfield(SRMSE,m), continue; end

        fig = figure('Visible','off','Position',[100 100 900 450]);
        plot_map(SRMSE.(m), lon, lat, 1);
        title(sprintf('SRMSE Map (vs Mascon) - %s', m), 'Interpreter','none','FontWeight','bold');
        colorbar;
        out = fullfile(fig_dir, sprintf('SRMSE_Map_%s.png', m));
        print(fig, out, '-dpng', sprintf('-r%d', dpi));
        close(fig);
        fprintf('[QC] ✓ SRMSE map: %s\n', out);
    end
end

function qc_plot_cc_maps(EWH_eval, lon, lat, plot_methods, min_valid, fig_dir, dpi)
% Compute and plot per-grid correlation maps vs Mascon for selected methods
    Nt = size(EWH_eval.Mascon,3);
    Nlon = size(EWH_eval.Mascon,1);
    Nlat = size(EWH_eval.Mascon,2);

    methods = plot_methods;
    methods(strcmp(methods,'Mascon')) = [];

    for k = 1:numel(methods)
        m = methods{k};
        if ~isfield(EWH_eval,m), continue; end

        fprintf('[QC] Computing CC map: %s ...\n', m);
        ccmap = nan(Nlon, Nlat);

        for x = 1:Nlon
            for y = 1:Nlat
                ts_m = squeeze(EWH_eval.(m)(x,y,:));
                ts_r = squeeze(EWH_eval.Mascon(x,y,:));
                if sum(~isnan(ts_m)) >= min_valid && sum(~isnan(ts_r)) >= min_valid
                    ccmap(x,y) = corr(ts_m, ts_r, 'rows','complete');
                end
            end
        end

        safe_save_struct(fullfile(fig_dir, sprintf('CC_Map_%s.mat', m)), false, struct('ccmap', ccmap, 'm', m, 'min_valid', min_valid, 'Nt', Nt));
        fig = figure('Visible','off','Position',[100 100 900 450]);
        plot_map(ccmap, lon, lat, 1);
        title(sprintf('Global CC Map (vs Mascon) - %s', m), 'Interpreter','none','FontWeight','bold');
        cb = colorbar; cb.Label.String='Correlation';
        out = fullfile(fig_dir, sprintf('CC_Map_%s.png', m));
        print(fig, out, '-dpng', sprintf('-r%d', dpi));
        close(fig);
        fprintf('[QC] ✓ CC map: %s\n', out);
    end
end

function qc_basin_metrics(EWH_eval, lon, lat, rivers_new, years, dates, stats_dir, max_basins)
% Basin-scale RMSE vs Mascon (robust indexing)
    fprintf('[QC] Basin-scale metrics...\n');
    t0 = tic;

    if ~isvector(lon), lon = lon(:); end
    if ~isvector(lat), lat = lat(:); end

    methods = fieldnames(EWH_eval);
    methods(strcmp(methods,'Mascon')) = [];
    methods(strcmp(methods,'Input'))  = [];

    num_basins = min(max_basins, numel(rivers_new));
    basin_name = strings(num_basins,1);
    basin_area = zeros(num_basins,1);

    RMSE_tbl = table(basin_name, basin_area, 'VariableNames', {'Basin','Area'});
    for mi = 1:numel(methods)
        RMSE_tbl.(methods{mi}) = nan(num_basins,1);
    end

    % years vector for basin analysis
    try
        y_use = year(dates) + (month(dates)-1)/12;
    catch
        y_use = (1:numel(dates))';
    end

    for i = 1:num_basins
        [Lon_b, Lat_b, mask_b] = mkmask(rivers_new(i), 1);
        basin_name(i) = string(rivers_new(i).DRAINAGE);
        basin_area(i) = rivers_new(i).AREA;

        i1 = nearest_idx(lon, Lon_b(1));
        i2 = nearest_idx(lon, Lon_b(end));
        j1 = nearest_idx(lat, Lat_b(1));
        j2 = nearest_idx(lat, Lat_b(end));
        if i1>i2, tmp=i1; i1=i2; i2=tmp; end
        if j1>j2, tmp=j1; j1=j2; j2=tmp; end

        if isequal(size(mask_b), [numel(Lat_b), numel(Lon_b)])
            mask2 = mask_b';
        else
            mask2 = mask_b;
        end

        nlon = i2-i1+1; nlat = j2-j1+1;
        if ~isequal(size(mask2), [nlon,nlat])
            mask2 = mask2(1:min(end,nlon), 1:min(end,nlat));
            if size(mask2,1) < nlon, mask2(end+1:nlon,:) = 0; end
            if size(mask2,2) < nlat, mask2(:,end+1:nlat) = 0; end
        end

        ts_ref = Basin_Analysis(EWH_eval.Mascon(i1:i2, j1:j2, :) .* mask2, y_use, Lon_b, Lat_b);
        ts_ref = ts_ref(:);

        for mi = 1:numel(methods)
            m = methods{mi};
            ts_m = Basin_Analysis(EWH_eval.(m)(i1:i2, j1:j2, :) .* mask2, y_use, Lon_b, Lat_b);
            ts_m = ts_m(:);
            RMSE_tbl.(m)(i) = rmse_local(ts_m, ts_ref);
        end

        if mod(i,20)==0 || i==1 || i==num_basins
            fprintf('[QC] Basins %d/%d\n', i, num_basins);
        end
    end

    RMSE_tbl.Basin = basin_name;
    RMSE_tbl.Area  = basin_area;

    out_csv = fullfile(stats_dir,'basin_rmse.csv');
    writetable(RMSE_tbl, out_csv);
    safe_save_struct(fullfile(stats_dir,'basin_rmse.mat'), true, struct('RMSE_tbl', RMSE_tbl));

    fprintf('[QC] ✓ Basin RMSE saved: %s\n', out_csv);
    fprintf('[QC] ✓ Basin module done in %.1f sec\n', toc(t0));
end

function qc_shc_geoid(EWH_eval, dates, stats_dir)
% Optional SHC conversion + geoid errors (requires project functions)
    if exist('gmt_grid2cs','file')~=2 || exist('Function_GeoidErrorRealEGM','file')~=2
        warning('[QC] SHC/Geoid functions not found -> skip');
        return;
    end

    fprintf('[QC] SHC + Geoid-degree error module (slow)...\n');
    t0 = tic;

    methods = fieldnames(EWH_eval);
    Nt = size(EWH_eval.Mascon,3);
    lmax = 60;

    SC = struct();
    for i = 1:numel(methods)
        m = methods{i};
        SC.(m) = zeros(lmax+1, 2*lmax+1, Nt);
    end

    for t = 1:Nt
        for i = 1:numel(methods)
            m = methods{i};
            cs = gmt_grid2cs(EWH_eval.(m)(:,:,t)' / 100, lmax); % cm->m
            gc = gmt_mc2gc(cs);
            sc = gmt_cs2sc(gc);
            SC.(m)(:,:,t) = sc;
        end
        if mod(t,20)==0 || t==1 || t==Nt
            fprintf('[QC] SHC %3d/%d\n', t, Nt);
        end
    end

    degree = (0:lmax)';
    GeoidError = struct();

    for t = 1:Nt
        Cref = SC.Mascon(:, lmax+1:2*lmax+1, t);
        Sref = [zeros(lmax+1,1), SC.Mascon(:, 1:lmax, t)];
        Cref(isnan(Cref))=0; Sref(isnan(Sref))=0;

        for i = 1:numel(methods)
            m = methods{i};
            Cc = SC.(m)(:, lmax+1:2*lmax+1, t);
            Sc = [zeros(lmax+1,1), SC.(m)(:, 1:lmax, t)];
            Cc(isnan(Cc))=0; Sc(isnan(Sc))=0;

            [GeoidError.(m).Degree(:,:,t), GeoidError.(m).Cumulative(:,:,t)] = ...
                Function_GeoidErrorRealEGM(Cc, Sc, Cref, Sref, lmax, lmax);
        end
    end

    safe_save_struct(fullfile(stats_dir,'shc_geoid.mat'), true, struct('SC', SC, 'GeoidError', GeoidError, 'degree', degree, 'dates', dates));
    fprintf('[QC] ✓ SHC/Geoid saved: %s\n', fullfile(stats_dir,'shc_geoid.mat'));
    fprintf('[QC] ✓ SHC/Geoid module done in %.1f sec\n', toc(t0));
end

function idx = nearest_idx(vec, val)
    [~, idx] = min(abs(vec - val));
end

function r = rmse_local(a,b)
    d = a(:) - b(:);
    r = sqrt(mean(d.^2,'omitnan'));
end

function safe_save_struct(fp, use_v73, S)
%SAFE_SAVE_STRUCT Write MAT file via temp file to avoid corruption on failure.
    tmp = [fp '.tmp'];
    if exist(tmp,'file'); delete(tmp); end
    try
        if use_v73
            save(tmp, '-struct', 'S', '-v7.3');
        else
            save(tmp, '-struct', 'S');
        end
        movefile(tmp, fp, 'f');
    catch ME
        if exist(tmp,'file'); delete(tmp); end
        rethrow(ME);
    end
end
