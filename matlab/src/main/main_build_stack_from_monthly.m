function Stack = main_build_stack_from_monthly(cfg, paths, tag, T, lonVec, latVec)
%MAIN_BUILD_STACK_FROM_MONTHLY Load monthly products and merge into a 3D stack.
%
% MEMORY OPTIMIZATION: Uses single precision to reduce memory by 50%.
% A 360x180x163 grid at double=340MB, at single=170MB.

    nLon = numel(lonVec); nLat = numel(latVec); nT = numel(T);
    
    % MEMORY OPTIMIZATION: Use single precision for large EWH stack
    % This cuts memory usage by 50% (8 bytes -> 4 bytes per element)
    E = nan(nLon, nLat, nT, 'single');
    ok = false(nT,1);

    for k = 1:nT
        fp = io_find_product_mat(paths, tag, T(k));
        if ~isfile(fp); continue; end
        try
            P = io_load_product_mat(fp);
            X = P.grid.ewh;
            if isequal(size(X), [nLat, nLon]); X = X.'; end
            if ~isequal(size(X), [nLon, nLat]); continue; end
            E(:,:,k) = single(X);  % Convert to single on assignment
            ok(k) = true;
            
            % MEMORY OPTIMIZATION: Clear loaded product immediately
            clear P X;
        catch
        end
    end

    if ~any(ok)
        Stack = [];
        return;
    end

    Stack = struct();
    Stack.tag = tag;
    Stack.lat = latVec(:).';
    Stack.lon = lonVec(:).';
    Stack.t   = {T.ym};
    Stack.ok  = ok;
    Stack.ewh = E;
    
    % MEMORY OPTIMIZATION: Clear temporary arrays
    clear E ok;
end
