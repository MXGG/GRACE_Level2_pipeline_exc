function mode = inv_get_mean_mode(cfg)
%INV_GET_MEAN_MODE Return mean-field mode: fixed_range or mission_full_period.

    mode = "fixed_range";
    if ~isfield(cfg, 'inversion') || ~isstruct(cfg.inversion)
        return;
    end
    inv = cfg.inversion;

    if isfield(inv, 'mean_mode') && ~isempty(inv.mean_mode)
        mode = string(inv.mean_mode);
    elseif isfield(inv, 'mean') && isstruct(inv.mean) && isfield(inv.mean, 'mode') ...
            && ~isempty(inv.mean.mode)
        mode = string(inv.mean.mode);
    end

    mode = lower(strrep(mode, '-', '_'));
    if mode ~= "mission_full_period"
        mode = "fixed_range";
    end
end
