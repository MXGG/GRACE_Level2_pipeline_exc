function Stack = merge_time_stack(cfg, AllProducts, T, tag)
%MERGE_TIME_STACK Merge monthly products into a 3D stack for a given tag.
% AllProducts{k} is a struct containing Product structs for that month.
% tag: e.g., 'HSAF' or 'P4M6' or 'RAW'
%
% Output Stack.ewh: [nLon x nLat x nT]

    if nargin < 4 || isempty(tag); tag = 'HSAF'; end

    [lon, lat] = make_lonlat_vec(cfg);
    nLon = numel(lon); nLat = numel(lat); nT = numel(T);

    E = nan(nLon, nLat, nT);
    ok = false(nT,1);

    for k = 1:nT
        Pk = AllProducts{k};
        if isempty(Pk) || ~isfield(Pk, tag); continue; end
        g = Pk.(tag).grid;
        if isfield(g,'ewh') && ~isempty(g.ewh)
            X = g.ewh;
            if ~isequal(size(X), [nLon, nLat])
                warning('[%s] %s grid size mismatch. expected %dx%d, got %dx%d', ...
                    T(k).ym, tag, nLon, nLat, size(X,1), size(X,2));
                continue;
            end
            E(:,:,k) = X;
            ok(k) = true;
        end
    end

    Stack.tag = tag;
    Stack.lat = lat;
    Stack.lon = lon;
    Stack.t   = {T.ym};
    Stack.ok  = ok;
    Stack.ewh = E;
end
