function log_error(cfg, Tk, ME)
%LOG_ERROR Append error info to output/LOG/errors.log
    try
        logDir = fullfile(cfg.path.OUTPUT,'LOG');
        ensure_dir(logDir);
        fp = fullfile(logDir,'errors.log');
        fid = fopen(fp,'a');
        if fid<0; return; end
        fprintf(fid,'[%s] %s\n', Tk.ym, ME.getReport('extended','hyperlinks','off'));
        fclose(fid);
    catch
        % silent
    end
end
