function out = cfg_merge_struct(base, override)
%CFG_MERGE_STRUCT Recursively merge two structs: override takes precedence.

    out = base;

    if isempty(override)
        return;
    end

    f = fieldnames(override);
    for i = 1:numel(f)
        key = f{i};
        if isfield(base, key) && isstruct(base.(key)) && isstruct(override.(key))
            out.(key) = cfg_merge_struct(base.(key), override.(key));
        else
            out.(key) = override.(key);
        end
    end
end
