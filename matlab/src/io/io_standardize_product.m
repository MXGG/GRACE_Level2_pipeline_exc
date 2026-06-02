function P = io_standardize_product(P, lonVec, latVec)
%IO_STANDARDIZE_PRODUCT Ensure Product grid is [nLon x nLat] aligned to lonVec/latVec.
% Transposes automatically if [nLat x nLon].

    X = P.grid.ewh;
    nLon = numel(lonVec); nLat = numel(latVec);

    if isequal(size(X), [nLon, nLat])
        % ok
    elseif isequal(size(X), [nLat, nLon])
        X = X.';
    else
        error('Product "%s": grid size %dx%d not compatible with lon/lat (%dx%d).', ...
            P.tag, size(X,1), size(X,2), nLon, nLat);
    end

    P.grid.lon = lonVec(:).';
    P.grid.lat = latVec(:).';
    P.grid.ewh = X;
end
