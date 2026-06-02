function meanSH = inv_compute_mean_sh(cfg, T)
%INV_COMPUTE_MEAN_SH Compute mean SH coefficients used for anomaly removal.
% Modes:
%   - fixed_range: single mean over [mean_start_ym, mean_end_ym]
%   - mission_full_period: separate means for GRACE and GRACE-FO spans

    mode = inv_get_mean_mode(cfg);
    if mode == "mission_full_period"
        meanSH = compute_mean_by_mission(cfg, T);
    else
        meanSH = compute_mean_fixed_range(cfg, T);
    end
end

function meanSH = compute_mean_fixed_range(cfg, T)
    Lmax = cfg.inversion.Lmax;
    sumC = zeros(Lmax+1, Lmax+1);
    sumS = zeros(Lmax+1, Lmax+1);
    cnt  = 0;

    [mStart, mEnd] = inv_get_mean_range(cfg);
    Tmean = subset_time_range(T, mStart, mEnd);
    if isempty(Tmean)
        error('No months found in mean-baseline range %s to %s.', mStart, mEnd);
    end

    for k = 1:numel(Tmean)
        try
            SHk = inv_read_gsm_month(cfg, Tmean(k));
            SHk = inv_replace_low_degree(cfg, SHk, Tmean(k));
            sumC = sumC + SHk.C;
            sumS = sumS + SHk.S;
            cnt  = cnt + 1;
        catch ME
            warning('[MEAN] Skip %s: %s', Tmean(k).ym, ME.message);
        end
    end

    if cnt == 0
        error('No valid months found to compute mean SH.');
    end

    meanSH = struct();
    meanSH.mode = 'fixed_range';
    meanSH.Lmax = Lmax;
    meanSH.C = sumC / cnt;
    meanSH.S = sumS / cnt;
    meanSH.meta = struct('cnt', cnt, 'start', mStart, 'end', mEnd);
end

function meanSH = compute_mean_by_mission(cfg, T)
    Lmax = cfg.inversion.Lmax;

    keys = {'grace', 'grace_fo', 'unknown'};
    sums = struct();
    for i = 1:numel(keys)
        k = keys{i};
        sums.(k).C = zeros(Lmax+1, Lmax+1);
        sums.(k).S = zeros(Lmax+1, Lmax+1);
        sums.(k).cnt = 0;
        sums.(k).start = '';
        sums.(k).end = '';
    end

    for i = 1:numel(T)
        Tk = T(i);
        try
            SHk = inv_read_gsm_month(cfg, Tk);
            SHk = inv_replace_low_degree(cfg, SHk, Tk);
            key = mission_to_key(inv_infer_mission(Tk, cfg));
            sums.(key).C = sums.(key).C + SHk.C;
            sums.(key).S = sums.(key).S + SHk.S;
            sums.(key).cnt = sums.(key).cnt + 1;
            if isempty(sums.(key).start)
                sums.(key).start = Tk.ym;
            end
            sums.(key).end = Tk.ym;
        catch ME
            warning('[MEAN][%s] Skip %s: %s', mission_to_label(key), Tk.ym, ME.message);
        end
    end

    totalCnt = sums.grace.cnt + sums.grace_fo.cnt + sums.unknown.cnt;
    if totalCnt == 0
        error('No valid months found to compute mission means.');
    end

    meanSH = struct();
    meanSH.mode = 'mission_full_period';
    meanSH.Lmax = Lmax;
    meanSH.by_mission = struct();

    totalC = zeros(Lmax+1, Lmax+1);
    totalS = zeros(Lmax+1, Lmax+1);

    for i = 1:numel(keys)
        key = keys{i};
        blk = sums.(key);
        out = struct('cnt', blk.cnt, 'start', blk.start, 'end', blk.end);
        if blk.cnt > 0
            out.C = blk.C / blk.cnt;
            out.S = blk.S / blk.cnt;
            totalC = totalC + blk.C;
            totalS = totalS + blk.S;
        else
            out.C = [];
            out.S = [];
        end
        meanSH.by_mission.(key) = out;
    end

    % Fallback mean for unmatched months.
    meanSH.C = totalC / totalCnt;
    meanSH.S = totalS / totalCnt;
    meanSH.meta = struct( ...
        'cnt_total', totalCnt, ...
        'grace_cnt', sums.grace.cnt, ...
        'grace_fo_cnt', sums.grace_fo.cnt, ...
        'unknown_cnt', sums.unknown.cnt);
end

function [mStart, mEnd] = inv_get_mean_range(cfg)
%INV_GET_MEAN_RANGE Return mean-baseline start/end (YYYY-MM).
    mStart = cfg.time.start_ym;
    mEnd   = cfg.time.end_ym;
    if isfield(cfg, 'inversion')
        if isfield(cfg.inversion, 'mean_start_ym') && ~isempty(cfg.inversion.mean_start_ym)
            mStart = cfg.inversion.mean_start_ym;
        end
        if isfield(cfg.inversion, 'mean_end_ym') && ~isempty(cfg.inversion.mean_end_ym)
            mEnd = cfg.inversion.mean_end_ym;
        end
    end
end

function Tsub = subset_time_range(T, start_ym, end_ym)
%SUBSET_TIME_RANGE Filter T array by inclusive YYYY-MM strings.
    try
        tAll = datetime({T.ym}, 'InputFormat', 'yyyy-MM');
    catch
        tAll = datetime([T.year]', [T.month]', 1);
    end
    t0 = datetime(start_ym, 'InputFormat', 'yyyy-MM');
    t1 = datetime(end_ym, 'InputFormat', 'yyyy-MM');
    mask = (tAll >= t0) & (tAll <= t1);
    Tsub = T(mask);
end

function key = mission_to_key(mission)
    m = upper(string(mission));
    if m == "GRACE-FO"
        key = 'grace_fo';
    elseif m == "GRACE"
        key = 'grace';
    else
        key = 'unknown';
    end
end

function label = mission_to_label(key)
    switch key
        case 'grace_fo'
            label = 'GRACE-FO';
        case 'grace'
            label = 'GRACE';
        otherwise
            label = 'UNKNOWN';
    end
end
