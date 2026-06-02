% TRMM 3B43 preprocessing (1deg) + lag analysis vs GRACE filters
% Outputs: time series figure + lag metrics CSV for 4 basins (2004-2013).
clear; clc;

thisFile = mfilename('fullpath');
groupDir = fileparts(thisFile);
scriptsDir = fileparts(groupDir);
matlabRoot = fileparts(scriptsDir);
root = fileparts(matlabRoot);
addpath(genpath(fullfile(matlabRoot,'src')));

outDir = fullfile(root,'output','local','trmm');
if ~exist(outDir,'dir'); mkdir(outDir); end

% --- Load reference stack for grid/time (HSAF)
Sref = load(fullfile(root,'output','local','stacks','HSAF_stack_200204-201706.mat'));
StackRef = Sref.Stack;
lonVec = StackRef.lon(:);
latVec = StackRef.lat(:);
tStr = StackRef.t(:);
t = datetime(tStr,'InputFormat','yyyy-MM');
Nt = numel(t);

% --- Basin selection
shp = fullfile(root,'data','Boundary','LargeBasin.shp');
Sbasin = shaperead(shp,'UseGeoCoords',true);
basinKeys = {'AMAZONAS','MISSISSIPPI RIVER','YENISEI','LAKE CHAD'};
basinAlt = {'AMAZONAS','MISSISSIPPI RIVER','YENISEI','NIGER'};
basins = repmat(struct(),1,numel(basinKeys));
basinNames = strings(1,numel(basinKeys));
for i = 1:numel(basinKeys)
    B = pick_basin(Sbasin, basinKeys{i});
    if isempty(B)
        B = pick_basin(Sbasin, basinAlt{i});
    end
    basins(i).B = B;
    basinNames(i) = string(strtrim(B(1).whymap_riv));
end
nBasins = numel(basins);

% --- Basin masks on GRACE grid
masks = false(numel(lonVec), numel(latVec), nBasins);
for i = 1:nBasins
    masks(:,:,i) = basin_make_mask(lonVec, latVec, basins(i).B);
end

% --- Load stacks for filters (nLon x nLat x Nt)
stacks = struct();
stacks.HSAF = load_stack(fullfile(root,'output','local','stacks','HSAF_stack_200204-201706.mat'), lonVec, latVec);
stacks.GAUSS = load_stack(fullfile(root,'output','local','stacks','GAUSS_stack_200204-201706.mat'), lonVec, latVec);
stacks.DDK = load_stack(fullfile(root,'output','local','stacks','DDK_stack_200204-201706.mat'), lonVec, latVec);
stacks.P4M6_GAUSS = load_stack(fullfile(root,'output','local','stacks','P4M6_GAUSS_stack_200204-201706.mat'), lonVec, latVec);
% FAN stacks are in latest remote run
stacks.FAN = load_stack(fullfile(root,'output','remote','183543','stacks','FAN_stack_200204-201706.mat'), lonVec, latVec);
stacks.P4M6_FAN = load_stack(fullfile(root,'output','remote','183543','stacks','P4M6_FAN_stack_200204-201706.mat'), lonVec, latVec);

methodNames = {'GAUSS','FAN','P4M6_GAUSS','P4M6_FAN','DDK','HSAF'};

% --- TRMM config (3B43)
trmmDir = fullfile(root,'data','Hydro','TRMM','3B43');
lon0 = -180 + 0.25/2 : 0.25 : 180 - 0.25/2;
lat0 = -50  + 0.25/2 : 0.25 : 50  - 0.25/2;
lon1 = -179.5 : 1 : 179.5;
lat1 = -49.5  : 1 : 49.5;
[LONQ, LATQ] = ndgrid(wrapTo180(lonVec), latVec);

% --- Allocate TRMM basin series
trmm = nan(Nt, nBasins);

for k = 1:Nt
    y = year(t(k)); m = month(t(k));
    if y < 2004 || y > 2013
        continue;
    end
    if (y < 2010) || (y == 2010 && m <= 9)
        tag = '7A';
    else
        tag = '7';
    end
    f = fullfile(trmmDir, sprintf('3B43.%04d%02d01.%s.HDF', y, m, tag));
    if ~isfile(f); continue; end

    P = double(hdfread(f,'precipitation')); % mm/hr
    P(P < -9990) = NaN;
    P = P * 24 * eomday(y,m); % mm/month

    % Aggregate 0.25 deg to 1 deg (block mean)
    if numel(lon0) ~= 1440 || numel(lat0) ~= 400
        error('Unexpected TRMM grid size.');
    end
    P = reshape(P, 4, 360, 4, 100);
    P1 = squeeze(nanmean(nanmean(P,1),3)); % [360 x 100]

    % Interpolate to GRACE grid for basin averaging
    F = griddedInterpolant({lon1, lat1}, P1, 'linear', 'none');
    Gp = F(LONQ, LATQ);

    for i = 1:nBasins
        trmm(k,i) = basin_mean_one(Gp, masks(:,:,i), latVec);
    end
end

% --- GRACE basin series for all methods
basin_ts = struct();
for m = 1:numel(methodNames)
    key = methodNames{m};
    G = stacks.(key);
    ts = nan(Nt, nBasins);
    for i = 1:nBasins
        ts(:,i) = basin_mean_ts(G, masks(:,:,i), latVec, true);
    end
    basin_ts.(key) = ts;
end

% --- Define window for 2004-2013
idxWin = t >= datetime(2004,1,1) & t <= datetime(2013,12,1);
tWin = t(idxWin);

% --- Convert to anomalies over 2004-2013
trmmA = trmm - mean(trmm(idxWin,:), 'omitnan');

basin_tsa = struct();
for m = 1:numel(methodNames)
    key = methodNames{m};
    tmp = basin_ts.(key);
    basin_tsa.(key) = tmp - mean(tmp(idxWin,:), 'omitnan');
end

% --- Lag analysis (TRMM leads GRACE by 0-2 months)
lags = 0:2;
bestLag = zeros(numel(methodNames), nBasins);
bestR = nan(numel(methodNames), nBasins);
bestRMSE = nan(numel(methodNames), nBasins);

for i = 1:nBasins
    p = trmmA(idxWin,i);
    for m = 1:numel(methodNames)
        key = methodNames{m};
        x = basin_tsa.(key)(idxWin,i);
        bestR0 = -Inf;
        bestL0 = 0;
        bestE0 = NaN;
        for L = lags
            if numel(x) <= L+2
                continue;
            end
            xx = x(1+L:end);
            yy = p(1:end-L);
            if all(isnan(xx)) || all(isnan(yy))
                continue;
            end
            xs = (xx - mean(xx,'omitnan')) ./ std(xx,[],'omitnan');
            ys = (yy - mean(yy,'omitnan')) ./ std(yy,[],'omitnan');
            r = corr(xs, ys, 'Rows','complete');
            e = sqrt(mean((xs - ys).^2, 'omitnan'));
            if r > bestR0
                bestR0 = r; bestL0 = L; bestE0 = e;
            end
        end
        bestLag(m,i) = bestL0;
        bestR(m,i) = bestR0;
        bestRMSE(m,i) = bestE0;
    end
end

% --- Plot time series comparison (4 basins)
fig = figure('Color','w','Position',[100 100 1400 800]);
colors = lines(numel(methodNames));
idxH = find(strcmp(methodNames,'HSAF'),1);
for i = 1:nBasins
    subplot(2,2,i);
    hold on;
    for m = 1:numel(methodNames)
        key = methodNames{m};
        plot(tWin, basin_tsa.(key)(idxWin,i), 'LineWidth', 1.0, 'Color', colors(m,:));
    end
    % TRMM (scaled, lagged to HSAF best lag)
    L = bestLag(idxH,i);
    p = trmmA(idxWin,i);
    pLag = [nan(L,1); p(1:end-L)];
    scale = std(basin_tsa.HSAF(idxWin,i),[],'omitnan') / std(p,'omitnan');
    plot(tWin, pLag * scale, 'k--', 'LineWidth', 1.2);

    grid on;
    title(basinNames(i));
    ylabel('mm (scaled for TRMM)');
    if i == 1
        legend([methodNames, {'TRMM (lagged)'}], 'Location','best');
    end
end
saveas(fig, fullfile(outDir,'ts_trmm_compare_filters_4basins.png'));
close(fig);

% --- Save metrics
T = table();
for i = 1:nBasins
    for m = 1:numel(methodNames)
        row = table(basinNames(i), string(methodNames{m}), bestLag(m,i), bestR(m,i), bestRMSE(m,i), ...
            'VariableNames', {'Basin','Method','BestLag','Corr','RMSE'});
        T = [T; row]; %#ok<AGROW>
    end
end
writetable(T, fullfile(outDir,'trmm_lag_metrics_2004_2013.csv'));
save(fullfile(outDir,'trmm_lag_metrics_2004_2013.mat'), ...
    't','tWin','basinNames','methodNames','trmmA','basin_tsa','bestLag','bestR','bestRMSE');

fprintf('Outputs saved to: %s\n', outDir);

% ---- helpers ----
function B = pick_basin(S, key)
    names = string({S.whymap_riv});
    idx = find(strcmpi(strtrim(names), key), 1);
    if isempty(idx)
        idx = find(contains(upper(names), upper(key)), 1);
    end
    if isempty(idx)
        B = struct([]);
    else
        B = S(idx);
    end
end

function G = load_stack(filePath, lonVec, latVec)
    S = load(filePath);
    Stack = S.Stack;
    data = double(Stack.ewh);
    % Ensure [nLon x nLat x Nt]
    if size(data,1) == numel(lonVec) && size(data,2) == numel(latVec)
        G = data;
    elseif size(data,1) == numel(latVec) && size(data,2) == numel(lonVec)
        G = permute(data, [2 1 3]);
    else
        error('Unexpected stack size in %s', filePath);
    end
end

function m = basin_mean_one(G, mask, latVec)
    if all(isnan(G(:))) || nnz(mask)==0
        m = NaN; return;
    end
    w = cosd(latVec(:))';
    W = mask .* w;
    num = nansum(G(:) .* W(:));
    den = nansum(W(:));
    m = num / den;
end

