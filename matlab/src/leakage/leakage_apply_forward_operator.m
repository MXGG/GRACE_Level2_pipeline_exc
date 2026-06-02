function Gobs_sim = leakage_apply_forward_operator(Gtrue, lonVec, latVec, methodTag, cfg, L)
%LEAKAGE_APPLY_FORWARD_OPERATOR Apply "GRACE-like" filtering operator to a true field.
% This is the core operator used by both SF and FM.
%
% Input/Output grids are mmEWH, [nLon x nLat].

    Gtrue = ensure_latlon_order(Gtrue, lonVec, latVec);

    % Parse operations from tag
    op = leakage_parse_filter_tag(methodTag, cfg);

    % Prepare defaults
    if nargin < 6 || isempty(L)
        L = leakage_merge_cfg(cfg);
    end
    Lmax = L.Lmax;
    grid_interval = L.grid_interval;

    % If DDK is requested, apply in SH-domain for stability
    if op.use_ddk
        if exist('gmt_grid2cs','file') ~= 2 || exist('gmt_cs2grid','file') ~= 2
            error(['leakage_apply_forward_operator requires gmt_grid2cs/gmt_cs2grid on path.\n' ...
                'Please ensure src/tools/gmt/ is added to path in setup_env.']);
        end
        cs = gmt_grid2cs(Gtrue.' / 1000, Lmax);
        [Dc, Ds, ok] = leakage_cs_to_arrays(cs, Lmax);
        if ~ok
            error('DDK leakage failed: cannot parse CS format.');
        end
        [Dc2, Ds2] = filter_sh_ddk(Dc, Ds, cfg.filter.ddk, cfg.path);
        cs2 = leakage_arrays_to_cs(cs, Dc2, Ds2, Lmax);
        Gsim_m = gmt_cs2grid(cs2, 0, grid_interval, 'NONE');
        Gobs_sim = (Gsim_m * 1000).';
        return;
    end

    % SH-domain operations using GMT toolbox if available
    if exist('gmt_grid2cs','file') ~= 2 || exist('gmt_cs2grid','file') ~= 2
        error(['leakage_apply_forward_operator requires gmt_grid2cs/gmt_cs2grid on path.\n' ...
       'Please ensure src/tools/gmt/ is added to path in setup_env.']);
    end

    % mm -> m for stable numeric scale; transform
    cs = gmt_grid2cs(Gtrue.' / 1000, Lmax);

    % destriping / decorrelation (P4M6-like)
    if op.use_p4m6
        cs = leakage_try_destriping(cs);
    end

    % Gaussian / Fan
    if op.use_gauss
        if exist('gmt_gaussian_filter','file') == 2
            cs = gmt_gaussian_filter(cs, op.gaussian_km);
        else
            % fallback: apply via filters/filter_sh_gaussian if possible
            cs = leakage_apply_gaussian_fallback(cs, op.gaussian_km, Lmax);
        end
    end
    if op.use_fan
        if exist('gmt_fan_filter','file') == 2
            cs = gmt_fan_filter(cs, op.fan_r1_km, op.fan_r2_km);
        else
            cs = leakage_apply_fan_fallback(cs, op.fan_r1_km, op.fan_r2_km, Lmax);
        end
    end

    % back to grid (m) then to mm
    Gsim_m = gmt_cs2grid(cs, 0, grid_interval, 'NONE');
    Gsim = (Gsim_m * 1000).';

    % optional Hankel in grid domain
    if op.use_hankel
        if exist('filter_grid_hsaf','file') ~= 2
            error('Hankel requested but filters/filter_grid_hsaf.m not found on path.');
        end
        Ts = mean(diff(lonVec));
        [Gsim, ~] = filter_grid_hsaf(Gsim, lonVec, latVec, op.hankel, Ts);
    end

    Gobs_sim = Gsim;
end

% ================= helpers =================

function cs2 = leakage_try_destriping(cs)
    if exist('gmt_destriping','file') == 2
        cs2 = gmt_destriping(cs, 'CHENP4M6');
    else
        % Some toolboxes implement destriping within gmt_cs2grid via keyword,
        % but here we stay in CS domain; if missing, keep cs unchanged.
        warning('gmt_destriping not found; P4M6 destriping skipped in leakage operator.');
        cs2 = cs;
    end
end

function cs2 = leakage_apply_gaussian_fallback(cs, rkm, Lmax)
    % Try to parse CS format to Dc/Ds and apply our filter_sh_gaussian
    [Dc, Ds, ok] = leakage_cs_to_arrays(cs, Lmax);
    if ~ok
        error('Gaussian fallback failed: cannot parse cs format.');
    end
    [Dc2, Ds2] = filter_sh_gaussian(Dc, Ds, Lmax, rkm);
    cs2 = leakage_arrays_to_cs(cs, Dc2, Ds2, Lmax);
end

function cs2 = leakage_apply_fan_fallback(cs, r1, r2, Lmax)
    [Dc, Ds, ok] = leakage_cs_to_arrays(cs, Lmax);
    if ~ok
        error('Fan fallback failed: cannot parse cs format.');
    end
    [Dc2, Ds2] = filter_sh_fan(Dc, Ds, Lmax, r1, r2);
    cs2 = leakage_arrays_to_cs(cs, Dc2, Ds2, Lmax);
end

function [Dc, Ds, ok] = leakage_cs_to_arrays(cs, Lmax)
% Try common CS representations:
% 1) numeric matrix with columns [l m C S]
% 2) struct with fields C,S already as (Lmax+1)x(Lmax+1)
    ok = false;
    Dc = []; Ds = [];
    if isstruct(cs) && isfield(cs,'C') && isfield(cs,'S')
        Dc = cs.C; Ds = cs.S; ok = true; return;
    end
    if isnumeric(cs) && size(cs,2) >= 4
        Dc = zeros(Lmax+1, Lmax+1);
        Ds = zeros(Lmax+1, Lmax+1);
        lm = cs(:,1:2);
        C  = cs(:,3);
        S  = cs(:,4);
        for i = 1:size(lm,1)
            l = lm(i,1); m = lm(i,2);
            if ~isfinite(l) || ~isfinite(m)
                continue;
            end
            if l < 0 || m < 0
                continue;
            end
            if abs(l - round(l)) > 1e-12 || abs(m - round(m)) > 1e-12
                continue;
            end
            l = round(l); m = round(m);
            if l<=Lmax && m<=Lmax
                Dc(l+1,m+1) = C(i);
                Ds(l+1,m+1) = S(i);
            end
        end
        ok = true;
    end
end

function cs2 = leakage_arrays_to_cs(cs, Dc, Ds, Lmax)
% Return in the same "style" as input if possible.
    if isstruct(cs) && isfield(cs,'C') && isfield(cs,'S')
        cs2 = cs;
        cs2.C = Dc; cs2.S = Ds;
        return;
    end
    if isnumeric(cs) && size(cs,2) >= 4
        cs2 = cs;
        for i = 1:size(cs,1)
            l = cs(i,1); m = cs(i,2);
            if ~isfinite(l) || ~isfinite(m)
                continue;
            end
            if l < 0 || m < 0
                continue;
            end
            if abs(l - round(l)) > 1e-12 || abs(m - round(m)) > 1e-12
                continue;
            end
            l = round(l); m = round(m);
            if l<=Lmax && m<=Lmax
                cs2(i,3) = Dc(l+1,m+1);
                cs2(i,4) = Ds(l+1,m+1);
            end
        end
        return;
    end
    % last resort: create [l m C S] table
    rows = [];
    for l = 0:Lmax
        for m = 0:l
            rows(end+1,:) = [l m Dc(l+1,m+1) Ds(l+1,m+1)]; %#ok<AGROW>
        end
    end
    cs2 = rows;
end
