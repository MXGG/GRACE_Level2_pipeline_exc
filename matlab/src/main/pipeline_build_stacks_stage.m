function [Stacks, stackTags, wantReturnStacks, perf] = pipeline_build_stacks_stage(cfg, paths, plan, T, lonVec, latVec, basin, plotCfg, refOutput, refTag, perf)
%PIPELINE_BUILD_STACKS_STAGE Build monthly-product stacks and quicklooks.

    fprintf('\n[STACK] Building stacks from monthly MATs...\n');
    stackTags = unique(plan.order, 'stable');
    if refOutput
        stackTags = unique([stackTags, {refTag}], 'stable');
    end

    wantReturnStacks = isfield(cfg,'io') && isfield(cfg.io,'return_stacks') && cfg.io.return_stacks;
    if wantReturnStacks
        warning('run_pipeline:MemoryWarning', ...
            'return_stacks=true can cause high memory usage. Consider setting to false.');
    end

    Stacks = struct();
    pbStack = progress_bar('create', numel(stackTags), 'Tag', 'Stack', 'RefreshInterval', 0.2);
    for i = 1:numel(stackTags)
        tag = stackTags{i};
        pbStack = progress_bar('update', pbStack, i-1, 'substep', sprintf('Build %s', tag));
        tStack = tic;
        Stack = main_build_stack_from_monthly(cfg, paths, tag, T, lonVec, latVec);
        perf = perf_tracker('add', perf, 'Stack', toc(tStack));
        if ~isempty(Stack)
            io_save_stack(cfg, paths, Stack);
            if wantReturnStacks
                Stacks.(tag) = Stack;
            end

            if plotCfg.stack_mean
                pipeline_plot_stack_mean(paths, tag, Stack, lonVec, latVec, basin, plotCfg);
            end
            if plotCfg.stack_trend_amp
                pipeline_plot_stack_trend_amp(paths, tag, Stack, lonVec, latVec, plotCfg);
            end
        end
        pbStack = progress_bar('update', pbStack, i, 'substep', sprintf('Done %s', tag));

        if ~wantReturnStacks
            Stack = []; %#ok<NASGU>
        end
    end
    progress_bar('finish', pbStack);
    clear Stack;
    pause(0.1);
end
