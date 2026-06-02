function pipeline_plot_stack_trend_amp(paths, tag, Stack, lonVec, latVec, plotCfg)
%PIPELINE_PLOT_STACK_TREND_AMP Plot trend and annual amplitude quicklooks.

    if ~isfield(Stack, 'ewh') || isempty(Stack.ewh)
        return;
    end
    if ~isfield(Stack, 't') || isempty(Stack.t)
        return;
    end

    grid = ensure_latlon_order(Stack.ewh, lonVec, latVec);
    t = Stack.t;
    if iscell(t)
        t = datetime(t, 'InputFormat', 'yyyy-MM');
    end

    [trendMap, ampMap] = pipeline_trend_amp_maps(grid, t);

    fig1 = plot_map_global(trendMap, lonVec, latVec, struct( ...
        'title', sprintf('%s trend', tag), ...
        'caxis', plotCfg.caxis.trend, ...
        'cbar_label', 'mm/yr', ...
        'boundary', plotCfg.boundary, ...
        'colormap', plotCfg.cmap.trend));
    outPng1 = fullfile(paths.plots, sprintf('stack_trend_%s.png', tag));
    saveas(fig1, outPng1);
    close(fig1);

    fig2 = plot_map_global(ampMap, lonVec, latVec, struct( ...
        'title', sprintf('%s amplitude', tag), ...
        'caxis', plotCfg.caxis.amp, ...
        'cbar_label', 'mm', ...
        'boundary', plotCfg.boundary, ...
        'colormap', plotCfg.cmap.amp));
    outPng2 = fullfile(paths.plots, sprintf('stack_amp_%s.png', tag));
    saveas(fig2, outPng2);
    close(fig2);
end
