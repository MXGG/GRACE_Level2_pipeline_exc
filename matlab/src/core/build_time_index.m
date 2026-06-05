function T = build_time_index(cfg)
%BUILD_TIME_INDEX Build monthly time index either from cfg bounds or detected GFC files.
    if ~isfield(cfg,'time')
        error('cfg.time section is required to build the time index.');
    end

    autoDetect = isfield(cfg.time,'auto_detect_gfc') && cfg.time.auto_detect_gfc;
    months = datetime.empty(0,1);
    gfcFiles = struct('yyyymm',{},'file',{},'start_dt',{},'end_dt',{},'mid_dt',{});

    productType = '';
    if isfield(cfg.time,'product_type')
        productType = cfg.time.product_type;
    end
    fileExt = '';
    if isfield(cfg.time,'file_ext')
        fileExt = cfg.time.file_ext;
    end

    if autoDetect
        if ~isfield(cfg,'path') || ~isfield(cfg.path,'GFC')
            error('cfg.path.GFC must be set when auto_detect_gfc=true.');
        end
        entries = detect_gfc_months(cfg.path.GFC, productType, fileExt);
        if isempty(entries)
            error('No GSM/GFC files found under %s.', cfg.path.GFC);
        end
        entries = filter_entries_by_cfg_range(entries, cfg.time);
        if isempty(entries)
            error('No GSM/GFC files found in configured range %s to %s.', cfg.time.start_ym, cfg.time.end_ym);
        end
        months = [entries.dt].';
        for i = 1:numel(entries)
            gfcFiles(i).yyyymm = entries(i).key;
            gfcFiles(i).file = entries(i).file;
            gfcFiles(i).start_dt = entries(i).start_dt;
            gfcFiles(i).end_dt = entries(i).end_dt;
            gfcFiles(i).mid_dt = entries(i).mid_dt;
        end
    else
        if ~isfield(cfg.time,'start_ym') || ~isfield(cfg.time,'end_ym')
            error('cfg.time.start_ym and cfg.time.end_ym must be set when auto detection is disabled.');
        end
        s = datetime(cfg.time.start_ym,'InputFormat','yyyy-MM');
        e = datetime(cfg.time.end_ym,  'InputFormat','yyyy-MM');
        if e < s
            error('end_ym must be >= start_ym');
        end
        months = (s:calmonths(1):e).';
        gfcFiles = arrayfun(@(dt) struct( ...
            'yyyymm', datestr(dt,'yyyymm'), ...
            'file', '', ...
            'start_dt', dateshift(dt, 'start', 'month'), ...
            'end_dt', dateshift(dt, 'end', 'month'), ...
            'mid_dt', dateshift(dt, 'start', 'month') + days(14)), months);
    end

    n = numel(months);
    T = repmat(struct( ...
        'ym','', ...
        'yyyymm','', ...
        'dt',datetime, ...
        'file_guess','', ...
        'gfc_start_dt',datetime, ...
        'gfc_end_dt',datetime, ...
        'gfc_mid_dt',datetime), n, 1);

    monthFileMap = containers.Map('KeyType','char','ValueType','char');
    startMap = containers.Map('KeyType','char','ValueType','any');
    endMap = containers.Map('KeyType','char','ValueType','any');
    midMap = containers.Map('KeyType','char','ValueType','any');
    for i = 1:numel(gfcFiles)
        monthFileMap(gfcFiles(i).yyyymm) = gfcFiles(i).file;
        startMap(gfcFiles(i).yyyymm) = gfcFiles(i).start_dt;
        endMap(gfcFiles(i).yyyymm) = gfcFiles(i).end_dt;
        midMap(gfcFiles(i).yyyymm) = gfcFiles(i).mid_dt;
    end

    for k = 1:n
        dt = months(k);
        ym = datestr(dt,'yyyy-mm');
        yyyymm = datestr(dt,'yyyymm');

        T(k).dt = dt;
        T(k).ym = ym;
        T(k).yyyymm = yyyymm;
        if isKey(startMap, yyyymm); T(k).gfc_start_dt = startMap(yyyymm); end
        if isKey(endMap, yyyymm); T(k).gfc_end_dt = endMap(yyyymm); end
        if isKey(midMap, yyyymm); T(k).gfc_mid_dt = midMap(yyyymm); end

        if isKey(monthFileMap, yyyymm)
            T(k).file_guess = monthFileMap(yyyymm);
        elseif isfield(cfg,'path') && isfield(cfg.path,'GFC') && isfolder(cfg.path.GFC)
            pat = sprintf('*%s*%s*%s', cfg.time.product_type, yyyymm, cfg.time.file_ext);
            d = dir(fullfile(cfg.path.GFC, pat));
            if ~isempty(d)
                T(k).file_guess = fullfile(d(1).folder, d(1).name);
            end
        end
    end
end

function entries = filter_entries_by_cfg_range(entries, timeCfg)
    if ~isfield(timeCfg,'start_ym') && ~isfield(timeCfg,'end_ym')
        return;
    end

    keep = true(size(entries));
    if isfield(timeCfg,'start_ym') && ~isempty(timeCfg.start_ym)
        s = datetime(timeCfg.start_ym,'InputFormat','yyyy-MM');
        keep = keep & ([entries.dt] >= s);
    end
    if isfield(timeCfg,'end_ym') && ~isempty(timeCfg.end_ym)
        e = datetime(timeCfg.end_ym,'InputFormat','yyyy-MM');
        keep = keep & ([entries.dt] <= e);
    end
    entries = entries(keep);
end

function entries = detect_gfc_months(gfcDir, productType, fileExt)
    entries = struct('key',{},'dt',{},'file',{},'start_dt',{},'end_dt',{},'mid_dt',{});
    files = [dir(fullfile(gfcDir,'*.gfc')); dir(fullfile(gfcDir,'*.GFC'))];
    if isempty(files); return; end

    productTypeLower = '';
    if nargin >= 2 && ~isempty(productType)
        productTypeLower = lower(productType);
    end
    fileExtLower = '';
    if nargin >= 3 && ~isempty(fileExt)
        fileExtLower = lower(fileExt);
    end
    if ~isempty(productTypeLower)
        namesLower = lower({files.name});
        if ~any(contains(namesLower, productTypeLower))
            productTypeLower = '';
        end
    end

    idxCount = 0;
    seen = containers.Map('KeyType','char','ValueType','logical');
    seenTag = containers.Map('KeyType','char','ValueType','logical');
    for i = 1:numel(files)
        name = files(i).name;
        if ~isempty(productTypeLower) && ~contains(lower(name), productTypeLower)
            continue;
        end
        if ~isempty(fileExtLower) && ~endsWith(lower(name), fileExtLower)
            continue;
        end

        tagTok = regexp(name, '(\d{7}-\d{7})', 'match', 'once');
        if isempty(tagTok)
            tagTok = name;
        end
        if isKey(seenTag, tagTok)
            continue;
        end
        seenTag(tagTok) = true;

        [startDT, endDT] = parse_gfc_dates(name);
        if isempty(startDT) || isempty(endDT)
            continue;
        end

        midDT = startDT + (endDT - startDT) / 2;
        curr = dateshift(midDT, 'start', 'month');
        key = datestr(curr,'yyyymm');

        if isKey(seen, key)
            if month(startDT) ~= month(endDT) || year(startDT) ~= year(endDT)
                curr = dateshift(endDT, 'start', 'month');
                key = datestr(curr,'yyyymm');
            end
            while isKey(seen, key)
                curr = dateshift(curr, 'start', 'month') + calmonths(1);
                key = datestr(curr,'yyyymm');
            end
        end

        idxCount = idxCount + 1;
        entries(idxCount).key = key;
        entries(idxCount).dt = curr;
        entries(idxCount).file = fullfile(files(i).folder, name);
        entries(idxCount).start_dt = startDT;
        entries(idxCount).end_dt = endDT;
        entries(idxCount).mid_dt = midDT;
        seen(key) = true;
    end

    if idxCount == 0
        return;
    end

    [~, order] = sort([entries.dt]);
    entries = entries(order);

end

function [startDT, endDT] = parse_gfc_dates(name)
    startDT = [];
    endDT = [];

    tok = regexp(name, '(?<y1>\d{4})(?<d1>\d{3})-(?<y2>\d{4})(?<d2>\d{3})', 'names', 'once');
    if ~isempty(tok)
        startDT = datetime(str2double(tok.y1), 1, 1) + days(str2double(tok.d1) - 1);
        endDT = datetime(str2double(tok.y2), 1, 1) + days(str2double(tok.d2) - 1);
        return;
    end

    % e.g. IGG-SLR-DORIS_1984-01.gfc
    ymTok = regexp(name, '(?<y>\d{4})-(?<m>\d{2})', 'names');
    if ~isempty(ymTok)
        y = str2double(ymTok(1).y);
        m = str2double(ymTok(1).m);
        if isfinite(y) && isfinite(m) && m >= 1 && m <= 12
            startDT = datetime(y, m, 1);
            endDT = dateshift(startDT, 'end', 'month');
            return;
        end
    end

    matches = regexp(name, '(\d{6})', 'match');
    if isempty(matches)
        return;
    end

    startYM = matches{1};
    try
        startDT0 = datetime(str2double(startYM(1:4)), str2double(startYM(5:6)), 1);
    catch
        startDT0 = [];
    end

    endYM = matches{end};
    try
        endDT0 = datetime(str2double(endYM(1:4)), str2double(endYM(5:6)), 1);
        endDT0 = dateshift(endDT0,'end','month');
    catch
        endDT0 = [];
    end

    if isempty(startDT0)
        return;
    end
    if isempty(endDT0)
        endDT0 = dateshift(startDT0,'end','month');
    end

    startDT = startDT0;
    endDT = endDT0;
end
