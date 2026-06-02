function [C20, C30, matchInfo] = inv_read_lowdeg_tn14_c20(tn14File, year, month, spanStart, spanEnd)
%INV_READ_LOWDEG_TN14_C20 Read monthly C20/C30 from TN-14 style SLR file.
%
% Supports two common TN-14 formats:
% 1) Legacy: first two numeric columns are [year month]
% 2) Modern TN-14 v2+: columns include MJD start/end and year-fraction
%
% Returns:
%   C20 (scalar), C30 (scalar or NaN if unavailable). Error if C20 not found.
%
% Matching:
%   If spanStart/spanEnd are provided, modern TN-14 rows are selected by
%   maximum overlap with the GSM solution arc. Otherwise the calendar month
%   [year, month] is used. This keeps YYYYMM products and YYYYDDD-YYYYDDD
%   CSR/JPL/GFZ products on the same replacement path.

    if ~isfile(tn14File)
        error('TN-14 file not found: %s', tn14File);
    end
    if nargin < 4 || isempty(spanStart) || ~isdatetime(spanStart) || isnat(spanStart)
        spanStart = datetime(year, month, 1);
    end
    if nargin < 5 || isempty(spanEnd) || ~isdatetime(spanEnd) || isnat(spanEnd)
        spanEnd = dateshift(datetime(year, month, 1), 'end', 'month');
    end
    if spanEnd < spanStart
        spanStart = datetime(year, month, 1);
        spanEnd = dateshift(spanStart, 'end', 'month');
    end

    fid = fopen(tn14File,'r');
    if fid<0, error('Cannot open TN-14 file.'); end

    C20 = NaN;
    C30 = NaN;
    matchInfo = struct('method', '', 'overlap_days', NaN, ...
        'mjd_start', NaN, 'mjd_end', NaN, 'line', '');
    bestOverlapDays = -Inf;
    mjd0 = dt2mjd(spanStart);
    mjd1 = dt2mjd(spanEnd);
    while true
        ln = fgetl(fid);
        if ~ischar(ln), break; end
        ln = strtrim(ln);
        if isempty(ln), continue; end
        if startsWith(ln,'#') || startsWith(lower(ln),'end') || startsWith(lower(ln),'begin')
            continue;
        end

        nums = sscanf(ln,'%f');
        if numel(nums) < 5
            continue;
        end

        % Modern TN-14 v2+: [mjd_start, yearfrac_start, C20, ..., mjd_end, yearfrac_end]
        if numel(nums) >= 10 && nums(1) > 10000 && nums(2) > 1900 && nums(2) < 2100
            mjdStart = nums(1);
            c20 = nums(3);
            c30 = NaN;
            if numel(nums) >= 6
                c30 = nums(6);
            end
            mjdEnd = nums(9);

            oStart = max(mjd0, mjdStart);
            oEnd = min(mjd1, mjdEnd);
            if oEnd < oStart
                continue;
            end
            overlapDays = oEnd - oStart + 1;
            if overlapDays > bestOverlapDays
                bestOverlapDays = overlapDays;
                C20 = c20;
                C30 = c30;
                matchInfo.method = 'mjd_overlap';
                matchInfo.overlap_days = overlapDays;
                matchInfo.mjd_start = mjdStart;
                matchInfo.mjd_end = mjdEnd;
                matchInfo.line = ln;
            end
            continue;
        end

        % Legacy format: [year month ... C20 ...]
        yy = round(nums(1));
        mm = round(nums(2));
        if yy == year && mm == month
            C20 = nums(5);
            if numel(nums) >= 8
                C30 = nums(8);
            end
            bestOverlapDays = 1;
            matchInfo.method = 'year_month';
            matchInfo.overlap_days = 1;
            matchInfo.line = ln;
        end
    end

    fclose(fid);

    if isnan(C20)
        error('C20 not found in TN-14 file for %04d-%02d / %s to %s.', ...
            year, month, datestr(spanStart, 'yyyy-mm-dd'), datestr(spanEnd, 'yyyy-mm-dd'));
    end
end

function mjd = dt2mjd(dt)
    mjd0 = datetime(1858, 11, 17);
    mjd = days(dt - mjd0);
end
