function Fit = basin_fit_seasonal_trend(y, t)
%BASIN_FIT_SEASONAL_TREND Least-squares fit: trend + annual + semi-annual.
%
% Model:
%   y(t) = a0 + a1*(t- t0) + A1*sin(2π*(t-t0)) + B1*cos(2π*(t-t0))
%                    + A2*sin(4π*(t-t0)) + B2*cos(4π*(t-t0)) + e
%
% Inputs:
%   y : Nx1
%   t : datetime array (N) or numeric year fraction
%
% Output Fit:
%   Fit.coef, Fit.yfit, Fit.res, Fit.trend_per_yr,
%   Fit.annual_amp, Fit.annual_phase_rad,
%   Fit.semi_amp, Fit.semi_phase_rad, Fit.R2

    y = y(:);
    if isdatetime(t)
        tn = yearfrac(t);
    else
        tn = t(:);
    end
    if numel(tn) ~= numel(y)
        error('t and y must have same length.');
    end

    v = isfinite(y) & isfinite(tn);
    yv = y(v);
    tv = tn(v);

    if numel(yv) < 8
        error('Not enough valid points for seasonal fit.');
    end

    t0 = mean(tv);
    x = tv - t0;

    X = [ones(size(x)), x, ...
         sin(2*pi*x), cos(2*pi*x), ...
         sin(4*pi*x), cos(4*pi*x)];

    coef = X \ yv;
    yfit_v = X * coef;

    yfit = nan(size(y));
    yfit(v) = yfit_v;

    res = y - yfit;

    % metrics
    ss_res = nansum((yv - yfit_v).^2);
    ss_tot = nansum((yv - mean(yv)).^2);
    R2 = 1 - ss_res/(ss_tot+eps);

    A1 = coef(3); B1 = coef(4);
    A2 = coef(5); B2 = coef(6);

    Fit = struct();
    Fit.coef = coef;
    Fit.t0 = t0;
    Fit.yfit = yfit;
    Fit.res = res;
    Fit.trend_per_yr = coef(2);

    Fit.annual_amp = sqrt(A1^2 + B1^2);
    Fit.annual_phase_rad = atan2(B1, A1); % consistent with sin+cos form

    Fit.semi_amp = sqrt(A2^2 + B2^2);
    Fit.semi_phase_rad = atan2(B2, A2);

    Fit.R2 = R2;
end

function yf = yearfrac(t)
    % approximate year fraction using days since first point
    t = t(:);
    t0 = t(1);
    dt = days(t - t0);
    yf = year(t0) + (month(t0)-1)/12 + dt/365.2425;
end
