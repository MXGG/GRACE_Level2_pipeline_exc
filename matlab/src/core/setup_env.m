function setup_env(cfg)
%SETUP_ENV Initialize runtime environment and required paths.
%
% Description:
%   This function sets up the MATLAB environment for the GRACE Level-2
%   processing pipeline. It automatically discovers and adds all required
%   paths based on the project root directory (no hardcoded paths).
%
% Usage:
%   setup_env(cfg)
%
% Input:
%   cfg - Configuration struct from cfg_load()
%
% Features:
%   - Recursive path discovery from project root
%   - Dependency verification with detailed warnings
%   - Output directory initialization
%   - Optional parallel pool setup
%
% Author: GRACE Pipeline Team
% Last Modified: 2024

    % =====================================================================
    % STEP 1: Discover project root directory (no hardcoding)
    % =====================================================================
    thisFile = mfilename('fullpath');
    coreDir  = fileparts(thisFile);           % <ROOT>/src/core
    srcDir   = fileparts(coreDir);            % <ROOT>/src
    rootDir  = fileparts(srcDir);             % <ROOT>

    fprintf('\n[ENV] Initializing environment...\n');
    fprintf('[ENV] Project root: %s\n', rootDir);

    % =====================================================================
    % STEP 2: Build path list recursively (exclude hidden/private folders)
    % =====================================================================
    pathList = build_path_list(rootDir);
    
    % Add paths in priority order
    for i = 1:numel(pathList)
        addpath(pathList{i});
    end
    
    fprintf('[ENV] Added %d directories to MATLAB path.\n', numel(pathList));

    % =====================================================================
    % STEP 3: Verify critical dependencies
    % =====================================================================
    fprintf('[ENV] Checking dependencies...\n');
    deps = check_dependencies();
    print_dependency_status(deps);
    
    if ~deps.all_ok
        warning('SETUP_ENV:MissingDeps', ...
            'Some dependencies missing; certain pipeline steps may fail.');
    end

    % =====================================================================
    % STEP 4: Initialize output directories
    % =====================================================================
    if isfield(cfg, 'path') && isfield(cfg.path, 'OUTPUT')
        init_output_dirs(cfg.path.OUTPUT);
    end

    % =====================================================================
    % STEP 5: Optional parallel pool setup
    % =====================================================================
    if isfield(cfg, 'parallel') && isfield(cfg.parallel, 'enable') && cfg.parallel.enable
        setup_parallel_pool(cfg.parallel);
    end

    fprintf('[ENV] Environment ready.\n\n');
end

%% ========================================================================
%  LOCAL HELPER FUNCTIONS
%  ========================================================================

function pathList = build_path_list(rootDir)
%BUILD_PATH_LIST Recursively discover all valid MATLAB directories.
%
% Priority order:
%   1. cfg/
%   2. src/core/
%   3. src/inversion/
%   4. src/filters/
%   5. src/io/
%   6. src/basin/
%   7. src/leakage/
%   8. src/metrics/
%   9. src/plot/
%  10. src/main/
%  11. src/tools/ (including subdirectories, added last)

    pathList = {};
    
    % Priority modules (order matters for function shadowing)
    priorityDirs = {
        fullfile(rootDir, 'cfg')
        fullfile(rootDir, 'src', 'core')
        fullfile(rootDir, 'src', 'inversion')
        fullfile(rootDir, 'src', 'filters')
        fullfile(rootDir, 'src', 'io')
        fullfile(rootDir, 'src', 'basin')
        fullfile(rootDir, 'src', 'leakage')
        fullfile(rootDir, 'src', 'metrics')
        fullfile(rootDir, 'src', 'plot')
        fullfile(rootDir, 'src', 'main')
        fullfile(rootDir, 'src', 'tools')
    };
    
    % Add priority directories if they exist
    for i = 1:numel(priorityDirs)
        if isfolder(priorityDirs{i})
            pathList{end+1} = priorityDirs{i}; %#ok<AGROW>
        end
    end
    
    % Recursively add tools directory (placed at end to avoid shadowing)
    toolsDir = fullfile(rootDir, 'src', 'tools');
    if isfolder(toolsDir)
        toolsPaths = get_all_subdirs(toolsDir);
        pathList = [pathList, toolsPaths];
    end
end

function subdirs = get_all_subdirs(parentDir)
%GET_ALL_SUBDIRS Recursively get all subdirectories (excluding private/hidden).

    subdirs = {parentDir};
    
    items = dir(parentDir);
    items = items([items.isdir]);
    
    for i = 1:numel(items)
        name = items(i).name;
        
        % Skip special directories
        if strcmp(name, '.') || strcmp(name, '..')
            continue;
        end
        if strcmp(name, 'private')  % MATLAB private folders
            continue;
        end
        if startsWith(name, '.')    % Hidden folders
            continue;
        end
        if strcmp(name, 'doc') || strcmp(name, 'docs')  % Documentation
            continue;
        end
        if strcmp(name, 'tests') || strcmp(name, 'test')  % Test folders
            continue;
        end
        
        subPath = fullfile(parentDir, name);
        subSubdirs = get_all_subdirs(subPath);
        subdirs = [subdirs, subSubdirs]; %#ok<AGROW>
    end
end

function deps = check_dependencies()
%CHECK_DEPENDENCIES Verify that required external functions are available.

    deps = struct();
    
    % Hankel/HSAF dependencies
    deps.H_RCs = (exist('H_RCs', 'file') == 2);
    deps.HTLS_PM = (exist('HTLS_PM', 'file') == 2);
    
    % GMT tools
    deps.gmt_grid2cs = (exist('gmt_grid2cs', 'file') == 2);
    deps.gmt_readgsm = (exist('gmt_readgsm', 'file') == 2);
    
    % DDK filter
    deps.filterSH = (exist('filterSH', 'file') == 2);
    deps.read_BIN = (exist('read_BIN', 'file') == 2);
    
    % Spherical harmonic tools
    deps.plm2xyz = (exist('plm2xyz', 'file') == 2);
    deps.xyz2plm = (exist('xyz2plm', 'file') == 2);
    
    % m_map (optional, for plotting)
    deps.m_proj = (exist('m_proj', 'file') == 2);
    
    % Check overall status
    criticalDeps = [deps.H_RCs, deps.HTLS_PM, deps.filterSH, deps.read_BIN];
    deps.all_ok = all(criticalDeps);
end

function print_dependency_status(deps)
%PRINT_DEPENDENCY_STATUS Display dependency check results.

    fn = fieldnames(deps);
    fprintf('[ENV] Dependency status:\n');
    
    for i = 1:numel(fn)
        name = fn{i};
        if strcmp(name, 'all_ok')
            continue;
        end
        
        if deps.(name)
            status = 'OK';
        else
            status = 'MISSING';
        end
        fprintf('      %-15s : %s\n', name, status);
    end
end

function init_output_dirs(outputRoot)
%INIT_OUTPUT_DIRS Create standard output directory structure.

    dirs = {
        outputRoot
        fullfile(outputRoot, 'monthly_mat')
        fullfile(outputRoot, 'monthly_txt')
        fullfile(outputRoot, 'stacks')
        fullfile(outputRoot, 'metrics')
        fullfile(outputRoot, 'metrics', 'timeseries')
        fullfile(outputRoot, 'basin')
        fullfile(outputRoot, 'plots')
        fullfile(outputRoot, 'logs')
        fullfile(outputRoot, 'tmp')
        fullfile(outputRoot, 'CACHE')
    };
    
    for i = 1:numel(dirs)
        if ~isfolder(dirs{i})
            try
                mkdir(dirs{i});
            catch ME
                error('Failed to create output dir %s: %s', dirs{i}, ME.message);
            end
        end
    end
    
    fprintf('[ENV] Output directories initialized at: %s\n', outputRoot);
end

function setup_parallel_pool(parallelCfg)
%SETUP_PARALLEL_POOL Initialize MATLAB parallel pool if available.

    if ~isfield(parallelCfg, 'nWorkers')
        reqWorkers = 4;
    else
        reqWorkers = parallelCfg.nWorkers;
    end

    if isempty(reqWorkers) || ~isfinite(reqWorkers) || reqWorkers <= 0
        fprintf('[ENV] Parallel disabled (nWorkers=%g)\n', reqWorkers);
        return;
    end

    maxWorkers = feature('numcores');
    slurmCpus = str2double(getenv('SLURM_CPUS_PER_TASK'));
    if isfinite(slurmCpus) && slurmCpus > 0
        maxWorkers = min(maxWorkers, slurmCpus);
    end
    nWorkers = min(reqWorkers, maxWorkers);
    if nWorkers < 1
        fprintf('[ENV] Parallel disabled (resolved workers=%d)\n', nWorkers);
        return;
    end

    try
        % Clean up leftover local jobs that hold crash dumps.
        try
            c = parcluster('local');
            if ~isempty(c.Jobs)
                delete(c.Jobs);
            end
        catch
        end
        pool = gcp('nocreate');
        if isempty(pool)
            parpool('local', nWorkers);
            fprintf('[ENV] Parallel pool started with %d workers.\n', nWorkers);
        else
            fprintf('[ENV] Using existing parallel pool (%d workers).\n', pool.NumWorkers);
        end
    catch ME
        warning('SETUP_ENV:ParallelFailed', ...
            'Failed to start parallel pool: %s', ME.message);
    end
end
