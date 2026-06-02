function [EWH_f, info] = filter_grid_hsaf(EWH, lonVec, latVec, cfg_hankel, grid_dlon)
%FILTER_GRID_HSAF Apply Hankel Spectrum Analysis Filtering (HSAF) to one map or a stack.
%
% This entry point is intentionally thin:
%   - filter_grid_hsaf_setup() prepares the runtime context
%   - filter_grid_hsaf_global_map() handles global HSAF map filtering
%   - filter_grid_hsaf_adaptive_profile() handles legacy adaptive profile filtering
%
% The public signature, JSON contract, and output layout are preserved.

    ctx = filter_grid_hsaf_setup(EWH, lonVec, latVec, cfg_hankel, grid_dlon);

    info = ctx.info;
    EWH_f = ctx.EWH;
    stats = ctx.stats;

    if ctx.useParallel
        try
            pctRunOnAll warning('off', 'all');
        catch
        end
    end

    if strcmpi(ctx.variant, 'global') && ctx.is3 && ctx.useParallel
        EWH_f = zeros(size(ctx.EWH), 'like', ctx.EWH);
        okArr = false(1, ctx.Nt);
        nRemovedArr = zeros(1, ctx.Nt);
        dq = [];

        logCtx = struct('enabled', ctx.logProgress, 'count', 0, 'total', ctx.Nt);
        if logCtx.enabled
            logCtx.start = tic;
            dq = parallel.pool.DataQueue;
            afterEach(dq, @(~) update_map_progress());
        end

        parfor t = 1:ctx.Nt
            X = ctx.EWH(:,:,t);
            [Y, nRemoved, ok] = filter_grid_hsaf_global_map(X, ctx.Ts, ctx.baseParams);
            EWH_f(:,:,t) = Y;
            okArr(t) = ok;
            nRemovedArr(t) = nRemoved;
            if ~isempty(dq)
                send(dq, t); %#ok<PFBNS>
            end
        end

        stats.processed_maps = sum(okArr);
        stats.failed_maps = ctx.Nt - stats.processed_maps;
        stats.components_removed = sum(nRemovedArr);
    else
        for t = 1:ctx.Nt
            if ctx.is3
                X = ctx.EWH(:,:,t);
            else
                X = ctx.EWH;
            end

            if strcmpi(ctx.variant, 'adaptive') && ~isempty(ctx.latVec)
                Y = X;
                nLat = numel(ctx.latVec);
                okArr = false(1, nLat);
                nRemovedArr = zeros(1, nLat);

                if ctx.useParallel
                    Y_rows = cell(nLat, 1);
                    dq = [];
                    if ctx.logProgress
                        logCtx = struct('enabled', true, 'count', 0, 'total', nLat, 'tIdx', t, 'Nt', ctx.Nt);
                        logCtx.start = tic;
                        dq = parallel.pool.DataQueue;
                        afterEach(dq, @(~) update_lat_progress());
                    end

                    parfor j = 1:nLat
                        x_prof = X(:,j);
                        if all(~isfinite(x_prof))
                            Y_rows{j} = x_prof;
                            okArr(j) = true;
                            continue;
                        end

                        [y_out, nRem, ok] = filter_grid_hsaf_adaptive_profile( ...
                            x_prof, ctx.Ts, ctx.latVec(j), ctx.cfg_hankel, ctx.baseLegacy);
                        if isempty(y_out) || all(~isfinite(y_out))
                            Y_rows{j} = x_prof;
                        else
                            Y_rows{j} = y_out(:);
                        end
                        okArr(j) = ok;
                        nRemovedArr(j) = nRem;
                        if ~isempty(dq)
                            send(dq, j); %#ok<PFBNS>
                        end
                    end

                    for j = 1:nLat
                        Y(:,j) = Y_rows{j};
                    end
                    stats.processed_profiles = stats.processed_profiles + sum(okArr);
                    stats.failed_profiles = stats.failed_profiles + sum(~okArr);
                    stats.components_removed = stats.components_removed + sum(nRemovedArr);
                else
                    pb = progress_bar('create', nLat, 'Tag', 'HSAF Adaptive');
                    for j = 1:nLat
                        x = X(:,j);
                        if all(~isfinite(x))
                            pb = progress_bar('update', pb, j);
                            continue;
                        end
                        [y, nRemoved, ok] = filter_grid_hsaf_adaptive_profile( ...
                            x, ctx.Ts, ctx.latVec(j), ctx.cfg_hankel, ctx.baseLegacy);
                        if isempty(y) || all(~isfinite(y))
                            stats.failed_profiles = stats.failed_profiles + 1;
                        else
                            Y(:,j) = y(:);
                            stats.processed_profiles = stats.processed_profiles + 1;
                            stats.components_removed = stats.components_removed + nRemoved;
                        end
                        okArr(j) = ok;
                        nRemovedArr(j) = nRemoved;
                        pb = progress_bar('update', pb, j);
                    end
                    progress_bar('finish', pb);
                end
            else
                [Y, nRemoved, ok] = filter_grid_hsaf_global_map(X, ctx.Ts, ctx.baseParams);
                if ok
                    stats.processed_maps = stats.processed_maps + 1;
                    stats.components_removed = stats.components_removed + nRemoved;
                else
                    stats.failed_maps = stats.failed_maps + 1;
                end
            end

            if ctx.is3
                EWH_f(:,:,t) = Y;
            else
                EWH_f = Y;
            end
        end
    end

    info.used.Ts = ctx.Ts;
    info.used.variant = ctx.variant;
    if strcmpi(ctx.variant, 'adaptive')
        info.used.p = ctx.baseLegacy.p;
        info.used.k = ctx.baseLegacy.k;
        info.used.wl_band_deg = ctx.baseLegacy.wl_band_deg;
    else
        info.used.N = ctx.baseParams.N;
        info.used.P = ctx.baseParams.P;
        info.used.K = ctx.baseParams.K;
        info.used.J = ctx.baseParams.J;
        info.used.iterations = ctx.baseParams.iterations;
        info.used.window_size = ctx.baseParams.N;
        info.used.p = ctx.baseParams.P;
        info.used.order = ctx.baseParams.K;
        info.used.buffer = ctx.baseParams.J;
    end

    info.stats = stats;
    info.stats.avg_components_per_map = stats.components_removed / max(stats.processed_maps, 1);
    info.stats.log_progress = ctx.logProgress;

    function update_map_progress()
        logCtx.count = logCtx.count + 1;
        step = max(1, floor(logCtx.total / 10));
        if mod(logCtx.count, step) == 0 || logCtx.count == logCtx.total
            fprintf('[HSAF][global] %d/%d maps (%.1f%%) elapsed %s\n', ...
                logCtx.count, logCtx.total, 100 * logCtx.count / max(logCtx.total, 1), ...
                duration(0, 0, toc(logCtx.start), 'Format', 'hh:mm:ss'));
        end
    end

    function update_lat_progress()
        logCtx.count = logCtx.count + 1;
        step = max(1, floor(logCtx.total / 10));
        if mod(logCtx.count, step) == 0 || logCtx.count == logCtx.total
            fprintf('[HSAF][adaptive] t=%d/%d %d/%d lat (%.1f%%) elapsed %s\n', ...
                logCtx.tIdx, logCtx.Nt, logCtx.count, logCtx.total, ...
                100 * logCtx.count / max(logCtx.total, 1), ...
                duration(0, 0, toc(logCtx.start), 'Format', 'hh:mm:ss'));
        end
    end
end
