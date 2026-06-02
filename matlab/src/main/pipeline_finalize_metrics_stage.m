function OUT = pipeline_finalize_metrics_stage(cfg, paths, ACC, refTag, T, plotCfg, OUT, doMetrics)
%PIPELINE_FINALIZE_METRICS_STAGE Finalize and persist metrics outputs.

    if ~(doMetrics && ~isempty(ACC))
        return;
    end

    OUTmetrics = struct();
    OUTmetrics.ACC = metrics_finalize(ACC);
    OUTmetrics.refTag = refTag;
    OUTmetrics.time = [T.dt];
    io_save_metrics(cfg, paths, OUTmetrics, T);
    if isfield(cfg,'io') && isfield(cfg.io,'return_metrics') && cfg.io.return_metrics
        OUT.metrics = OUTmetrics;
    end

    if plotCfg.metrics_ts || plotCfg.metrics_maps
        pipeline_plot_metrics_outputs(paths, OUTmetrics, plotCfg);
    end
end
