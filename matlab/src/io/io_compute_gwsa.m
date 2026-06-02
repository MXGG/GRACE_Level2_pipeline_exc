function [P, ok] = io_compute_gwsa(cfg, Tk, lonVec, latVec)
%IO_COMPUTE_GWSA Compute GWSA if GLDAS NOAH data is available that matches Tk.
    ok = false;
    P = struct();
    if nargin < 4 || ~isfield(cfg,'gldas') || ~isfield(cfg.gldas,'dir'); return; end

    gdir = cfg.gldas.dir;
    if ~isfolder(gdir); return; end

    pattern = 'GLDAS_NOAH_{YYYYMM}.nc';
    if isfield(cfg.gldas,'pattern') && ~isempty(cfg.gldas.pattern)
        pattern = cfg.gldas.pattern;
    end

    file = fullfile(gdir, strrep(pattern, '{YYYYMM}', Tk.yyyymm));
    if ~isfile(file); return; end

    info = ncinfo(file);
    lonName = first_existing_variable(info, {'lon','longitude'});
    latName = first_existing_variable(info, {'lat','latitude'});
    timeName = first_existing_variable(info, {'time'});
    if isempty(lonName) || isempty(latName) || isempty(timeName)
        warning('GLDAS file %s lacks lon/lat/time variables.', file);
        return;
    end

    lonRef = ncread(file, lonName);
    latRef = ncread(file, latName);
    timeInfo = ncinfo(file, timeName);
    timeVals = ncread(file, timeName);
    dtVec = nc_time_to_datetime(timeInfo, timeVals);
    idx = find(dtVec.Year == Tk.dt.Year & dtVec.Month == Tk.dt.Month, 1);
    if isempty(idx)
        warning('GLDAS file %s does not cover %s.', file, Tk.ym);
        return;
    end

    twsName = first_existing_variable(info, config_field(cfg.gldas,'vars','tws','lwe_thickness'));
    if isempty(twsName)
        warning('No TWS variable found in %s.', file);
        return;
    end
    tws = read_var_at_time(file, twsName, idx);

    soilNames = config_field(cfg.gldas,'vars','soil', {'SoilMoi00_10cm_inst','SoilMoi10_40cm_inst','SoilMoi40_100cm_inst'});
    soil = zeros(size(tws));
    for i = 1:numel(soilNames)
        varName = first_existing_variable(info, soilNames{i});
        if isempty(varName); continue; end
        soil = soil + read_var_at_time(file, varName, idx);
    end

    snowName = first_existing_variable(info, config_field(cfg.gldas,'vars','snow','SWE_inst'));
    snow = zeros(size(tws));
    if ~isempty(snowName)
        snow = read_var_at_time(file, snowName, idx);
    end

    canopyName = first_existing_variable(info, config_field(cfg.gldas,'vars','canopy','CanopyWater_inst'));
    canopy = zeros(size(tws));
    if ~isempty(canopyName)
        canopy = read_var_at_time(file, canopyName, idx);
    end

    lonRef = lonRef(:);
    latRef = latRef(:);
    lonRef = wrapTo180(lonRef);

    comp = soil + snow + canopy;
    gwsaGrid = tws - comp;
    [grid, lonRefSorted, latRefSorted] = align_grid(gwsaGrid, lonRef, latRef);

    lonVec180 = wrapTo180(lonVec(:));
    latVecCol = latVec(:);
    F = griddedInterpolant({lonRefSorted, latRefSorted}, grid, 'linear', 'nearest');
    [LonQ, LatQ] = ndgrid(lonVec180, latVecCol);
    gwsa = F(LonQ, LatQ);

    meta = struct('source','GLDAS','file',file,'time',dtVec(idx),'components', struct('soil',nnz(soil>0),'snow',nnz(snow>0),'canopy',nnz(canopy>0)));
    P = io_make_product('GWSA', Tk, lonVec, latVec, gwsa, meta);
    ok = true;
end

function val = config_field(cfg, group, field, defaultVal)
    val = defaultVal;
    if ~isfield(cfg, group); return; end
    groupStruct = cfg.(group);
    if isstruct(groupStruct) && isfield(groupStruct, field) && ~isempty(groupStruct.(field))
        val = groupStruct.(field);
    end
end

function names = first_existing_variable(info, candidate)
    if isempty(candidate)
        names = '';
        return;
    end
    if ischar(candidate)
        candidate = {candidate};
    end
    varNames = {info.Variables.Name};
    names = '';
    for j = 1:numel(candidate)
        idx = find(strcmpi(varNames, candidate{j}), 1);
        if ~isempty(idx)
            names = varNames{idx};
            return;
        end
    end
end

function [grid, lonSorted, latSorted] = align_grid(data, lonRef, latRef)
    sz = size(data);
    if numel(sz) ~= 2
        error('Expected 2-D grid data, got %d-D.', numel(sz));
    end
    if sz(1) == numel(lonRef) && sz(2) == numel(latRef)
        grid = data;
    elseif sz(1) == numel(latRef) && sz(2) == numel(lonRef)
        grid = data.';
    else
        grid = reshape(data, [numel(lonRef), numel(latRef)]);
    end
    [lonSorted, iLon] = sort(lonRef);
    grid = grid(iLon, :);
    [latSorted, iLat] = sort(latRef);
    grid = grid(:, iLat);
end

function data = read_var_at_time(file, varName, idx)
    info = ncinfo(file, varName);
    dims = info.Dimensions;
    start = ones(1,numel(dims));
    count = info.Size;
    tdim = find(strcmpi({dims.Name}, 'time'), 1);
    if ~isempty(tdim)
        start(tdim) = idx;
        count(tdim) = 1;
    end
    data = ncread(file, varName, start, count);
    data = double(squeeze(data));
end
