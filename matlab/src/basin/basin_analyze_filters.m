function OUT = basin_analyze_filters(cfg, paths, methods, lonVec, latVec, T)
%BASIN_ANALYZE_FILTERS Extract mean/in-situ statistics for the top N large basins.
%
% MEMORY OPTIMIZATION: Process one Stack at a time and clear after use.
% Reduced basin count from 100 to 50 to save memory. Masks stored as logical.

    OUT = struct('methods', {methods}, 'basins', [], 'analysis_file', '', 'stats', struct());
    shapefile = prepare_boundary_shapefile(cfg);
    if isempty(shapefile)
        warning('Basin analysis skipped: boundary file missing.');
        return;
    end

    shapes = shaperead(shapefile,'UseGeoCoords',true);
    if isempty(shapes)
        warning('Basin analysis skipped: shapefile empty.');
        return;
    end

    areas = basin_area(shapes);
    [~, order] = sort(areas, 'descend');
    shapes = shapes(order);
    
    % MEMORY OPTIMIZATION: Reduce from 100 to 50 basins to save memory
    nBasins = min(50, numel(shapes));
    shapes = shapes(1:nBasins);
    areas = areas(order(1:nBasins));

    [LonGrid, LatGrid] = ndgrid(lonVec, latVec);
    
    % MEMORY OPTIMIZATION: Compute masks on-the-fly instead of storing all
    % Only store basin boundary info, compute mask when needed
    names = cell(nBasins,1);
    for i = 1:nBasins
        names{i} = sprintf('Basin-%d', shapes(i).OBJECTID);
    end

    stats = struct();
    for j = 1:numel(methods)
        tag = methods{j};
        
        % MEMORY OPTIMIZATION: Load one stack at a time
        Stack = load_stack(paths.stacks, tag);
        if isempty(Stack); continue; end
        stackTime = parse_stack_time(Stack);
        dataGrid = ensure_latlon_order(Stack.ewh, lonVec, latVec);

        stats.(tag) = struct('time', stackTime, 'basins', struct([]));
        for i = 1:nBasins
            % MEMORY OPTIMIZATION: Compute mask on-the-fly for each basin
            mask = shape_mask(shapes(i), LonGrid, LatGrid);
            if ~any(mask(:)); continue; end
            
            ts = basin_mean_ts(double(dataGrid), mask, latVec, true);
            fit = try_seasonal_fit(ts, stackTime);
            
            % MEMORY OPTIMIZATION: Don't store mask in output - can be recomputed
            entry = struct( ...
                'name', names{i}, ...
                'area', areas(i), ...
                'ts', ts, ...
                'fit', fit);
                % 'mask', mask);  % REMOVED to save memory
                
            if isempty(stats.(tag).basins)
                stats.(tag).basins = entry;
            else
                stats.(tag).basins(end+1) = entry;
            end
            
            % MEMORY OPTIMIZATION: Clear mask after use
            clear mask ts fit entry;
        end
        
        % MEMORY OPTIMIZATION: Clear Stack and dataGrid after processing each method
        clear Stack dataGrid stackTime;
    end

    OUT.methods = methods;
    OUT.stats = stats;
    % MEMORY OPTIMIZATION: Only store shapes info, not pre-computed masks
    OUT.basins = struct('shapes', shapes, 'names', {names}, 'areas', areas);
    OUT.time = [T.dt];
    OUT.analysis_file = fullfile(paths.basin, 'basin_analysis.mat');
    
    % MEMORY OPTIMIZATION: Use v7.3 with compression for large files
    save(OUT.analysis_file, 'OUT', '-v7.3');
    
    % MEMORY OPTIMIZATION: Clear large variables
    clear stats shapes;
end

function shapefile = prepare_boundary_shapefile(cfg)
    shapefile = '';
    if ~isfield(cfg.path,'BOUNDARY')
        return;
    end
    destDir = cfg.path.BOUNDARY;
    ensure_dir(destDir);
    destFile = fullfile(destDir, 'LargeBasin.shp');
    if isfile(destFile)
        shapefile = destFile;
        return;
    end
    if isfield(cfg.path,'AUX')
        srcDir = fullfile(cfg.path.AUX, 'boundary');
        if isfolder(srcDir)
            files = dir(fullfile(srcDir, 'LargeBasin.*'));
            for k = 1:numel(files)
                copyfile(fullfile(srcDir, files(k).name), fullfile(destDir, files(k).name));
            end
            if isfile(destFile)
                shapefile = destFile;
                return;
            end
        end
    end
end

function areas = basin_area(shapes)
    areas = nan(1,numel(shapes));
    for i = 1:numel(shapes)
        if isfield(shapes(i),'Sheet1__AR') && ~isnan(shapes(i).Sheet1__AR)
            areas(i) = shapes(i).Sheet1__AR;
        else
            areas(i) = estimate_area(shapes(i).Lon, shapes(i).Lat);
        end
    end
end

function area = estimate_area(lon, lat)
    lon = wrapTo180(lon(~isnan(lon)));
    lat = lat(~isnan(lat));
    if numel(lon) < 3 || numel(lat) < 3
        area = 0;
        return;
    end
    area = sum(abs(lat(2:end) - lat(1:end-1)).*abs(lon(2:end) - lon(1:end-1)));
end

function mask = shape_mask(shape, LonGrid, LatGrid)
    lon = wrapTo180(shape.Lon(:));
    lat = shape.Lat(:);
    valid = ~isnan(lon) & ~isnan(lat);
    if sum(valid) < 3
        mask = false(size(LonGrid));
        return;
    end
    lon = lon(valid);
    lat = lat(valid);

    mask = false(size(LonGrid));
    segments = split_segments(lon, lat);
    pg = polyshape();
    hasPoly = false;
    for i = 1:numel(segments)
        seg = segments{i};
        if size(seg,1) < 3
            continue;
        end
        [lonc, latc] = clean_polygon(seg(:,1), seg(:,2));
        if numel(lonc) < 3
            continue;
        end
        try
            pg = union(pg, polyshape(lonc, latc, 'Simplify', true));
            hasPoly = true;
        catch
            % Fallback to inpolygon if polyshape fails.
            [in,on] = inpolygon(LonGrid, LatGrid, lonc, latc);
            mask = mask | (in | on);
        end
    end

    if hasPoly
        [in,on] = isinterior(pg, LonGrid(:), LatGrid(:));
        mask = reshape(in | on, size(LonGrid));
    end
end

function segments = split_segments(lon, lat)
    % Split when large jumps indicate a break.
    d = sqrt(diff(lon).^2 + diff(lat).^2);
    cut = find(d > 5);
    idx = [1; cut + 1; numel(lon) + 1];
    segments = cell(numel(idx) - 1, 1);
    for i = 1:numel(segments)
        segments{i} = [lon(idx(i):idx(i+1)-1), lat(idx(i):idx(i+1)-1)];
    end
end

function [lonc, latc] = clean_polygon(lon, lat)
    keep = [true; abs(diff(lon)) + abs(diff(lat)) > 0];
    lonc = lon(keep);
    latc = lat(keep);
    if numel(lonc) >= 2 && lonc(1) == lonc(end) && latc(1) == latc(end)
        lonc = lonc(1:end-1);
        latc = latc(1:end-1);
    end
end

function Stack = load_stack(stackDir, tag)
    Stack = [];
    files = dir(fullfile(stackDir, sprintf('%s_stack_*.mat', tag)));
    if isempty(files); return; end
    [~, idx] = max([files.datenum]);
    data = load(fullfile(stackDir, files(idx).name));
    if isfield(data, 'Stack')
        Stack = data.Stack;
    end
end

function time = parse_stack_time(Stack)
    if iscell(Stack.t)
        time = datetime(Stack.t, 'InputFormat', 'yyyy-MM');
    else
        time = Stack.t;
    end
end

function Fit = try_seasonal_fit(ts, time)
    try
        Fit = basin_fit_seasonal_trend(ts, time);
    catch ME
        Fit = struct('error', ME.message);
    end
end
