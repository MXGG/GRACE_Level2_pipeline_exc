function op = leakage_parse_filter_tag(tag, cfg)
%LEAKAGE_PARSE_FILTER_TAG Parse a product/filter tag into operations.
%
% Supports tags like:
%   'RAW', 'None'
%   'Gaussian', 'P4M6', 'P4M6_Gaussian'
%   'Fan', 'P4M6_Fan'
%   'DDK4'
%   'Hankel', 'HSAF', 'P4M6_Gaussian_HSAF' (grid-domain Hankel after SH filters)

    op = struct();
    op.tag = char(tag);

    tagU = upper(string(tag));

    op.use_p4m6   = contains(tagU, "P4M6") | contains(tagU, "DECORR") | contains(tagU,"DESTRIP");
    op.use_gauss  = contains(tagU, "GAUSS");
    op.use_fan    = contains(tagU, "FAN");
    op.use_ddk    = startsWith(tagU, "DDK");
    op.use_hankel = contains(tagU, "HANKEL") | contains(tagU, "HSAF");

    % Gaussian / Fan radii from cfg.filter if available
    op.gaussian_km = get_nested(cfg, {'filter','gaussian','radius_km'}, 0);
    op.fan_r1_km   = get_nested(cfg, {'filter','fan','radius1_km'}, 0);
    op.fan_r2_km   = get_nested(cfg, {'filter','fan','radius2_km'}, 0);

    % DDK type: 'DDK4' -> store 'DDK4'
    if op.use_ddk
        suffix = char(extractAfter(tagU, "DDK"));
        if isempty(suffix)
            op.ddk_type = get_nested(cfg, {'filter','ddk','type'}, 'DDK4');
        else
            op.ddk_type = ['DDK', suffix];
        end
    else
        op.ddk_type = get_nested(cfg, {'filter','ddk','type'}, 'DDK4');
    end

    % Hankel params expected in cfg.filter.hankel.params
    op.hankel = get_nested(cfg, {'filter','hankel'}, struct());

    % Lmax
    op.Lmax = get_nested(cfg, {'inversion','Lmax'}, 60);
end

function v = get_nested(S, path, defaultVal)
    v = defaultVal;
    try
        cur = S;
        for i = 1:numel(path)
            if ~isstruct(cur) || ~isfield(cur, path{i})
                return;
            end
            cur = cur.(path{i});
        end
        if ~isempty(cur); v = cur; end
    catch
        v = defaultVal;
    end
end
