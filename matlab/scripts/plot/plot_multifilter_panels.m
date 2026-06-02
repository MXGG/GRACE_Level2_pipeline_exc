% Multi-filter spatial panels for comparison (global maps)
% Generates per-filter monthly panels + comparison grids.
clear; clc;
thisFile = mfilename('fullpath');
groupDir = fileparts(thisFile);
scriptsDir = fileparts(groupDir);
matlabRoot = fileparts(scriptsDir);
root = fileparts(matlabRoot);
addpath(genpath(fullfile(matlabRoot,'src')));

runRoot = fullfile(root,'output','local','global_nogia_mascon_undo','local');
% runRoot = fullfile(root,'output','local','adaptive_nogia_mascon_undo','local');

stackDir = fullfile(runRoot,'stacks');
plotDir = fullfile(runRoot,'plots');
if ~exist(plotDir,'dir'); mkdir(plotDir); end

% ---- Settings ----
randSeed = 1;
numMonths = 4;
monthIdx = [];                  % Optional: manual month indices
caxis_month_cm = [-30 30];      % unify EWH colorbar to +/- 30 cm
colormap_month = 'redblue';     % 'jet' or 'redblue'
proj = 'robinson';

style = struct( ...
    'proj', proj, ...
    'grid_style', 'dotted', ...
    'grid_color', [0.6 0.6 0.6], ...
    'coast_res', 'high', ...
    'coast_linewidth', 0.7, ...
    'font', 'Times New Roman', ...
    'fontsize', 8);

% Filters to include (skip missing)
allTags = {'P4M6_FAN','DDK','HSAF','Mascon'};

avail = collect_stacks(stackDir, allTags);

% Fallback: load Mascon netCDF directly if missing
if ~any(strcmpi({avail.tag}, 'Mascon'))
    masconFile = fullfile(root, 'data', 'Reference', 'Mascon', 'CSR_GRACE_GRACE-FO_RL06_Mascons_all-corrections_v02.nc');
    if isfile(masconFile)
        StackM = build_mascon_stack(masconFile);
        if ~isempty(StackM)
            avail(end+1).tag = 'Mascon'; %#ok<AGROW>
            avail(end).label = 'Mascon';
            avail(end).file = masconFile;
            avail(end).stack = StackM;
        end
    end
end

if isempty(avail)
    error('No stack files found in %s', stackDir);
end

% Load stacks (or use prebuilt)
Stacks = cell(numel(avail),1);
for i = 1:numel(avail)
    if isfield(avail(i),'stack') && ~isempty(avail(i).stack)
        Stacks{i} = avail(i).stack;
    else
        S = load(avail(i).file);
        Stacks{i} = S.Stack;
    end
end

% Shared lon/lat/t from non-Mascon stack when possible
idxBase = find(~strcmpi({avail.tag}, 'Mascon'), 1);
if isempty(idxBase); idxBase = 1; end
Stack0 = Stacks{idxBase};
lonVec = Stack0.lon; latVec = Stack0.lat;

% Use time from base stack (or Mascon if only reference exists)
t = Stack0.t;
if iscell(t); t = datetime(t,'InputFormat','yyyy-MM'); end
Nt = numel(t);

rng(randSeed);
if isempty(monthIdx)
    numMonths = min(numMonths, Nt);
    monthIdx = sort(randperm(Nt, numMonths));
else
    numMonths = numel(monthIdx);
end
monthLabels = cellstr(datestr(t(monthIdx), 'yyyy-mm'));

% Precompute monthly slices + indicators
mapsMonthly = cell(numel(avail), numMonths);
meanMaps = cell(numel(avail), 1);
trendMaps = cell(numel(avail), 1);
ampMaps = cell(numel(avail), 1);

for i = 1:numel(avail)
    Stack = Stacks{i};
    ewh = align_stack_to_grid(Stack, lonVec, latVec); % mm
    for k = 1:numMonths
        mapsMonthly{i,k} = ewh(:,:,monthIdx(k)) / 10; % mm -> cm
    end
    meanMaps{i} = mean(ewh, 3, 'omitnan') / 10; % cm
    [trendMap, ampMap] = trend_amp_maps_local(ewh, t); % mm/yr, mm
    trendMaps{i} = trendMap;
    ampMaps{i} = ampMap;
    clear ewh;
end

% Auto caxis for indicators across all filters
meanVals = cat(1, meanMaps{:});
trendVals = cat(1, trendMaps{:});
ampVals = cat(1, ampMaps{:});
meanVals = meanVals(isfinite(meanVals));
trendVals = trendVals(isfinite(trendVals));
ampVals = ampVals(isfinite(ampVals));

caxis_mean_cm = [-30 30];
caxis_trend_mm = prc_range(trendVals, [2 98], [-5 5]);
caxis_amp_mm = prc_range(ampVals, [2 98], [0 15]);

% ---- Per-filter monthly panels ----
for i = 1:numel(avail)
    tagLabel = avail(i).label;
    fig = figure('Color','w','Position',[100 100 1400 700]);
    tlo = tiledlayout(2, ceil(numMonths/2), 'TileSpacing','compact','Padding','compact');
    for k = 1:numMonths
        ax = nexttile(tlo);
        map = mapsMonthly{i,k};
        opts = merge_opts(style, struct( ...
            'ax', ax, ...
            'title', sprintf('%s %s', tagLabel, monthLabels{k}), ...
            'caxis', caxis_month_cm, ...
            'cbar_label', 'EWH (cm)', ...
            'colormap', colormap_month, ...
            'show_colorbar', false));
        plot_map_global(map, lonVec, latVec, opts);
    end
    cb = colorbar;
    cb.Layout.Tile = 'east';
    cb.Label.String = 'EWH (cm)';
    cb.Label.FontName = style.font;
    colormap(fig, get_cmap(colormap_month));
    outPng = fullfile(plotDir, sprintf('panel_%s.png', safe_name(tagLabel)));
    saveas(fig, outPng);
    close(fig);
end

% ---- Combined comparison grid (months) ----
fig = figure('Color','w','Position',[50 50 1600 900]);
rows = numel(avail);
cols = numMonths;
tlo = tiledlayout(rows, cols, 'TileSpacing','compact','Padding','compact');
for r = 1:rows
    tagLabel = avail(r).label;
    for c = 1:cols
        ax = nexttile(tlo);
        map = mapsMonthly{r,c};
        titleStr = '';
        if r == 1
            titleStr = monthLabels{c};
        end
        if c == 1
            if isempty(titleStr)
                titleStr = tagLabel;
            else
                titleStr = sprintf('%s\n%s', tagLabel, titleStr);
            end
        end
        opts = merge_opts(style, struct( ...
            'ax', ax, ...
            'title', titleStr, ...
            'caxis', caxis_month_cm, ...
            'cbar_label', 'EWH (cm)', ...
            'colormap', colormap_month, ...
            'show_colorbar', false));
        plot_map_global(map, lonVec, latVec, opts);
    end
end
cb = colorbar;
cb.Layout.Tile = 'east';
cb.Label.String = 'EWH (cm)';
cb.Label.FontName = style.font;
colormap(fig, get_cmap(colormap_month));

outPng = fullfile(plotDir, 'compare_filters_months.png');
saveas(fig, outPng);
close(fig);

% ---- Indicator grid (mean / trend / amp) ----
indicatorNames = {'Mean (RMS)', 'Trend', 'Amplitude'};
indicatorUnits = {'EWH (cm)', 'mm/yr', 'mm'};
indicatorCaxis = {caxis_mean_cm, caxis_trend_mm, caxis_amp_mm};
indicatorCmap = {'redblue', 'redblue', 'redblue'};
indicatorMaps = {meanMaps, trendMaps, ampMaps};

fig = figure('Color','w','Position',[50 50 1800 900]);
rows = numel(avail);
cols = numel(indicatorNames);
tlo = tiledlayout(rows, cols, 'TileSpacing','compact','Padding','compact');
for r = 1:rows
    tagLabel = avail(r).label;
    for c = 1:cols
        ax = nexttile(tlo);
        map = indicatorMaps{c}{r};
        titleStr = '';
        if r == 1
            titleStr = indicatorNames{c};
        end
        if c == 1
            if isempty(titleStr)
                titleStr = tagLabel;
            else
                titleStr = sprintf('%s\n%s', tagLabel, titleStr);
            end
        end
        opts = merge_opts(style, struct( ...
            'ax', ax, ...
            'title', titleStr, ...
            'caxis', indicatorCaxis{c}, ...
            'cbar_label', indicatorUnits{c}, ...
            'colormap', indicatorCmap{c}, ...
            'show_colorbar', false));
        plot_map_global(map, lonVec, latVec, opts);
        if r == rows
            cb = colorbar(ax);
            cb.Location = 'eastoutside';
            cb.Label.String = indicatorUnits{c};
            cb.Label.FontName = style.font;
            colormap(ax, get_cmap(indicatorCmap{c}));
        end
    end
end

outPng = fullfile(plotDir, 'compare_filters_indicators.png');
saveas(fig, outPng);
close(fig);

fprintf('Panels written to: %s\n', plotDir);

% ---- helpers ----
function cmap = get_cmap(name)
    if nargin < 1 || isempty(name); name = 'jet'; end
    switch lower(name)
        case 'jet'
            cmap = jet(256);
        case {'redblue','bwr','rdblu'}
            n = 256; n2 = floor(n/2);
            r = [(0:n2-1)'/max(n2-1,1); ones(n-n2,1)];
            g = [(0:n2-1)'/max(n2-1,1); (n-n2-1:-1:0)'/max(n-n2-1,1)];
            b = [ones(n2,1); (n-n2-1:-1:0)'/max(n-n2-1,1)];
            cmap = [r g b];
        otherwise
            try
                cmap = feval(name, 256);
            catch
                cmap = jet(256);
            end
    end
end

function out = merge_opts(base, extra)
    out = base;
    if isempty(extra); return; end
    f = fieldnames(extra);
    for i = 1:numel(f)
        out.(f{i}) = extra.(f{i});
    end
end

function name = safe_name(s)
    name = regexprep(s, '[^A-Za-z0-9_\-]+', '_');
end

function valRange = prc_range(vals, prc, fallback)
    if isempty(vals)
        valRange = fallback;
        return;
    end
    pr = prctile(vals, prc);
    if pr(1) == pr(2)
        pr = pr + [-1 1] * max(abs(pr(1)), 1e-6);
    end
    valRange = pr;
end

function [trendMap, ampMap] = trend_amp_maps_local(grid, t)
    nLon = size(grid,1);
    nLat = size(grid,2);
    Nt = size(grid,3);

    tNum = datenum(t);
    tYear = (tNum - tNum(1)) / 365.25;
    tYear = tYear(:);

    X = [ones(Nt,1), tYear, sin(2*pi*tYear), cos(2*pi*tYear)];

    Y = reshape(grid, nLon*nLat, Nt);
    trendMap = nan(nLon*nLat, 1);
    ampMap = nan(nLon*nLat, 1);
    for i = 1:size(Y,1)
        yi = Y(i, :).';
        good = isfinite(yi);
        if sum(good) < 4
            continue;
        end
        Xi = X(good, :);
        Bi = Xi \ yi(good);
        trendMap(i) = Bi(2);
        ampMap(i) = sqrt(Bi(3).^2 + Bi(4).^2);
    end
    trendMap = reshape(trendMap, nLon, nLat);
    ampMap = reshape(ampMap, nLon, nLat);
end

function avail = collect_stacks(stackDir, allTags)
    avail = struct('tag',{},'label',{},'file',{},'stack',{});
    for i = 1:numel(allTags)
        tag = allTags{i};
        files = dir(fullfile(stackDir, sprintf('%s_stack_*.mat', tag)));
        if isempty(files)
            continue;
        end
        if strcmpi(tag, 'HSAF')
            for k = 1:numel(files)
                fp = fullfile(files(k).folder, files(k).name);
                S = load(fp, 'Stack');
                label = display_label(tag, S.Stack);
                avail(end+1).tag = tag; %#ok<AGROW>
                avail(end).label = label;
                avail(end).file = fp;
                avail(end).stack = [];
            end
        else
            [~, idx] = max([files.datenum]);
            fp = fullfile(files(idx).folder, files(idx).name);
            S = load(fp, 'Stack');
            label = display_label(tag, S.Stack);
            avail(end+1).tag = tag; %#ok<AGROW>
            avail(end).label = label;
            avail(end).file = fp;
            avail(end).stack = [];
        end
    end
end

function label = display_label(tag, Stack)
    label = tag;
    switch upper(tag)
        case 'P4M6_FAN'
            label = 'FAN+P4M6';
    end
    if strcmpi(tag, 'HSAF')
        label = 'HSAF';
    end
end

function ewh = align_stack_to_grid(Stack, lonVec, latVec)
    ewh = double(Stack.ewh);
    lonS = Stack.lon(:); latS = Stack.lat(:);
    if isequal(size(ewh,1), numel(latS)) && isequal(size(ewh,2), numel(lonS))
        ewh = permute(ewh, [2 1 3]);
    end
    if isequal(lonS, lonVec(:)) && isequal(latS, latVec(:))
        return;
    end
    ewh = resample_stack(ewh, lonS, latS, lonVec, latVec);
end

function Eout = resample_stack(E, lonRef, latRef, lonTar, latTar)
    lonRef = lonRef(:);
    latRef = latRef(:);
    lonRef = mod(lonRef + 180, 360) - 180;
    [lonRef, iLon] = sort(lonRef);
    [latRef, iLat] = sort(latRef);
    if size(E,1) == numel(lonRef)
        E = E(iLon, :, :);
    elseif size(E,2) == numel(lonRef)
        E = E(:, iLon, :);
    end
    if size(E,2) == numel(latRef)
        E = E(:, iLat, :);
    elseif size(E,1) == numel(latRef)
        E = E(iLat, :, :);
    end

    [LonQ, LatQ] = ndgrid(lonTar(:), latTar(:));
    Eout = nan(numel(lonTar), numel(latTar), size(E,3));
    F = griddedInterpolant({lonRef, latRef}, E(:,:,1), 'linear', 'nearest');
    for k = 1:size(E,3)
        F.Values = E(:,:,k);
        Eout(:,:,k) = F(LonQ, LatQ);
    end
end

function Stack = build_mascon_stack(fp)
    Stack = [];
    try
        info = ncinfo(fp);
        varName = pick_reference_variable(info);
        if isempty(varName)
            return;
        end
        data = ncread(fp, varName);
        lon = ncread(fp, 'lon');
        lat = ncread(fp, 'lat');
        timeInfo = ncinfo(fp, 'time');
        timeVals = ncread(fp, 'time');
        dtVec = nc_time_to_datetime(timeInfo, timeVals);
    catch
        return;
    end

    sz = size(data);
    nLon = numel(lon); nLat = numel(lat); nT = numel(dtVec);
    if numel(sz) == 3
        if sz(1) == nLon && sz(2) == nLat && sz(3) == nT
            E = data;
        elseif sz(1) == nLat && sz(2) == nLon && sz(3) == nT
            E = permute(data, [2 1 3]);
        elseif sz(1) == nT && sz(2) == nLon && sz(3) == nLat
            E = permute(data, [2 3 1]);
        elseif sz(1) == nT && sz(2) == nLat && sz(3) == nLon
            E = permute(data, [3 2 1]);
        else
            return;
        end
    else
        return;
    end

    lon = mod(lon + 180, 360) - 180;
    [lon, iLon] = sort(lon(:));
    [lat, iLat] = sort(lat(:));
    E = E(iLon, iLat, :);

    Stack = struct();
    Stack.tag = 'Mascon';
    Stack.lon = lon(:).';
    Stack.lat = lat(:).';
    Stack.t = cellstr(datestr(dtVec, 'yyyy-mm'));
    Stack.ok = true(numel(dtVec),1);
    Stack.ewh = E;
end

function varName = pick_reference_variable(info)
    varName = '';
    if isempty(info.Variables)
        return;
    end
    names = lower({info.Variables.Name});
    candidates = {'lwe_thickness','mascon','ewh','lwe','grid','data','field'};
    for i = 1:numel(candidates)
        matches = find(contains(names, candidates{i}));
        if ~isempty(matches)
            varName = info.Variables(matches(1)).Name;
            return;
        end
    end
    for i = 1:numel(info.Variables)
        if numel(info.Variables(i).Size) < 2
            continue;
        end
        nm = names{i};
        if any(contains(nm, {'lon','lat','latitude','longitude','time','month','day'}))
            continue;
        end
        varName = info.Variables(i).Name;
        return;
    end
end

