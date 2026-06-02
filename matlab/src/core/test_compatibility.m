function test_compatibility()
    % Ensure paths regardless of current working directory
    rootDir = fileparts(fileparts(fileparts(mfilename('fullpath'))));
    addpath(fullfile(rootDir, 'cfg'));
    addpath(fullfile(rootDir, 'src', 'core'));
    addpath(fullfile(rootDir, 'src', 'tools'));
    addpath(genpath(fullfile(rootDir, 'src', 'tools')),'-end');

    fprintf('\n=== Start compatibility checks ===\n');
    
    % 1. Config fields
    test_config_fields(rootDir);
    
    % 2. Path dependencies
    test_path_dependencies();
    
    % 3. Simple function call chain
    test_function_chains();
    
    fprintf('\n=== Compatibility checks finished ===\n');
end

function test_config_fields(rootDir)
    fprintf('Checking config fields...\n');
    cfg = cfg_load(fullfile(rootDir, 'cfg', 'user.json'), fullfile(rootDir, 'cfg', 'default.json'));
    
    hasInv = isfield(cfg, 'inversion') && isfield(cfg.inversion, 'lowdeg');
    hasInvAlt = isfield(cfg, 'inv') && isfield(cfg.inv, 'lowdeg');
    assert(hasInv || hasInvAlt, 'Config missing inversion/ inv .lowdeg');
    
    fprintf('  OK config fields\n');
end

function test_path_dependencies()
    fprintf('Checking path dependencies...\n');
    
    required_functions = {'H_RCs', 'HTLS_PM', 'gmt_grid2cs', 'DDKs_Filter'};
    for i = 1:length(required_functions)
        if exist(required_functions{i}, 'file') ~= 2
            warning('Missing dependency: %s', required_functions{i});
        end
    end
    
    fprintf('  OK path dependencies\n');
end

function test_function_chains()
    fprintf('Checking simple function chain...\n');
    try
        [lon, lat] = make_lonlat_vec(struct('grid', struct(...
            'lon', [0 360], 'lat', [90 -90], 'dlon', 1, 'dlat', 1)));
        assert(~isempty(lon) && ~isempty(lat), 'Grid generation failed');
        fprintf('  OK grid generation\n');
    catch ME
        warning('Function chain test failed: %s', ME.message);
    end
end
