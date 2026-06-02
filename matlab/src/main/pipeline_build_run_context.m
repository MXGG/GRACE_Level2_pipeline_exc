function ctx = pipeline_build_run_context(cfg)
%PIPELINE_BUILD_RUN_CONTEXT Build the immutable run context for run_pipeline.

    ctx = struct();

    ctx.paths = io_init_paths(cfg);
    io_log_run(ctx.paths, 'Pipeline started');

    ctx.plan = compute_plan(cfg);
    ctx.T = build_time_index(cfg);
    [ctx.lonVec, ctx.latVec] = make_lonlat_vec(cfg);
    ctx.Nt = numel(ctx.T);

    ctx.useParfor = isfield(cfg,'parallel') && isfield(cfg.parallel,'enable') && cfg.parallel.enable;

    perfCfg = struct('enable', true, 'show', true, 'min_seconds', 0);
    if isfield(cfg, 'perf')
        perfCfg = merge_struct_local(perfCfg, cfg.perf);
    end
    if ctx.useParfor
        perfCfg.enable = false;
        perfCfg.show = false;
    end
    ctx.perf = perf_tracker('create', perfCfg);
    ctx.pipelineTimer = tic;

    ctx.plotCfg = get_plot_cfg(cfg);
    ctx.plotCfg.boundary = load_boundary_overlay(cfg);
    ctx.syn = inv_prepare_synthesis(cfg);

    ctx.meanSH = [];
    if isfield(cfg,'inversion') && isfield(cfg.inversion,'remove_mean') && cfg.inversion.remove_mean
        fprintf('[INV] Computing/Loading mean SH...\n');
        ctx.meanSH = inv_get_mean_sh(cfg, ctx.T);
    end

    ctx.landMask = main_try_load_landmask(cfg, ctx.lonVec, ctx.latVec);
    ctx.refTag = 'Mascon';

    ctx.doMetrics = true;
    if isfield(cfg,'metrics') && isfield(cfg.metrics,'enable')
        ctx.doMetrics = cfg.metrics.enable;
    end
    if isfield(cfg,'filter') && isfield(cfg.filter,'hankel') && isfield(cfg.filter.hankel,'stack_mode') && cfg.filter.hankel.stack_mode
        ctx.doMetrics = false;
    end

    ctx.refOutput = true;
    if isfield(cfg,'reference') && isfield(cfg.reference,'export')
        ctx.refOutput = cfg.reference.export;
    end

    if ctx.useParfor && ctx.doMetrics
        warning('Metrics disabled in parfor month loop.');
        ctx.doMetrics = false;
    end

    ctx.methodsForMetrics = ctx.plan.order;
    if ctx.doMetrics
        ctx.ACC = metrics_acc_init(ctx.methodsForMetrics, ctx.lonVec, ctx.latVec, ctx.Nt);
    else
        ctx.ACC = [];
    end

    ctx.refMissingMonths = {};
    ctx.refAvailableCount = 0;

    ctx.basin = struct('enable', false);
    if isfield(cfg,'basin') && isfield(cfg.basin,'boundary_file') && isfile(cfg.basin.boundary_file)
        ctx.basin.enable = true;
        ctx.basin.boundary_file = cfg.basin.boundary_file;
        ctx.basin.name = main_infer_basin_name(cfg.basin.boundary_file);
        ctx.basin.B = basin_read_boundary(ctx.basin.boundary_file);
        ctx.basin.mask = basin_make_mask(ctx.lonVec, ctx.latVec, ctx.basin.B);
        fprintf('[BASIN] Enabled: %s\n', ctx.basin.name);
    end

    ctx.leakEnable = isfield(cfg,'leakage') && isfield(cfg.leakage,'enable') && cfg.leakage.enable;
    if ctx.leakEnable && ~ctx.basin.enable
        warning('Leakage enabled but basin boundary not provided. Leakage will be skipped.');
        ctx.leakEnable = false;
    end

    ctx.resumeEnable = isfield(cfg,'io') && isfield(cfg.io,'resume') && cfg.io.resume;
    ctx.skipExisting = ctx.resumeEnable;
    ctx.startIdx = 1;

    if ctx.useParfor && ctx.resumeEnable
        warning('Resume disabled in parfor month loop.');
        ctx.resumeEnable = false;
        ctx.skipExisting = false;
    end

    if ctx.resumeEnable
        checkpoint = checkpoint_manager('load', ctx.paths, cfg, ctx.plan, ctx.T);
        fprintf('[CHECKPOINT] %s\n', checkpoint.message);
        if ~checkpoint.is_valid
            checkpoint_manager('clear', ctx.paths);
            ctx.skipExisting = false;
            ctx.startIdx = 1;
        elseif checkpoint.has_state && checkpoint.start_idx > 1
            if checkpoint.last_complete >= 1
                outputsOk = checkpoint_manager('verify', ctx.paths, cfg, ctx.plan, ctx.T, checkpoint.last_complete);
                if ~outputsOk
                    fprintf('[CHECKPOINT] Missing cached outputs. Starting fresh.\n');
                    checkpoint_manager('clear', ctx.paths);
                    ctx.skipExisting = false;
                    checkpoint.start_idx = 1;
                end
            end
            ctx.startIdx = checkpoint.start_idx;
        else
            ctx.skipExisting = false;
        end
    else
        checkpoint_manager('clear', ctx.paths);
        ctx.skipExisting = false;
    end
end

function out = merge_struct_local(base, override)
    out = base;
    if isempty(override); return; end
    f = fieldnames(override);
    for i = 1:numel(f)
        out.(f{i}) = override.(f{i});
    end
end
