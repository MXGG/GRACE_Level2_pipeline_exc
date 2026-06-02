% GLDAS vs GRACE (HSAF) comparison: global map + basin time series
% Uses short path to avoid Windows reserved-name issues in MATLAB.
clear; clc;
thisFile = mfilename('fullpath');
groupDir = fileparts(thisFile);
scriptsDir = fileparts(groupDir);
matlabRoot = fileparts(scriptsDir);
root = fileparts(matlabRoot);
addpath(genpath(fullfile(matlabRoot,'src')));

cd(root);

outDir = fullfile(root,'output','local','gldas');
if ~exist(outDir,'dir'); mkdir(outDir); end

% --- Load GRACE HSAF stack (for grid + time reference)
S = load(fullfile(root,'output','local','stacks','HSAF_stack_200204-201706.mat'));
Stack = S.Stack;
lonVec = Stack.lon(:);
latVec = Stack.lat(:);
tStr = Stack.t(:);
t = datetime(tStr,'InputFormat','yyyy-MM');
Nt = numel(t);

% --- GLDAS data config
gldasDir = fullfile(root,'data','GLDAS');
filePattern = 'GLDAS_NOAH10_M.A%04d%02d.021.nc4';
soilVars = {'SoilMoi0_10cm_inst','SoilMoi10_40cm_inst','SoilMoi40_100cm_inst','SoilMoi100_200cm_inst'};
snowVar = 'SWE_inst';
canopyVar = 'CanopInt_inst';

% --- Read GLDAS grid from a sample month
f0 = fullfile(gldasDir, sprintf(filePattern, year(t(1)), month(t(1))));
lonG = ncread(f0,'lon'); lonG = lonG(:);
latG = ncread(f0,'lat'); latG = latG(:);

% Target grid
lonQ = wrapTo180(lonVec);
latQ = latVec;
[LONQ, LATQ] = ndgrid(lonQ, latQ);

% --- Basin setup (top N largest basins)
shp = fullfile(root,'data','Boundary','LargeBasin.shp');
Sbasin = shaperead(shp,'UseGeoCoords',true);
areas = [Sbasin.Sheet1__AR];
[~, order] = sort(areas,'descend');
topN = 10;
Sbasin = Sbasin(order(1:topN));
basinNames = strtrim(string({Sbasin.whymap_riv}));

masks = false(numel(lonVec), numel(latVec), topN);
for i = 1:topN
    masks(:,:,i) = basin_make_mask(lonVec, latVec, Sbasin(i));
end

% --- Allocate basin time series
gldas_tws = nan(Nt, topN);
gldas_soil = nan(Nt, topN);
gldas_snow = nan(Nt, topN);
gldas_canopy = nan(Nt, topN);

% --- Map storage (for a reference month)
mapMonth = datetime(2007,10,1);
mapIdx = find(year(t)==year(mapMonth) & month(t)==month(mapMonth), 1);
TWS_map = [];

% --- Running mean for anomaly map
sumMap = zeros(numel(lonVec), numel(latVec));
cntMap = zeros(numel(lonVec), numel(latVec));

% --- Loop over months
for k = 1:Nt
    y = year(t(k)); m = month(t(k));
    f = fullfile(gldasDir, sprintf(filePattern, y, m));
    if ~isfile(f)
        continue;
    end

    % Read components (kg/m^2 == mm)
    soil = 0;
    for sv = 1:numel(soilVars)
        soil = soil + double(ncread(f, soilVars{sv}));
    end
    snow = double(ncread(f, snowVar));
    canopy = double(ncread(f, canopyVar));
    tws = soil + snow + canopy;

    % Ensure lon/lat dimensions are [nLon x nLat]
    if size(tws,1) == numel(latG) && size(tws,2) == numel(lonG)
        tws = tws.';
        soil = soil.';
        snow = snow.';
        canopy = canopy.';
    end

    % Interpolate to target grid
    F = griddedInterpolant({lonG, latG}, tws, 'linear', 'none');
    Gtws = F(LONQ, LATQ);
    F.Values = soil;   Gsoil = F(LONQ, LATQ);
    F.Values = snow;   Gsnow = F(LONQ, LATQ);
    F.Values = canopy; Gcan = F(LONQ, LATQ);

    % Basin means
    for i = 1:topN
        gldas_tws(k,i) = basin_mean_one(Gtws, masks(:,:,i), latVec);
        gldas_soil(k,i) = basin_mean_one(Gsoil, masks(:,:,i), latVec);
        gldas_snow(k,i) = basin_mean_one(Gsnow, masks(:,:,i), latVec);
        gldas_canopy(k,i) = basin_mean_one(Gcan, masks(:,:,i), latVec);
    end

    % Running mean for anomaly map
    valid = ~isnan(Gtws);
    sumMap(valid) = sumMap(valid) + Gtws(valid);
    cntMap(valid) = cntMap(valid) + 1;

    if k == mapIdx
        TWS_map = Gtws;
    end
end

meanMap = sumMap ./ max(cntMap,1);
TWSA_map = TWS_map - meanMap;

% --- GRACE basin time series (HSAF)
grace_tws = nan(Nt, topN);
% Stack.ewh is [nLat x nLon x Nt] in this dataset, convert to [nLon x nLat x Nt]
graceGrid = permute(double(Stack.ewh), [2 1 3]);
for i = 1:topN
    grace_tws(:,i) = basin_mean_ts(graceGrid, masks(:,:,i), latVec, true);
end

% --- Convert to anomalies (remove mean)
gldas_twsA = gldas_tws - mean(gldas_tws, 'omitnan');
gldas_soilA = gldas_soil - mean(gldas_soil, 'omitnan');
gldas_snowA = gldas_snow - mean(gldas_snow, 'omitnan');
gldas_canopyA = gldas_canopy - mean(gldas_canopy, 'omitnan');
grace_twsA = grace_tws - mean(grace_tws, 'omitnan');

% --- Save data
save(fullfile(outDir,'gldas_basin_timeseries.mat'), ...
    't','basinNames','gldas_twsA','gldas_soilA','gldas_snowA','gldas_canopyA','grace_twsA');

% --- Plot: global map (GLDAS TWSA)
if ~isempty(TWSA_map)
    fig = plot_map_global(TWSA_map, lonVec, latVec, struct('title', ...
        sprintf('GLDAS TWSA %s', datestr(t(mapIdx),'yyyy-mm')), 'caxis', [-30 30]));
    outPng = fullfile(outDir, sprintf('gldas_twsA_map_%s.png', datestr(t(mapIdx),'yyyymm')));
    saveas(fig, outPng);
    close(fig);
end

% --- Plot: basin time series comparison (top 6)
nPlot = min(6, topN);
fig = figure('Color','w','Position',[100 100 1200 800]);
for i = 1:nPlot
    subplot(3,2,i);
    plot(t, grace_twsA(:,i), 'k-', 'LineWidth', 1.2); hold on;
    plot(t, gldas_twsA(:,i), 'r-', 'LineWidth', 1.0);
    plot(t, gldas_soilA(:,i), 'b--', 'LineWidth', 0.8);
    plot(t, gldas_snowA(:,i), 'c--', 'LineWidth', 0.8);
    plot(t, gldas_canopyA(:,i), 'm--', 'LineWidth', 0.8);
    grid on;
    title(basinNames(i));
    ylabel('mm');
    if i == 1
        legend({'GRACE-HSAF','GLDAS-TWS','Soil','Snow','Canopy'}, 'Location','best');
    end
end
outPng = fullfile(outDir, 'gldas_grace_basin_timeseries_top6.png');
saveas(fig, outPng);
close(fig);

fprintf('GLDAS comparison outputs saved to: %s\n', outDir);

% --- Local helper
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

