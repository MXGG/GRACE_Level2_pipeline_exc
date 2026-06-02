function OUT = run_oneclick_cfg(cfgFile)
%RUN_ONECLICK_CFG One-click entry with explicit config file path.
%   Priority: input arg -> GRACE_CFG env var -> cfg/user.json

    warning off;
    thisFile = mfilename('fullpath');
    srcDir   = fileparts(fileparts(thisFile)); % <MATLAB_ROOT>/src
    rootDir  = fileparts(srcDir);              % <MATLAB_ROOT>
    repoRoot = fileparts(rootDir);             % <REPO_ROOT>

    addpath(fullfile(rootDir,'cfg'));
    addpath(genpath(fullfile(rootDir,'src')));
    addpath(fullfile(rootDir,'src','tools'));
    addpath(genpath(fullfile(rootDir,'src','tools')),'-end');

    if nargin < 1 || isempty(cfgFile)
        cfgFile = getenv('GRACE_CFG');
    end
    cfgFile = resolve_config_path(cfgFile, rootDir, repoRoot, fullfile(rootDir,'cfg','user.json'));
    if ~isfile(cfgFile)
        error('Config file not found: %s', cfgFile);
    end

    defaultCfg = resolve_config_path('', rootDir, repoRoot, fullfile(rootDir,'cfg','default.json'));
    cfg = cfg_load(cfgFile, defaultCfg);
    setup_env(cfg);

    OUT = run_pipeline(cfg);
end
