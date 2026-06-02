function state = pipeline_prepare_month_input(cfg, paths, plan, Tk, lonVec, latVec, refTag, doMetrics, refOutput, skipExisting)
%PIPELINE_PREPARE_MONTH_INPUT Load reference products and detect cache status.

    state = struct();
    state.Products = struct();
    state.refOk = false;
    state.refMonth = '';
    state.cacheHit = false;

    if doMetrics || refOutput
        [Pref, state.refOk] = main_try_load_reference(cfg, Tk, lonVec, latVec);
        if state.refOk
            state.Products.(refTag) = Pref;
        else
            state.refMonth = Tk.ym;
        end
    end

    if skipExisting
        allExist = true;
        for ii = 1:numel(plan.order)
            tag = plan.order{ii};
            fp = io_find_product_mat(paths, tag, Tk);
            if ~isfile(fp)
                allExist = false;
                break;
            end
        end
        state.cacheHit = allExist;
    end
end
