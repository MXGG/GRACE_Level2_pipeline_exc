function mask = basin_make_mask(lonVec, latVec, B)
%BASIN_MAKE_MASK Build grid mask from boundary polygons.
% lonVec: [1 x nLon], latVec: [1 x nLat]
% B: struct array with Lon, Lat

    [LON, LAT] = ndgrid(lonVec, latVec);
    mask = false(size(LON));

    for i = 1:numel(B)
        lon = B(i).Lon(:);
        lat = B(i).Lat(:);

        good = isfinite(lon) & isfinite(lat);
        lon = lon(good); lat = lat(good);
        if numel(lon) < 3; continue; end

        mask = mask | inpolygon(LON, LAT, lon, lat);
    end
end
