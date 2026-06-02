function [isLand, isOcean] = mask_land_ocean(landMask, lonVec, latVec)
%MASK_LAND_OCEAN Convert a land-mask matrix into logical land/ocean masks.
% landMask can be:
%   - logical true=land
%   - numeric with NaN over ocean
%   - numeric 0/1
% Output masks are [nLon x nLat] logical.
    if isempty(landMask)
        isLand = [];
        isOcean = [];
        return;
    end

    landMask = ensure_latlon_order(landMask, lonVec, latVec);

    if islogical(landMask)
        isLand = landMask;
    else
        if any(isnan(landMask(:)))
            isLand = ~isnan(landMask);
        else
            isLand = landMask > 0.5;
        end
    end
    isOcean = ~isLand;
end
