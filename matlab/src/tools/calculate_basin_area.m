function [name,areas,sorted_idx] = calculate_basin_area(rivers)
%CALCULATE_BASIN_AREA Calculate area of river basins from shapefile data.
%
% Description:
%   Computes the area of river basins defined by polygon shapefiles using
%   a 0.5-degree grid approximation with spherical Earth assumption.
%
% INPUT:
%   rivers - Structure array from shaperead() containing basin polygons
%            Each element must have: X, Y (coordinates), BoundingBox, DRAINAGE (name)
%
% OUTPUT:
%   name       - Cell array of basin names sorted by area (descending)
%   areas      - Vector of basin areas in square meters (sorted descending)
%   sorted_idx - Original indices after sorting
%
% Method:
%   1. Create 0.5-degree grid over each basin's bounding box
%   2. Check if grid cell centers fall within the basin polygon
%   3. Sum trapezoid areas on spherical Earth (R = 6371 km)
%
% See also: trapezoid_area, inpolygon, shaperead
%
% Author: GRACE Pipeline Team

    areas = zeros(length(rivers), 1);
    names = cell(1, length(rivers));
    
    for k = 1:length(rivers)
        river = rivers(k);
        X = river.X;
        Y = river.Y;
        BoundingBox = river.BoundingBox;
        names{k} = rivers(k).DRAINAGE;
        
        % Extract bounding box limits
        min_lon = BoundingBox(1);
        max_lon = BoundingBox(2);
        min_lat = BoundingBox(3);
        max_lat = BoundingBox(4);
        
        % Create 0.5-degree grid
        lons = min_lon:0.5:max_lon;
        lats = min_lat:0.5:max_lat;
        
        % Initialize basin area accumulator
        basin_area = 0;
        
        % Calculate grid cell areas and check if inside basin
        for i = 1:length(lons)-1
            for j = 1:length(lats)-1
                lon1 = lons(i);
                lon2 = lons(i+1);
                lat1 = lats(j);
                lat2 = lats(j+1);
                
                % Compute grid cell center
                center_lon = (lon1 + lon2) / 2;
                center_lat = (lat1 + lat2) / 2;
                
                % Check if center is inside the basin polygon
                if inpolygon(center_lon, center_lat, X, Y)
                    % Calculate spherical trapezoid area (Earth radius = 6371 km)
                    grid_area = trapezoid_area(lat1, lat2, lon1, lon2, 6371000);
                    basin_area = basin_area + grid_area;
                end
            end
        end
        
        areas(k) = basin_area;
    end
    
    % Sort basins by area in descending order
    [areas, sort_idx] = sort(areas, 'descend');
    name = names(sort_idx);
    sorted_idx = sort_idx;
end