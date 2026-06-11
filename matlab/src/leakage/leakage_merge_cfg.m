function L = leakage_merge_cfg(cfg)
%LEAKAGE_MERGE_CFG Merge cfg.leakage into defaults.
    L = leakage_default_cfg();
    if ~isfield(cfg,'leakage') || isempty(cfg.leakage)
        return;
    end
    U = cfg.leakage;
    L = merge_struct(L, U);

    % nested merge
    if isfield(U,'SF'); L.SF = merge_struct(L.SF, U.SF); end
    if isfield(U,'FM'); L.FM = merge_struct(L.FM, U.FM); end

    % Compatibility with GUI/default JSON flat leakage fields.
    if isfield(U, 'fm_operator') && ~isempty(U.fm_operator)
        L.FM.operator = U.fm_operator;
    end
    if isfield(U, 'fm_max_iter') && ~isempty(U.fm_max_iter)
        L.FM.nIter = U.fm_max_iter;
    end
    if isfield(U, 'fm_min_iter') && ~isempty(U.fm_min_iter)
        L.FM.minIter = U.fm_min_iter;
    end
    if isfield(U, 'fm_tol') && ~isempty(U.fm_tol)
        L.FM.tol_rmse_mm = U.fm_tol;
    end
    if isfield(U, 'fm_accel') && ~isempty(U.fm_accel)
        L.FM.accel = U.fm_accel;
    end
    if isfield(U, 'fm_patience') && ~isempty(U.fm_patience)
        L.FM.patience = U.fm_patience;
    end
    if isfield(U, 'fm_min_improve') && ~isempty(U.fm_min_improve)
        L.FM.min_improve = U.fm_min_improve;
    end
    if isfield(U, 'fm_metric') && ~isempty(U.fm_metric)
        L.FM.metric = U.fm_metric;
    end
    if isfield(U, 'fm_mass_conservation') && ~isempty(U.fm_mass_conservation)
        L.FM.mass_conservation = U.fm_mass_conservation;
    end
    if isfield(U, 'fm_output_mode') && ~isempty(U.fm_output_mode)
        L.FM.output_mode = U.fm_output_mode;
    end
    if isfield(U, 'sf_grid_interval') && ~isempty(U.sf_grid_interval) ...
            && (~isfield(U, 'grid_interval') || isempty(U.grid_interval))
        L.grid_interval = U.sf_grid_interval;
    end

    % Keep a nested FM block in the effective config for downstream metadata.
    L.FM.nIter = max(1, round(to_double(L.FM.nIter, 30)));
    L.FM.minIter = max(1, min(round(to_double(L.FM.minIter, 1)), L.FM.nIter));
    L.FM.tol_rmse_mm = to_double(L.FM.tol_rmse_mm, 1e-3);
    L.FM.accel = to_double(L.FM.accel, 1.0);
    L.FM.patience = max(0, round(to_double(L.FM.patience, 0)));
    L.FM.min_improve = to_double(L.FM.min_improve, 0.0);
end

function A = merge_struct(A, B)
    if isempty(B); return; end
    fn = fieldnames(B);
    for i = 1:numel(fn)
        A.(fn{i}) = B.(fn{i});
    end
end

function x = to_double(v, defaultVal)
    if isnumeric(v) && isscalar(v) && isfinite(v)
        x = double(v);
        return;
    end
    if ischar(v) || isstring(v)
        x = str2double(v);
        if isfinite(x)
            return;
        end
    end
    x = defaultVal;
end
