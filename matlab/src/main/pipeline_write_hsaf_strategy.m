function manifest = pipeline_write_hsaf_strategy(paths, cfg, plan)
%PIPELINE_WRITE_HSAF_STRATEGY Persist effective HSAF strategy for run parity checks.

    manifest = struct();
    if ~isfield(cfg, 'filter') || ~isfield(cfg.filter, 'hankel') ...
            || ~isfield(cfg.filter.hankel, 'enable') || ~cfg.filter.hankel.enable
        return;
    end

    hk = cfg.filter.hankel;
    variantRequested = get_field_default(hk, 'variant', 'global');
    variantEffective = normalize_hsaf_variant(variantRequested);
    adaptiveZones = get_field_default(hk, 'adaptive', []);
    if strcmpi(variantEffective, 'adaptive') && isempty(adaptiveZones)
        variantEffective = 'global';
    end

    paramsIn = get_field_default(hk, 'params', struct());
    params = struct();
    params.N = get_first_field(paramsIn, {'N','n','window_size','window'}, 30);
    params.P = get_first_field(paramsIn, {'P','p'}, 10);
    params.K = get_first_field(paramsIn, {'K','k','order'}, 6);
    params.J = get_first_field(paramsIn, {'J','j','buffer'}, 1);
    params.iterations = get_first_field(paramsIn, {'iterations','iter','n_iter','niter'}, 1);

    inputTag = get_field_default(plan, 'hankel_input_tag', 'P4M6');
    stackMode = get_field_default(plan, 'hankel_stack_mode', false);

    if strcmpi(variantEffective, 'adaptive')
        strategyName = 'latitude_adaptive';
        fprintf('[HSAF] Strategy=latitude_adaptive | input=%s | zones=%d | stack_mode=%s\n', ...
            inputTag, numel(adaptiveZones), on_off(stackMode));
    else
        strategyName = 'global_fixed';
        fprintf('[HSAF] Strategy=global_fixed | input=%s | N=%d P=%d K=%d J=%d | stack_mode=%s\n', ...
            inputTag, params.N, params.P, params.K, params.J, on_off(stackMode));
    end

    manifest = struct();
    manifest.strategy = strategyName;
    manifest.variant_requested = variantRequested;
    manifest.variant_effective = variantEffective;
    manifest.input_tag = inputTag;
    manifest.stack_mode = logical(stackMode);
    manifest.params = params;
    manifest.adaptive_zone_count = numel(adaptiveZones);
    manifest.generated_at = datestr(now, 'yyyy-mm-dd HH:MM:SS');

    if isfield(paths, 'logs') && ~isempty(paths.logs)
        ensure_dir(paths.logs);
        outPath = fullfile(paths.logs, 'hsaf_strategy.json');
        write_json_safe(outPath, manifest);
    end
end

function out = normalize_hsaf_variant(raw)
    if nargin < 1 || isempty(raw)
        out = 'global';
        return;
    end
    if isstring(raw)
        key = char(raw);
    else
        key = raw;
    end
    key = lower(strtrim(key));
    key = strrep(key, '-', '_');
    switch key
        case {'adaptive', 'lat_adaptive', 'latitude_adaptive', 'adaptive_lat', 'latitude'}
            out = 'adaptive';
        otherwise
            out = 'global';
    end
end

function v = get_first_field(S, names, defaultVal)
    v = defaultVal;
    for i = 1:numel(names)
        name = names{i};
        if isfield(S, name) && ~isempty(S.(name))
            v = S.(name);
            return;
        end
    end
end

function v = get_field_default(S, name, defaultVal)
    if isfield(S, name) && ~isempty(S.(name))
        v = S.(name);
    else
        v = defaultVal;
    end
end

function txt = on_off(flag)
    if flag
        txt = 'on';
    else
        txt = 'off';
    end
end

function write_json_safe(pathJson, data)
    tmpPath = [pathJson '.tmp'];
    fid = fopen(tmpPath, 'w');
    if fid < 0
        warning('HSAF:StrategyWrite', 'Failed to open file: %s', tmpPath);
        return;
    end
    cleaner = onCleanup(@() fclose_if_open(fid));
    try
        txt = jsonencode(data, 'PrettyPrint', true);
    catch
        txt = jsonencode(data);
    end
    fwrite(fid, txt, 'char');
    clear cleaner;
    [ok, msg] = movefile(tmpPath, pathJson, 'f');
    if ~ok
        warning('HSAF:StrategyWrite', 'Failed to move strategy manifest: %s', msg);
    end
end

function fclose_if_open(fid)
    if nargin < 1 || isempty(fid)
        return;
    end
    try
        fclose(fid);
    catch
    end
end
