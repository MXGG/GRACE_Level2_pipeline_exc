function [Gobs_sim, info] = leakage_apply_forward_operator_optimized(Gtrue, lonVec, latVec, methodTag, cfg, L)
%LEAKAGE_APPLY_FORWARD_OPERATOR_OPTIMIZED Internal SH forward operator.
%
% This backend extracts the reusable core of the legacy Forward Modeling
% scripts without their fixed paths, txt intermediates, or hard-coded grid.
% It uses a self-consistent real SH projection:
%   grid -> truncated SH -> configured filter chain -> grid
%
% Input/Output grids are [nLon x nLat] in the same EWH unit as Gtrue.

    if nargin < 6 || isempty(L)
        L = leakage_merge_cfg(cfg);
    end

    Gtrue = ensure_latlon_order(Gtrue, lonVec, latVec);
    op = leakage_parse_filter_tag(methodTag, cfg);

    Lmax = L.Lmax;
    if isfield(op, 'Lmax') && ~isempty(op.Lmax)
        Lmax = op.Lmax;
    end
    Lmax = max(1, round(double(Lmax)));
    Lmax = min(Lmax, max(1, min(numel(lonVec) / 2, numel(latVec) - 1)));

    basis = local_basis(lonVec, latVec, Lmax);
    [C, S] = local_grid_to_sh(Gtrue, basis);

    stages = {};
    if op.use_p4m6
        [C, S, metaP] = filter_sh_p4m6(C, S, Lmax, ...
            get_nested_local(cfg, {'filter','p4m6','poly_deg'}, 4), ...
            get_nested_local(cfg, {'filter','p4m6','m_start'}, 6));
        stages{end+1} = metaP; %#ok<AGROW>
    end

    if op.use_ddk
        cfgDDK = get_nested_local(cfg, {'filter','ddk'}, struct());
        if ~isstruct(cfgDDK); cfgDDK = struct(); end
        cfgDDK.type = op.ddk_type;
        [C, S, metaD] = filter_sh_ddk(C, S, cfgDDK, cfg.path);
        stages{end+1} = metaD; %#ok<AGROW>
    end

    if op.use_gauss
        [C, S, metaG] = filter_sh_gaussian(C, S, Lmax, op.gaussian_km);
        stages{end+1} = metaG; %#ok<AGROW>
    end

    if op.use_fan
        [C, S, metaF] = filter_sh_fan(C, S, Lmax, op.fan_r1_km, op.fan_r2_km);
        stages{end+1} = metaF; %#ok<AGROW>
    end

    Gobs_sim = local_sh_to_grid(C, S, basis);

    if op.use_hankel
        if exist('filter_grid_hsaf','file') ~= 2
            error('Hankel requested but filters/filter_grid_hsaf.m not found on path.');
        end
        Ts = get_nested_local(cfg, {'filter','hankel','Ts'}, mean(diff(lonVec)));
        if isempty(Ts) || ~isfinite(Ts)
            Ts = mean(diff(lonVec));
        end
        [Gobs_sim, hinfo] = filter_grid_hsaf(Gobs_sim, lonVec, latVec, op.hankel, Ts);
        stages{end+1} = struct('type','HSAF','input',get_nested_local(cfg, {'filter','pre_hankel_input'}, 'P4M6'), 'info',hinfo); %#ok<AGROW>
    end

    info = struct();
    info.operator = 'optimized_sh';
    info.Lmax = Lmax;
    info.methodTag = char(methodTag);
    info.stages = stages;
end

function basis = local_basis(lonVec, latVec, Lmax)
    persistent cache
    if isempty(cache); cache = struct(); end
    lon = lonVec(:);
    lat = latVec(:);
    key = sprintf('L%d_nlon%d_nlat%d_lon%.12g_%.12g_lat%.12g_%.12g', ...
        Lmax, numel(lon), numel(lat), lon(1), mean(diff(lon)), lat(1), mean(diff(lat)));
    key = matlab.lang.makeValidName(key);
    if isfield(cache, key)
        basis = cache.(key);
        return;
    end

    nLon = numel(lon);
    nLat = numel(lat);
    m = (0:Lmax).';
    lonRad = deg2rad(lon(:).');
    cosM = cos(m * lonRad);
    sinM = sin(m * lonRad);

    lonAlpha = 2.0 / max(1, nLon) * ones(Lmax+1, 1);
    lonAlpha(1) = 1.0 / max(1, nLon);

    wLat = cosd(lat(:));
    wLat(~isfinite(wLat) | wLat <= 0) = eps;
    wSqrt = sqrt(wLat);

    x = sind(lat(:).');
    P = zeros(Lmax+1, Lmax+1, nLat);
    for l = 0:Lmax
        rows = legendre(l, x, 'norm');
        for mm = 0:l
            fac = 1.0;
            if mm > 0
                fac = sqrt(2.0);
            end
            P(l+1, mm+1, :) = reshape(rows(mm+1, :) * fac, [1 1 nLat]);
        end
    end

    pinvByM = cell(Lmax+1, 1);
    pByM = cell(Lmax+1, 1);
    for mm = 0:Lmax
        Pm = zeros(nLat, Lmax-mm+1);
        for l = mm:Lmax
            Pm(:, l-mm+1) = squeeze(P(l+1, mm+1, :));
        end
        pByM{mm+1} = Pm;
        pinvByM{mm+1} = pinv(Pm .* wSqrt);
    end

    basis = struct('Lmax', Lmax, 'lon', lon, 'lat', lat, ...
        'cosM', cosM, 'sinM', sinM, 'lonAlpha', lonAlpha, ...
        'wSqrt', wSqrt, 'pByM', {pByM}, 'pinvByM', {pinvByM});
    cache.(key) = basis;
end

function [C, S] = local_grid_to_sh(G, basis)
    Lmax = basis.Lmax;
    C = zeros(Lmax+1, Lmax+1);
    S = zeros(Lmax+1, Lmax+1);
    G = double(G);
    G(~isfinite(G)) = 0;

    for mm = 0:Lmax
        aLat = basis.lonAlpha(mm+1) * (basis.cosM(mm+1, :) * G);
        bLat = basis.lonAlpha(mm+1) * (basis.sinM(mm+1, :) * G);
        coeffC = basis.pinvByM{mm+1} * (aLat(:) .* basis.wSqrt);
        coeffS = basis.pinvByM{mm+1} * (bLat(:) .* basis.wSqrt);
        for l = mm:Lmax
            C(l+1, mm+1) = coeffC(l-mm+1);
            S(l+1, mm+1) = coeffS(l-mm+1);
        end
    end
    S(:,1) = 0;
end

function G = local_sh_to_grid(C, S, basis)
    Lmax = basis.Lmax;
    nLon = numel(basis.lon);
    nLat = numel(basis.lat);
    G = zeros(nLon, nLat);
    for mm = 0:Lmax
        Pm = basis.pByM{mm+1};
        cc = C(mm+1:Lmax+1, mm+1);
        ss = S(mm+1:Lmax+1, mm+1);
        latC = Pm * cc;
        latS = Pm * ss;
        G = G + basis.cosM(mm+1, :).'*latC(:).';
        G = G + basis.sinM(mm+1, :).'*latS(:).';
    end
end

function v = get_nested_local(S, path, defaultVal)
    v = defaultVal;
    try
        cur = S;
        for i = 1:numel(path)
            if ~isstruct(cur) || ~isfield(cur, path{i})
                return;
            end
            cur = cur.(path{i});
        end
        if ~isempty(cur); v = cur; end
    catch
        v = defaultVal;
    end
end
