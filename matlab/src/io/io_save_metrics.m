function fp = io_save_metrics(cfg, paths, OUTmetrics, T)
%IO_SAVE_METRICS Save metrics struct and optional time-series TXT per method.

    if nargin < 4; T = []; end

    if ~isempty(T)
        t0 = strrep(T(1).ym,'-',''); t1 = strrep(T(end).ym,'-','');
    else
        t0 = 'start'; t1 = 'end';
    end

    fp = fullfile(paths.metrics, sprintf('metrics_%s-%s.mat', t0, t1));
    io_save_mat(fp, 'OUTmetrics');

    exportTxt = isfield(cfg,'io') && isfield(cfg.io,'export_txt') && cfg.io.export_txt;
    if ~exportTxt; return; end

    % Export ts metrics if present
    if isfield(OUTmetrics,'ACC') && isfield(OUTmetrics.ACC,'ts')
        methods = fieldnames(OUTmetrics.ACC.ts);
        for i = 1:numel(methods)
            m = methods{i};
            keys = fieldnames(OUTmetrics.ACC.ts.(m));
            for k = 1:numel(keys)
                key = keys{k};
                v = OUTmetrics.ACC.ts.(m).(key);
                if ~isnumeric(v) || ~isvector(v); continue; end
                outDir = fullfile(paths.metrics_ts, m);
                ensure_dir(outDir);
                outFile = fullfile(outDir, sprintf('%s_%s_%s-%s.txt', m, key, t0, t1));
                if ~isempty(T)
                    yyyymm = arrayfun(@(s) str2double(strrep(s.ym,'-','')), T(:));
                    io_write_timeseries_txt(outFile, yyyymm, v(:));
                else
                    io_write_timeseries_txt(outFile, (1:numel(v)).', v(:));
                end
            end
        end
    end
end
