function ensure_dir(p)
%ENSURE_DIR Create directory if not exist.
    if exist(p,'dir')
        return;
    end
    w = warning('off','MATLAB:MKDIR:DirectoryExists');
    cleanup = onCleanup(@() warning(w)); %#ok<NASGU>
    [ok, msg] = mkdir(p);
    if ~ok && ~exist(p,'dir')
        error('ensure_dir:mkdirFailed', 'Failed to create dir %s: %s', p, msg);
    end
end
