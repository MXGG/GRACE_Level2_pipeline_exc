function OUT = leakage_correct_products(cfg, Products, refTag, mask, lonVec, latVec, mode)
%LEAKAGE_CORRECT_PRODUCTS Apply leakage correction (FM or SF) to one product in Products.
%
% Inputs:
%   refTag: which product field to correct (e.g., 'P4M6_Gaussian')
%   mode  : 'SF' or 'FM' (optional; default cfg.leakage.method)
%
% Output OUT:
%   OUT.ProductsCorr : corrected product added as new tag
%   OUT.SF           : scale factor (SF mode)
%   OUT.FM.info      : diagnostics (FM mode)

    L = leakage_merge_cfg(cfg);
    if nargin < 7 || isempty(mode)
        mode = L.method;
    end

    if ~isfield(Products, refTag)
        error('Products does not contain refTag: %s', refTag);
    end

    P = Products.(refTag);
    G = P.grid.ewh;
    G = ensure_latlon_order(G, lonVec, latVec);

    OUT = struct();
    OUT.SF = [];
    OUT.FM = struct();
    OUT.ProductsCorr = Products;

    switch upper(string(mode))
        case "SF"
            SF = leakage_sf_compute(cfg, refTag, mask, lonVec, latVec);
            [Gcorr, info] = leakage_sf_apply(G, mask, SF);

            tagNew = [refTag, '_SF'];
            P2 = P;
            P2.tag = tagNew;
            P2.grid.ewh = Gcorr;
            P2.leakage = info;

            OUT.ProductsCorr.(tagNew) = P2;
            OUT.SF = SF;

        case "FM"
            [Gcorr, info] = leakage_fm_correct_month(cfg, G, refTag, mask, lonVec, latVec);

            tagNew = [refTag, '_FM'];
            P2 = P;
            P2.tag = tagNew;
            P2.grid.ewh = Gcorr;
            P2.leakage = info;

            OUT.ProductsCorr.(tagNew) = P2;
            OUT.FM.info = info;

        otherwise
            error('Unknown leakage correction mode: %s', mode);
    end
end
