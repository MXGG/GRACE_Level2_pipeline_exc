function OUT = run_oneclick()
%RUN_ONECLICK One-click entry for the modular GRACE Level-2 pipeline.
    thisFile = mfilename('fullpath');
    srcDir   = fileparts(fileparts(thisFile));
    rootDir  = fileparts(srcDir);
    repoRoot = fileparts(rootDir);

    addpath(fullfile(rootDir,'cfg'));
    addpath(genpath(fullfile(rootDir,'src')));
    addpath(fullfile(rootDir,'src','tools'));
    addpath(genpath(fullfile(rootDir,'src','tools')),'-end');

    userCfg = getenv('GRACE_USER_CONFIG');
    userCfg = resolve_config_path(userCfg, rootDir, repoRoot, fullfile(repoRoot,'configs','user.json'));
    if ~isfile(userCfg)
        userCfg = resolve_config_path('', rootDir, repoRoot, fullfile(rootDir,'cfg','user.json'));
    end

    defaultCfg = getenv('GRACE_DEFAULT_CONFIG');
    defaultCfg = resolve_config_path(defaultCfg, rootDir, repoRoot, fullfile(repoRoot,'configs','default.json'));
    if ~isfile(defaultCfg)
        defaultCfg = resolve_config_path('', rootDir, repoRoot, fullfile(rootDir,'cfg','default.json'));
    end

    cfg = cfg_load(userCfg, defaultCfg);
    setup_env(cfg);

    OUT = run_pipeline(cfg);
end
