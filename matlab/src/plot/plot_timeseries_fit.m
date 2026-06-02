function [fig, ax] = plot_timeseries_fit(t, y, Fit, opt)
%PLOT_TIMESERIES_FIT Plot time series + fitted curve + residual.
% Fit: output of basin_fit_seasonal_trend

    if nargin < 4; opt = struct(); end
    if ~isfield(opt,'title'); opt.title = 'Time series'; end

    fig = figure('Color','w');
    tiledlayout(fig,2,1,'TileSpacing','compact','Padding','compact');

    ax1 = nexttile(fig,1); hold(ax1,'on'); box(ax1,'on'); grid(ax1,'on');
    plot(ax1, t, y, '-');
    if isfield(Fit,'yfit')
        plot(ax1, t, Fit.yfit, '--', 'LineWidth', 1.5);
        legend(ax1, {'Obs','Fit'}, 'Location','best');
    end
    title(ax1, opt.title, 'Interpreter','none');
    ylabel(ax1, 'mmEWH');

    ax2 = nexttile(fig,2); hold(ax2,'on'); box(ax2,'on'); grid(ax2,'on');
    if isfield(Fit,'res')
        plot(ax2, t, Fit.res, '-');
        yline(ax2, 0, ':');
    end
    ylabel(ax2,'Residual'); xlabel(ax2,'Time');

    ax = [ax1, ax2];
end
