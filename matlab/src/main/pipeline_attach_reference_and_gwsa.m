function Products = pipeline_attach_reference_and_gwsa(cfg, Products, state, Tk, lonVec, latVec, refTag)
%PIPELINE_ATTACH_REFERENCE_AND_GWSA Attach reference and optional GWSA outputs.

    if state.refOk && isfield(state.Products, refTag)
        Products.(refTag) = state.Products.(refTag);
    end

    if isfield(cfg,'gldas') && isfield(cfg.gldas,'dir') && isfolder(cfg.gldas.dir)
        [GWSAprod, gwsOk] = io_compute_gwsa(cfg, Tk, lonVec, latVec);
        if gwsOk
            GWSAprod = io_standardize_product(GWSAprod, lonVec, latVec);
            Products.GWSA = GWSAprod;
        end
    end
end
