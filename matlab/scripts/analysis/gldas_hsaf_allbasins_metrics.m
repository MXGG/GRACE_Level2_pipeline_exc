% HSAF vs GLDAS for all large basins (2004-2013)
% Outputs: CSV with basin correlation/RMSE against GLDAS TWSA.
clear; clc;

thisFile = mfilename('fullpath');
groupDir = fileparts(thisFile);
scriptsDir = fileparts(groupDir);
matlabRoot = fileparts(scriptsDir);
root = fileparts(matlabRoot);
addpath(genpath(fullfile(matlabRoot,'src')));

outDir = fullfile(root,'output','local','gldas_ext');
if ~exist(outDir,'dir'); mkdir(outDir); end

% --- Load GRACE HSAF stack (for grid + time reference)
S = load(fullfile(root,'output','local','stacks','HSAF_stack_200204-201706.mat'));
Stack = S.Stack;
lonVec = Stack.lon(:);
latVec = Stack.lat(:);
tStr = Stack.t(:);
t = datetime(tStr,'InputFormat','yyyy-MM');
Nt = numel(t);

% --- Basins
shp = fullfile(root,'data','Boundary','LargeBasin.shp');
Sbasin = shaperead(shp,'UseGeoCoords',true);
basinNames = strtrim(string({Sbasin.whymap_riv}));
nb = numel(Sbasin);

masks = false(numel(lonVec), numel(latVec), nb);
for i = 1:nb
    masks(:,:,i) = basin_make_mask(lonVec, latVec, Sbasin(i));
end

% --- GLDAS config
gldasDir = fullfile(root,'data','GLDAS');
filePattern = 'GLDAS_NOAH10_M.A%04d%02d.021.nc4';
soilVars = {'SoilMoi0_10cm_inst','SoilMoi10_40cm_inst','SoilMoi40_100cm_inst','SoilMoi100_200cm_inst'};
snowVar = 'SWE_inst';
canopyVar = 'CanopInt_inst';

% Read GLDAS grid from a sample month
f0 = fullfile(gldasDir, sprintf(filePattern, year(t(1)), month(t(1))));
lonG = ncread(f0,'lon'); lonG = lonG(:);
latG = ncread(f0,'lat'); latG = latG(:);
[LONQ, LATQ] = ndgrid(wrapTo180(lonVec), latVec);

% --- Allocate
gldas_tws = nan(Nt, nb);

% --- Loop over months
for k = 1:Nt
    y = year(t(k)); m = month(t(k));
    f = fullfile(gldasDir, sprintf(filePattern, y, m));
    if ~isfile(f); continue; end

    % Read components (kg/m^2 == mm)
    sms = 0;
    for sv = 1:numel(soilVars)
        sms = sms + double(ncread(f, soilVars{sv}));
    end
    swe = double(ncread(f, snowVar));
    cws = double(ncread(f, canopyVar));
    tws = sms + swe + cws;

    % Ensure lon/lat dimensions are [nLon x nLat]
    if size(tws,1) == numel(latG) && size(tws,2) == numel(lonG)
        tws = tws.';
    end

    % Interpolate to GRACE grid
    F = griddedInterpolant({lonG, latG}, tws, 'linear', 'none');
    Gtws = F(LONQ, LATQ);

    % Basin means
    for i = 1:nb
        gldas_tws(k,i) = basin_mean_one(Gtws, masks(:,:,i), latVec);
    end
end

% --- GRACE HSAF basin time series
graceGrid = double(Stack.ewh);
% Stack.ewh might be [nLat x nLon x Nt], convert to [nLon x nLat x Nt]
if size(graceGrid,1) == numel(latVec) && size(graceGrid,2) == numel(lonVec)
    graceGrid = permute(graceGrid, [2 1 3]);
end

grace_tws = nan(Nt, nb);
for i = 1:nb
    grace_tws(:,i) = basin_mean_ts(graceGrid, masks(:,:,i), latVec, true);
end

% --- Window and anomalies
idxWin = t >= datetime(2004,1,1) & t <= datetime(2013,12,1);
gldas_twsA = gldas_tws - mean(gldas_tws(idxWin,:), 'omitnan');
grace_twsA = grace_tws - mean(grace_tws(idxWin,:), 'omitnan');

% --- Metrics
Corr = nan(nb,1);
RMSE = nan(nb,1);
for i = 1:nb
    x = grace_twsA(idxWin,i);
    g = gldas_twsA(idxWin,i);
    Corr(i) = corr(x,g,'Rows','complete');
    RMSE(i) = sqrt(mean((x-g).^2, 'omitnan'));
end

T = table(basinNames(:), Corr, RMSE, 'VariableNames', {'Basin','Corr','RMSE'});
writetable(T, fullfile(outDir,'gldas_hsaf_allbasins_metrics_2004_2013.csv'));
save(fullfile(outDir,'gldas_hsaf_allbasins_metrics_2004_2013.mat'), ...
    't','basinNames','gldas_twsA','grace_twsA','Corr','RMSE');

fprintf('Saved metrics to: %s\n', outDir);

% ---- helper ----
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

