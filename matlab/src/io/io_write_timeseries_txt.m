function io_write_timeseries_txt(outFile, x, y)
%IO_WRITE_TIMESERIES_TXT Write two columns: index/value.

    fid = fopen(outFile, 'w');
    fprintf(fid, '%d %.10g\n', [x(:), y(:)].');
    fclose(fid);
end
