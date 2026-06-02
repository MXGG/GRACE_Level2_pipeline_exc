function cfg = cfg_load(userJsonPath, defaultJsonPath)
%CFG_LOAD Load default config + user override config from JSON.
%
% Usage:
%   cfg = cfg_load('config/user.json', 'config/default.json');

    if nargin < 2 || isempty(defaultJsonPath)
        error('defaultJsonPath is required.');
    end

    cfgDir = fileparts(mfilename('fullpath'));      % .../matlab/cfg
    matlabRoot = fileparts(cfgDir);                 % .../matlab
    repoRoot = fileparts(matlabRoot);               % .../<repo>
    if isfolder(fullfile(repoRoot,'data')) && isfolder(fullfile(repoRoot,'output'))
        rootDir = repoRoot;
    else
        rootDir = matlabRoot;
    end

    cfgDefault = cfg_read_json(defaultJsonPath);
    cfgUser    = struct();
    if nargin >= 1 && ~isempty(userJsonPath) && isfile(userJsonPath)
        cfgUser = cfg_read_json(userJsonPath);
    end

    % Merge: user overrides default
    cfg = cfg_merge_struct(cfgDefault, cfgUser);

    % Resolve placeholders like ${ROOT}
    cfg = cfg_resolve_placeholders(cfg, rootDir);

    % Compatibility: sync inv/inversion fields.
    if isfield(cfg, 'inversion') && ~isfield(cfg, 'inv')
        cfg.inv = cfg.inversion;
    elseif isfield(cfg, 'inv') && ~isfield(cfg, 'inversion')
        cfg.inversion = cfg.inv;
    elseif isfield(cfg, 'inv') && isfield(cfg, 'inversion')
        warning('Both cfg.inv and cfg.inversion exist. Make sure they are consistent.');
    end

    cfg_validate(cfg);
end
