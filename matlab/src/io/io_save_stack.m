function fp = io_save_stack(cfg, paths, Stack)
%IO_SAVE_STACK Save a 3D stack to MAT.

    if ~isfield(cfg,'io') || ~isfield(cfg.io,'save_stack_mat') || cfg.io.save_stack_mat
        tag = Stack.tag;
        if isfield(Stack,'t') && ~isempty(Stack.t)
            t0 = strrep(Stack.t{1},'-','');
            t1 = strrep(Stack.t{end},'-','');
        else
            t0 = 'start'; t1 = 'end';
        end
        fp = fullfile(paths.stacks, sprintf('%s_stack_%s-%s.mat', tag, t0, t1));
        io_save_mat(fp, 'Stack');
    else
        fp = '';
    end
end
