function [rangeLon, rangeLat, mask] = mkmask(shpf, deltD)
%MKMASK Create binary mask from shapefile polygon(s).
%
% Description:
%   Generates a 2D binary mask grid from one or more shapefile polygons.
%   Grid points inside any polygon are marked as 1, outside as NaN.
%
% INPUT:
%   shpf   - Structure array from shaperead() with X and Y coordinate fields
%   deltD  - Grid spacing in degrees (e.g., 0.5 or 1.0)
%
% OUTPUT:
%   rangeLon - Vector of longitude grid points
%   rangeLat - Vector of latitude grid points
%   mask     - 2D matrix [numel(rangeLat) x numel(rangeLon)]
%              Values: 1 (inside polygon), NaN (outside)
%
% Example:
%   shp = shaperead('basin.shp');
%   [lon, lat, mask] = mkmask(shp, 0.5);
%   imagesc(lon, lat, mask);
%
% See also: shaperead, inpolygon
%
% Author: GRACE Pipeline Team

    Boundaries = cell(length(shpf), 1);
    
    % Find global bounding box across all polygons
    allLonWest = inf;
    allLonEast = -inf;
    allLatSouth = inf;
    allLatNorth = -inf;
    
    for i = 1:length(shpf)
        Boundaries{i} = [shpf(i).X; shpf(i).Y];
        lonWest = min(shpf(i).X);
        lonEast = max(shpf(i).X);
        latSouth = min(shpf(i).Y);
        latNorth = max(shpf(i).Y);
        allLonWest = min(allLonWest, lonWest);
        allLonEast = max(allLonEast, lonEast);
        allLatSouth = min(allLatSouth, latSouth);
        allLatNorth = max(allLatNorth, latNorth);
    end
    
    % Extend bounding box by half grid cell on each side
    lonWest = floor(allLonWest) - deltD / 2;
    lonEast = ceil(allLonEast) + deltD / 2;
    latSouth = floor(allLatSouth) - deltD / 2;
    latNorth = ceil(allLatNorth) + deltD / 2;
    
    % Create grid vectors
    rangeLon = lonWest : deltD : lonEast;
    rangeLat = latSouth : deltD : latNorth;
    
    % Create meshgrid for point-in-polygon testing
    [mhLon, mhLat] = meshgrid(rangeLon, rangeLat);
    mask = zeros(size(mhLon));
    
    % Test each polygon and accumulate mask
    for i = 1:length(shpf)
        xv = shpf(i).X;
        yv = shpf(i).Y;
        maskcell = inpolygon(mhLon, mhLat, xv, yv);
        mask = mask + maskcell;
    end
    
    % Convert to binary mask (1 inside, NaN outside)
    mask(mask == 0) = NaN;
end