function result = pipeline_process_month(cfg, ctx, Tk)
%PIPELINE_PROCESS_MONTH Shared month worker used by serial and parfor runs.

    state = pipeline_prepare_month_input( ...
        cfg, ctx.paths, ctx.plan, Tk, ctx.lonVec, ctx.latVec, ...
        ctx.refTag, ctx.doMetrics, ctx.refOutput, ctx.skipExisting);

    Products = pipeline_load_or_compute_month( ...
        cfg, ctx.paths, ctx.plan, Tk, ctx.syn, ctx.meanSH, ...
        ctx.lonVec, ctx.latVec, state.cacheHit);

    Products = pipeline_attach_reference_and_gwsa( ...
        cfg, Products, state, Tk, ctx.lonVec, ctx.latVec, ctx.refTag);

    Products = pipeline_save_month_outputs( ...
        cfg, ctx.paths, ctx.plan, Products, ctx.lonVec, ctx.latVec, ...
        ctx.refTag, ctx.refOutput);

    if ctx.leakEnable
        Products = pipeline_apply_month_leakage( ...
            cfg, ctx.paths, Products, ctx.basin.mask, ctx.lonVec, ctx.latVec);
    end

    result = struct();
    result.Products = Products;
    result.refOk = state.refOk;
    result.refMonth = state.refMonth;
    result.cacheHit = state.cacheHit;
end
