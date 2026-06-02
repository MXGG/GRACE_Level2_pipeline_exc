function [Stacks, stackTags] = pipeline_run_hsaf_stack_stage(cfg, paths, plan, T, Nt, lonVec, latVec, wantReturnStacks, Stacks, stackTags)
%PIPELINE_RUN_HSAF_STACK_STAGE Build stack-mode HSAF output when enabled.

    if ~plan.hankel_stack_mode
        return;
    end

    fprintf('\n[HSAF] Stack mode enabled. Building HSAF from stack...\n');
    hinTag = plan.hankel_input_tag;
    if wantReturnStacks && isfield(Stacks, hinTag)
        StackIn = Stacks.(hinTag);
    else
        StackIn = pipeline_load_stack_from_disk(paths.stacks, hinTag);
    end
    if isempty(StackIn) || ~isfield(StackIn,'ewh') || isempty(StackIn.ewh)
        warning('HSAF stack mode: input stack "%s" not found. Skipping HSAF stack.', hinTag);
        return;
    end

    Ts = mean(diff(lonVec));
    if isfield(cfg,'filter') && isfield(cfg.filter,'hankel')
        if isfield(cfg.filter.hankel,'Ts') && ~isempty(cfg.filter.hankel.Ts)
            Ts = cfg.filter.hankel.Ts;
        elseif isfield(cfg.filter.hankel,'params') && isfield(cfg.filter.hankel.params,'Ts') ...
                && ~isempty(cfg.filter.hankel.params.Ts)
            Ts = cfg.filter.hankel.params.Ts;
        end
    end

    [EWHf, info] = filter_grid_hsaf(StackIn.ewh, lonVec, latVec, cfg.filter.hankel, Ts);
    StackH = StackIn;
    StackH.tag = 'HSAF';
    StackH.ewh = EWHf;
    StackH.meta = struct('input',hinTag,'info',info);
    io_save_stack(cfg, paths, StackH);
    if wantReturnStacks
        Stacks.HSAF = StackH;
    end
    if isfield(cfg,'io') && isfield(cfg.io,'save_monthly_mat') && cfg.io.save_monthly_mat
        fprintf('[HSAF] Writing monthly products from stack...\n');
        for k = 1:Nt
            Tk = T(k);
            P = io_make_product('HSAF', Tk, lonVec, latVec, StackH.ewh(:,:,k), StackH.meta);
            io_save_product(cfg, paths, P);
        end
    end
    stackTags = unique([stackTags, {'HSAF'}], 'stable');
end
