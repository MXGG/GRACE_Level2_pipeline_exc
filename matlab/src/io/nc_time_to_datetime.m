function dtVec = nc_time_to_datetime(timeInfo, timeVals)
%NC_TIME_TO_DATETIME Convert NetCDF time variable to MATLAB datetime.
    attrNames = {timeInfo.Attributes.Name};
    idx = find(strcmpi(attrNames, 'Units'), 1);
    if isempty(idx)
        error('Time variable lacks Units attribute.');
    end

    unitsRaw = timeInfo.Attributes(idx).Value;
    if iscell(unitsRaw)
        unitsRaw = strjoin(cellfun(@char, unitsRaw, 'UniformOutput', false), ' ');
    elseif isnumeric(unitsRaw)
        unitsRaw = char(unitsRaw(:).');
    end

    units = char(unitsRaw(:).');
    units = regexprep(units, '[^ -~]', ' ');
    units = strtrim(regexprep(units, '\s+', ' '));
    tok = regexp(units, '(?<unit>\w+)\s+since\s+(?<base>[^\s]+)', 'names', 'once', 'ignorecase');
    if isempty(tok)
        parts = regexpi(units, 'since', 'split');
        if numel(parts) >= 2
            tok = struct();
            tok.unit = strtrim(parts{1});
            tok.base = strtrim(parts{2});
            semi = regexp(tok.base, ';', 'once');
            if ~isempty(semi)
                tok.base = strtrim(tok.base(1:semi-1));
            end
        end
    end
    if isempty(tok) || isempty(tok.base) || isempty(tok.unit)
        error('Cannot parse time units: %s', units);
    end
    base = tok.base;
    base = strrep(base, 'T', ' ');
    base = strrep(base, 'Z', '');
    fmt = 'yyyy-MM-dd HH:mm:ss';
    if ~contains(base, ':')
        fmt = 'yyyy-MM-dd';
    end
    dtBase = datetime(base, 'InputFormat', fmt);
    switch lower(tok.unit)
        case {'day', 'days'}
            dtVec = dtBase + days(timeVals);
        case {'hour', 'hours'}
            dtVec = dtBase + hours(timeVals);
        otherwise
            error('Unsupported time unit: %s', tok.unit);
    end
end
