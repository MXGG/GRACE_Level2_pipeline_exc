function OUT = pipeline_run_basin_stage(cfg, paths, stackTags, lonVec, latVec, T, wantReturnStacks, Stacks, basin, plotCfg, OUT)
%PIPELINE_RUN_BASIN_STAGE Run multi-basin and single-basin post processing.

    basinAnalysisEnable = isfield(cfg,'basin') && isfield(cfg.basin,'analysis_enable') && cfg.basin.analysis_enable;
    if basinAnalysisEnable
        if exist('basin_analyze_filters', 'file') == 2
            fprintf('\n[BASIN] Running multi-basin analysis...\n');
            basinStats = basin_analyze_filters(cfg, paths, stackTags, lonVec, latVec, T);
            if ~isempty(fieldnames(basinStats.stats))
                if isfield(cfg,'io') && isfield(cfg.io,'return_basin') && cfg.io.return_basin
                    OUT.basinStats = basinStats;
                end
            end
            if ~(isfield(cfg,'io') && isfield(cfg.io,'return_basin') && cfg.io.return_basin)
                clear basinStats;
            end
        else
            warning('basin_analyze_filters not found on path. Basin analysis skipped.');
        end
    end

    if ~basin.enable
        return;
    end

    fprintf('\n[BASIN] Extracting basin time series...\n');
    basinTags = stackTags;
    for i = 1:numel(basinTags)
        tag = basinTags{i};
        if wantReturnStacks
            if ~isfield(Stacks, tag)
                continue;
            end
            Stack = Stacks.(tag);
        else
            Stack = pipeline_load_stack_from_disk(paths.stacks, tag);
            if isempty(Stack)
                continue;
            end
        end

        ts = basin_mean_ts(double(Stack.ewh), basin.mask, latVec, true);
        Fit = basin_fit_seasonal_trend(ts, [T.dt]);

        io_save_basin_result(cfg, paths, basin.name, tag, T, ts, Fit, basin.mask);

        if plotCfg.quicklook
            try
                [fig, ~] = plot_timeseries_fit([T.dt], ts, Fit, struct('title',sprintf('%s - %s', basin.name, tag)));
                outDir = fullfile(paths.basin, basin.name);
                ensure_dir(outDir);
                outPng = fullfile(outDir, sprintf('basin_%s_%s.png', basin.name, tag));
                saveas(fig, outPng);
                close(fig);
            catch
            end
        end

        clear Stack ts Fit;
    end
end
