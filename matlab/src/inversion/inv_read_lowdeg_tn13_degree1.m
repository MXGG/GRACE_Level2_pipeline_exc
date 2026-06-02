function [C10,C11,S11] = inv_read_lowdeg_tn13_degree1(tn13File, year, month)
%INV_READ_LOWDEG_TN13_DEGREE1 Read degree-1 geocenter terms from TN-13 style file.
%
% Supports two common TN-13 formats:
% 1) Legacy table: first two numeric columns are [year month]
% 2) Modern ICGEM-like lines (e.g. GRCOF2 1 0 ... yyyymmdd yyyymmdd)
%
% Returns scalars C10,C11,S11. Error if not found.

    if ~isfile(tn13File)
        error('TN-13 file not found: %s', tn13File);
    end

    fid = fopen(tn13File,'r');
    if fid<0, error('Cannot open TN-13 file.'); end

    C10 = NaN; C11 = NaN; S11 = NaN;
    bestC10 = -Inf; best11 = -Inf;
    dt0 = datetime(year, month, 1);
    dt1 = dateshift(dt0, 'end', 'month');

    while true
        ln = fgetl(fid);
        if ~ischar(ln), break; end
        ln = strtrim(ln);
        if isempty(ln), continue; end
        if startsWith(ln,'#') || startsWith(lower(ln),'end') || startsWith(lower(ln),'begin')
            continue;
        end

        % Modern ICGEM-like format: GRCOF2 l m C S ... yyyymmdd yyyymmdd
        tok = regexp(ln, '^\s*\w+\s+(?<l>\d+)\s+(?<m>\d+)\s+(?<C>[-+0-9.eE]+)\s+(?<S>[-+0-9.eE]+)\s+.*?(?<d0>\d{8})\.\d+\s+(?<d1>\d{8})\.\d+\s*$', 'names', 'once');
        if ~isempty(tok)
            l = str2double(tok.l);
            m = str2double(tok.m);
            C = str2double(tok.C);
            S = str2double(tok.S);
            tStart = datetime(tok.d0, 'InputFormat', 'yyyyMMdd');
            tEndExcl = datetime(tok.d1, 'InputFormat', 'yyyyMMdd');
            tEnd = tEndExcl - days(1); % inclusive end-of-span

            oStart = max(dt0, tStart);
            oEnd = min(dt1, tEnd);
            if oEnd < oStart
                continue;
            end
            overlapDays = days(oEnd - oStart) + 1;

            if l == 1 && m == 0
                if overlapDays > bestC10
                    bestC10 = overlapDays;
                    C10 = C;
                end
            elseif l == 1 && m == 1
                if overlapDays > best11
                    best11 = overlapDays;
                    C11 = C;
                    S11 = S;
                end
            end
            continue;
        end

        % Legacy numeric table format: [year month C10 C11 S11 ...]
        nums = sscanf(ln,'%f');
        if numel(nums) >= 5
            yy = round(nums(1));
            mm = round(nums(2));
            if yy == year && mm == month
                C10 = nums(3);
                C11 = nums(4);
                S11 = nums(5);
                bestC10 = 1; best11 = 1;
            end
        end
    end

    fclose(fid);

    if any(isnan([C10,C11,S11]))
        error('Degree-1 terms not found in TN-13 file for %04d-%02d.', year, month);
    end
end
