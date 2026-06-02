function [Y, nRemoved, ok] = filter_grid_hsaf_global_map(X, Ts, params)
%FILTER_GRID_HSAF_GLOBAL_MAP Apply HSAF to a 2-D grid using global parameters.

    Y = X;
    nRemoved = 0;
    ok = false;

    nIter = max(1, round(params.iterations));
    for ii = 1:nIter %#ok<NASGU>
        nanMask = ~isfinite(Y);
        if any(nanMask(:))
            Y = fill_nan_grid(Y);
        end

        try
            Hankel_Mode = HSA(Y, Ts, params.N, params.P, params.K, params.J);
        catch ME
            warning('HSAF:HSAFailed', 'HSA filtering failed: %s', ME.message);
            return;
        end

        if isempty(Hankel_Mode) || ndims(Hankel_Mode) < 3
            warning('HSAF:HSAEmpty', 'HSA returned empty output.');
            return;
        end
        if any(~isfinite(Hankel_Mode(:)))
            Hankel_Mode(~isfinite(Hankel_Mode)) = 0;
        end

        order = params.K;
        if size(Hankel_Mode, 3) < order
            warning('HSAF:HSAOrder', ...
                'HSA components (%d) < requested order (%d).', size(Hankel_Mode, 3), order);
            return;
        end

        idx = hsaf_noise_mode_indices(order);
        if isempty(idx)
            error('HSAF:UnsupportedOrder', 'Order %d not supported.', order);
        end

        Y_noise = sum(Hankel_Mode(:,:,idx), 3);
        Y_prev = Y;
        Y = Y - Y_noise;
        bad = ~isfinite(Y);
        if any(bad(:))
            Y(bad) = Y_prev(bad);
        end
        if any(nanMask(:))
            Y(nanMask) = NaN;
        end
        nRemoved = nRemoved + numel(idx);
    end

    ok = true;
end

function idx = hsaf_noise_mode_indices(order)
% Noise mode selection logic consistent with the historical HSAF template.
    switch order
        case 3
            idx = [1 3];
        case 4
            idx = [1 4];
        case 5
            idx = [1 2 4 5];
        case 6
            idx = [1 2 5 6];
        case 7
            idx = [1 2 6 7];
        case 8
            idx = [1 2 3 6 7 8];
        case 9
            idx = [1 2 3 7 8 9];
        case 10
            idx = [1 2 3 8 9 10];
        otherwise
            idx = [];
    end
end

function Y = fill_nan_grid(Y)
    nanMask = ~isfinite(Y);
    if ~any(nanMask(:))
        return;
    end
    try
        Y = fillmissing(Y, 'linear', 1, 'EndValues', 'nearest');
        Y = fillmissing(Y, 'linear', 2, 'EndValues', 'nearest');
    catch
        m = mean(Y(~nanMask), 'omitnan');
        if ~isfinite(m)
            m = 0;
        end
        Y(nanMask) = m;
    end
    Y(~isfinite(Y)) = 0;
end
