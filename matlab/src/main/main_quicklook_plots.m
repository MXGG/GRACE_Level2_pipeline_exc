function main_quicklook_plots(cfg, paths, Products, Tk, lonVec, latVec, basin)
%MAIN_QUICKLOOK_PLOTS Lightweight plotting for quick QA.

    try
        % choose a primary map to plot
        tag = 'HSAF';
        if ~isfield(Products,'HSAF'); tag = 'RAW'; end
        if ~isfield(Products,tag); return; end

        G = Products.(tag).grid.ewh;
        cax = [];
        if isfield(cfg,'plot') && isfield(cfg.plot,'caxis') && isfield(cfg.plot.caxis,'ewh')
            cax = cfg.plot.caxis.ewh;
        end
        [fig, ~] = plot_map_global(G, lonVec, latVec, struct( ...
            'title', sprintf('%s %s', tag, Tk.ym), ...
            'caxis', cax, ...
            'cbar_label', 'EWH (mm)'));
        outDir = fullfile(paths.plots, 'monthly');
        ensure_dir(outDir);
        outPng = fullfile(outDir, sprintf('%s_%s.png', tag, Tk.yyyymm));
        saveas(fig, outPng);
        close(fig);

        if basin.enable
            Gm = G;
            Gm(~basin.mask) = NaN;
            [fig2, ~] = plot_map_basin(Gm, lonVec, latVec, basin.B, struct( ...
                'title', sprintf('%s %s (%s)', tag, Tk.ym, basin.name), ...
                'caxis', cax));
            outDir2 = fullfile(paths.basin, basin.name);
            ensure_dir(outDir2);
            outPng2 = fullfile(outDir2, sprintf('%s_%s_%s.png', tag, basin.name, Tk.yyyymm));
            saveas(fig2, outPng2);
            close(fig2);
        end
    catch
        % plotting is best-effort
    end
end
