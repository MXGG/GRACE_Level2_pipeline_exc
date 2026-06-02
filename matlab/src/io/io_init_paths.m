function paths = io_init_paths(cfg)
%IO_INIT_PATHS Create and return standard output folder paths.
% This is the compatibility layer across modules.

    outRoot = cfg.path.OUTPUT;
    % Route outputs to local/ or remote/<jobid> based on SLURM env.
    slurmJob = getenv('SLURM_JOB_ID');
    if ~isempty(slurmJob)
        outRoot = fullfile(outRoot, 'remote', slurmJob);
    else
        outRoot = fullfile(outRoot, 'local');
    end
    ensure_dir(outRoot);

    paths = struct();
    paths.root = outRoot;

    paths.monthly_mat = fullfile(outRoot, 'monthly_mat');
    paths.monthly_txt = fullfile(outRoot, 'monthly_txt');
    paths.stacks      = fullfile(outRoot, 'stacks');
    paths.metrics     = fullfile(outRoot, 'metrics');
    paths.metrics_ts  = fullfile(outRoot, 'metrics', 'timeseries');
    paths.basin       = fullfile(outRoot, 'basin');
    paths.plots       = fullfile(outRoot, 'plots');
    paths.logs        = fullfile(outRoot, 'logs');
    paths.tmp         = fullfile(outRoot, 'tmp');
    paths.cache       = fullfile(outRoot, 'CACHE');

    ensure_dir(paths.monthly_mat);
    ensure_dir(paths.monthly_txt);
    ensure_dir(paths.stacks);
    ensure_dir(paths.metrics);
    ensure_dir(paths.metrics_ts);
    ensure_dir(paths.basin);
    ensure_dir(paths.plots);
    ensure_dir(paths.logs);
    ensure_dir(paths.tmp);
    ensure_dir(paths.cache);
end
