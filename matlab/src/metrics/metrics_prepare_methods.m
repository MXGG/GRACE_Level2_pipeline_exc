function methods = metrics_prepare_methods(Products, refTag, allowList)
%METRICS_PREPARE_METHODS Pick method list from Products fields that have .grid.ewh
    f = fieldnames(Products);
    f = f(:);

    ok = false(size(f));
    for i = 1:numel(f)
        s = Products.(f{i});
        ok(i) = isstruct(s) && isfield(s,'grid') && isfield(s.grid,'ewh');
    end
    methods = f(ok);

    if nargin >= 2 && ~isempty(refTag)
        if ~any(strcmp(methods, refTag))
            error('Reference tag "%s" not found among Products.', refTag);
        end
    end

    if nargin >= 3 && ~isempty(allowList)
        methods = intersect(methods, allowList(:), 'stable');
    end
end
