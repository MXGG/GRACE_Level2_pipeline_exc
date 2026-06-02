function fp = io_save_basin_result(cfg, paths, basinName, tag, T, ts, Fit, mask)
%IO_SAVE_BASIN_RESULT Save basin time-series + fit output.

    outDir = fullfile(paths.basin, basinName);
    ensure_dir(outDir);

    t0 = strrep(T(1).ym,'-',''); t1 = strrep(T(end).ym,'-','');
    fp = fullfile(outDir, sprintf('%s_%s_%s-%s.mat', basinName, tag, t0, t1));

    Basin = struct();
    Basin.name = basinName;
    Basin.tag = tag;
    Basin.t = {T.ym};
    Basin.ts = ts(:);
    Basin.Fit = Fit;
    Basin.mask = mask;

    io_save_mat(fp, 'Basin');

    if isfield(cfg,'io') && isfield(cfg.io,'export_txt') && cfg.io.export_txt
        outTxt = fullfile(outDir, sprintf('%s_%s_%s-%s.txt', basinName, tag, t0, t1));
        yyyymm = arrayfun(@(s) str2double(strrep(s.ym,'-','')), T(:));
        io_write_timeseries_txt(outTxt, yyyymm, ts(:));
    end
end
