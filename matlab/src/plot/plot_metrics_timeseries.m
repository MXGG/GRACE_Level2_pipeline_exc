function plot_metrics_timeseries(paths, OUTmetrics)
%PLOT_METRICS_TIMESERIES Save summary time-series plots for metrics.

    if ~isfield(OUTmetrics, 'ACC') || ~isfield(OUTmetrics.ACC, 'ts')
        return;
    end

    ts = OUTmetrics.ACC.ts;
    methods = fieldnames(ts);
    if isempty(methods)
        return;
    end

    if isfield(OUTmetrics, 'time') && ~isempty(OUTmetrics.time)
        t = OUTmetrics.time;
    else
        t = 1:numel(ts.(methods{1}).CC);
    end

    metrics = {'CC','RMSE','MAE'};
    fig = figure('Color','w');

    for i = 1:numel(metrics)
        metric = metrics{i};
        ax = subplot(numel(metrics), 1, i);
        hold(ax, 'on');
        for m = 1:numel(methods)
            method = methods{m};
            if isfield(ts.(method), metric)
                plot(ax, t, ts.(method).(metric), 'DisplayName', method);
            end
        end
        grid(ax, 'on');
        ylabel(ax, metric);
        if i == 1
            title(ax, 'Metrics time series');
        end
        if i == numel(metrics)
            xlabel(ax, 'Time');
            legend(ax, 'Location', 'best');
        end
    end

    outPng = fullfile(paths.plots, 'metrics_timeseries.png');
    saveas(fig, outPng);
    close(fig);
end
