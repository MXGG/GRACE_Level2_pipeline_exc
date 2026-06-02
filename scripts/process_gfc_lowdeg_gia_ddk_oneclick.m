%% process_gfc_lowdeg_gia_ddk_oneclick.m
% One-click MATLAB processing for monthly GFC files:
%   1) read input GFC coefficients
%   2) replace low-degree terms: degree-1 from TN-13, C20/C30 from TN-14
%   3) apply GIA Stokes correction
%   4) apply DDK3/DDK4/DDK5 filters
%   5) write processed GFC files
%
% Usage:
%   Edit the "USER CONFIGURATION" block below, then press Run in MATLAB.
%
% Notes:
%   - This script writes a RAW_LD_GIA product and DDK products.
%   - DDK binary reading and filtering are implemented as local functions in
%     this file. You only need the DDK kernel data folder.
%   - GIA mode "fixed" subtracts the Stokes coefficients directly.
%     GIA mode "rate" subtracts coefficient_rate*(decimal_year-reference_epoch).

clear; clc;

%% USER CONFIGURATION
cfg = struct();

% Required input/output paths. Replace these with your machine's paths.
cfg.inputDir = "PATH_TO_INPUT_HUST_N96_GFC_FOLDER";
cfg.outputDir = "PATH_TO_OUTPUT_FOLDER";
cfg.degree1File = "PATH_TO_TN13_DEGREE1_FILE.txt";
cfg.c20c30File = "PATH_TO_TN14_C20_C30_FILE.txt";
cfg.giaFile = "PATH_TO_GIA_STOKES_FILE.txt";
cfg.ddkDataDir = "PATH_TO_DDK_KERNEL_FOLDER";

% Processing options.
cfg.Lmax = 96;
cfg.ddkTypes = ["DDK3", "DDK4", "DDK5"];
cfg.writeRawLowdegGia = true;
cfg.skipExisting = false;

% C30 is usually applied for GRACE-FO months only.
cfg.c30StartYm = "2018-06";

% GIA options.
% "fixed": subtract GIA Stokes file directly.
% "rate" : subtract GIA Stokes rate*(decimal_year-reference_epoch).
cfg.giaMode = "fixed";
cfg.giaReferenceEpoch = 2002.0;

%% RUN
process_gfc_lowdeg_gia_ddk(cfg);

%% MAIN FUNCTION
function process_gfc_lowdeg_gia_ddk(cfg)
    validate_config(cfg);

    files = dir(fullfile(cfg.inputDir, "*.gfc"));
    if isempty(files)
        files = dir(fullfile(cfg.inputDir, "*.GFC"));
    end
    if isempty(files)
        error("No .gfc files found in inputDir: %s", cfg.inputDir);
    end
    [~, idx] = sort({files.name});
    files = files(idx);

    degree1Rows = read_tn13_degree1_rows(cfg.degree1File);
    slrRows = read_tn14_c20_c30_rows(cfg.c20c30File);
    [Cgia, Sgia] = read_gia_first_occurrence(cfg.giaFile, cfg.Lmax);
    ddkCache = containers.Map('KeyType', 'char', 'ValueType', 'any');

    counts = struct();
    counts.RAW_LD_GIA = 0;
    for k = 1:numel(cfg.ddkTypes)
        counts.(char(cfg.ddkTypes(k))) = 0;
    end

    manifest = struct();
    manifest.inputDir = char(cfg.inputDir);
    manifest.outputDir = char(cfg.outputDir);
    manifest.Lmax = cfg.Lmax;
    manifest.degree1File = char(cfg.degree1File);
    manifest.c20c30File = char(cfg.c20c30File);
    manifest.giaFile = char(cfg.giaFile);
    manifest.giaMode = char(cfg.giaMode);
    manifest.giaReferenceEpoch = cfg.giaReferenceEpoch;
    manifest.ddkDataDir = char(cfg.ddkDataDir);
    manifest.ddkTypes = cellstr(cfg.ddkTypes);
    manifest.files = struct([]);

    ensure_folder(cfg.outputDir);

    for i = 1:numel(files)
        src = fullfile(files(i).folder, files(i).name);
        ym = extract_ym_from_gfc_name(files(i).name);
        if strlength(ym) == 0
            error("Cannot infer YYYY-MM from filename: %s", files(i).name);
        end
        [year, month] = split_ym(ym);

        SH = read_gfc_local(src, cfg.Lmax);
        [SH, lowMeta] = apply_low_degree_local(SH, ym, year, month, degree1Rows, slrRows, cfg.c30StartYm);
        [SH, giaMeta] = apply_gia_local(SH, Cgia, Sgia, year, month, cfg.giaMode, cfg.giaReferenceEpoch);

        rec = struct();
        rec.source = src;
        rec.ym = char(ym);
        rec.lowDegree = lowMeta;
        rec.gia = giaMeta;
        rec.outputs = struct();

        if cfg.writeRawLowdegGia
            tag = "RAW_LD_GIA";
            outFile = fullfile(cfg.outputDir, tag, output_name(files(i).name, tag));
            if ~cfg.skipExisting || ~isfile(outFile)
                write_gfc_like_source(src, outFile, SH.C, SH.S, tag, cfg.Lmax);
                counts.RAW_LD_GIA = counts.RAW_LD_GIA + 1;
            end
            rec.outputs.RAW_LD_GIA = outFile;
        end

        for k = 1:numel(cfg.ddkTypes)
            ddkType = normalize_ddk(cfg.ddkTypes(k));
            tag = "LD_GIA_" + ddkType;
            outFile = fullfile(cfg.outputDir, ddkType, output_name(files(i).name, tag));
            if ~cfg.skipExisting || ~isfile(outFile)
                W = get_ddk_kernel(ddkType, cfg.ddkDataDir, ddkCache);
                [Cf, Sf] = filter_sh_ddk_local(W, SH.C, SH.S);
                write_gfc_like_source(src, outFile, Cf, Sf, tag, cfg.Lmax);
                counts.(char(ddkType)) = counts.(char(ddkType)) + 1;
            end
            rec.outputs.(char(ddkType)) = outFile;
        end

        manifest.files(i) = rec; %#ok<AGROW>
        fprintf("[%d/%d] %s processed\n", i, numel(files), files(i).name);
    end

    manifest.countsWritten = counts;
    manifestPath = fullfile(cfg.outputDir, "manifest_lowdeg_gia_ddk_matlab.json");
    write_text_atomic(manifestPath, jsonencode(manifest));

    fprintf("\nDone.\n");
    fprintf("RAW_LD_GIA: %d files\n", counts.RAW_LD_GIA);
    for k = 1:numel(cfg.ddkTypes)
        key = char(normalize_ddk(cfg.ddkTypes(k)));
        fprintf("%s: %d files\n", key, counts.(key));
    end
    fprintf("Manifest: %s\n", manifestPath);
end

%% HELPERS
function validate_config(cfg)
    must_exist_folder(cfg.inputDir, "inputDir");
    must_exist_folder(cfg.ddkDataDir, "ddkDataDir");
    must_exist_file(cfg.degree1File, "degree1File");
    must_exist_file(cfg.c20c30File, "c20c30File");
    must_exist_file(cfg.giaFile, "giaFile");
end

function must_exist_folder(pathValue, label)
    if ~isfolder(pathValue)
        error("%s does not exist or is not a folder: %s", label, pathValue);
    end
end

function must_exist_file(pathValue, label)
    if ~isfile(pathValue)
        error("%s does not exist or is not a file: %s", label, pathValue);
    end
end

function ensure_folder(folder)
    if ~isfolder(folder)
        mkdir(folder);
    end
end

function ddkType = normalize_ddk(raw)
    txt = upper(strtrim(string(raw)));
    if all(isstrprop(char(txt), 'digit'))
        txt = "DDK" + txt;
    elseif ~startsWith(txt, "DDK")
        txt = "DDK" + txt;
    end
    ok = any(txt == "DDK" + string(1:8));
    if ~ok
        error("Unsupported DDK type: %s", raw);
    end
    ddkType = txt;
end

function W = get_ddk_kernel(ddkType, ddkDataDir, cache)
    ddkType = normalize_ddk(ddkType);
    map = containers.Map( ...
        {'DDK1','DDK2','DDK3','DDK4','DDK5','DDK6','DDK7','DDK8'}, ...
        {'Wbd_2-120.a_1d14p_4','Wbd_2-120.a_1d13p_4','Wbd_2-120.a_1d12p_4', ...
         'Wbd_2-120.a_5d11p_4','Wbd_2-120.a_1d11p_4','Wbd_2-120.a_5d10p_4', ...
         'Wbd_2-120.a_1d10p_4','Wbd_2-120.a_5d9p_4'});
    file = fullfile(ddkDataDir, map(char(ddkType)));
    if ~isfile(file)
        error("DDK kernel not found: %s", file);
    end
    key = char(ddkType);
    if isKey(cache, key)
        W = cache(key);
    else
        W = read_ddk_bin_local(file);
        cache(key) = W;
    end
end

function W = read_ddk_bin_local(file)
    fid = fopen(file, 'r', 'ieee-le');
    if fid < 0; error("Cannot open DDK binary file: %s", file); end
    endian = fread(fid, 1, 'uint16');
    if isempty(endian)
        fclose(fid);
        error("Empty DDK binary file: %s", file);
    end
    if endian ~= 18754
        fclose(fid);
        fid = fopen(file, 'r', 'ieee-be');
        if fid < 0; error("Cannot reopen DDK binary file: %s", file); end
        endian = fread(fid, 1, 'uint16'); %#ok<NASGU>
    end
    cleanup = onCleanup(@() fclose(fid));

    verBytes = fread(fid, 6, 'uint8=>char')';
    version = ['BI', char(verBytes)];
    ver = str2double(version(5:8));
    type = strtrim(char(fread(fid, 8, 'uint8=>char')'));
    fread(fid, 80, 'uint8=>char');

    meta = fread(fid, 4, 'uint32');
    if numel(meta) < 4
        error("Invalid DDK binary header: %s", file);
    end
    nints = double(meta(1));
    ndbls = double(meta(2));
    nval1 = double(meta(3));
    nval2 = double(meta(4));

    if ver < 2.4
        pval = fread(fid, 2, 'uint32');
    else
        pval = fread(fid, 2, 'uint64');
    end
    pval1 = double(pval(1));
    pval2 = double(pval(2));

    if ver <= 2.1
        nvec = 0;
        nread = 0;
    else
        nvec = double(fread(fid, 1, 'int32'));
        nread = double(fread(fid, 1, 'int32'));
    end

    if ismember(type, {'BDSYMV0_', 'BDSYMV0', 'BDFULLV0', 'BDSYMVN_', 'BDFULLVN'})
        nblocks = double(fread(fid, 1, 'int32'));
    else
        nblocks = 0;
    end

    if nread > 0
        fread(fid, nread * 80, 'uint8=>char');
    end

    ints_d = strings(nints, 1);
    ints = zeros(nints, 1);
    for i = 1:nints
        ints_d(i) = string(strtrim(char(fread(fid, 24, 'uint8=>char')')));
    end
    if nints > 0
        if ver <= 2.4
            ints = double(fread(fid, nints, 'int32'));
        else
            ints = double(fread(fid, nints, 'int64'));
        end
    end

    if ndbls > 0
        fread(fid, ndbls * 24, 'uint8=>char');
        fread(fid, ndbls, 'double');
    end

    fread(fid, nval1 * 24, 'uint8=>char');

    if nblocks > 0
        blockind = double(fread(fid, nblocks, 'int32'));
    else
        blockind = [];
    end

    if ismember(type, {'BDFULLV0', 'BDFULLVN', 'FULLSQV0', 'FULLSQVN'})
        if ver > 2.2
            fread(fid, nval2 * 24, 'uint8=>char');
        end
    elseif strcmp(type, 'FULL2DVN')
        fread(fid, nval2 * 24, 'uint8=>char');
    end

    if nvec > 0
        fread(fid, nval1 * nvec, 'double');
    end

    pack1 = fread(fid, pval1 * pval2, 'double');
    if isempty(blockind) || isempty(pack1)
        error("Invalid DDK binary payload: %s", file);
    end

    W = struct();
    W.version = version;
    W.ver = ver;
    W.type = type;
    W.nints = nints;
    W.ints_d = ints_d;
    W.ints = ints;
    W.nblocks = nblocks;
    W.blockind = blockind;
    W.pack1 = pack1;
end

function [Cout, Sout] = filter_sh_ddk_local(W, C, S)
    if ~isfield(W, 'type') || ~strcmp(strtrim(W.type), 'BDFULLV0')
        error("Unsupported DDK matrix type: %s", string(W.type));
    end

    nmax = size(C, 1) - 1;
    nmaxfilt = nmax;
    nminfilt = 0;
    for i = 1:numel(W.ints_d)
        label = char(W.ints_d(i));
        if startsWith(label, 'Lmax')
            nmaxfilt = W.ints(i);
        elseif startsWith(label, 'Lmin')
            nminfilt = W.ints(i);
        end
    end
    nmaxout = min(nmax, nmaxfilt);

    Cout = zeros(size(C));
    Sout = zeros(size(S));
    lastBlockInd = 0;
    lastIndex = 0;

    for iblk = 1:W.nblocks
        order = floor(iblk / 2);
        if order > nmaxout
            break;
        end
        trig = floor(mod(iblk + double(iblk > 1), 2)); % 1 cosine, 0 sine
        sz = W.blockind(iblk) - lastBlockInd;
        if sz <= 0
            continue;
        end

        blockn = eye(nmaxfilt + 1 - order);
        nminblk = max(nminfilt, order);
        shift = nminblk - order + 1;
        block = reshape(W.pack1(lastIndex + 1:lastIndex + sz^2), sz, sz);
        blockn(shift:shift+sz-1, shift:shift+sz-1) = block;

        sub = blockn(1:nmaxout+1-order, 1:nmaxout+1-order);
        if trig
            Cout(order+1:nmaxout+1, order+1) = sub * C(order+1:nmaxout+1, order+1);
        else
            Sout(order+1:nmaxout+1, order+1) = sub * S(order+1:nmaxout+1, order+1);
        end

        lastBlockInd = W.blockind(iblk);
        lastIndex = lastIndex + sz^2;
    end
end

function SH = read_gfc_local(gfcFile, Lmax)
    fid = fopen(gfcFile, 'r');
    if fid < 0
        error("Cannot open GFC file: %s", gfcFile);
    end
    cleanup = onCleanup(@() fclose(fid));

    C = zeros(Lmax+1, Lmax+1);
    S = zeros(Lmax+1, Lmax+1);
    coeffCount = 0;

    while true
        ln = fgetl(fid);
        if ~ischar(ln)
            error("Invalid GFC file without end_of_head: %s", gfcFile);
        end
        if contains(lower(ln), "end_of_head")
            break;
        end
    end

    while true
        ln = fgetl(fid);
        if ~ischar(ln); break; end
        parts = regexp(strtrim(ln), '\s+', 'split');
        if numel(parts) < 5; continue; end
        tok = lower(parts{1});
        if ~(startsWith(tok, "gfc") || strcmp(tok, "grcof2")); continue; end
        l = round(parse_float(parts{2}));
        m = round(parse_float(parts{3}));
        cVal = parse_float(parts{4});
        sVal = parse_float(parts{5});
        if l >= 0 && m >= 0 && m <= l && l <= Lmax
            C(l+1, m+1) = cVal;
            S(l+1, m+1) = sVal;
            coeffCount = coeffCount + 1;
        end
    end

    SH = struct('C', C, 'S', S, 'Lmax', Lmax, 'coeffCount', coeffCount);
end

function value = parse_float(token)
    token = strrep(string(token), "D", "E");
    token = strrep(token, "d", "e");
    value = str2double(token);
end

function ym = extract_ym_from_gfc_name(name)
    token = regexp(char(name), '(?<!\d)(\d{4})[-_]?(\d{2})(?!\d)', 'tokens', 'once');
    if isempty(token)
        ym = "";
    else
        month = str2double(token{2});
        if month >= 1 && month <= 12
            ym = string(token{1}) + "-" + string(token{2});
        else
            ym = "";
        end
    end
end

function [year, month] = split_ym(ym)
    parts = split(string(ym), "-");
    year = str2double(parts(1));
    month = str2double(parts(2));
end

function out = output_name(inputName, tag)
    [~, stem, ext] = fileparts(char(inputName));
    if strlength(ext) == 0
        ext = ".gfc";
    end
    out = string(stem) + "_" + string(tag) + string(ext);
end

function rows = read_tn13_degree1_rows(file)
    rows = struct('startDate', {}, 'endDate', {}, 'ymMid', {}, 'C10', {}, 'C11', {}, 'S11', {});
    partial = struct('key', {}, 'startDate', {}, 'endDate', {}, 'ymMid', {}, 'C10', {}, 'C11', {}, 'S11', {});
    fid = fopen(file, 'r');
    if fid < 0; error("Cannot open TN-13 file: %s", file); end
    cleanup = onCleanup(@() fclose(fid));

    while true
        ln = fgetl(fid);
        if ~ischar(ln); break; end
        ln = strtrim(ln);
        if isempty(ln) || startsWith(ln, "#") || startsWith(ln, "%"); continue; end
        parts = regexp(ln, '\s+', 'split');

        if numel(parts) >= 9 && startsWith(upper(parts{1}), "GRCOF2")
            l = str2double(parts{2});
            m = str2double(parts{3});
            c = parse_float(parts{4});
            s = parse_float(parts{5});
            d0 = regexp(ln, '(\d{8})\.\d+\s+(\d{8})\.\d+\s*$', 'tokens', 'once');
            if isempty(d0) || l ~= 1 || ~(m == 0 || m == 1); continue; end
            t0 = datetime(d0{1}, InputFormat='yyyyMMdd');
            t1 = datetime(d0{2}, InputFormat='yyyyMMdd') - days(1);
            ymMid = ym_from_datetime(t0 + (t1 - t0) / 2);
            key = char(string(d0{1}) + "_" + string(d0{2}));
            idx = find(strcmp({partial.key}, key), 1);
            if isempty(idx)
                entry = struct('key', key, 'startDate', t0, 'endDate', t1, ...
                    'ymMid', ymMid, 'C10', NaN, 'C11', NaN, 'S11', NaN);
                partial(end+1) = entry; %#ok<AGROW>
                idx = numel(partial);
            end
            if m == 0
                partial(idx).C10 = c;
            else
                partial(idx).C11 = c;
                partial(idx).S11 = s;
            end
            continue;
        end

        nums = sscanf(ln, '%f');
        if numel(nums) >= 5
            yy = round(nums(1));
            mm = round(nums(2));
            if yy < 100
                if yy < 50; yy = yy + 2000; else; yy = yy + 1900; end
            end
            if mm >= 1 && mm <= 12
                t0 = datetime(yy, mm, 1);
                t1 = dateshift(t0, 'end', 'month');
                partial(end+1) = struct('key', sprintf('%04d-%02d', yy, mm), ...
                    'startDate', t0, 'endDate', t1, 'ymMid', string(sprintf('%04d-%02d', yy, mm)), ...
                    'C10', nums(3), 'C11', nums(4), 'S11', nums(5)); %#ok<AGROW>
            end
        end
    end

    for i = 1:numel(partial)
        if all(isfinite([partial(i).C10, partial(i).C11, partial(i).S11]))
            rows(end+1) = rmfield(partial(i), 'key'); %#ok<AGROW>
        end
    end
end

function ym = ym_from_datetime(dt)
    ym = string(sprintf('%04d-%02d', year(dt), month(dt)));
end

function rows = read_tn14_c20_c30_rows(file)
    rows = struct('mjdStart', {}, 'mjdEnd', {}, 'ym', {}, 'C20', {}, 'C30', {});
    fid = fopen(file, 'r');
    if fid < 0; error("Cannot open TN-14 file: %s", file); end
    cleanup = onCleanup(@() fclose(fid));
    while true
        ln = fgetl(fid);
        if ~ischar(ln); break; end
        ln = strtrim(ln);
        if isempty(ln) || startsWith(ln, "#") || startsWith(ln, "%"); continue; end
        nums = sscanf(ln, '%f');
        if numel(nums) < 9; continue; end
        row = struct();
        row.mjdStart = nums(1);
        row.C20 = nums(3);
        row.C30 = nums(6);
        row.mjdEnd = nums(9);
        row.ym = ym_from_mjd_window(row.mjdStart, row.mjdEnd);
        rows(end+1) = row; %#ok<AGROW>
    end
end

function ym = ym_from_mjd_window(mjd0, mjd1)
    t0 = datetime(1858, 11, 17) + days(mjd0);
    t1 = datetime(1858, 11, 17) + days(mjd1);
    mid = t0 + (t1 - t0) / 2;
    ym = string(sprintf('%04d-%02d', year(mid), month(mid)));
end

function [SH, meta] = apply_low_degree_local(SH, ym, yearValue, monthValue, degree1Rows, slrRows, c30StartYm)
    meta = struct('degree1', 'missing', 'degree1Match', '', 'degree1SourceYm', '', ...
        'C20', 'missing', 'C30', 'not_applied');

    deg1 = select_degree1_row(degree1Rows, yearValue, monthValue);
    if ~isempty(deg1)
        SH.C(2,1) = deg1.C10;
        SH.C(2,2) = deg1.C11;
        SH.S(2,2) = deg1.S11;
        meta.degree1 = 'replaced';
        meta.degree1Match = 'max_overlap';
        meta.degree1SourceYm = char(deg1.ymMid);
    end

    row = select_tn14_row(slrRows, yearValue, monthValue);
    if ~isempty(row) && isfinite(row.C20)
        SH.C(3,1) = row.C20;
        meta.C20 = 'replaced';
    end
    if ym_ge(ym, c30StartYm) && ~isempty(row) && isfinite(row.C30)
        SH.C(4,1) = row.C30;
        meta.C30 = 'replaced';
    end
end

function tf = ym_ge(a, b)
    [ay, am] = split_ym(a);
    [by, bm] = split_ym(b);
    tf = (ay > by) || (ay == by && am >= bm);
end

function row = select_degree1_row(rows, yearValue, monthValue)
    row = [];
    if isempty(rows); return; end
    dt0 = datetime(yearValue, monthValue, 1);
    dt1 = dateshift(dt0, 'end', 'month');
    best = -Inf;
    for i = 1:numel(rows)
        overlap = days(min(dt1, rows(i).endDate) - max(dt0, rows(i).startDate)) + 1;
        if overlap >= 0 && overlap > best
            best = overlap;
            row = rows(i);
        end
    end
end

function row = select_tn14_row(rows, yearValue, monthValue)
    row = [];
    if isempty(rows); return; end
    dt0 = datetime(yearValue, monthValue, 1);
    dt1 = dateshift(dt0, 'end', 'month');
    mjd0 = days(dt0 - datetime(1858, 11, 17));
    mjd1 = days(dt1 - datetime(1858, 11, 17));
    best = -Inf;
    for i = 1:numel(rows)
        overlap = min(mjd1, rows(i).mjdEnd) - max(mjd0, rows(i).mjdStart) + 1;
        if overlap >= 0 && overlap > best
            best = overlap;
            row = rows(i);
        end
    end
end

function [Cgia, Sgia] = read_gia_first_occurrence(file, Lmax)
    Cgia = zeros(Lmax+1, Lmax+1);
    Sgia = zeros(Lmax+1, Lmax+1);
    seen = false(Lmax+1, Lmax+1);

    fid = fopen(file, 'r');
    if fid < 0; error("Cannot open GIA file: %s", file); end
    cleanup = onCleanup(@() fclose(fid));

    while true
        ln = fgetl(fid);
        if ~ischar(ln); break; end
        nums = sscanf(ln, '%f');
        if numel(nums) < 4; continue; end
        l = round(nums(1));
        m = round(nums(2));
        if l < 0 || m < 0 || m > l || l > Lmax; continue; end
        if seen(l+1, m+1); continue; end
        Cgia(l+1, m+1) = nums(3);
        Sgia(l+1, m+1) = nums(4);
        seen(l+1, m+1) = true;
    end
end

function [SH, meta] = apply_gia_local(SH, Cgia, Sgia, yearValue, monthValue, giaMode, referenceEpoch)
    Lmax = min(SH.Lmax, size(Cgia, 1)-1);
    if strcmpi(string(giaMode), "rate")
        decimalYear = yearValue + (monthValue - 0.5) / 12.0;
        factor = decimalYear - referenceEpoch;
    else
        factor = 1.0;
    end
    SH.C(1:Lmax+1, 1:Lmax+1) = SH.C(1:Lmax+1, 1:Lmax+1) - Cgia(1:Lmax+1, 1:Lmax+1) * factor;
    SH.S(1:Lmax+1, 1:Lmax+1) = SH.S(1:Lmax+1, 1:Lmax+1) - Sgia(1:Lmax+1, 1:Lmax+1) * factor;
    meta = struct('mode', char(giaMode), 'factor', factor, 'Lmax', Lmax);
end

function write_gfc_like_source(sourceFile, targetFile, C, S, tag, Lmax)
    ensure_folder(fileparts(targetFile));
    tmpFile = targetFile + ".tmp";
    fin = fopen(sourceFile, 'r');
    if fin < 0; error("Cannot open source GFC: %s", sourceFile); end
    fout = fopen(tmpFile, 'w');
    if fout < 0
        fclose(fin);
        error("Cannot open output GFC: %s", tmpFile);
    end
    cleaner = onCleanup(@() cleanup_open_files(fin, fout));

    while true
        ln = fgetl(fin);
        if ~ischar(ln); break; end
        parts = regexp(strtrim(ln), '\s+', 'split');
        if numel(parts) >= 5 && startsWith(lower(parts{1}), "gfc")
            l = round(parse_float(parts{2}));
            m = round(parse_float(parts{3}));
            if l >= 0 && m >= 0 && m <= l && l <= Lmax
                if numel(parts) >= 7
                    sigC = parts{6};
                    sigS = parts{7};
                else
                    sigC = '0.0000E+00';
                    sigS = '0.0000E+00';
                end
                fprintf(fout, 'gfc %4d %4d % .12E % .12E %11s %11s\n', ...
                    l, m, C(l+1,m+1), S(l+1,m+1), sigC, sigS);
            else
                fprintf(fout, '%s\n', ln);
            end
            continue;
        end

        stripped = strtrim(ln);
        if startsWith(lower(stripped), "modelname")
            model = regexp(stripped, '^\S+\s+(.+)$', 'tokens', 'once');
            if isempty(model); model = {erase(string(get_filename(sourceFile)), ".gfc")}; end
            fprintf(fout, '   modelname                %s_%s\n', string(model{1}), string(tag));
        elseif startsWith(lower(stripped), "max_degree")
            fprintf(fout, '   max_degree               %d\n', Lmax);
        else
            fprintf(fout, '%s\n', ln);
        end
    end

    fclose(fin);
    fclose(fout);
    clear cleaner;
    movefile(tmpFile, targetFile, 'f');
end

function cleanup_open_files(fin, fout)
    if fin > 0; fclose(fin); end
    if fout > 0; fclose(fout); end
end

function name = get_filename(pathValue)
    [~, stem, ext] = fileparts(pathValue);
    name = string(stem) + string(ext);
end

function write_text_atomic(pathValue, text)
    ensure_folder(fileparts(pathValue));
    tmp = pathValue + ".tmp";
    fid = fopen(tmp, 'w');
    if fid < 0; error("Cannot write file: %s", tmp); end
    fprintf(fid, '%s', text);
    fclose(fid);
    movefile(tmp, pathValue, 'f');
end
