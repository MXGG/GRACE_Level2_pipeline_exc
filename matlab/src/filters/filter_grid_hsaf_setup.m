function ctx = filter_grid_hsaf_setup(EWH, lonVec, latVec, cfg_hankel, grid_dlon)
%FILTER_GRID_HSAF_SETUP Prepare the runtime context for HSAF filtering.

    if nargin < 5 || isempty(grid_dlon)
        grid_dlon = mean(diff(lonVec));
    end
    if nargin < 4 || isempty(cfg_hankel)
        cfg_hankel = struct();
    end
    if ~isfield(cfg_hankel, 'params') || isempty(cfg_hankel.params)
        cfg_hankel.params = struct();
    end

    deps = struct();
    deps.HSA = (exist('HSA', 'file') == 2);
    deps.H_RCs = (exist('H_RCs', 'file') == 2);

    variant = normalize_hsaf_variant(getfield_default(cfg_hankel, 'variant', 'global'));
    if strcmpi(variant, 'adaptive')
        if ~isfield(cfg_hankel, 'adaptive') || isempty(cfg_hankel.adaptive)
            warning('HSAF:NoAdaptiveConfig', ...
                ['Adaptive mode selected but no adaptive bands were configured. ' ...
                 'Falling back to global mode.']);
            variant = 'global';
        end
    end

    if strcmpi(variant, 'global')
        if ~deps.HSA
            error(['HSAF (global) requires HSA() on path.\n' ...
                'Please add your HSAF core toolbox to MATLAB path via setup_env.\n']);
        end
    else
        if ~deps.H_RCs
            error(['HSAF (adaptive) requires H_RCs() on path.\n' ...
                'Please add your HSAF core toolbox to MATLAB path via setup_env.\n']);
        end
    end

    defaults = struct('N', 30, 'P', 10, 'K', 6, 'J', 1, 'iterations', 1);
    baseParams = normalize_hsaf_params(cfg_hankel.params, defaults);

    legacyDefaults = struct('p', 60, 'k', 30, 'wl_band_deg', [5, 60]);
    baseLegacy = struct();
    baseLegacy.p = getfield_default(cfg_hankel.params, 'p', legacyDefaults.p);
    baseLegacy.k = getfield_default(cfg_hankel.params, 'K', legacyDefaults.k);
    baseLegacy.wl_band_deg = getfield_default(cfg_hankel.params, 'wl_band_deg', legacyDefaults.wl_band_deg);

    baseLegacy.opt = struct();
    baseLegacy.opt = set_default(baseLegacy.opt, 'detrend_mode', 'mean');
    baseLegacy.opt = set_default(baseLegacy.opt, 'taper_alpha', 0.0);
    baseLegacy.opt = set_default(baseLegacy.opt, 'protect_wl_gt_deg', inf);
    baseLegacy.opt = set_default(baseLegacy.opt, 'force_conjugate_pairs', true);
    baseLegacy.opt = set_default(baseLegacy.opt, 'min_mode_energy_ratio', 0);
    baseLegacy.opt = set_default(baseLegacy.opt, 'use_sliding', true);
    baseLegacy.opt = set_default(baseLegacy.opt, 'win_min', 60);
    baseLegacy.opt = set_default(baseLegacy.opt, 'win_overlap', 0.90);
    baseLegacy.opt = set_default(baseLegacy.opt, 'step', []);
    baseLegacy.opt = set_default(baseLegacy.opt, 'ola_window', 'hann');
    baseLegacy.opt = set_default(baseLegacy.opt, 'ola_tukey_alpha', 0.25);
    baseLegacy.opt = set_default(baseLegacy.opt, 'p_cap_ratio', 1/3);
    baseLegacy.opt = set_default(baseLegacy.opt, 'p_min_win', 24);
    baseLegacy.opt = set_default(baseLegacy.opt, 'k_per_window', false);
    baseLegacy.opt = set_default(baseLegacy.opt, 'k_energy', 0.95);
    baseLegacy.opt = set_default(baseLegacy.opt, 'k_min', 6);
    baseLegacy.opt = set_default(baseLegacy.opt, 'k_max', 28);
    baseLegacy.opt = set_default(baseLegacy.opt, 'circular', true);
    baseLegacy.opt = set_default(baseLegacy.opt, 'pair_tol', 0.01);
    baseLegacy.opt = set_default(baseLegacy.opt, 'win_len', []);

    EWH = ensure_latlon_order(EWH, lonVec, latVec);
    szEWH = size(EWH);
    is3 = numel(szEWH) == 3 && szEWH(3) > 1;
    if is3
        Nt = szEWH(3);
    else
        Nt = 1;
    end

    useParallel = false;
    if isfield(cfg_hankel, 'parallel') && isfield(cfg_hankel.parallel, 'enable')
        useParallel = logical(cfg_hankel.parallel.enable);
    else
        try
            useParallel = ~isempty(gcp('nocreate'));
        catch
            useParallel = false;
        end
    end

    logProgress = false;
    if isfield(cfg_hankel, 'log_progress')
        logProgress = logical(cfg_hankel.log_progress);
    end

    ctx = struct();
    ctx.cfg_hankel = cfg_hankel;
    ctx.variant = variant;
    ctx.dependency = deps;
    ctx.baseParams = baseParams;
    ctx.baseLegacy = baseLegacy;
    ctx.EWH = EWH;
    ctx.lonVec = lonVec;
    ctx.latVec = latVec;
    ctx.Ts = grid_dlon;
    ctx.is3 = is3;
    ctx.Nt = Nt;
    ctx.useParallel = useParallel;
    ctx.logProgress = logProgress;
    ctx.stats = struct('processed_maps', 0, 'failed_maps', 0, ...
        'processed_profiles', 0, 'failed_profiles', 0, 'components_removed', 0);
    ctx.info = struct('dependency', deps, 'used', struct());
end

function params = normalize_hsaf_params(inParams, defaults)
    params = defaults;
    if isempty(inParams)
        return;
    end
    params.N = get_first_field(inParams, {'N', 'n', 'window_size', 'window'}, defaults.N);
    params.P = get_first_field(inParams, {'P', 'p'}, defaults.P);
    params.K = get_first_field(inParams, {'K', 'k', 'order'}, defaults.K);
    params.J = get_first_field(inParams, {'J', 'j', 'buffer'}, defaults.J);
    params.iterations = get_first_field(inParams, {'iterations', 'iter', 'n_iter', 'niter'}, defaults.iterations);
end

function v = get_first_field(S, names, defaultVal)
    v = defaultVal;
    for i = 1:numel(names)
        name = names{i};
        if isfield(S, name) && ~isempty(S.(name))
            v = S.(name);
            return;
        end
    end
end

function v = getfield_default(S, name, defaultVal)
    if isfield(S, name) && ~isempty(S.(name))
        v = S.(name);
    else
        v = defaultVal;
    end
end

function opt = set_default(opt, name, val)
    if ~isfield(opt, name) || isempty(opt.(name))
        opt.(name) = val;
    end
end

function out = normalize_hsaf_variant(raw)
    if nargin < 1 || isempty(raw)
        out = 'global';
        return;
    end
    if isstring(raw)
        key = char(raw);
    else
        key = raw;
    end
    key = lower(strtrim(key));
    key = strrep(key, '-', '_');
    switch key
        case {'adaptive', 'lat_adaptive', 'latitude_adaptive', 'adaptive_lat', 'latitude'}
            out = 'adaptive';
        otherwise
            out = 'global';
    end
end
