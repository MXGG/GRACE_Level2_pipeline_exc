function checkpoint = checkpoint_manager(action, paths, cfg, plan, T, varargin)
%CHECKPOINT_MANAGER Manage pipeline checkpoints for resume capability.
%
% Description:
%   This function handles saving and loading pipeline state for
%   checkpoint-based resume functionality. It uses configuration
%   hashing to detect changes that would invalidate cached results.
%
% Usage:
%   checkpoint = checkpoint_manager('init', paths, cfg, plan, T)
%   checkpoint = checkpoint_manager('load', paths, cfg, plan, T)
%   checkpoint_manager('save', paths, cfg, plan, T, currentIdx)
%   checkpoint_manager('clear', paths)
%   isValid = checkpoint_manager('verify', paths, cfg, plan, T, idx)
%
% Actions:
%   'init'   - Initialize checkpoint structure
%   'load'   - Load existing checkpoint and validate
%   'save'   - Save current state to checkpoint file
%   'clear'  - Remove checkpoint file
%   'verify' - Verify cached outputs for a specific month
%
% Checkpoint Validation:
%   - Configuration hash must match
%   - Plan order must match
%   - Time range must match
%   - Cached output files must exist (if resume_verify enabled)
%
% Author: GRACE Pipeline Team

    stateFile = fullfile(paths.logs, 'run_state.mat');
    
    switch lower(action)
        case 'init'
            checkpoint = init_checkpoint(cfg, plan, T);
            
        case 'load'
            checkpoint = load_checkpoint(stateFile, cfg, plan, T);
            
        case 'save'
            if nargin < 6
                error('CHECKPOINT:MissingArg', 'currentIdx required for save action');
            end
            currentIdx = varargin{1};
            save_checkpoint(stateFile, cfg, plan, T, currentIdx);
            checkpoint = [];
            
        case 'clear'
            if isfile(stateFile)
                delete(stateFile);
            end
            checkpoint = [];
            
        case 'verify'
            if nargin < 6
                error('CHECKPOINT:MissingArg', 'idx required for verify action');
            end
            idx = varargin{1};
            checkpoint = verify_month_outputs(paths, plan, T(idx));
            
        otherwise
            error('CHECKPOINT:UnknownAction', 'Unknown action: %s', action);
    end
end

%% ========================================================================
%  LOCAL HELPER FUNCTIONS
%  ========================================================================

function checkpoint = init_checkpoint(cfg, plan, T)
%INIT_CHECKPOINT Create initial checkpoint structure.
    checkpoint = struct();
    checkpoint.cfgHash = cfg_hash(cfg);
    checkpoint.planHash = plan_hash(plan);
    checkpoint.codeHash = code_hash(cfg);
    checkpoint.timeRange = sprintf('%s_%s', T(1).yyyymm, T(end).yyyymm);
    checkpoint.Nt = numel(T);
    checkpoint.last_complete = 0;
    checkpoint.start_idx = 1;
    checkpoint.is_valid = true;
    checkpoint.has_state = false;
    checkpoint.message = 'Fresh start';
end

function checkpoint = load_checkpoint(stateFile, cfg, plan, T)
%LOAD_CHECKPOINT Load and validate existing checkpoint.
    checkpoint = init_checkpoint(cfg, plan, T);
    
    if ~isfile(stateFile)
        checkpoint.message = 'No checkpoint file found. Starting fresh.';
        return;
    end
    
    try
        S = load(stateFile);
    catch
        checkpoint.message = 'Checkpoint file corrupted. Starting fresh.';
        return;
    end
    
    if ~isfield(S, 'state')
        checkpoint.message = 'Invalid checkpoint format. Starting fresh.';
        return;
    end
    
    state = S.state;
    checkpoint.has_state = true;
    
    % Validate configuration hash
    currentCfgHash = cfg_hash(cfg);
    if ~isfield(state, 'cfgHash') || ~strcmp(state.cfgHash, currentCfgHash)
        checkpoint.is_valid = false;
        checkpoint.message = 'Configuration changed. Resume disabled.';
        return;
    end
    
    % Validate plan hash (if stored)
    currentPlanHash = plan_hash(plan);
    if isfield(state, 'planHash') && ~strcmp(state.planHash, currentPlanHash)
        checkpoint.is_valid = false;
        checkpoint.message = 'Processing plan changed. Resume disabled.';
        return;
    end

    % Validate code hash
    currentCodeHash = code_hash(cfg);
    if ~isfield(state, 'codeHash') || ~strcmp(state.codeHash, currentCodeHash)
        checkpoint.is_valid = false;
        checkpoint.message = 'Pipeline code changed. Resume disabled.';
        return;
    end
    
    % Validate time range
    currentTimeRange = sprintf('%s_%s', T(1).yyyymm, T(end).yyyymm);
    if isfield(state, 'timeRange') && ~strcmp(state.timeRange, currentTimeRange)
        checkpoint.is_valid = false;
        checkpoint.message = 'Time range changed. Resume disabled.';
        return;
    end
    
    % Get last completed index
    if ~isfield(state, 'last_complete') || state.last_complete < 1
        checkpoint.message = 'No completed months in checkpoint.';
        return;
    end
    
    lastIdx = state.last_complete;
    
    if lastIdx >= numel(T)
        checkpoint.start_idx = numel(T) + 1;
        checkpoint.last_complete = lastIdx;
        checkpoint.message = 'All months already completed.';
        return;
    end
    
    % Valid checkpoint found
    checkpoint.last_complete = lastIdx;
    checkpoint.start_idx = lastIdx + 1;
    checkpoint.is_valid = true;
    checkpoint.message = sprintf('Resuming from month %d/%d (%s).', ...
        lastIdx + 1, numel(T), T(lastIdx + 1).ym);
    
    % Copy additional metadata
    if isfield(state, 'updated')
        checkpoint.last_updated = state.updated;
    end
end

function save_checkpoint(stateFile, cfg, plan, T, currentIdx)
%SAVE_CHECKPOINT Save current pipeline state.
    state = struct();
    state.cfgHash = cfg_hash(cfg);
    state.planHash = plan_hash(plan);
    state.codeHash = code_hash(cfg);
    state.timeRange = sprintf('%s_%s', T(1).yyyymm, T(end).yyyymm);
    state.last_complete = currentIdx;
    state.last_ym = T(currentIdx).ym;
    state.updated = datestr(now, 'yyyy-mm-dd HH:MM:SS');
    state.plan_order = plan.order;
    state.Nt = numel(T);
    
    % Create directory if needed
    logDir = fileparts(stateFile);
    if ~isfolder(logDir)
        mkdir(logDir);
    end
    
    save(stateFile, 'state', '-v7.3');
end

function ok = verify_month_outputs(paths, plan, Tk)
%VERIFY_MONTH_OUTPUTS Check if all output files exist for a month.
    ok = true;
    
    for ii = 1:numel(plan.order)
        tag = plan.order{ii};
        fp = io_find_product_mat(paths, tag, Tk);
        
        if ~isfile(fp)
            ok = false;
            return;
        end
        
        % Optionally verify file integrity
        try
            % Quick load test
            S = load(fp, '-mat');
            if ~isfield(S, 'P')
                ok = false;
                return;
            end
        catch
            ok = false;
            return;
        end
    end
end

function h = plan_hash(plan)
%PLAN_HASH Create hash of processing plan.
    planStr = strjoin(plan.order, ',');
    if isfield(plan, 'hankel_input_tag')
        planStr = [planStr '|' plan.hankel_input_tag];
    end
    h = cfg_hash(struct('plan', planStr));
end

function h = code_hash(cfg)
%CODE_HASH Hash MATLAB source files under src/ to detect code changes.
    rootDir = '';
    if isfield(cfg, 'path') && isfield(cfg.path, 'ROOT') && isfolder(cfg.path.ROOT)
        rootDir = cfg.path.ROOT;
    end
    if isempty(rootDir)
        thisFile = mfilename('fullpath');
        rootDir = fileparts(fileparts(fileparts(thisFile))); % <ROOT>/src/core -> <ROOT>
    end

    srcDir = fullfile(rootDir, 'src');
    if ~isfolder(srcDir)
        h = '';
        return;
    end

    files = list_m_files(srcDir);
    files = sort(files);
    parts = cell(numel(files), 1);
    for i = 1:numel(files)
        fp = files{i};
        try
            txt = fileread(fp);
            parts{i} = [fp '|' md5_string(txt)];
        catch
            parts{i} = [fp '|READ_ERROR'];
        end
    end
    h = md5_string(strjoin(parts, ';'));
end

function files = list_m_files(rootDir)
%LIST_M_FILES Recursively list .m files under a directory.
    files = {};
    stack = {rootDir};
    while ~isempty(stack)
        d = stack{end};
        stack(end) = [];
        items = dir(d);
        for k = 1:numel(items)
            name = items(k).name;
            if name(1) == '.'
                continue;
            end
            path = fullfile(d, name);
            if items(k).isdir
                stack{end+1} = path; %#ok<AGROW>
            else
                [~,~,ext] = fileparts(name);
                if strcmpi(ext, '.m')
                    files{end+1} = path; %#ok<AGROW>
                end
            end
        end
    end
end

function h = md5_string(s)
%MD5_STRING Compute MD5 hash of a string.
    try
        md = java.security.MessageDigest.getInstance('MD5');
        md.update(uint8(s));
        h = sprintf('%.2x', typecast(md.digest(), 'uint8'));
    catch
        h = sprintf('%08x', sum(uint8(s)));
    end
end
