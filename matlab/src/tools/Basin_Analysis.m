function [Annual_Amplitude, Semi_Amplitude, Trend, Residual, Average_Time_Series,b] = Basin_Analysis(Basin_Grid, t, ~, Basin_Lat)
%BASIN_ANALYSIS Comprehensive basin analysis to extract trend and seasonal signals.
%
% Description:
%   Performs weighted spatial averaging of gridded time series over a basin,
%   then fits annual/semi-annual harmonics and linear trend using least squares.
%
% INPUT:
%   Basin_Grid   - 3D array [nLon x nLat x Nt] of EWH values (NaN outside basin)
%   t            - Time vector in decimal years
%   ~            - Unused parameter (placeholder for compatibility)
%   Basin_Lat    - Vector of latitude values for the grid
%
% OUTPUT:
%   Annual_Amplitude   - Amplitude of annual signal (mm)
%   Semi_Amplitude     - Amplitude of semi-annual signal (mm)
%   Trend              - Linear trend (mm/year)
%   Residual           - Residual after removing fitted signals
%   Average_Time_Series - Area-weighted basin mean time series
%   b                  - Intercept term for trend line
%
% Method:
%   1. Compute area-weighted (cosine of latitude) spatial average
%   2. Fit model: y = A0 + trend*t + A_cos*cos(2*pi*t) + A_sin*sin(2*pi*t)
%                      + B_cos*cos(4*pi*t) + B_sin*sin(4*pi*t)
%   3. Extract amplitudes: Annual = sqrt(A_cos^2 + A_sin^2)
%                          Semi   = sqrt(B_cos^2 + B_sin^2)
%
% Author: GRACE Pipeline Team

    % Reference time span for computing intercept
    start_date = datetime(2003,1,1);
    end_date = datetime(2007,12,1);
    dates = start_date:calmonths(1):end_date;
    years = year(dates) + (day(dates,'dayofyear') - 1) / days(datetime(year(dates), 12, 31) - datetime(year(dates), 1, 1) + 1);

    [num_rows, num_cols] = size(Basin_Grid,[1,2]);
    
    % Initialize weighted sum of time series
    time_series_sum = zeros(1, size(Basin_Grid,3));
    tag = 0;  % Counter for valid grid points
    
    % Loop over all grid points
    for i = 1:num_rows
        for j = 1:num_cols
            if ~isnan(Basin_Grid(i, j))
                % Compute latitude weight (cosine weighting for area)
                tag = tag + 1;
                lat = Basin_Lat(j);
                weight = cosd(lat);
                
                % Extract time series for this grid point
                time_series = Basin_Grid(i, j, :);
                time_series = squeeze(time_series);  % Remove singleton dimensions
                
                % Accumulate weighted sum
                time_series_sum = time_series_sum + weight * time_series';
            end
        end
    end
    
    % Compute basin-averaged time series
    Average_Time_Series = time_series_sum / tag;
    
    % Build design matrix for least-squares fit
    % Model: offset + trend + annual + semi-annual harmonics
    n = 1:length(Average_Time_Series);
    X = [ones(length(n), 1), t', cos(2*pi*t'), sin(2*pi*t'), cos(4*pi*t'), sin(4*pi*t')];
    
    % Solve using ordinary least squares: beta = (X'X)^-1 * X'Y
    Y = Average_Time_Series';
    beta = (X' * X) \ X' * Y;
    
    % Extract fitted coefficients
    A0 = beta(1);      % Offset (unused in output)
    Atr = beta(2);     % Linear trend
    Ac_an = beta(3);   % Annual cosine coefficient
    As_an = beta(4);   % Annual sine coefficient
    Ac_se = beta(5);   % Semi-annual cosine coefficient
    As_se = beta(6);   % Semi-annual sine coefficient
    
    % Compute amplitudes and trend
    Trend = Atr;
    Annual_Amplitude = sqrt(Ac_an^2 + As_an^2);
    Semi_Amplitude = sqrt(Ac_se^2 + As_se^2);
    
    % Compute residual (observed - fitted)
    Residual = Y - X * beta;
    
    % Compute intercept for trend line at reference time
    b = mean(Average_Time_Series) - Trend * mean(years(1:48));
end
