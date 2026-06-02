function io_log_run(paths, msg)
%IO_LOG_RUN Append message to a log file with timestamp.

    ensure_dir(paths.logs);
    fp = fullfile(paths.logs, 'pipeline.log');
    ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
    fid = fopen(fp, 'a');
    fprintf(fid, '[%s] %s\n', ts, msg);
    fclose(fid);
end
