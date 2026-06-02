function X = ensure_latlon_order(X, lonVec, latVec)
%ENSURE_LATLON_ORDER Ensure grid is [nLon x nLat] (or [nLon x nLat x Nt]).
    nLon = numel(lonVec);
    nLat = numel(latVec);

    if ismatrix(X)
        if isequal(size(X), [nLon, nLat])
            return;
        elseif isequal(size(X), [nLat, nLon])
            X = X.';
            return;
        else
            error('Grid size mismatch: %dx%d, expected %dx%d (lon x lat).', ...
                size(X,1), size(X,2), nLon, nLat);
        end
    end

    if ndims(X) == 3
        if size(X,1) == nLon && size(X,2) == nLat
            return;
        elseif size(X,1) == nLat && size(X,2) == nLon
            X = permute(X, [2 1 3]);
            return;
        end
    end

    error('Grid size mismatch: %dx%dx%d, expected %dx%dxN (lon x lat x time).', ...
        size(X,1), size(X,2), size(X,3), nLon, nLat);
end
