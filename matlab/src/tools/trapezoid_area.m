function area = trapezoid_area(lat1, lat2, lon1, lon2, R)
%TRAPEZOID_AREA Calculate area of a latitude-longitude cell on a sphere.
%
% Description:
%   Computes the area of a trapezoidal grid cell on a spherical Earth
%   defined by latitude and longitude bounds.
%
% INPUT:
%   lat1 - Southern latitude bound (degrees)
%   lat2 - Northern latitude bound (degrees)
%   lon1 - Western longitude bound (degrees, unused in calculation)
%   lon2 - Eastern longitude bound (degrees, unused in calculation)
%   R    - Earth radius in meters (e.g., 6371000)
%
% OUTPUT:
%   area - Grid cell area in square meters
%
% Method:
%   Approximates the cell as a trapezoid where:
%   - Height = arc length along meridian = R * delta_lat
%   - Parallel sides = arc lengths at each latitude = R * cos(lat)
%
% Note:
%   This is a first-order approximation. For more accurate results,
%   use the exact spherical formula with longitude extent.
%
% Author: GRACE Pipeline Team

    % Convert degrees to radians
    lat1 = deg2rad(lat1);
    lat2 = deg2rad(lat2);
    lon1 = deg2rad(lon1);
    lon2 = deg2rad(lon2);
    
    % Calculate parallel lengths at each latitude
    L1 = R * cos(lat1);
    L2 = R * cos(lat2);
    
    % Calculate meridional arc length (trapezoid height)
    h = R * abs(lat2 - lat1);
    
    % Trapezoid area formula: A = 0.5 * (b1 + b2) * h
    area = 0.5 * (L1 + L2) * h;
end