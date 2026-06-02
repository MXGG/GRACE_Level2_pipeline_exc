function B = basin_read_boundary(filePath, nameField)
%BASIN_READ_BOUNDARY Read basin boundary from .shp or txt (lon lat).
% Output B is a struct array with fields:
%   Name, Lon, Lat

    if nargin < 2 || isempty(nameField); nameField = 'Name'; end
    if ~isfile(filePath)
        error('Boundary file not found: %s', filePath);
    end

    [~,~,ext] = fileparts(filePath);
    ext = lower(ext);

    switch ext
        case '.shp'
            B = read_shapefile(filePath, nameField);
        otherwise
            B = read_txt_poly(filePath);
    end
end

function B = read_shapefile(fp, nameField)
    if exist('shaperead','file') == 2
        S = shaperead(fp,'UseGeoCoords',true);
        B = repmat(struct('Name','','Lon',[],'Lat',[]), numel(S), 1);
        for i = 1:numel(S)
            B(i).Name = pick_name_field(S(i), nameField, i);
            B(i).Lon = wrap_lon(S(i).Lon(:));
            B(i).Lat = S(i).Lat(:);
        end
        return;
    end

    if exist('m_shaperead','file') == 2
        S = m_shaperead(fp);
        B = repmat(struct('Name','','Lon',[],'Lat',[]), numel(S), 1);
        for i = 1:numel(S)
            B(i).Name = pick_name_field(S(i), nameField, i);
            if isfield(S(i),'ncst')
                B(i).Lon = wrap_lon(S(i).ncst(:,1));
                B(i).Lat = S(i).ncst(:,2);
            elseif isfield(S(i),'X') && isfield(S(i),'Y')
                B(i).Lon = wrap_lon(S(i).X(:));
                B(i).Lat = S(i).Y(:);
            else
                error('Unrecognized m_shaperead output.');
            end
        end
        return;
    end

    error('No shapefile reader found. Need Mapping Toolbox (shaperead) or m_map (m_shaperead).');
end

function B = read_txt_poly(fp)
    M = readmatrix(fp);
    if size(M,2) < 2
        error('TXT boundary must have at least 2 columns: lon lat');
    end
    lon = wrap_lon(M(:,1)); lat = M(:,2);

    % Split by NaNs
    nanIdx = isnan(lon) | isnan(lat);
    seg = split_by_nan(lon, lat, nanIdx);

    B = repmat(struct('Name','','Lon',[],'Lat',[]), numel(seg), 1);
    for i = 1:numel(seg)
        B(i).Name = sprintf('poly_%d', i);
        B(i).Lon = seg{i}(:,1);
        B(i).Lat = seg{i}(:,2);
    end
end

function lon = wrap_lon(lon)
    if exist('wrapTo180','file') == 2
        lon = wrapTo180(lon);
    else
        lon = mod(lon + 180, 360) - 180;
    end
end

function name = pick_name_field(Si, nameField, idx)
    name = '';
    if ~isempty(nameField) && isfield(Si, nameField)
        name = char(string(Si.(nameField)));
    elseif isfield(Si, 'NAME')
        name = char(string(Si.NAME));
    elseif isfield(Si, 'Name')
        name = char(string(Si.Name));
    elseif isfield(Si, 'whymap_r_2')
        name = char(string(Si.whymap_r_2));
    elseif isfield(Si, 'whymap_riv')
        name = char(string(Si.whymap_riv));
    elseif isfield(Si, 'OBJECTID')
        name = sprintf('OBJECTID_%d', Si.OBJECTID);
    end
    if isempty(name)
        name = sprintf('poly_%d', idx);
    end
end

function seg = split_by_nan(lon, lat, nanIdx)
    seg = {};
    start = 1;
    n = numel(lon);
    for i = 1:n
        if nanIdx(i)
            if i-1 >= start
                seg{end+1} = [lon(start:i-1), lat(start:i-1)]; %#ok<AGROW>
            end
            start = i+1;
        end
    end
    if start <= n
        seg{end+1} = [lon(start:n), lat(start:n)]; %#ok<AGROW>
    end
end
