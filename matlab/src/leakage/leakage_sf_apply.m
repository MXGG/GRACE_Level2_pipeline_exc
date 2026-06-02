function [Gcorr, info] = leakage_sf_apply(Gobs, mask, SF)
%LEAKAGE_SF_APPLY Apply scale factor to a grid.
%
% Output:
%   - Gcorr: same size as Gobs; inside mask scaled, outside unchanged
%   - info: struct with SF

    mask = logical(mask);
    Gcorr = Gobs;
    Gcorr(mask) = Gobs(mask) * SF;

    info = struct('SF',SF);
end
