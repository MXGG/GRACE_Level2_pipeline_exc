function OUT = run_leakage_only(cfg)
%RUN_LEAKAGE_ONLY Apply leakage correction + basin stats using existing products.
%
% This function does not recompute inversion/filters. It loads monthly
% products from disk, applies leakage correction (FM/SF), saves corrected
% monthly products, and outputs basin time series for available tags.

    fprintf('\n');
    fprintf('================================================================\n');
    fprintf('  GRACE Leakage-Only Pipeline\n');
    fprintf('  Started: %s\n', datestr(now, 'yyyy-mm-dd HH:MM:SS'));
    fprintf('================================================================\n');

    paths = io_init_paths(cfg);
    io_log_run(paths, 'Leakage-only pipeline started');

    T = build_time_index(cfg);
    [lonVec, latVec] = make_lonlat_vec(cfg);
    Nt = numel(T);

    OUT = struct('paths', paths, 'T', T);

    sourcePaths = paths;
    inputRoot = '';
    if isfield(cfg,'io') && isfield(cfg.io,'input_root') && ~isempty(cfg.io.input_root)
        inputRoot = char(cfg.io.input_root);
    end
    if isempty(inputRoot) || strcmpi(inputRoot, 'AUTO')
        inputRoot = find_latest_input_root(cfg.path.OUTPUT);
    end
    if ~isempty(inputRoot)
        sourcePaths = build_paths_from_root(inputRoot);
        fprintf('[INPUT] Using existing products from: %s\n', sourcePaths.root);
    end

    basin = struct('enable', false);
    if isfield(cfg,'basin') && isfield(cfg.basin,'boundary_file') && isfile(cfg.basin.boundary_file)
        basin.enable = true;
        basin.boundary_file = cfg.basin.boundary_file;
        basin.name = main_infer_basin_name(cfg.basin.boundary_file);
        basin.B = basin_read_boundary(basin.boundary_file);
        basin.mask = basin_make_mask(lonVec, latVec, basin.B);
        fprintf('[BASIN] Enabled: %s\n', basin.name);
    end

    leakEnable = isfield(cfg,'leakage') && isfield(cfg.leakage,'enable') && cfg.leakage.enable;
    if ~leakEnable
        error('Leakage-only pipeline requires cfg.leakage.enable = true.');
    end
    if ~basin.enable
        error('Leakage-only pipeline requires cfg.basin.boundary_file.');
    end
    if ~isfield(cfg.leakage,'apply_to') || isempty(cfg.leakage.apply_to)
        error('Leakage-only pipeline requires cfg.leakage.apply_to.');
    end

    tags = cfg.leakage.apply_to;
    if ischar(tags)
        tags = {tags};
    end

    mode = 'SF';
    if isfield(cfg.leakage,'method') && ~isempty(cfg.leakage.method)
        mode = cfg.leakage.method;
    end

    fprintf('[LEAKAGE] Mode=%s; tags=%s\n', mode, strjoin(tags, ','));

    parfor k = 1:Nt
        Tk = T(k);
        Products = struct();
        for i = 1:numel(tags)
            tag = tags{i};
            fp = io_find_product_mat(sourcePaths, tag, Tk);
            if ~isfile(fp)
                continue;
            end
            try
                P = io_load_product_mat(fp);
                P = io_standardize_product(P, lonVec, latVec);
                Products.(tag) = P;
            catch
                warning('Leakage-only: failed to load %s for %s.', tag, Tk.ym);
            end
        end

        if isempty(fieldnames(Products))
            continue;
        end

        for i = 1:numel(tags)
            tag0 = tags{i};
            if ~isfield(Products, tag0)
                continue;
            end
            P0 = Products.(tag0);
            Pwrap = struct();
            Pwrap.(tag0) = P0;
            OUTleak = leakage_correct_products(cfg, Pwrap, tag0, basin.mask, lonVec, latVec, mode);

            tagNew = [tag0 '_' upper(mode)];
            if isfield(OUTleak.ProductsCorr, tagNew)
                P2 = io_standardize_product(OUTleak.ProductsCorr.(tagNew), lonVec, latVec);
                io_save_product(cfg, paths, P2);
            end
        end
    end

    % Basin time series for available tags (original + leakage-corrected)
    fprintf('\n[BASIN] Extracting basin time series...\n');
    tagsAll = list_monthly_tags(sourcePaths.monthly_mat);
    for i = 1:numel(tagsAll)
        tag = tagsAll{i};
        Stack = main_build_stack_from_monthly(cfg, sourcePaths, tag, T, lonVec, latVec);
        if isempty(Stack) || ~isfield(Stack,'ewh')
            continue;
        end
        ts = basin_mean_ts(double(Stack.ewh), basin.mask, latVec, true);
        Fit = basin_fit_seasonal_trend(ts, [T.dt]);
        io_save_basin_result(cfg, paths, basin.name, tag, T, ts, Fit, basin.mask);
        clear Stack ts Fit;
    end
end

function tags = list_monthly_tags(dirPath)
    tags = {};
    if ~isfolder(dirPath)
        return;
    end
    d = dir(dirPath);
    for i = 1:numel(d)
        if d(i).isdir && ~ismember(d(i).name, {'.','..'})
            tags{end+1} = d(i).name; %#ok<AGROW>
        end
    end
end

function paths = build_paths_from_root(rootDir)
    paths = struct();
    paths.root = rootDir;
    paths.monthly_mat = fullfile(rootDir, 'monthly_mat');
    paths.monthly_txt = fullfile(rootDir, 'monthly_txt');
    paths.stacks      = fullfile(rootDir, 'stacks');
    paths.metrics     = fullfile(rootDir, 'metrics');
    paths.metrics_ts  = fullfile(rootDir, 'metrics', 'timeseries');
    paths.basin       = fullfile(rootDir, 'basin');
    paths.plots       = fullfile(rootDir, 'plots');
    paths.logs        = fullfile(rootDir, 'logs');
    paths.tmp         = fullfile(rootDir, 'tmp');
    paths.cache       = fullfile(rootDir, 'CACHE');
end

function rootDir = find_latest_input_root(outputRoot)
    rootDir = '';
    if isempty(outputRoot)
        return;
    end

    % Prefer the most recent remote job output.
    remoteDir = fullfile(outputRoot, 'remote');
    if isfolder(remoteDir)
        jobDirs = dir(remoteDir);
        jobDirs = jobDirs([jobDirs.isdir]);
        jobDirs = jobDirs(~ismember({jobDirs.name}, {'.','..'}));
        if ~isempty(jobDirs)
            slurmJob = getenv('SLURM_JOB_ID');
            jobDirs = jobDirs(~strcmp({jobDirs.name}, slurmJob));
            valid = false(1, numel(jobDirs));
            for i = 1:numel(jobDirs)
                cand = fullfile(remoteDir, jobDirs(i).name);
                valid(i) = has_monthly_products(cand);
            end
            jobDirs = jobDirs(valid);
            if ~isempty(jobDirs)
                [~, idx] = max([jobDirs.datenum]);
                rootDir = fullfile(remoteDir, jobDirs(idx).name);
                return;
            end
        end
    end

    % Fallback to local output.
    localDir = fullfile(outputRoot, 'local');
    if isfolder(localDir) && has_monthly_products(localDir)
        rootDir = localDir;
    end
end

function tf = has_monthly_products(rootDir)
    tf = false;
    if isempty(rootDir)
        return;
    end
    monthlyDir = fullfile(rootDir, 'monthly_mat');
    if ~isfolder(monthlyDir)
        return;
    end
    d = dir(fullfile(monthlyDir, '*', '*.mat'));
    tf = ~isempty(d);
end
