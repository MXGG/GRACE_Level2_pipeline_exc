function mask_sanity_report(global_coast, lonVec, latVec, LAT_ORDER_IN_MATRIX)
%MASK_SANITY_REPORT Quick check for land/ocean mask alignment.
    fprintf('Mask sanity check (1=land, 0=ocean):\n');
    pts = [
        62.25  25.25;
        77.25  28.25;
        0.25   0.25;
        200.25 0.25;
        135.25 -25.25;
    ];

    if strcmpi(LAT_ORDER_IN_MATRIX, 'desc')
        latUse = flipud(latVec(:));
    else
        latUse = latVec(:);
    end

    for i = 1:size(pts,1)
        [~,ix] = min(abs(lonVec - pts(i,1)));
        [~,iy] = min(abs(latUse - pts(i,2)));
        fprintf('  lon=%6.2f lat=%6.2f -> mask=%d\n', pts(i,1), pts(i,2), global_coast(ix,iy));
    end
end
