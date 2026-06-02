function plot_metrics_srmse_maps(paths, OUTmetrics)
%PLOT_METRICS_SRMSE_MAPS Save SRMSE maps for each method.

    if ~isfield(OUTmetrics, 'ACC') || ~isfield(OUTmetrics.ACC, 'srmse')
        return;
    end

    srmse = OUTmetrics.ACC.srmse;
    methods = fieldnames(srmse);
    if isempty(methods)
        return;
    end

    lon = OUTmetrics.ACC.lon;
    lat = OUTmetrics.ACC.lat;

    for i = 1:numel(methods)
        method = methods{i};
        fig = plot_map_global(srmse.(method), lon, lat, struct('title', sprintf('SRMSE %s', method)));
        outPng = fullfile(paths.plots, sprintf('metrics_srmse_%s.png', method));
        saveas(fig, outPng);
        close(fig);
    end
end
