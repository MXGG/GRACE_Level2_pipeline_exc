function io_write_grid_xyz(outFile, M, lonVec, latVec, LAT_ORDER_IN_MATRIX)
%IO_WRITE_GRID_XYZ Write lon-lat-value XYZ (GMT-friendly).

    if nargin < 5 || isempty(LAT_ORDER_IN_MATRIX)
        LAT_ORDER_IN_MATRIX = 'asc'; % latVec ascending (default in this project)
    end

    nLon = numel(lonVec);
    nLat = numel(latVec);

    if isvector(M)
        assert(numel(M) == nLon*nLat, 'io_write_grid_xyz: size mismatch (vector)');
        Muse = reshape(M, [nLon, nLat]).';
    else
        if ~(size(M,1)==nLon && size(M,2)==nLat)
            if (size(M,1)==nLat && size(M,2)==nLon)
                M = M.';
            else
                error('io_write_grid_xyz: size(M)=[%d %d], expect [%d %d]', size(M,1), size(M,2), nLon, nLat);
            end
        end
        Muse = M.';
    end

    if strcmpi(LAT_ORDER_IN_MATRIX,'desc')
        Muse = flipud(Muse);
        latUse = flipud(latVec(:));
    else
        latUse = latVec(:);
    end

    [LON, LAT] = meshgrid(lonVec, latUse);
    xyz = [LON(:), LAT(:), Muse(:)];

    fid = fopen(outFile, 'w');
    fprintf(fid, '%.6f %.6f %.10g\n', xyz.');
    fclose(fid);
end
