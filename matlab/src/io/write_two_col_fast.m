function write_two_col_fast(outFile, x, y)
%WRITE_TWO_COL_FAST Write two-column text file.
    fid = fopen(outFile, 'w');
    if fid < 0; error('Cannot open file: %s', outFile); end
    fprintf(fid, '%.10g %.10g\n', [x(:), y(:)].');
    fclose(fid);
end
