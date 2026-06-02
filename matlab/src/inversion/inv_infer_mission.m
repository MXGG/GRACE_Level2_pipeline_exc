function mission = inv_infer_mission(Tk, cfg)
%INV_INFER_MISSION Infer mission family (GRACE or GRACE-FO) for a time entry.
%
% Priority:
%   1) File-name tokens (GRFO/GRAC)
%   2) Time threshold (default 2018-06, configurable)

    if nargin < 2
        cfg = struct();
    end

    mission = 'UNKNOWN';
    names = collect_candidate_names(Tk);
    for i = 1:numel(names)
        s = upper(names{i});
        if contains(s, 'GRFO') || contains(s, 'GRACE-FO') || contains(s, 'GRACE_FO') || contains(s, 'GRACEFO')
            mission = 'GRACE-FO';
            return;
        end
        if contains(s, 'GRAC')
            mission = 'GRACE';
            return;
        end
    end

    gfoStart = resolve_gfo_start(cfg);
    if isfield(Tk, 'dt') && isdatetime(Tk.dt) && ~isnat(Tk.dt)
        if Tk.dt >= gfoStart
            mission = 'GRACE-FO';
        else
            mission = 'GRACE';
        end
        return;
    end

    if isfield(Tk, 'ym') && ~isempty(Tk.ym)
        try
            dt = datetime(Tk.ym, 'InputFormat', 'yyyy-MM');
            if dt >= gfoStart
                mission = 'GRACE-FO';
            else
                mission = 'GRACE';
            end
        catch
            mission = 'UNKNOWN';
        end
    end
end

function names = collect_candidate_names(Tk)
    names = {};
    if isfield(Tk, 'file_guess') && ~isempty(Tk.file_guess)
        [~, nm, ext] = fileparts(Tk.file_guess);
        names{end+1} = [nm ext]; %#ok<AGROW>
    end
end

function dt = resolve_gfo_start(cfg)
    ym = '2018-06';
    if isfield(cfg, 'inversion') && isstruct(cfg.inversion)
        inv = cfg.inversion;
        if isfield(inv, 'mean') && isstruct(inv.mean) && isfield(inv.mean, 'grace_fo_start_ym') ...
                && ~isempty(inv.mean.grace_fo_start_ym)
            ym = char(string(inv.mean.grace_fo_start_ym));
        elseif isfield(inv, 'grace_fo_start_ym') && ~isempty(inv.grace_fo_start_ym)
            ym = char(string(inv.grace_fo_start_ym));
        end
    end
    dt = datetime(ym, 'InputFormat', 'yyyy-MM');
end
