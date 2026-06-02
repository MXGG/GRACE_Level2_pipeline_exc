function Products = pipeline_load_or_compute_month(cfg, paths, plan, Tk, syn, meanSH, lonVec, latVec, cacheHit)
%PIPELINE_LOAD_OR_COMPUTE_MONTH Load cached monthly products or compute them.

    Products = struct();

    if cacheHit
        for ii = 1:numel(plan.order)
            tag = plan.order{ii};
            fp = io_find_product_mat(paths, tag, Tk);
            Products.(tag) = io_load_product_mat(fp);
        end
        return;
    end

    SH = inv_read_gsm_month(cfg, Tk);
    SH = inv_replace_low_degree(cfg, SH, Tk);

    if ~isempty(meanSH) && isfield(cfg,'inversion') && isfield(cfg.inversion,'remove_mean') && cfg.inversion.remove_mean
        [Cmean, Smean, meanTag] = inv_select_mean_sh(meanSH, Tk, cfg);
        if ~isempty(Cmean) && ~isempty(Smean)
            SH.C = SH.C - Cmean;
            SH.S = SH.S - Smean;
            SH.meta.removed_mean = true;
            SH.meta.removed_mean_tag = meanTag;
        else
            SH.meta.removed_mean = false;
            SH.meta.removed_mean_tag = '';
            warning('remove_mean enabled but no mean field found for %s. Mean removal skipped.', Tk.ym);
        end
    else
        SH.meta.removed_mean = false;
        SH.meta.removed_mean_tag = '';
    end

    if isfield(cfg,'inversion') && isfield(cfg.inversion,'gia') && cfg.inversion.gia.enable
        SH = inv_apply_gia(cfg, SH);
    end

    Products = main_compute_products_month(cfg, Tk, SH, syn, plan, Products, lonVec, latVec);
end
