function Stack = pipeline_load_stack_from_disk(stackDir, tag)
%PIPELINE_LOAD_STACK_FROM_DISK Load the newest saved stack for a tag.

    Stack = [];
    files = dir(fullfile(stackDir, sprintf('%s_stack_*.mat', tag)));
    if isempty(files)
        return;
    end
    [~, idx] = max([files.datenum]);
    data = load(fullfile(stackDir, files(idx).name));
    if isfield(data, 'Stack')
        Stack = data.Stack;
    end
end
