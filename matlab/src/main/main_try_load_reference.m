function [Pref, ok] = main_try_load_reference(cfg, Tk, lonVec, latVec)
%MAIN_TRY_LOAD_REFERENCE Try to load reference (default: Mascon) for a given month.
% This is an extensible hook: you can support HIS True fields for closed-loop tests.

    ok = false;
    Pref = struct();

    % ---- 1) Mascon reference (recommended) ----
    if isfield(cfg,'reference') && isfield(cfg.reference,'type')
        typ = lower(string(cfg.reference.type));
    else
        typ = "mascon";
    end

    switch typ
        case "mascon"
            [Pref, ok] = main_try_load_mascon(cfg, Tk, lonVec, latVec);
        case "his_true"
            [Pref, ok] = main_try_load_his_true(cfg, Tk, lonVec, latVec);
        otherwise
            ok = false;
    end
end

function [P, ok] = main_try_load_mascon(cfg, Tk, lonVec, latVec)
    ok = false;
    P = struct();

    % User can define:
    %   cfg.reference.mascon_dir
    %   cfg.reference.mascon_pattern (supports {YYYYMM})
    masDir = '';
    pat = 'Mascon_{YYYYMM}.mat';

    if isfield(cfg,'reference') && isfield(cfg.reference,'mascon_dir')
        masDir = cfg.reference.mascon_dir;
    elseif isfield(cfg,'path') && isfield(cfg.path,'AUX')
        masDir = fullfile(cfg.path.AUX, 'mascon');
    end
    if isfield(cfg,'reference') && isfield(cfg.reference,'mascon_pattern')
        pat = cfg.reference.mascon_pattern;
    end

    if isempty(masDir) || ~isfolder(masDir)
        return;
    end

    yyyymm = Tk.yyyymm;
    fp = fullfile(masDir, strrep(pat, '{YYYYMM}', yyyymm));

    if ~isfile(fp)
        d = dir(fullfile(masDir, ['*' yyyymm '*']));
        if ~isempty(d)
            fp = fullfile(d(1).folder, d(1).name);
        else
            % fallback: if only one netCDF exists, use it
            dnc = dir(fullfile(masDir, '*.nc'));
            if isempty(dnc)
                return;
            end
            fp = fullfile(dnc(1).folder, dnc(1).name);
        end
    end

    try
        [X, metaGrid] = read_reference_grid(fp, Tk, cfg);
    catch ME
        warning('Failed loading Mascon reference: %s', ME.message);
        return;
    end

    % Handle missing month case (X is empty)
    if isempty(X)
        return;  % ok remains false
    end

    [X, metaGrid] = resample_reference_grid(X, metaGrid, lonVec, latVec);

    nLon = numel(lonVec); nLat = numel(latVec);
    if isequal(size(X), [nLat, nLon]); X = X.'; end
    if ~isequal(size(X), [nLon, nLat])
        return;
    end

    meta = metaGrid;
    meta.source = 'Mascon';
    P = io_make_product('Mascon', Tk, lonVec, latVec, X, meta);
    ok = true;
end

function [X, meta] = read_reference_grid(fp, Tk, cfg)
    [~,~,ext] = fileparts(fp);
    meta = struct('file', fp, 'format', 'unknown');
    switch lower(ext)
        case '.mat'
            [X, fieldName] = load_mat_reference(fp);
            meta.format = 'mat';
            meta.field = fieldName;
        case {'.nc', '.nc4', '.cdf'}
            info = ncinfo(fp);
            varName = pick_reference_variable(info);
            if isempty(varName)
                error('No suitable variable found in %s', fp);
            end
            varInfo = ncinfo(fp, varName);
            dimNames = {varInfo.Dimensions.Name};
            timeDimIdx = find(strcmpi(dimNames, 'time'), 1);
            if isempty(timeDimIdx)
                X = ncread(fp, varName);
            else
                timeInfo = ncinfo(fp, 'time');
                timeVals = ncread(fp, 'time');
                dtVec = nc_time_to_datetime(timeInfo, timeVals);
                [idx, matchMeta] = find_reference_time_index(dtVec, Tk, cfg);
                if isempty(idx)
                    warning('REFERENCE:MonthNotFound', 'Mascon reference does not cover %s (available: %s to %s)', ...
                        Tk.ym, datestr(dtVec(1), 'yyyy-mm'), datestr(dtVec(end), 'yyyy-mm'));
                    X = [];
                    meta.format = 'netcdf';
                    meta.missing_month = true;
                    return;
                end
                start = ones(1, numel(dimNames));
                count = varInfo.Size;
                start(timeDimIdx) = idx;
                count(timeDimIdx) = 1;
                X = ncread(fp, varName, start, count);
            end
            X = squeeze(X);
            % 使用 size 检查维度，避免 ndims 问题
            szX = size(X);
            if numel(szX) > 2 && szX(3) > 1
                X = X(:,:,1);
            end
            try
                meta.lon = ncread(fp, 'lon');
                meta.lat = ncread(fp, 'lat');
            catch
                % ignore missing coordinates
            end
            meta.format = 'netcdf';
            meta.variable = varName;
            if ~isempty(timeDimIdx) && exist('dtVec','var') && ~isempty(idx)
                meta.time = dtVec(idx);
                meta.match = matchMeta;
            end

            % Optional: undo CSR Mascon corrections for comparison
            if isfield(cfg,'reference') && isfield(cfg.reference,'mascon_undo') && ...
                    isfield(cfg.reference.mascon_undo,'enable') && cfg.reference.mascon_undo.enable
                [X, meta] = apply_mascon_undo(cfg, fp, Tk, X, meta);
            end
        otherwise
            error('Unsupported reference format ''%s''', ext);
    end
    if ~ismatrix(X)
        error('Reference grid %s must be 2-D', fp);
    end
end


function [X, fieldName] = load_mat_reference(fp)
    S = load(fp);
    if isfield(S,'EWH')
        X = S.EWH;
        fieldName = 'EWH';
    elseif isfield(S,'ewh')
        X = S.ewh;
        fieldName = 'ewh';
    elseif isfield(S,'grid') && isfield(S.grid,'ewh')
        X = S.grid.ewh;
        fieldName = 'grid.ewh';
    else
        error('MAT file %s lacks EWH/ewh/grid.ewh variables', fp);
    end
end

function [X, meta] = apply_mascon_undo(cfg, fp, Tk, X, meta)
%APPLY_MASCON_UNDO Undo CSR Mascon corrections: X = X - GAD + GIA.
    masDir = '';
    if isfield(cfg,'reference') && isfield(cfg.reference,'mascon_dir')
        masDir = cfg.reference.mascon_dir;
    end
    if isempty(masDir)
        [masDir, ~, ~] = fileparts(fp);
    end

    gadFile = '';
    giaFile = '';
    if isfield(cfg.reference,'mascon_undo')
        if isfield(cfg.reference.mascon_undo,'gad_file'); gadFile = cfg.reference.mascon_undo.gad_file; end
        if isfield(cfg.reference.mascon_undo,'gia_file'); giaFile = cfg.reference.mascon_undo.gia_file; end
    end
    if isempty(gadFile); gadFile = 'CSR_GRACE_GRACE-FO_RL0603_Mascons_GAD-component.nc'; end
    if isempty(giaFile); giaFile = 'CSR_GRACE_GRACE-FO_RL0603_Mascons_GIA-component.nc'; end

    if isfile(gadFile)
        gadPath = gadFile;
    else
        gadPath = fullfile(masDir, gadFile);
    end
    if isfile(giaFile)
        giaPath = giaFile;
    else
        giaPath = fullfile(masDir, giaFile);
    end

    if ~isfile(gadPath) || ~isfile(giaPath)
        warning('Mascon undo enabled but component files not found. GAD: %s, GIA: %s', gadPath, giaPath);
        return;
    end

    try
        Xgad = read_mascon_component(gadPath, Tk, cfg);
        Xgia = read_mascon_component(giaPath, Tk, cfg);
        X = X - Xgad + Xgia;
        meta.corrections = 'Mascon undo: X = X - GAD + GIA';
        meta.gad_file = gadPath;
        meta.gia_file = giaPath;
    catch ME
        warning('Failed to apply Mascon undo: %s', ME.message);
    end
end

function X = read_mascon_component(fp, Tk, cfg)
%READ_MASCON_COMPONENT Read lwe_thickness from component file at Tk.
    info = ncinfo(fp);
    varName = pick_reference_variable(info);
    if isempty(varName)
        error('No suitable variable found in %s', fp);
    end
    X = read_netcdf_time_slice(fp, varName, Tk, cfg);
    X = squeeze(X);
end

function X = read_netcdf_time_slice(fp, varName, Tk, cfg)
%READ_NETCDF_TIME_SLICE Read varName at Tk from netCDF.
    varInfo = ncinfo(fp, varName);
    dimNames = {varInfo.Dimensions.Name};
    timeDimIdx = find(strcmpi(dimNames, 'time'), 1);
    if isempty(timeDimIdx)
        X = ncread(fp, varName);
        return;
    end
    timeInfo = ncinfo(fp, 'time');
    timeVals = ncread(fp, 'time');
    dtVec = nc_time_to_datetime(timeInfo, timeVals);
    [idx, ~] = find_reference_time_index(dtVec, Tk, cfg);
    if isempty(idx)
        error('Mascon component does not cover %s.', Tk.ym);
    end
    start = ones(1, numel(dimNames));
    count = varInfo.Size;
    start(timeDimIdx) = idx;
    count(timeDimIdx) = 1;
    X = ncread(fp, varName, start, count);
end

function [idx, meta] = find_reference_time_index(dtVec, Tk, cfg)
%FIND_REFERENCE_TIME_INDEX Match Mascon time by exact month first, then GFC-aware date fallback.
    idx = [];
    meta = struct('mode', 'unmatched');

    if nargin < 2 || isempty(Tk)
        idx = 1;
        meta.mode = 'first';
        return;
    end

    idx = find(dtVec.Year == Tk.dt.Year & dtVec.Month == Tk.dt.Month, 1);
    if ~isempty(idx)
        meta.mode = 'exact_month';
        meta.target_time = Tk.dt;
        meta.reference_time = dtVec(idx);
        meta.delta_days = abs(days(dtVec(idx) - Tk.dt));
        return;
    end

    allowFallback = true;
    if isfield(cfg,'reference') && isfield(cfg.reference,'allow_nearest_month')
        allowFallback = logical(cfg.reference.allow_nearest_month);
    end
    if ~allowFallback
        idx = [];
        return;
    end

    tolDays = 45;
    if isfield(cfg,'reference') && isfield(cfg.reference,'nearest_month_tolerance_days')
        tolDays = cfg.reference.nearest_month_tolerance_days;
    end

    targetDT = Tk.dt;
    if isfield(Tk,'gfc_mid_dt') && isdatetime(Tk.gfc_mid_dt) && ~isnat(Tk.gfc_mid_dt)
        targetDT = Tk.gfc_mid_dt;
        meta.target_source = 'gfc_mid_dt';
    else
        meta.target_source = 'month_start';
    end

    [dmin, idxNear] = min(abs(days(dtVec - targetDT)));
    if isempty(idxNear) || dmin > tolDays
        idx = [];
        return;
    end

    idx = idxNear;
    meta.mode = 'date_fallback';
    meta.target_time = targetDT;
    meta.reference_time = dtVec(idx);
    meta.delta_days = dmin;
end

function varName = pick_reference_variable(info)
    varName = '';
    if isempty(info.Variables)
        return;
    end
    names = lower({info.Variables.Name});
    candidates = {'lwe_thickness','mascon','ewh','lwe','grid','data','field'};
    for i = 1:numel(candidates)
        matches = find(contains(names, candidates{i}));
        if ~isempty(matches)
            varName = info.Variables(matches(1)).Name;
            return;
        end
    end
    for i = 1:numel(info.Variables)
        if numel(info.Variables(i).Size) < 2
            continue;
        end
        nm = names{i};
        if any(contains(nm, {'lon','lat','latitude','longitude','time','month','day'}))
            continue;
        end
        varName = info.Variables(i).Name;
        return;
    end
end

function [Xout, meta] = resample_reference_grid(X, meta, lonVec, latVec)
    Xout = X;
    if isempty(X) || ~isfield(meta, 'lon') || ~isfield(meta, 'lat')
        return;
    end
    lonRef = meta.lon(:);
    latRef = meta.lat(:);
    if isequal(size(Xout), [numel(latRef), numel(lonRef)])
        Xout = Xout.';
    end
    lonRef = mod(lonRef + 180, 360) - 180;
    [lonRef, iLon] = sort(lonRef);
    Xout = Xout(iLon, :);
    [latRef, iLat] = sort(latRef);
    Xout = Xout(:, iLat);

    F = griddedInterpolant({lonRef, latRef}, Xout, 'linear', 'nearest');
    [LonQ, LatQ] = ndgrid(lonVec(:), latVec(:));
    Xout = F(LonQ, LatQ);

    meta.lon = lonVec;
    meta.lat = latVec;
    meta.resampled = true;
end

function [P, ok] = main_try_load_his_true(cfg, Tk, lonVec, latVec)
    ok = false; P = struct();
    if ~isfield(cfg,'reference') || ~isfield(cfg.reference,'his_true_dir'); return; end
    d0 = cfg.reference.his_true_dir;
    if ~isfolder(d0); return; end
    yyyymm = Tk.yyyymm;
    fp = fullfile(d0, sprintf('HIS_TRUE_%s.mat', yyyymm));
    if ~isfile(fp); return; end
    S = load(fp);
    if isfield(S,'EWH'); X=S.EWH; elseif isfield(S,'ewh'); X=S.ewh; else; return; end
    nLon=numel(lonVec); nLat=numel(latVec);
    if isequal(size(X), [nLat, nLon]); X=X.'; end
    if ~isequal(size(X), [nLon, nLat]); return; end
    P = io_make_product('HIS_TRUE', Tk, lonVec, latVec, X, struct('source','HIS_TRUE','file',fp));
    ok = true;
end
