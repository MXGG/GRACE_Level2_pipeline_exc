function OUT = run_slr_sigma_ddk4(cfgFile)
%RUN_SLR_SIGMA_DDK4 Compute SLR EWH uncertainty from sigmaC/sigmaS and apply DDK4.
%
% Workflow:
%   1) Read each monthly GFC under cfg.path.GFC
%   2) Use sigmaC/sigmaS to synthesize grid EWH uncertainty (no anomaly removal)
%   3) Propagate sigma through DDK4 in SH domain
%   4) Synthesize DDK4-filtered uncertainty and save monthly MAT outputs
%
% Outputs:
%   monthly_mat/SIGMA_RAW/SIGMA_RAW_YYYYMM.mat
%   monthly_mat/SIGMA_DDK4/SIGMA_DDK4_YYYYMM.mat

    warning('off', 'verbose');

    thisFile = mfilename('fullpath');
    srcDir   = fileparts(fileparts(thisFile)); % <MATLAB_ROOT>/src
    rootDir  = fileparts(srcDir);              % <MATLAB_ROOT>
    repoRoot = fileparts(rootDir);             % <REPO_ROOT>

    addpath(fullfile(rootDir, 'cfg'));
    addpath(genpath(fullfile(rootDir, 'src')));
    addpath(fullfile(rootDir, 'src', 'tools'));
    addpath(genpath(fullfile(rootDir, 'src', 'tools')), '-end');

    if nargin < 1 || isempty(cfgFile)
        cfgFile = getenv('GRACE_CFG');
    end
    cfgFile = resolve_config_path(cfgFile, rootDir, repoRoot, fullfile(rootDir, 'cfg', 'user_slr.json'));
    if ~isfile(cfgFile)
        error('Config file not found: %s', cfgFile);
    end

    defaultCfg = resolve_config_path('', rootDir, repoRoot, fullfile(rootDir, 'cfg', 'default.json'));
    cfg = cfg_load(cfgFile, defaultCfg);
    setup_env(cfg);

    % Force DDK4 as requested for uncertainty filtering.
    if ~isfield(cfg, 'filter'); cfg.filter = struct(); end
    if ~isfield(cfg.filter, 'ddk') || ~isstruct(cfg.filter.ddk)
        cfg.filter.ddk = struct();
    end
    cfg.filter.ddk.enable = true;
    cfg.filter.ddk.type = 'DDK4';

    % Keep low-degree replacement off for SLR-only gravity fields.
    if ~isfield(cfg, 'inversion'); cfg.inversion = struct(); end
    if ~isfield(cfg.inversion, 'lowdeg') || ~isstruct(cfg.inversion.lowdeg)
        cfg.inversion.lowdeg = struct();
    end
    cfg.inversion.lowdeg.enable = false;

    % SLR filenames usually do not contain "GSM" token; disable this filter.
    if ~isfield(cfg, 'time') || ~isstruct(cfg.time)
        cfg.time = struct();
    end
    cfg.time.product_type = '';

    paths = io_init_paths(cfg);
    T = build_time_index(cfg);
    if isfield(cfg.time, 'start_ym') && isfield(cfg.time, 'end_ym') ...
            && ~isempty(cfg.time.start_ym) && ~isempty(cfg.time.end_ym)
        try
            dt0 = datetime(cfg.time.start_ym, 'InputFormat', 'yyyy-MM');
            dt1 = datetime(cfg.time.end_ym, 'InputFormat', 'yyyy-MM');
            keep = arrayfun(@(x) x.dt >= dt0 && x.dt <= dt1, T);
            T = T(keep);
        catch
            % Ignore malformed bound strings and keep all detected months.
        end
    end
    if isempty(T)
        error('No months selected after applying time bounds.');
    end
    syn = inv_prepare_synthesis(cfg);
    lonVec = syn.lonVec;
    latVec = syn.latVec;

    nTotal = numel(T);
    nDone = 0;
    nSkipNoSigma = 0;

    fprintf('\n[SIGMA] Start SLR uncertainty workflow (no anomaly removal).\n');
    fprintf('[SIGMA] GFC dir: %s\n', cfg.path.GFC);
    fprintf('[SIGMA] Months: %d (%s -> %s)\n', nTotal, T(1).ym, T(end).ym);
    fprintf('[SIGMA] DDK type: %s\n\n', cfg.filter.ddk.type);

    for k = 1:nTotal
        Tk = T(k);
        fprintf('[SIGMA][%4d/%4d] %s ... ', k, nTotal, Tk.ym);

        SH = inv_read_gsm_month(cfg, Tk); % read direct monthly coefficients and their sigma
        if ~isfield(SH, 'hasSigma') || ~SH.hasSigma
            fprintf('skip (no sigma columns)\n');
            nSkipNoSigma = nSkipNoSigma + 1;
            continue;
        end

        % Raw uncertainty from original sigmaC/sigmaS (no mean/anomaly removal).
        ewhSigmaRaw = inv_synthesize_ewh_sigma_diag(SH.sigmaC, SH.sigmaS, syn);

        % DDK4 filter + diagonal sigma propagation in SH domain.
        [~, ~, sigmaC_DDK4, sigmaS_DDK4, metaDDK] = filter_sh_ddk( ...
            SH.C, SH.S, cfg.filter.ddk, cfg.path, SH.sigmaC, SH.sigmaS);
        ewhSigmaDDK4 = inv_synthesize_ewh_sigma_diag(sigmaC_DDK4, sigmaS_DDK4, syn);

        metaRaw = struct();
        metaRaw.source = 'gfc_sigmaC_sigmaS';
        metaRaw.method = 'diag_variance_propagation';
        metaRaw.anomaly_removed = false;
        metaRaw.unit = cfg.grid.unit;
        metaRaw.gfc_file = SH.meta.file;
        metaRaw.output = 'sigma';

        metaFiltered = struct();
        metaFiltered.source = 'gfc_sigmaC_sigmaS';
        metaFiltered.method = 'diag_variance_propagation';
        metaFiltered.anomaly_removed = false;
        metaFiltered.unit = cfg.grid.unit;
        metaFiltered.gfc_file = SH.meta.file;
        metaFiltered.output = 'sigma';
        metaFiltered.filter = metaDDK;

        Praw = io_make_product('SIGMA_RAW', Tk, lonVec, latVec, ewhSigmaRaw, metaRaw);
        Pddk = io_make_product('SIGMA_DDK4', Tk, lonVec, latVec, ewhSigmaDDK4, metaFiltered);

        io_save_product(cfg, paths, Praw);
        io_save_product(cfg, paths, Pddk);
        nDone = nDone + 1;
        fprintf('ok\n');
    end

    fprintf('\n[SIGMA] Finished. saved=%d, skipped(no sigma)=%d, total=%d\n', ...
        nDone, nSkipNoSigma, nTotal);
    fprintf('[SIGMA] Output root: %s\n', paths.root);

    OUT = struct();
    OUT.paths = paths;
    OUT.T = T;
    OUT.saved_months = nDone;
    OUT.skipped_no_sigma = nSkipNoSigma;
    OUT.total_months = nTotal;
end
