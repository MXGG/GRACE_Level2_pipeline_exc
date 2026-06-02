function gfcFile = inv_find_gfc_file(cfg, Tk)
%INV_FIND_GFC_FILE Locate the GSM/GFC file for a given month.
% Preference:
%   1) Tk.file_guess (from core/build_time_index)
%   2) search in cfg.path.GFC by product_type + YYYYMM + file_ext

    gfcFile = '';

    if isfield(Tk,'file_guess') && ~isempty(Tk.file_guess) && isfile(Tk.file_guess)
        gfcFile = Tk.file_guess;
        return;
    end

    if ~isfield(cfg,'path') || ~isfield(cfg.path,'GFC')
        error('cfg.path.GFC is missing.');
    end
    if ~isfolder(cfg.path.GFC)
        error('GFC folder not found: %s', cfg.path.GFC);
    end

    yyyymm = Tk.yyyymm;
    prod   = cfg.time.product_type;
    ext    = cfg.time.file_ext;

    pats = {
        sprintf('*%s*%s*%s', prod, yyyymm, ext), ...
        sprintf('*%s*%s*',    prod, yyyymm) ...
    };

    for i = 1:numel(pats)
        d = dir(fullfile(cfg.path.GFC, pats{i}));
        if ~isempty(d)
            gfcFile = fullfile(d(1).folder, d(1).name);
            return;
        end
    end

    % Fallback: GRACE files sometimes encode date ranges as YYYYDDD-YYYYDDD
    % e.g. GSM-2_2008061-2008091_....gfc (no explicit YYYYMM in name).
    yearStr = yyyymm(1:4);
    d = dir(fullfile(cfg.path.GFC, sprintf('*%s*%s*%s', prod, yearStr, ext)));
    if ~isempty(d)
        dt0 = datetime(Tk.dt.Year, Tk.dt.Month, 1);
        dt1 = dateshift(dt0, 'end', 'month');
        bestIdx = 0;
        bestOverlapDays = -Inf;
        for ii = 1:numel(d)
            name = d(ii).name;
            tok = regexp(name, '(?<y1>\d{4})(?<d1>\d{3})-(?<y2>\d{4})(?<d2>\d{3})', 'names', 'once');
            if isempty(tok)
                continue;
            end
            tStart = datetime(str2double(tok.y1), 1, 1) + days(str2double(tok.d1) - 1);
            tEnd   = datetime(str2double(tok.y2), 1, 1) + days(str2double(tok.d2) - 1);

            % overlap in days (inclusive)
            oStart = max(dt0, tStart);
            oEnd   = min(dt1, tEnd);
            if oEnd < oStart
                continue;
            end
            overlapDays = days(oEnd - oStart) + 1;
            if overlapDays > bestOverlapDays
                bestOverlapDays = overlapDays;
                bestIdx = ii;
            end
        end
        if bestIdx > 0
            gfcFile = fullfile(d(bestIdx).folder, d(bestIdx).name);
            return;
        end
    end

    error('No gfc file found for %s (YYYYMM=%s) in %s', Tk.ym, yyyymm, cfg.path.GFC);
end
