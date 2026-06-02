function pipeline_finalize_month(cfg, paths, plotCfg, Products, Tk, lonVec, latVec, basin, doCheckpoint, plan, T, k)
%PIPELINE_FINALIZE_MONTH Run per-month finalization steps after computation.

    if plotCfg.quicklook
        main_quicklook_plots(cfg, paths, Products, Tk, lonVec, latVec, basin);
    end

    if doCheckpoint
        checkpoint_manager('save', paths, cfg, plan, T, k);
    end
end
