function [Gcorr, info] = leakage_fm_correct_month(cfg, Gobs, methodTag, mask, lonVec, latVec)
%LEAKAGE_FM_CORRECT_MONTH Forward Modeling iterative correction for one month.
%
% Gobs: observed filtered grid (mm) for a given methodTag.
% mask: target region mask (logical)

    L = leakage_merge_cfg(cfg);

    Gobs = ensure_latlon_order(Gobs, lonVec, latVec);
    mask = logical(mask);
    if ~isequal(size(Gobs), size(mask))
        error('FM leakage mask shape does not match Gobs.');
    end
    if ~any(mask(:))
        error('FM leakage mask is empty.');
    end

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

    nIter = max(1, round(double(L.FM.nIter)));
    minIter = 1;
    if isfield(L.FM, 'minIter') && ~isempty(L.FM.minIter)
        minIter = max(1, min(round(double(L.FM.minIter)), nIter));
    end

    tol_rmse_mm = 0.0;
    if isfield(L, 'FM') && isfield(L.FM, 'tol_rmse_mm') && ~isempty(L.FM.tol_rmse_mm)
        tol_rmse_mm = L.FM.tol_rmse_mm;
    end
    accel = 1.0;
    if isfield(L.FM, 'accel') && ~isempty(L.FM.accel)
        accel = double(L.FM.accel);
    end
    patience = 0;
    if isfield(L.FM, 'patience') && ~isempty(L.FM.patience)
        patience = max(0, round(double(L.FM.patience)));
    end
    minImprove = 0.0;
    if isfield(L.FM, 'min_improve') && ~isempty(L.FM.min_improve)
        minImprove = double(L.FM.min_improve);
    end
    convMetric = 'rmse';
    if isfield(L.FM, 'metric') && ~isempty(L.FM.metric)
        convMetric = char(L.FM.metric);
    end
    massMode = L.mass_conservation;
    if isfield(L.FM, 'mass_conservation') && ~isempty(L.FM.mass_conservation)
        massMode = L.FM.mass_conservation;
    end
    outputMode = 'mask_zero';
    if isfield(L.FM, 'output_mode') && ~isempty(L.FM.output_mode)
        outputMode = char(L.FM.output_mode);
    end

    rmse_hist = nan(nIter,1);
    metric_hist = nan(nIter,1);
    bestMetric = inf;
    stale = 0;

    for it = 1:nIter
        Gfull = apply_mass_mode(Gest, mask, massMode);

        Gsim = leakage_apply_forward_operator(Gfull, lonVec, latVec, methodTag, cfg, L);

        R = Gobs - Gsim;

        % update
        switch lower(update_mode)
            case 'global'
                Gest = Gest + accel .* R;
            otherwise
                Gest(mask) = Gest(mask) + accel .* R(mask);
        end

        % convergence checks
        rmse = sqrt(mean(R(mask).^2, 'omitnan'));
        rmse_hist(it) = rmse;
        metricVal = convergence_value(R, mask, latVec, convMetric);
        metric_hist(it) = metricVal;

        improve = bestMetric - abs(metricVal);
        if abs(metricVal) < bestMetric
            bestMetric = abs(metricVal);
        end
        if it >= minIter && patience > 0
            if improve < minImprove
                stale = stale + 1;
            else
                stale = 0;
            end
        end

        if it >= minIter && tol_rmse_mm > 0 && abs(metricVal) < tol_rmse_mm
            rmse_hist = rmse_hist(1:it);
            metric_hist = metric_hist(1:it);
            break;
        end
        if it >= minIter && patience > 0 && stale >= patience
            rmse_hist = rmse_hist(1:it);
            metric_hist = metric_hist(1:it);
            break;
        end
    end

    Gcorr = apply_mass_mode(Gest, mask, massMode);
    switch lower(outputMode)
        case {'preserve_observed_outside_mask','preserve_observed','observed_outside'}
            Gcorr(~mask) = Gobs(~mask);
        case {'nan_outside_mask','mask_nan'}
            Gcorr(~mask) = NaN;
        otherwise
            Gcorr(~mask) = 0;
    end

    info = struct();
    info.nIter = numel(rmse_hist);
    info.rmse_hist = rmse_hist;
    info.metric = convMetric;
    info.metric_hist = metric_hist;
    info.final_rmse = rmse_hist(end);
    info.final_metric = metric_hist(end);
    info.accel = accel;
    info.minIter = minIter;
    info.patience = patience;
    info.min_improve = minImprove;
    info.mass_conservation = massMode;
    info.output_mode = outputMode;
    info.forward_operator = L.FM.operator;
end

function Gfull = apply_mass_mode(G, mask, mode)
    mode = lower(char(mode));
    Gfull = G;
    switch mode
        case {'global_zero_mean','ocean_uniform_land_balance'}
            n_in  = sum(mask(:));
            n_out = numel(mask) - n_in;
            if n_out > 0
                mean_in = mean(Gfull(mask), 'omitnan');
                c_out = -mean_in * (n_in / n_out);
                Gfull(~mask) = c_out;
            else
                Gfull(~mask) = 0;
            end
        case {'legacy_land_mean_fill','legacy','script_land_mean'}
            mean_in = mean(Gfull(mask), 'omitnan') * (sum(mask(:)) / numel(mask));
            Gfull(~mask) = -mean_in;
        otherwise
            Gfull(~mask) = 0;
    end
end

function v = convergence_value(R, mask, latVec, metric)
    switch lower(char(metric))
        case {'land_weighted_mean','weighted_mean','mean'}
            wLat = cosd(latVec(:).');
            W = repmat(wLat, [size(R,1), 1]);
            vals = R(mask);
            ww = W(mask);
            good = isfinite(vals) & isfinite(ww) & ww > 0;
            if any(good)
                v = sum(vals(good) .* ww(good)) / sum(ww(good));
            else
                v = NaN;
            end
        otherwise
            v = sqrt(mean(R(mask).^2, 'omitnan'));
    end
end
