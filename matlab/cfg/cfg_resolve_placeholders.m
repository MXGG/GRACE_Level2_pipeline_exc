function cfg = cfg_resolve_placeholders(cfg, rootDir)
%CFG_RESOLVE_PLACEHOLDERS Replace ${ROOT} in all string fields.

    cfg = walk(cfg);
    fprintf('[DEBUG] cfg_resolve rootDir=%s\n', rootDir);

    function x = walk(x)
        if isstruct(x)
            if numel(x) > 1
                for i = 1:numel(x)
                    x(i) = walk(x(i));
                end
                return
            end
            fn = fieldnames(x);
            for k = 1:numel(fn)
                x.(fn{k}) = walk(x.(fn{k}));
            end
        elseif iscell(x)
            for k = 1:numel(x)
                x{k} = walk(x{k});
            end
        elseif ischar(x) || (isstring(x) && isscalar(x))
            x = string(x);
            x = replace(x, "${ROOT}", string(rootDir));
            x = char(x);
        end
    end
end