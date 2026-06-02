function OUT = run_slr_sigma_build_stacks(cfgFile)
%RUN_SLR_SIGMA_BUILD_STACKS Build SIGMA_RAW / SIGMA_DDK4 stacks from monthly MAT files.
%
% This utility does not recompute SH uncertainty. It only aggregates:
%   monthly_mat/SIGMA_RAW/SIGMA_RAW_YYYYMM.mat
%   monthly_mat/SIGMA_DDK4/SIGMA_DDK4_YYYYMM.mat
% into stack MAT files under:
%   stacks/SIGMA_RAW_stack_YYYYMM-YYYYMM.mat
%   stacks/SIGMA_DDK4_stack_YYYYMM-YYYYMM.mat

    warning('off', 'verbose');

    thisFile = mfilename('fullpath');
    srcDir   = fileparts(fileparts(thisFile)); % <MATLAB_ROOT>/src
    rootDir  = fileparts(srcDir);              % <MATLAB_ROOT>
    repoRoot = fileparts(rootDir);             % <REPO_ROOT>

    addpath(fullfile(rootDir, 'cfg'));
    addpath(genpath(fullfile(rootDir, 'src')));

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
    paths = io_init_paths(cfg);

    % SLR filenames usually do not contain "GSM" token.
    if ~isfield(cfg, 'time') || ~isstruct(cfg.time)
        cfg.time = struct();
    end
    cfg.time.product_type = '';

    T = build_time_index(cfg);
    if isfield(cfg.time, 'start_ym') && isfield(cfg.time, 'end_ym') ...
            && ~isempty(cfg.time.start_ym) && ~isempty(cfg.time.end_ym)
        try
            dt0 = datetime(cfg.time.start_ym, 'InputFormat', 'yyyy-MM');
            dt1 = datetime(cfg.time.end_ym, 'InputFormat', 'yyyy-MM');
            keep = arrayfun(@(x) x.dt >= dt0 && x.dt <= dt1, T);
            T = T(keep);
        catch
            % keep all months when user bound format is invalid
        end
    end
    if isempty(T)
        error('No months available for stack aggregation.');
    end

    [lonVec, latVec] = make_lonlat_vec(cfg);
    tags = {'SIGMA_RAW', 'SIGMA_DDK4'};

    OUT = struct();
    OUT.paths = paths;
    OUT.stacks = struct();
    OUT.time = {T.ym};

    fprintf('\n[STACK] Build sigma stacks from monthly products...\n');
    fprintf('[STACK] Output dir: %s\n', paths.stacks);
    fprintf('[STACK] Months: %d (%s -> %s)\n\n', numel(T), T(1).ym, T(end).ym);

    for i = 1:numel(tags)
        tag = tags{i};
        fprintf('[STACK] %s ... ', tag);
        Stack = main_build_stack_from_monthly(cfg, paths, tag, T, lonVec, latVec);
        if isempty(Stack) || ~isfield(Stack, 'ewh') || isempty(Stack.ewh)
            fprintf('skip (no valid monthly mats)\n');
            OUT.stacks.(tag) = struct('saved', false, 'file', '', 'nValid', 0, 'nT', numel(T));
            continue;
        end

        fp = io_save_stack(cfg, paths, Stack);
        nValid = sum(Stack.ok);
        sz = size(Stack.ewh);
        fprintf('ok | valid=%d/%d | size=[%d %d %d]\n', nValid, numel(T), sz(1), sz(2), sz(3));

        OUT.stacks.(tag) = struct();
        OUT.stacks.(tag).saved = true;
        OUT.stacks.(tag).file = fp;
        OUT.stacks.(tag).nValid = nValid;
        OUT.stacks.(tag).nT = numel(T);
        OUT.stacks.(tag).size = sz;
    end

    fprintf('\n[STACK] Done.\n');
end
