function val = inv_read_lowdeg_scalar(filePath, year, month, nameTag)
%INV_READ_LOWDEG_SCALAR Generic reader for scalar low-degree series.
% Accepts files with numeric columns where first two are [year month].
% Uses the 3rd numeric column as value by default.

    if nargin < 4; nameTag = 'scalar'; end
    if ~isfile(filePath)
        error('%s file not found: %s', nameTag, filePath);
    end

    fid = fopen(filePath,'r');
    if fid<0, error('Cannot open %s file.', nameTag); end

    val = NaN;
    while true
        ln = fgetl(fid);
        if ~ischar(ln), break; end
        ln = strtrim(ln);
        if isempty(ln), continue; end
        if startsWith(ln,'#') || startsWith(lower(ln),'end') || startsWith(lower(ln),'begin')
            continue;
        end
        nums = sscanf(ln,'%f');
        if numel(nums) < 3, continue; end
        yy = round(nums(1)); mm = round(nums(2));
        if yy == year && mm == month
            val = nums(3);
            break;
        end
    end
    fclose(fid);

    if isnan(val)
        error('%s not found for %04d-%02d.', nameTag, year, month);
    end
end
