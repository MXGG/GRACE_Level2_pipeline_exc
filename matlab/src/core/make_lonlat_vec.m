function [lonVec, latVec] = make_lonlat_vec(cfg)
%MAKE_LONLAT_VEC Build lon/lat vectors from cfg.grid (regular grid).
% cfg.grid.lon: [lonMin, lonMax]
% cfg.grid.lat: [latMax, latMin] or [latMin, latMax]
    dlon = cfg.grid.dlon;
    dlat = cfg.grid.dlat;

    lonMin = cfg.grid.lon(1); lonMax = cfg.grid.lon(2);
    latA   = cfg.grid.lat(1); latB   = cfg.grid.lat(2);

    lonVec = lonMin:dlon:lonMax;
    if abs(lonMax - 360) < 1e-9
        lonVec = lonMin:dlon:(lonMax-dlon);
    end

    % keep descending lat if latA > latB
    if latA > latB
        latVec = latA:-dlat:latB;
    else
        latVec = latA:dlat:latB;
    end

    lonVec = lonVec(:).';
    latVec = latVec(:).';
end
