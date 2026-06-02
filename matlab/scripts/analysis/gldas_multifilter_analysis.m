% Multi-filter GRACE vs GLDAS comparison (basins + maps + components)
% Outputs: time series comparison, seasonal/interannual comparison, basin maps.
clear; clc;

thisFile = mfilename('fullpath');
groupDir = fileparts(thisFile);
scriptsDir = fileparts(groupDir);
matlabRoot = fileparts(scriptsDir);
root = fileparts(matlabRoot);
addpath(genpath(fullfile(matlabRoot,'src')));

outDir = fullfile(root,'output','local','gldas_ext');
if ~exist(outDir,'dir'); mkdir(outDir); end

% --- Load reference stack for grid/time (HSAF)
Sref = load(fullfile(root,'output','local','stacks','HSAF_stack_200204-201706.mat'));
StackRef = Sref.Stack;
lonVec = StackRef.lon(:);
latVec = StackRef.lat(:);
tStr = StackRef.t(:);
t = datetime(tStr,'InputFormat','yyyy-MM');
Nt = numel(t);

% --- Basin selection (fallback if missing)
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

% --- Basin masks
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

% --- GLDAS config
gldasDir = fullfile(root,'data','GLDAS');
filePattern = 'GLDAS_NOAH10_M.A%04d%02d.021.nc4';
soilVars = {'SoilMoi0_10cm_inst','SoilMoi10_40cm_inst','SoilMoi40_100cm_inst','SoilMoi100_200cm_inst'};
snowVar = 'SWE_inst';
canopyVar = 'CanopInt_inst';

% Read GLDAS grid from first GRACE month
f0 = fullfile(gldasDir, sprintf(filePattern, year(t(1)), month(t(1))));
lonG = ncread(f0,'lon'); lonG = lonG(:);
latG = ncread(f0,'lat'); latG = latG(:);
[LONQ, LATQ] = ndgrid(wrapTo180(lonVec), latVec);

% --- Allocate GLDAS basin series
gldas_sms = nan(Nt, nBasins);
gldas_swe = nan(Nt, nBasins);
gldas_cws = nan(Nt, nBasins);
gldas_tws = nan(Nt, nBasins);

% For maps
mapMonths = [datetime(2007,10,1), datetime(2010,8,1)];
mapIdx = arrayfun(@(d)find(year(t)==year(d)&month(t)==month(d),1), mapMonths);
gldas_map = cell(numel(mapMonths),1);

sumMap = zeros(numel(lonVec), numel(latVec));
cntMap = zeros(numel(lonVec), numel(latVec));

for k = 1:Nt
    y = year(t(k)); m = month(t(k));
    f = fullfile(gldasDir, sprintf(filePattern, y, m));
    if ~isfile(f); continue; end

    % read components (kg/m^2 == mm)
    sms = 0;
    for sv = 1:numel(soilVars)
        sms = sms + double(ncread(f, soilVars{sv}));
    end
    swe = double(ncread(f, snowVar));
    cws = double(ncread(f, canopyVar));

    % align to [nLon x nLat]
    if size(sms,1) == numel(latG) && size(sms,2) == numel(lonG)
        sms = sms.';
        swe = swe.';
        cws = cws.';
    end

    tws = sms + swe + cws;

    % interpolate to GRACE grid
    F = griddedInterpolant({lonG, latG}, tws, 'linear', 'none');
    Gtws = F(LONQ, LATQ);
    F.Values = sms; Gsms = F(LONQ, LATQ);
    F.Values = swe; Gswe = F(LONQ, LATQ);
    F.Values = cws; Gcws = F(LONQ, LATQ);

    % basin means
    for i = 1:nBasins
        gldas_tws(k,i) = basin_mean_one(Gtws, masks(:,:,i), latVec);
        gldas_sms(k,i) = basin_mean_one(Gsms, masks(:,:,i), latVec);
        gldas_swe(k,i) = basin_mean_one(Gswe, masks(:,:,i), latVec);
        gldas_cws(k,i) = basin_mean_one(Gcws, masks(:,:,i), latVec);
    end

    valid = ~isnan(Gtws);
    sumMap(valid) = sumMap(valid) + Gtws(valid);
    cntMap(valid) = cntMap(valid) + 1;

    midx = find(k == mapIdx, 1);
    if ~isempty(midx)
        gldas_map{midx} = Gtws;
    end
end

meanMap = sumMap ./ max(cntMap,1);

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
gldas_twsA = gldas_tws - mean(gldas_tws(idxWin,:), 'omitnan');
gldas_smsA = gldas_sms - mean(gldas_sms(idxWin,:), 'omitnan');
gldas_sweA = gldas_swe - mean(gldas_swe(idxWin,:), 'omitnan');
gldas_cwsA = gldas_cws - mean(gldas_cws(idxWin,:), 'omitnan');

basin_tsa = struct();
for m = 1:numel(methodNames)
    key = methodNames{m};
    tmp = basin_ts.(key);
    basin_tsa.(key) = tmp - mean(tmp(idxWin,:), 'omitnan');
end

% --- GWS from GRACE (HSAF) minus GLDAS components
gwsA = basin_tsa.HSAF - (gldas_smsA + gldas_sweA + gldas_cwsA);

% --- Plot time series comparison (4 basins)
fig = figure('Color','w','Position',[100 100 1400 800]);
colors = lines(numel(methodNames));
for i = 1:nBasins
    subplot(2,2,i);
    hold on;
    for m = 1:numel(methodNames)
        key = methodNames{m};
        plot(tWin, basin_tsa.(key)(idxWin,i), 'LineWidth', 1.0, 'Color', colors(m,:));
    end
    plot(tWin, gldas_twsA(idxWin,i), 'k--', 'LineWidth', 1.2);
    grid on;
    title(basinNames(i));
    ylabel('mm');
    if i == 1
        legend([methodNames, {'GLDAS'}], 'Location','best');
    end
end
saveas(fig, fullfile(outDir,'ts_compare_filters_4basins.png'));
close(fig);

% --- Seasonal / interannual comparison (use Amazon basin)
ib = 1; % Amazon basin
tsH = basin_tsa.HSAF(:,ib);
Fit = basin_fit_seasonal_trend(tsH, t);
trend = fit_trend(tsH, t, Fit);
seasonal = Fit.yfit - trend;
interannual = tsH - seasonal;

fig = figure('Color','w','Position',[100 100 1200 700]);
subplot(2,1,1);
plot(tWin, seasonal(idxWin), 'k-', 'LineWidth', 1.2); hold on;
plot(tWin, gldas_sweA(idxWin,ib), 'c--', 'LineWidth', 1.0);
plot(tWin, gldas_smsA(idxWin,ib), 'b--', 'LineWidth', 1.0);
plot(tWin, gldas_cwsA(idxWin,ib), 'm--', 'LineWidth', 1.0);
grid on; ylabel('mm');
title(sprintf('%s Seasonal vs GLDAS components', basinNames(ib)));
legend({'GRACE Seasonal','SWE','SMS','CWS'}, 'Location','best');

subplot(2,1,2);
plot(tWin, interannual(idxWin), 'k-', 'LineWidth', 1.2); hold on;
plot(tWin, gwsA(idxWin,ib), 'r--', 'LineWidth', 1.0);
grid on; ylabel('mm');
title(sprintf('%s Interannual vs GWS (GRACE-GLDAS)', basinNames(ib)));
legend({'GRACE Interannual','GWS'}, 'Location','best');

saveas(fig, fullfile(outDir,'ts_decomp_components_amazon.png'));
close(fig);

% --- Basin maps (Amazon) for 2 months: GRACE-HSAF vs GLDAS
B_amz = basins(ib).B;
for j = 1:numel(mapMonths)
    if isempty(mapIdx(j)); continue; end
    k = mapIdx(j);
    % GRACE-HSAF TWSA map
    Ghsaf = stacks.HSAF(:,:,k) - mean(stacks.HSAF(:,:,idxWin),3,'omitnan');
    fig = plot_map_basin(Ghsaf, lonVec, latVec, B_amz, struct('title', ...
        sprintf('GRACE-HSAF TWSA %s', datestr(t(k),'yyyy-mm')), 'caxis', [-30 30]));
    saveas(fig, fullfile(outDir, sprintf('amazon_grace_twsA_%s.png', datestr(t(k),'yyyymm'))));
    close(fig);

    % GLDAS TWSA map
    if ~isempty(gldas_map{j})
        Ggldas = gldas_map{j} - meanMap;
        fig = plot_map_basin(Ggldas, lonVec, latVec, B_amz, struct('title', ...
            sprintf('GLDAS TWSA %s', datestr(t(k),'yyyy-mm')), 'caxis', [-30 30]));
        saveas(fig, fullfile(outDir, sprintf('amazon_gldas_twsA_%s.png', datestr(t(k),'yyyymm'))));
        close(fig);
    end
end

save(fullfile(outDir,'gldas_multifilter_series.mat'), ...
    't','tWin','basinNames','methodNames','basin_tsa','gldas_twsA','gldas_smsA','gldas_sweA','gldas_cwsA','gwsA');

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

function trend = fit_trend(y, t, Fit)
    if isdatetime(t)
        tn = year(t) + (month(t)-1)/12 + (day(t)-1)/365.2425;
    else
        tn = t(:);
    end
    x = tn - Fit.t0;
    trend = Fit.coef(1) + Fit.coef(2) * x;
    trend = trend(:);
end

