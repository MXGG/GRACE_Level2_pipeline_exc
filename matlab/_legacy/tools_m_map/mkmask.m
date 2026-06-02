function [rangeLon, rangeLat,mask]=mkmask(shpf,deltD) 
    %shpf=shaperead(shapename);
    Boundaries = cell(length(shpf), 1);
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
    lonWest = floor(allLonWest) - deltD / 2;
    lonEast = ceil(allLonEast) + deltD / 2;
    latSouth = floor(allLatSouth) - deltD / 2;
    latNorth = ceil(allLatNorth) + deltD / 2;
    rangeLon = lonWest : deltD : lonEast;
    rangeLat = latSouth: deltD : latNorth;
    [mhLon, mhLat] = meshgrid(rangeLon, rangeLat);
    mask = zeros(size(mhLon));
    for i = 1:length(shpf)
        xv = shpf(i).X;
        yv = shpf(i).Y;
        maskcell = inpolygon(mhLon, mhLat, xv, yv);
        mask = mask + maskcell;
    end
    mask(mask == 0) = nan;
end