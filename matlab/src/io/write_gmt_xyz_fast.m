function write_gmt_xyz_fast(outFile, M, lonVec, latVec, LAT_ORDER_IN_MATRIX)
%WRITE_GMT_XYZ_FAST Write grid matrix to GMT xyz (lon lat value).
%
% M: [nLon x nLat] matrix aligned with lonVec and latVec.
% LAT_ORDER_IN_MATRIX:
%   'desc' -> M is stored with latitude descending (e.g., 89.5 -> -89.5)
%   'asc'  -> M is stored with latitude ascending

    nLon = numel(lonVec); nLat = numel(latVec);

    if isvector(M)
        assert(numel(M) == nLon*nLat, 'write_gmt_xyz_fast: size mismatch (vector)');
        M = reshape(M, [nLon, nLat]).';
    else
        if ~(size(M,1)==nLon && size(M,2)==nLat)
            if (size(M,1)==nLat && size(M,2)==nLon)
                M = M.'; % auto-fix common transpose issue
            else
                error('write_gmt_xyz_fast: size(M)=[%d %d], expect [%d %d]', size(M,1), size(M,2), nLon, nLat);
            end
        end
        M = M.';
    end

    if strcmpi(LAT_ORDER_IN_MATRIX, 'desc')
        Muse = flipud(M);
    else
        Muse = M;
    end

    [LON, LAT] = meshgrid(lonVec, latVec);
    xyz = [LON(:), LAT(:), Muse(:)];

    fid = fopen(outFile, 'w');
    if fid < 0; error('Cannot open file: %s', outFile); end
    fprintf(fid, '%.6f %.6f %.10g\n', xyz.');
    fclose(fid);
end
