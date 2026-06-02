function ts = basin_mean_ts(Stack, mask, latVec, areaWeight)
%BASIN_MEAN_TS Basin mean time series from a 3D stack.
% Stack: [nLon x nLat x Nt] (mmEWH)
% mask : [nLon x nLat] logical
% areaWeight: true -> cos(lat) weighting (recommended)

    if nargin < 4 || isempty(areaWeight); areaWeight = true; end
    mask = logical(mask);

    if ndims(Stack) ~= 3
        error('Stack must be 3D: [nLon x nLat x Nt]');
    end

    nLat = size(Stack,2);
    if numel(latVec) ~= nLat
        error('latVec length mismatch.');
    end

    Nt = size(Stack,3);
    ts = nan(Nt,1);

    if areaWeight
        wlat = cosd(latVec(:)).'; % 1 x nLat
        W = repmat(wlat, size(Stack,1), 1);
        W(~mask) = 0;
    else
        W = double(mask);
    end

    for t = 1:Nt
        G = Stack(:,:,t);
        v = isfinite(G) & mask;
        if ~any(v(:)); ts(t)=NaN; continue; end

        if areaWeight
            ww = W;
            ww(~v) = 0;
            ts(t) = nansum(G(:).*ww(:)) / (nansum(ww(:)) + eps);
        else
            ts(t) = mean(G(v), 'omitnan');
        end
    end
end
