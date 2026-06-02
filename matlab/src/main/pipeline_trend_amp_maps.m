function [trendMap, ampMap] = pipeline_trend_amp_maps(grid, t)
%PIPELINE_TREND_AMP_MAPS Estimate trend and annual amplitude on each grid cell.

    nLon = size(grid,1);
    nLat = size(grid,2);
    Nt = size(grid,3);

    tNum = datenum(t);
    tYear = (tNum - tNum(1)) / 365.25;
    tYear = tYear(:);

    X = [ones(Nt,1), tYear, sin(2*pi*tYear), cos(2*pi*tYear)];

    Y = reshape(grid, nLon*nLat, Nt);
    trendMap = nan(nLon*nLat, 1);
    ampMap = nan(nLon*nLat, 1);
    for i = 1:size(Y,1)
        yi = Y(i, :).';
        good = isfinite(yi);
        if sum(good) < 4
            continue;
        end
        Xi = X(good, :);
        Bi = Xi \ yi(good);
        trendMap(i) = Bi(2);
        ampMap(i) = sqrt(Bi(3).^2 + Bi(4).^2);
    end
    trendMap = reshape(trendMap, nLon, nLat);
    ampMap = reshape(ampMap, nLon, nLat);
end
