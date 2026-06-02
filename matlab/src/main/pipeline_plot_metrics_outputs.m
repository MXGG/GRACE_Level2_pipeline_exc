function pipeline_plot_metrics_outputs(paths, OUTmetrics, plotCfg)
%PIPELINE_PLOT_METRICS_OUTPUTS Plot metric quicklooks with guarded failures.

    if plotCfg.metrics_ts
        try
            plot_metrics_timeseries(paths, OUTmetrics);
        catch ME
            warning('Failed plotting metrics time series: %s', ME.message);
        end
    end
    if plotCfg.metrics_maps
        try
            plot_metrics_srmse_maps(paths, OUTmetrics);
        catch ME
            warning('Failed plotting metrics maps: %s', ME.message);
        end
    end
end
