function cfgPath = resolve_config_path(pathText, matlabRoot, repoRoot, defaultPath)
%RESOLVE_CONFIG_PATH Resolve config paths from either matlab-root or repo-root.
    if nargin < 4
        defaultPath = '';
    end

    if nargin < 3 || isempty(repoRoot)
        repoRoot = fileparts(matlabRoot);
    end

    if nargin < 2 || isempty(matlabRoot)
        matlabRoot = repoRoot;
    end

    if nargin < 1 || isempty(pathText)
        cfgPath = defaultPath;
        return;
    end

    pathText = char(pathText);
    candidates = {pathText};
    if ispc
        isAbsolute = ~isempty(regexp(pathText, '^[A-Za-z]:[\\/]', 'once')) || startsWith(pathText, '\\');
    else
        isAbsolute = startsWith(pathText, '/');
    end

    if ~isAbsolute
        candidates{end+1} = fullfile(matlabRoot, pathText); %#ok<AGROW>
        candidates{end+1} = fullfile(repoRoot, pathText); %#ok<AGROW>
    end

    cfgPath = '';
    for i = 1:numel(candidates)
        if isfile(candidates{i})
            cfgPath = candidates{i};
            return;
        end
    end

    if ~isempty(defaultPath)
        cfgPath = defaultPath;
    else
        cfgPath = candidates{1};
    end
end
