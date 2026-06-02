function [y, nRemoved, ok] = filter_grid_hsaf_adaptive_profile(x, Ts, lat, cfg_hankel, baseLegacy)
%FILTER_GRID_HSAF_ADAPTIVE_PROFILE Filter a single longitude profile using legacy HSAF/HTLS logic.

    params = hsaf_params_for_lat_legacy(lat, cfg_hankel, baseLegacy);

    nRemoved = 0;
    ok = false;
    x_in = x;
    x = x(:);
    N = numel(x);

    nanMask = isnan(x);
    if any(nanMask)
        if sum(~nanMask) < 10
            y = x_in;
            ok = true;
            return;
        end
        validIdx = find(~nanMask);
        x(nanMask) = interp1(validIdx, x(validIdx), find(nanMask), 'linear', 'extrap');
    end

    if isfield(params.opt, 'use_sliding') && params.opt.use_sliding
        y = hankel_destripe_oneprofile_sw(x, Ts, params.p, params.k, params.wl_band_deg, params.opt);
        bad = ~isfinite(y);
        if any(bad)
            y(bad) = x(bad);
        end
        y(nanMask) = NaN;
        ok = true;
        return;
    end

    if strcmpi(params.opt.detrend_mode, 'linear')
        n = (0:N-1)';
        pp = polyfit(n, x, 1);
        trend = polyval(pp, n);
    else
        trend = mean(x, 'omitnan') * ones(size(x));
    end
    xd = x - trend;

    if params.opt.taper_alpha > 0
        xd = xd .* tukeywin(N, params.opt.taper_alpha);
    end

    if std(xd, 'omitnan') < 1e-10
        y = x;
        y(nanMask) = NaN;
        ok = true;
        return;
    end

    try
        [~, ~, freq, ~, Y, ~] = H_RCs(xd, Ts, params.p, params.k);
    catch ME
        warning('HSAF:HTLSFailed', 'HTLS decomposition failed: %s', ME.message);
        y = x_in;
        return;
    end

    freq = freq(:);
    wl = 1 ./ abs(freq);
    wl(~isfinite(wl)) = inf;

    wl_band_deg = [min(params.wl_band_deg), max(params.wl_band_deg)];
    idx = (wl >= wl_band_deg(1)) & (wl <= wl_band_deg(2));
    idx = idx & isfinite(wl);

    if params.opt.force_conjugate_pairs && any(idx)
        idx = enforce_conjugate_pairs(freq, idx);
    end

    if params.opt.min_mode_energy_ratio > 0 && any(idx)
        e = mean(abs(Y).^2, 2);
        thr = params.opt.min_mode_energy_ratio * median(e);
        idx = idx & (e >= thr);
    end

    nRemoved = sum(idx);
    if ~any(idx)
        y = x;
        y(nanMask) = NaN;
        ok = true;
        return;
    end

    noise = sum(Y(idx, :), 1).';
    y = (xd - noise) + trend;
    y(nanMask) = NaN;
    ok = true;
end

function params = hsaf_params_for_lat_legacy(lat, cfg_hankel, base)
    params = base;
    if ~isfield(cfg_hankel, 'adaptive') || isempty(cfg_hankel.adaptive)
        return;
    end

    bands = cfg_hankel.adaptive;
    for i = 1:numel(bands)
        band = bands(i);
        if ~isfield(band, 'lat_range') || numel(band.lat_range) ~= 2
            continue;
        end
        minLat = min(band.lat_range);
        maxLat = max(band.lat_range);
        if lat >= minLat && lat <= maxLat
            params = override_hsaf_params_legacy(params, getfield_default(band, 'params', struct()));
            return;
        end
    end
end

function params = override_hsaf_params_legacy(params, overrides)
    if isempty(overrides)
        return;
    end
    if isfield(overrides, 'p'); params.p = overrides.p; end
    if isfield(overrides, 'K'); params.k = overrides.K; end
    if isfield(overrides, 'k'); params.k = overrides.k; end
    if isfield(overrides, 'wl_band_deg'); params.wl_band_deg = overrides.wl_band_deg; end
    if isfield(overrides, 'opt')
        fn = fieldnames(overrides.opt);
        for j = 1:numel(fn)
            params.opt.(fn{j}) = overrides.opt.(fn{j});
        end
    end
end

function v = getfield_default(S, name, defaultVal)
    if isfield(S, name) && ~isempty(S.(name))
        v = S.(name);
    else
        v = defaultVal;
    end
end

function [y, nRemoved] = hankel_destripe_oneprofile_sw(x, Ts, p_lat, k_lat, wl_band_deg, opt)
% Sliding-window HTLS destriping with OLA (V6_3-style).

    if ~isfield(opt, 'detrend_mode'); opt.detrend_mode = 'constant'; end
    if ~isfield(opt, 'taper_alpha'); opt.taper_alpha = 0.02; end
    if ~isfield(opt, 'force_conjugate_pairs'); opt.force_conjugate_pairs = true; end
    if ~isfield(opt, 'pair_tol'); opt.pair_tol = 0.01; end
    if ~isfield(opt, 'use_sliding'); opt.use_sliding = true; end
    if ~isfield(opt, 'win_len'); opt.win_len = []; end
    if ~isfield(opt, 'win_min'); opt.win_min = 30; end
    if ~isfield(opt, 'win_overlap'); opt.win_overlap = 0.75; end
    if ~isfield(opt, 'step'); opt.step = []; end
    if ~isfield(opt, 'circular'); opt.circular = true; end
    if ~isfield(opt, 'p_cap_ratio'); opt.p_cap_ratio = 1/3; end
    if ~isfield(opt, 'p_min_win'); opt.p_min_win = 24; end
    if ~isfield(opt, 'k_per_window'); opt.k_per_window = false; end
    if ~isfield(opt, 'k_energy'); opt.k_energy = 0.95; end
    if ~isfield(opt, 'k_min'); opt.k_min = 6; end
    if ~isfield(opt, 'k_max'); opt.k_max = 20; end
    if ~isfield(opt, 'min_mode_energy_ratio'); opt.min_mode_energy_ratio = 0.0; end
    if ~isfield(opt, 'protect_wl_gt_deg'); opt.protect_wl_gt_deg = inf; end
    if ~isfield(opt, 'ola_window'); opt.ola_window = 'hann'; end
    if ~isfield(opt, 'ola_tukey_alpha'); opt.ola_tukey_alpha = 0.25; end

    x_in = x;
    x = x(:);
    N = numel(x);

    if any(isnan(x))
        x = fillmissing(x, 'linear', 'EndValues', 'nearest');
    end

    if std(x, 'omitnan') < 1e-10
        y = reshape_like(x, x_in);
        nRemoved = 0;
        return;
    end

    if ~opt.use_sliding
        y = local_htls_destripe(x, Ts, p_lat, k_lat, wl_band_deg, opt);
        y = reshape_like(y, x_in);
        nRemoved = 0;
        return;
    end

    wl2 = wl_band_deg(2);
    T1 = round(3 * p_lat);
    T2 = ceil(1.5 * (wl2 / Ts));
    if isempty(opt.win_len)
        T = max([opt.win_min, T1, T2]);
        T = min(T, N);
    else
        T = min(max(opt.win_len, opt.win_min), N);
    end

    if isempty(opt.step)
        step = max(1, round(T * (1 - opt.win_overlap)));
    else
        step = max(1, round(opt.step));
    end

    w = make_ola_window(T, opt);
    w = w(:);

    acc = zeros(N, 1);
    wsum = zeros(N, 1);

    for s = 1:step:N
        if opt.circular
            idx = mod((s-1):(s+T-2), N) + 1;
        else
            idx = s:min(s+T-1, N);
        end
        seg = x(idx);

        p_win = min(p_lat, floor(numel(seg) * opt.p_cap_ratio));
        p_win = max(p_win, opt.p_min_win);
        p_win = min(p_win, numel(seg) - 2);
        k_win = min(k_lat, p_win - 1);

        if opt.k_per_window
            k_win = estimate_k_svd(seg, p_win, opt);
        else
            k_win = min(max(k_win, opt.k_min), opt.k_max);
        end

        seg_clean = local_htls_destripe(seg, Ts, p_win, k_win, wl_band_deg, opt);
        acc(idx) = acc(idx) + seg_clean(:) .* w(1:numel(idx));
        wsum(idx) = wsum(idx) + w(1:numel(idx));
    end

    y = acc ./ max(wsum, eps);
    bad = ~isfinite(y);
    if any(bad)
        y(bad) = x(bad);
    end
    y = reshape_like(y, x_in);
    nRemoved = 0;
end

function y = local_htls_destripe(x, Ts, p, k, wl_band_deg, opt)
    x = x(:);

    if strcmpi(opt.detrend_mode, 'linear')
        n = (0:numel(x)-1)';
        pp = polyfit(n, x, 1);
        trend = polyval(pp, n);
    else
        trend = mean(x) * ones(size(x));
    end
    xd = x - trend;

    if opt.taper_alpha > 0
        xd = xd .* tukeywin(numel(xd), opt.taper_alpha);
    end

    try
        [~, ~, freq, ~, Y, ~] = H_RCs(xd, Ts, p, k);
    catch
        y = x;
        return;
    end

    if ~all(isfinite(freq(:))) || ~all(isfinite(Y(:)))
        y = x;
        return;
    end

    freq = freq(:);
    wl = 1 ./ abs(freq);
    wl(~isfinite(wl)) = inf;

    idx = (wl >= wl_band_deg(1)) & (wl <= wl_band_deg(2));
    idx = idx & (wl <= opt.protect_wl_gt_deg);

    if opt.force_conjugate_pairs && any(idx)
        idx2 = false(size(idx));
        for i = find(idx)'
            idx2(i) = true;
            [dmin, j] = min(abs(freq - (-freq(i))));
            if j ~= i && dmin < opt.pair_tol
                idx2(j) = true;
            end
        end
        idx = idx2;
    end

    if opt.min_mode_energy_ratio > 0
        e = mean(abs(Y).^2, 2);
        thr = opt.min_mode_energy_ratio * median(e);
        idx = idx & (e >= thr);
        if ~any(idx)
            y = x;
            return;
        end
    end

    if ~any(idx)
        y = x;
        return;
    end

    noise = sum(Y(idx, :), 1).';
    y = (xd - noise) + trend;
end

function k = estimate_k_svd(x, p, opt)
    x = x(:);
    N = numel(x);
    L = N - p + 1;
    if L < 2
        k = opt.k_min;
        return;
    end
    H = hankel(x(1:L), x(L:N));
    s = svd(H, 'econ');
    e = cumsum(s.^2) / max(sum(s.^2), eps);
    k = find(e >= opt.k_energy, 1, 'first');
    if isempty(k)
        k = opt.k_min;
    end
    k = min(max(k, opt.k_min), min(opt.k_max, p - 1));
    if mod(k, 2) == 1
        k = k + 1;
    end
    k = min(k, p - 1);
end

function w = make_ola_window(T, opt)
    switch lower(opt.ola_window)
        case 'tukey'
            w = tukeywin(T, opt.ola_tukey_alpha);
        otherwise
            w = hann(T, 'periodic');
    end
    w = max(w, eps);
end

function y = reshape_like(ycol, xlike)
    if isrow(xlike)
        y = ycol(:).';
    else
        y = ycol(:);
    end
end

function idx2 = enforce_conjugate_pairs(freq, idx)
% Ensure selected frequencies include +/- pairs.

    idx2 = idx;
    fsel = freq(idx);
    if isempty(fsel)
        return;
    end

    pos = fsel(fsel > 0);
    neg = fsel(fsel < 0);

    for i = 1:numel(pos)
        [~, j] = min(abs(neg + pos(i)));
        if ~isempty(j)
            fpair = neg(j);
            idx2 = idx2 | (abs(freq - fpair) < 1e-12);
        end
    end
end
