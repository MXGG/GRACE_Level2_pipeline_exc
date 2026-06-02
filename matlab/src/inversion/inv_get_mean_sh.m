function meanSH = inv_get_mean_sh(cfg, T)
%INV_GET_MEAN_SH Load cached mean SH if exists; otherwise compute and cache.

    cacheDir = fullfile(cfg.path.OUTPUT, 'CACHE');
    ensure_dir(cacheDir);

    Lmax = cfg.inversion.Lmax;
    mode = inv_get_mean_mode(cfg);
    [mStart, mEnd] = inv_get_mean_range(cfg, T, mode);
    tag  = sprintf('meanSH_L%d_%s_%s_%s.mat', ...
        Lmax, char(mode), strrep(mStart,'-',''), strrep(mEnd,'-',''));
    fp   = fullfile(cacheDir, tag);

    if isfile(fp)
        S = load(fp);
        if isfield(S,'meanSH')
            meanSH = S.meanSH;
            return;
        end
    end

    meanSH = inv_compute_mean_sh(cfg, T);
    save(fp, 'meanSH', '-v7.3');
end

function [mStart, mEnd] = inv_get_mean_range(cfg, T, mode)
%INV_GET_MEAN_RANGE Return mean-baseline start/end (YYYY-MM).
    if nargin < 3
        mode = "fixed_range";
    end
    if mode == "mission_full_period"
        if isempty(T)
            mStart = cfg.time.start_ym;
            mEnd = cfg.time.end_ym;
            return;
        end
        mStart = T(1).ym;
        mEnd = T(end).ym;
        return;
    end

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
