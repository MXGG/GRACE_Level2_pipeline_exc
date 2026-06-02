function OUT = run_oneclick()
%RUN_ONECLICK One-click entry for the modular GRACE Level-2 pipeline.
    warning off;
    % run_oneclick.m lives in: <ROOT>/src/main/run_oneclick.m
    thisFile = mfilename('fullpath');
    srcDir   = fileparts(fileparts(thisFile)); % <MATLAB_ROOT>/src
    rootDir  = fileparts(srcDir);              % <MATLAB_ROOT>
    repoRoot = fileparts(rootDir);             % <REPO_ROOT>

    addpath(fullfile(rootDir,'cfg'));
    addpath(genpath(fullfile(rootDir,'src')));
    addpath(fullfile(rootDir,'src','tools'));
    addpath(genpath(fullfile(rootDir,'src','tools')),'-end');

    userCfg = getenv('GRACE_USER_CONFIG');
    userCfg = resolve_config_path(userCfg, rootDir, repoRoot, fullfile(rootDir,'cfg','user.json'));

    defaultCfg = getenv('GRACE_DEFAULT_CONFIG');
    defaultCfg = resolve_config_path(defaultCfg, rootDir, repoRoot, fullfile(rootDir,'cfg','default.json'));

    cfg = cfg_load(userCfg, defaultCfg);
    setup_env(cfg);

    OUT = run_pipeline(cfg);
end
