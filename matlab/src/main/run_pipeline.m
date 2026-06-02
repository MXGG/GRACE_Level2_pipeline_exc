function OUT = run_pipeline(cfg)
%RUN_PIPELINE Full GRACE Level-2 processing chain (one-click).
% Steps:
%   1) Build time index
%   2) Inversion: read GSM -> low-degree replace -> remove mean -> synthesize RAW
%   3) Spectral filters: GAUSS / P4M6 / FAN / DDK / combos
%   4) HSAF (grid-domain) using cfg.filter.pre_hankel_input
%   5) Monthly saving (MAT + optional TXT) via io/
%   6) Metrics vs reference (default: Mascon, if available)
%   7) Basin: mask -> basin TS -> seasonal+trend fit
%   8) Leakage correction (optional): FM / SF
%   9) Quicklook plots (optional)

    clc;
    warning('off','verbose');
    
    % Print banner
    fprintf('\n');
    fprintf('================================================================\n');
    fprintf('  GRACE Level-2 Modular Pipeline\n');
    fprintf('  Started: %s\n', datestr(now, 'yyyy-mm-dd HH:MM:SS'));
    fprintf('================================================================\n');

    if isfield(cfg,'leakage') && isfield(cfg.leakage,'enable') && cfg.leakage.enable ...
            && (~isfield(cfg.leakage,'apply_to') || isempty(cfg.leakage.apply_to))
        cfg.leakage.apply_to = {'HSAF'};
    end

    ctx = pipeline_build_run_context(cfg);
    paths = ctx.paths;
    plan = ctx.plan;
    T = ctx.T;
    lonVec = ctx.lonVec;
    latVec = ctx.latVec;
    Nt = ctx.Nt;
    useParfor = ctx.useParfor;
    perf = ctx.perf;
    plotCfg = ctx.plotCfg;
    refTag = ctx.refTag;
    refOutput = ctx.refOutput;
    doMetrics = ctx.doMetrics;
    ACC = ctx.ACC;
    basin = ctx.basin;
    startIdx = ctx.startIdx;
    refMissingMonths = {};
    refAvailableCount = 0;

    OUT = struct('paths', paths, 'plan', plan, 'T', T);

    fprintf('[TIME] %s -> %s  (Nt=%d)\n', T(1).ym, T(end).ym, Nt);
    fprintf('[PLAN] order = %s\n', strjoin(plan.order, ' -> '));
    pipeline_write_hsaf_strategy(paths, cfg, plan);

    if doMetrics && startIdx > 1
        ACC = prefill_metrics_from_cache(cfg, paths, plan, T, lonVec, latVec, ctx.landMask, ACC, startIdx-1, refTag);
    end

    if ~useParfor
        % Initialize Progress Bar
        pb = progress_bar('create', Nt, 'Tag', 'Pipeline');
        if startIdx > 1
            pb = progress_bar('update', pb, startIdx-1, 'substep', 'Resuming...');
        end
    else
        pb = [];
    end

    if useParfor
        refOkVec = false(1, Nt);
        refMissingMonths = cell(1, Nt);
        parfor k = startIdx:Nt
            Tk = T(k);
            result = pipeline_process_month(cfg, ctx, Tk);
            refOkVec(k) = result.refOk;
            if ~result.refOk && ~isempty(result.refMonth)
                refMissingMonths{k} = result.refMonth;
            end
            pipeline_finalize_month(cfg, paths, plotCfg, result.Products, Tk, lonVec, latVec, basin, false, plan, T, k);
        end

        refAvailableCount = sum(refOkVec);
        refMissingMonths = refMissingMonths(~cellfun('isempty', refMissingMonths));
    else
    for k = startIdx:Nt
        Tk = T(k);
        % fprintf('\n[MONTH %4d/%4d] %s\n', k, Nt, Tk.ym); % Replaced by progress bar
        monthTimer = tic;
        substepPrefix = sprintf('%s', Tk.ym);
        pb = progress_bar('update', pb, k-1, 'substep', [substepPrefix ': Start']);

        pb = progress_bar('update', pb, k-1, 'substep', [substepPrefix ': Load Ref']);
        tProcess = tic;
        result = pipeline_process_month(cfg, ctx, Tk);
        perf = perf_tracker('add', perf, 'Month I/O+Compute', toc(tProcess));
        Products = result.Products;
        refOk = result.refOk;
        if refOk
            refAvailableCount = refAvailableCount + 1;
        elseif ~isempty(result.refMonth)
            refMissingMonths{end+1} = result.refMonth; %#ok<AGROW>
        end

        if doMetrics && refOk
            pb = progress_bar('update', pb, k-1, 'substep', [substepPrefix ': Metrics']);
            tMetrics = tic;
            [Products, ACC] = pipeline_eval_month_metrics(cfg, Products, ACC, k, Tk, refTag, lonVec, latVec, ctx.landMask);
            perf = perf_tracker('add', perf, 'Metrics', toc(tMetrics));
        elseif doMetrics && ~refOk
            if k == 1
                warning('Mascon reference not found. Metrics will be skipped (unless you provide cfg.reference.*).');
            end
        end

        pipeline_finalize_month(cfg, paths, plotCfg, Products, Tk, lonVec, latVec, basin, ctx.resumeEnable, plan, T, k);

        perf = perf_tracker('add', perf, 'Month', toc(monthTimer));
        pb = progress_bar('update', pb, k, 'substep', [substepPrefix ': Done']);

        % Release large per-month variables after outputs are written.
        Products = struct();
        
        % MEMORY OPTIMIZATION: Force garbage collection every 20 months
        if mod(k, 20) == 0
            pause(0.05);  % Brief pause to allow memory cleanup
        end
    end
    progress_bar('finish', pb);
    perf = perf_tracker('finish', perf);
    end

    % Report reference data coverage
    if doMetrics || refOutput
        fprintf('\n[REFERENCE] GSM months: %d, Reference available: %d, Missing: %d\n', ...
            Nt, refAvailableCount, numel(refMissingMonths));
        if ~isempty(refMissingMonths)
            fprintf('[REFERENCE] Missing months: %s\n', strjoin(refMissingMonths, ', '));
        end
    end

    OUT = pipeline_finalize_metrics_stage(cfg, paths, ACC, refTag, T, plotCfg, OUT, doMetrics);

    [Stacks, stackTags, wantReturnStacks, perf] = pipeline_build_stacks_stage( ...
        cfg, paths, plan, T, lonVec, latVec, basin, plotCfg, refOutput, refTag, perf);

    [Stacks, stackTags] = pipeline_run_hsaf_stack_stage(cfg, paths, plan, T, Nt, lonVec, latVec, wantReturnStacks, Stacks, stackTags);

    if wantReturnStacks
        OUT.Stacks = Stacks;
    end

    OUT = pipeline_run_basin_stage(cfg, paths, stackTags, lonVec, latVec, T, wantReturnStacks, Stacks, basin, plotCfg, OUT);

    % MEMORY OPTIMIZATION: release stack cache once all consumers are done.
    if ~wantReturnStacks
        clear Stacks;
    end

    io_log_run(paths, 'Pipeline finished');
    fprintf('\n[PIPELINE] Finished.\n');
end

function progress_step(label, k, n)
    pct = 100 * k / max(n, 1);
    fprintf('[PROGRESS] %3.0f%% %s\n', pct, label);
end

%% ========================================================================
%  DEPRECATED: resume_start_index, save_run_state, month_outputs_exist
%  These functions have been replaced by checkpoint_manager.m in src/core/
%  ========================================================================

function plotCfg = get_plot_cfg(cfg)
    plotCfg = struct( ...
        'quicklook', false, ...
        'metrics_ts', true, ...
        'metrics_maps', true, ...
        'stack_mean', true, ...
        'stack_trend_amp', true, ...
        'basin_overlay', true, ...
        'auto_caxis_mean', true, ...
        'auto_caxis_prc', [2 98], ...
        'caxis', struct('ewh', [-30 30], 'trend', [-5 5], 'amp', [-15 15]), ...
        'cmap', struct('ewh', 'jet', 'trend', 'redblue', 'amp', 'jet'));
    if isfield(cfg,'plot')
        plotCfg = merge_struct(plotCfg, cfg.plot);
    end
    if isfield(cfg,'plot') && isfield(cfg.plot,'caxis')
        if ~isfield(plotCfg.caxis,'ewh'); plotCfg.caxis.ewh = [-30 30]; end
        if ~isfield(plotCfg.caxis,'trend'); plotCfg.caxis.trend = [-5 5]; end
        if ~isfield(plotCfg.caxis,'amp'); plotCfg.caxis.amp = [-15 15]; end
    end
    if isfield(cfg,'plot') && isfield(cfg.plot,'auto_caxis_mean')
        plotCfg.auto_caxis_mean = cfg.plot.auto_caxis_mean;
    end
    if isfield(cfg,'plot') && isfield(cfg.plot,'auto_caxis_prc')
        plotCfg.auto_caxis_prc = cfg.plot.auto_caxis_prc;
    end
    if ~isfield(plotCfg,'cmap') || isempty(plotCfg.cmap)
        plotCfg.cmap = struct('ewh','jet','trend','redblue','amp','jet');
    else
        if ~isfield(plotCfg.cmap,'ewh'); plotCfg.cmap.ewh = 'jet'; end
        if ~isfield(plotCfg.cmap,'trend'); plotCfg.cmap.trend = 'redblue'; end
        if ~isfield(plotCfg.cmap,'amp'); plotCfg.cmap.amp = 'jet'; end
    end
end

function B = load_boundary_overlay(cfg)
    B = [];
    if ~isfield(cfg, 'plot') || ~isfield(cfg.plot, 'basin_overlay') || ~cfg.plot.basin_overlay
        return;
    end
    if ~isfield(cfg.path, 'BOUNDARY')
        return;
    end
    shp = fullfile(cfg.path.BOUNDARY, 'LargeBasin.shp');
    if ~isfile(shp)
        return;
    end
    try
        B = basin_read_boundary(shp);
    catch
        B = [];
    end
end

function ACC = prefill_metrics_from_cache(cfg, paths, plan, T, lonVec, latVec, landMask, ACC, lastIdx, refTag)
    if lastIdx < 1
        return;
    end
    fprintf('[RESUME] Rebuilding metrics for months 1-%d from cache...\n', lastIdx);
    for k = 1:lastIdx
        Tk = T(k);
        Products = struct();
        for ii = 1:numel(plan.order)
            tag = plan.order{ii};
            fp = io_find_product_mat(paths, tag, Tk);
            if ~isfile(fp)
                Products = struct();
                break;
            end
            Products.(tag) = io_load_product_mat(fp);
        end
        if isempty(fieldnames(Products))
            continue;
        end
        [Pref, refOk] = main_try_load_reference(cfg, Tk, lonVec, latVec);
        if refOk
            Products.(refTag) = Pref;
            [~, ACC] = metrics_eval_month(cfg, Products, ACC, k, Tk, refTag, lonVec, latVec, landMask);
        end
    end
end

function out = merge_struct(base, override)
    out = base;
    if isempty(override); return; end
    f = fieldnames(override);
    for i = 1:numel(f)
        out.(f{i}) = override.(f{i});
    end
end

