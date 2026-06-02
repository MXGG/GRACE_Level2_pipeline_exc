function Products = pipeline_save_month_outputs(cfg, paths, plan, Products, lonVec, latVec, refTag, refOutput)
%PIPELINE_SAVE_MONTH_OUTPUTS Standardize and persist month products.

    if isfield(Products, 'GWSA')
        io_save_product(cfg, paths, Products.GWSA);
    end

    for ii = 1:numel(plan.order)
        tag = plan.order{ii};
        if ~isfield(Products, tag); continue; end
        P = io_standardize_product(Products.(tag), lonVec, latVec);
        io_save_product(cfg, paths, P);
        Products.(tag) = P;
    end

    if refOutput && isfield(Products, refTag)
        Pref = io_standardize_product(Products.(refTag), lonVec, latVec);
        io_save_product(cfg, paths, Pref);
        Products.(refTag) = Pref;
    end
end
