function Gm = basin_apply_mask(G, mask, fillValue)
%BASIN_APPLY_MASK Apply mask to grid.
% fillValue default NaN (outside mask).
    if nargin < 3 || isempty(fillValue); fillValue = NaN; end
    Gm = G;
    Gm(~mask) = fillValue;
end
