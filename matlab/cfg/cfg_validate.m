function cfg_validate(cfg)
%CFG_VALIDATE Minimal validation.

    % 兼容 inv 和 inversion 两种配置风格
    mustHave = {
        "path", "grid", "time", "filter", "io"
    };
    for i = 1:numel(mustHave)
        if ~isfield(cfg, mustHave{i})
            error('Config missing field: %s', mustHave{i});
        end
    end
    
    % 验证 inversion 或 inv 至少有一个存在
    if ~isfield(cfg, 'inv') && ~isfield(cfg, 'inversion')
        error('Config missing field: inv or inversion');
    end

    if ~isfield(cfg.path, 'GFC') || ~isfolder(cfg.path.GFC)
        warning('cfg.path.GFC does not exist: %s', cfg.path.GFC);
    end

    if ~isfield(cfg.path, 'OUTPUT')
        error('cfg.path.OUTPUT is required.');
    end

    if isfield(cfg.path, 'AUX') && ~isfolder(cfg.path.AUX)
        warning('cfg.path.AUX does not exist: %s', cfg.path.AUX);
    end

    if isfield(cfg.path, 'DDK') && ~isfolder(cfg.path.DDK)
        warning('cfg.path.DDK does not exist: %s', cfg.path.DDK);
    end

end
