function [Gcorr, info] = leakage_fm_correct_month(cfg, Gobs, methodTag, mask, lonVec, latVec)
%LEAKAGE_FM_CORRECT_MONTH Forward Modeling iterative correction for one month.
%
% Gobs: observed filtered grid (mm) for a given methodTag.
% mask: target region mask (logical)

    L = leakage_merge_cfg(cfg);

    Gobs = ensure_latlon_order(Gobs, lonVec, latVec);
    mask = logical(mask);

    init_mode = 'obs';
    if isfield(L, 'FM') && isfield(L.FM, 'init_mode') && ~isempty(L.FM.init_mode)
        init_mode = L.FM.init_mode;
    end
    update_mode = 'mask';
    if isfield(L, 'FM') && isfield(L.FM, 'update_mode') && ~isempty(L.FM.update_mode)
        update_mode = L.FM.update_mode;
    end

    % init
    switch lower(init_mode)
        case 'zeros'
            Gest = zeros(size(Gobs));
            Gest(mask) = 0;
        otherwise % 'obs'
            Gest = zeros(size(Gobs));
            Gest(mask) = Gobs(mask);
    end

    nIter = L.FM.nIter;
    if isfield(L, 'FM') && isfield(L.FM, 'nIter') && ~isempty(L.FM.nIter)
        nIter = L.FM.nIter;
    end
    if isempty(nIter) || nIter < 1
        nIter = 1;
    end

    tol_rmse_mm = 0;
    if isfield(L, 'FM') && isfield(L.FM, 'tol_rmse_mm') && ~isempty(L.FM.tol_rmse_mm)
        tol_rmse_mm = L.FM.tol_rmse_mm;
    end

    rmse_hist = nan(nIter,1);

    for it = 1:nIter
        % build full field for forward operator
        Gfull = Gest;
        if strcmpi(L.mass_conservation, 'global_zero_mean')
            % enforce global mean 0 by filling outside with constant
            n_in  = sum(mask(:));
            n_out = numel(mask) - n_in;
            if n_out > 0
                mean_in = mean(Gfull(mask), 'omitnan');
                c_out = -mean_in * (n_in / n_out);
                Gfull(~mask) = c_out;
            end
        else
            Gfull(~mask) = 0;
        end

        Gsim = leakage_apply_forward_operator(Gfull, lonVec, latVec, methodTag, cfg, L);

        R = Gobs - Gsim;

        % update
        switch lower(update_mode)
            case 'global'
                Gest = Gest + R;
            otherwise
                Gest(mask) = Gest(mask) + R(mask);
        end

        % convergence check (in mask)
        rmse = sqrt(mean(R(mask).^2, 'omitnan'));
        rmse_hist(it) = rmse;

        if tol_rmse_mm > 0 && rmse < tol_rmse_mm
            rmse_hist = rmse_hist(1:it);
            break;
        end
    end

    Gcorr = Gest;        % corrected "true" estimate in mask
    Gcorr(~mask) = 0;    % keep clean outside region

    info = struct();
    info.nIter = numel(rmse_hist);
    info.rmse_hist = rmse_hist;
    info.final_rmse = rmse_hist(end);
end
