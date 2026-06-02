function [Products, ACC] = metrics_eval_month_ctx(Products, ACC, ctx)
%METRICS_EVAL_MONTH_CTX Structured monthly metrics evaluation.
%
% ctx fields:
%   t, Tk, refTag, lonVec, latVec, landMask

    if ~isfield(Products, ctx.refTag)
        error('Reference tag "%s" not found in Products.', ctx.refTag);
    end

    Ft = ensure_latlon_order(Products.(ctx.refTag).grid.ewh, ctx.lonVec, ctx.latVec);
    [isLand, isOcean] = mask_land_ocean(ctx.landMask, ctx.lonVec, ctx.latVec);

    methodList = ACC.methods;
    for i = 1:numel(methodList)
        m = methodList{i};
        if strcmp(m, ctx.refTag); continue; end
        if ~isfield(Products, m); continue; end

        Fo = ensure_latlon_order(Products.(m).grid.ewh, ctx.lonVec, ctx.latVec);

        M = metrics_eval_global(Fo, Ft, isLand, isOcean);
        if ~isempty(ctx.Tk) && isfield(ctx.Tk, 'ym')
            M.ym = ctx.Tk.ym;
        end
        Products.(m).metrics.global = M;

        rec = struct( ...
            't', ctx.t, ...
            'method', m, ...
            'Fo', Fo, ...
            'Ft', Ft, ...
            'lonVec', ctx.lonVec, ...
            'latVec', ctx.latVec, ...
            'isLand', isLand, ...
            'isOcean', isOcean);
        ACC = metrics_acc_update_struct(ACC, rec);
    end
end
