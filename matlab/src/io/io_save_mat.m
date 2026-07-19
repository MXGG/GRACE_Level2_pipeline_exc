function io_save_mat(fp, varName, varargin)
%IO_SAVE_MAT Save variable(s) to MAT with -v7.3 by default and temp rename.
% Usage:
%   io_save_mat(fp, 'P')
%   io_save_mat(fp, 'Stack')
%   io_save_mat(fp, 'A','B','C') (pass multiple variable names)

    vars = [{varName}, varargin];
    S = struct();
    for i = 1:numel(vars)
        vn = vars{i};
        S.(vn) = evalin('caller', vn);
    end
    outDir = fileparts(fp);
    if ~isempty(outDir) && ~isfolder(outDir)
        mkdir(outDir);
    end
    tmp = [fp '.tmp'];
    if exist(tmp, 'file'); delete(tmp); end
    try
        save(tmp, '-struct', 'S', '-v7.3');
        movefile(tmp, fp, 'f');
    catch ME
        if exist(tmp, 'file'); delete(tmp); end
        rethrow(ME);
    end
end
