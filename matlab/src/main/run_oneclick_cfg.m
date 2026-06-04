function OUT = run_oneclick_cfg(cfgFile)
%RUN_ONECLICK_CFG One-click entry with explicit config file path.
%   Priority: input arg -> GRACE_CFG env var -> configs/user.json -> matlab/cfg/user.json

    thisFile = mfilename('fullpath');
    srcDir   = fileparts(fileparts(thisFile));
    rootDir  = fileparts(srcDir);
    repoRoot = fileparts(rootDir);

    addpath(fullfile(rootDir,'cfg'));
    addpath(genpath(fullfile(rootDir,'src')));
    addpath(fullfile(rootDir,'src','tools'));
    addpath(genpath(fullfile(rootDir,'src','tools')),'-end');

    if nargin < 1 || isempty(cfgFile)
        cfgFile = getenv('GRACE_CFG');
    end
    cfgFile = resolve_config_path(cfgFile, rootDir, repoRoot, fullfile(repoRoot,'configs','user.json'));
    if ~isfile(cfgFile)
        cfgFile = resolve_config_path('', rootDir, repoRoot, fullfile(rootDir,'cfg','user.json'));
    end
    if ~isfile(cfgFile)
        error('Config file not found: %s', cfgFile);
    end

    defaultCfg = resolve_config_path('', rootDir, repoRoot, fullfile(repoRoot,'configs','default.json'));
    if ~isfile(defaultCfg)
        defaultCfg = resolve_config_path('', rootDir, repoRoot, fullfile(rootDir,'cfg','default.json'));
    end
    cfg = cfg_load(cfgFile, defaultCfg);
    setup_env(cfg);

    OUT = run_pipeline(cfg);
end
