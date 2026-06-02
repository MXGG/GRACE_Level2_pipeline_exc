function plan = compute_plan(cfg)
%COMPUTE_PLAN Determine which products must be computed and in what dependency order.
%
% plan.order: cell array of product tags in recommended compute order
% plan.need.(TAG) = true/false
% plan.hankel_input_tag: which product is fed into HSAF/Hankel

    need = struct();
    need.RAW  = true;

    % Traditional filters
    need.GAUSS = isfield(cfg.filter,'gaussian') && isfield(cfg.filter.gaussian,'enable') && cfg.filter.gaussian.enable;
    need.P4M6  = isfield(cfg.filter,'p4m6')     && isfield(cfg.filter.p4m6,'enable')     && cfg.filter.p4m6.enable;
    need.FAN   = isfield(cfg.filter,'fan')      && isfield(cfg.filter.fan,'enable')      && cfg.filter.fan.enable;
    ddkTags = resolve_ddk_tags(cfg);
    need.DDK   = ~isempty(ddkTags);

    % Combined (auto-inferred by dependencies)
    need.P4M6_GAUSS = false;
    need.P4M6_FAN   = false;

    % Hankel dependencies
    wantHankel = isfield(cfg.filter,'hankel') && isfield(cfg.filter.hankel,'enable') && cfg.filter.hankel.enable;
    hankelStackMode = wantHankel && isfield(cfg.filter,'hankel') && isfield(cfg.filter.hankel,'stack_mode') && cfg.filter.hankel.stack_mode;

    hin = 'RAW';
    if isfield(cfg.filter,'pre_hankel_input') && ~isempty(cfg.filter.pre_hankel_input)
        hin = cfg.filter.pre_hankel_input;
    end
    hinU = upper(string(hin));

    need.HSAF = wantHankel;
    if hankelStackMode
        % Defer HSAF to stack-based processing later in the pipeline.
        need.HSAF = false;
    end

    if wantHankel
        if hinU == "NONE"
            need.HSAF = false;
            hankelStackMode = false;
        elseif hinU == "RAW"
            % no extra deps
        elseif hinU == "GAUSSIAN" || hinU == "GAUSS"
            need.GAUSS = true;
            hin = 'GAUSS';
        elseif hinU == "DECORRELATION" || hinU == "DECORR"
            need.P4M6 = true;
            hin = 'P4M6';
        elseif hinU == "P4M6"
            need.P4M6 = true;
            hin = 'P4M6';
        elseif hinU == "FAN"
            need.FAN = true;
            hin = 'FAN';
        elseif contains(hinU,"P4M6") && (contains(hinU,"GAUSS") || contains(hinU,"GAUSSIAN"))
            need.P4M6 = true;
            need.GAUSS = true;
            need.P4M6_GAUSS = true;
            hin = 'P4M6_GAUSS';
        elseif contains(hinU,"P4M6") && contains(hinU,"FAN")
            need.P4M6 = true;
            need.FAN = true;
            need.P4M6_FAN = true;
            hin = 'P4M6_FAN';
        else
            warning('Unknown pre_hankel_input="%s". Fallback to RAW.', hin);
            hin = 'RAW';
        end
    else
        hin = 'RAW';
    end

    need.P4M6_GAUSS = need.P4M6 && need.GAUSS;
    need.P4M6_FAN   = need.P4M6 && need.FAN;

    % Build compute order (deterministic)
    order = {'RAW'};

    if need.P4M6;        order{end+1} = 'P4M6';        end
    if need.GAUSS;       order{end+1} = 'GAUSS';       end
    if need.FAN;         order{end+1} = 'FAN';         end
    if need.P4M6_GAUSS;  order{end+1} = 'P4M6_GAUSS';  end
    if need.P4M6_FAN;    order{end+1} = 'P4M6_FAN';    end
    for i = 1:numel(ddkTags)
        order{end+1} = ddkTags{i}; %#ok<AGROW>
    end
    if need.HSAF;        order{end+1} = 'HSAF';        end

    plan.need = need;
    plan.order = order;
    plan.ddk_tags = ddkTags;
    plan.hankel_input_tag = hin;
    plan.hankel_stack_mode = hankelStackMode;
end

function tags = resolve_ddk_tags(cfg)
    tags = {};
    if ~isfield(cfg, 'filter') || ~isfield(cfg.filter, 'ddk') || ~isstruct(cfg.filter.ddk)
        return;
    end
    ddk = cfg.filter.ddk;
    if ~isfield(ddk, 'enable') || ~logical(ddk.enable)
        return;
    end

    raw = {};
    if isfield(ddk, 'types') && ~isempty(ddk.types)
        if ischar(ddk.types) || (isstring(ddk.types) && isscalar(ddk.types))
            toks = regexp(char(ddk.types), '[,\s;]+', 'split');
            toks = toks(~cellfun('isempty', toks));
            raw = toks(:).';
        elseif iscell(ddk.types)
            raw = ddk.types;
        else
            raw = cellstr(string(ddk.types));
        end
    elseif isfield(ddk, 'type') && ~isempty(ddk.type)
        raw = {ddk.type};
    else
        raw = {'DDK4'};
    end

    normTags = {};
    for i = 1:numel(raw)
        t = upper(strtrim(char(string(raw{i}))));
        if isempty(t)
            continue;
        end
        if ~startsWith(t, 'DDK')
            t = ['DDK', t];
        end
        tok = regexp(t, '^DDK(\d+)$', 'tokens', 'once');
        if isempty(tok)
            warning('Ignoring invalid DDK type: %s', t);
            continue;
        end
        n = str2double(tok{1});
        if ~isfinite(n) || n < 1 || n > 8
            warning('Ignoring out-of-range DDK type: %s', t);
            continue;
        end
        normTags{end+1} = sprintf('DDK%d', n); %#ok<AGROW>
    end

    if isempty(normTags)
        normTags = {'DDK4'};
    end
    tags = unique(normTags, 'stable');
end
