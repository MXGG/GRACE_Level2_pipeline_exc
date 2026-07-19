function Products = pipeline_apply_month_leakage(cfg, paths, Products, basinMask, lonVec, latVec)
%PIPELINE_APPLY_MONTH_LEAKAGE Apply configured leakage correction and persist outputs.

    if ~isfield(cfg,'leakage') || ~isfield(cfg.leakage,'apply_to') || isempty(cfg.leakage.apply_to)
        return;
    end

    mode = 'SF';
    if isfield(cfg.leakage, 'method')
        mode = cfg.leakage.method;
    end

    for ii = 1:numel(cfg.leakage.apply_to)
        tag0 = cfg.leakage.apply_to{ii};
        tag0 = resolve_product_tag(tag0, Products, cfg);
        if ~isfield(Products, tag0); continue; end

        OUTleak = leakage_correct_products(cfg, Products, tag0, basinMask, lonVec, latVec, mode);
        Products = OUTleak.ProductsCorr;

        tagNew = [tag0 '_' upper(mode)];
        if isfield(Products, tagNew)
            P2 = io_standardize_product(Products.(tagNew), lonVec, latVec);
            io_save_product(cfg, paths, P2);
            Products.(tagNew) = P2;
        end
    end
end

function tag = resolve_product_tag(tag, Products, cfg)
    tag = char(tag);
    if isfield(Products, tag)
        return;
    end

    if strcmpi(tag, 'DDK')
        ddkType = 'DDK4';
        if isfield(cfg, 'filter') && isfield(cfg.filter, 'ddk') ...
                && isfield(cfg.filter.ddk, 'type') && ~isempty(cfg.filter.ddk.type)
            ddkType = char(cfg.filter.ddk.type);
        end
        if isfield(Products, ddkType)
            tag = ddkType;
        end
    end
end
