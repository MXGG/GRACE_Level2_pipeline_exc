function m = leakage_basin_mean(G, mask)
%LEAKAGE_BASIN_MEAN Area-unweighted mean over mask (mask must align with G).
    mask = logical(mask);
    v = isfinite(G) & mask;
    if ~any(v(:))
        m = NaN; return;
    end
    m = mean(G(v), 'omitnan');
end
