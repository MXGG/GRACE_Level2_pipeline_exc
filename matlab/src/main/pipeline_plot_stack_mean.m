function pipeline_plot_stack_mean(paths, tag, Stack, lonVec, latVec, basin, plotCfg)
%PIPELINE_PLOT_STACK_MEAN Plot stack mean quicklooks.

    if ~isfield(Stack, 'ewh') || isempty(Stack.ewh)
        return;
    end
    meanMap = mean(Stack.ewh, 3, 'omitnan') / 10;
    meanMap = ensure_latlon_order(meanMap, lonVec, latVec);
    useAuto = false;
    if isfield(plotCfg,'auto_caxis_mean') && plotCfg.auto_caxis_mean
        useAuto = true;
    else
        vals = meanMap(isfinite(meanMap));
        if ~isempty(vals)
            rangeVal = max(vals) - min(vals);
            if rangeVal < 0.2 * diff(plotCfg.caxis.ewh) / 10
                useAuto = true;
            end
        end
    end
    if useAuto
        fig = plot_map_global(meanMap, lonVec, latVec, struct( ...
            'title', sprintf('%s mean', tag), ...
            'auto_caxis', true, ...
            'auto_caxis_prc', plotCfg.auto_caxis_prc, ...
            'cbar_label', 'EWH (cm)', ...
            'boundary', plotCfg.boundary, ...
            'colormap', plotCfg.cmap.ewh));
    else
        fig = plot_map_global(meanMap, lonVec, latVec, struct( ...
            'title', sprintf('%s mean', tag), ...
            'caxis', plotCfg.caxis.ewh / 10, ...
            'cbar_label', 'EWH (cm)', ...
            'boundary', plotCfg.boundary, ...
            'colormap', plotCfg.cmap.ewh));
    end
    outPng = fullfile(paths.plots, sprintf('stack_mean_%s.png', tag));
    saveas(fig, outPng);
    close(fig);

    if basin.enable
        try
            Gm = meanMap;
            Gm(~basin.mask) = NaN;
            if useAuto
                fig2 = plot_map_basin(Gm, lonVec, latVec, basin.B, struct( ...
                    'title', sprintf('%s mean (%s)', tag, basin.name), ...
                    'auto_caxis', true, ...
                    'auto_caxis_prc', plotCfg.auto_caxis_prc, ...
                    'colormap', plotCfg.cmap.ewh));
            else
                fig2 = plot_map_basin(Gm, lonVec, latVec, basin.B, struct( ...
                    'title', sprintf('%s mean (%s)', tag, basin.name), ...
                    'caxis', plotCfg.caxis.ewh / 10, ...
                    'colormap', plotCfg.cmap.ewh));
            end
            outDir = fullfile(paths.basin, basin.name);
            ensure_dir(outDir);
            outPng2 = fullfile(outDir, sprintf('stack_mean_%s_%s.png', tag, basin.name));
            saveas(fig2, outPng2);
            close(fig2);
        catch
        end
    end
end
