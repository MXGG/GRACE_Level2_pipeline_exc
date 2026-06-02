% GLDAS vs GRACE (all methods) for all large basins (2004-2013)
% Outputs: full metrics CSV + top40 per method.
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

% --- GLDAS basin series (all basins)
gldas_tws = nan(Nt, nb);
for k = 1:Nt
    y = year(t(k)); m = month(t(k));
    f = fullfile(gldasDir, sprintf(filePattern, y, m));
    if ~isfile(f); continue; end

    sms = 0;
    for sv = 1:numel(soilVars)
        sms = sms + double(ncread(f, soilVars{sv}));
    end
    swe = double(ncread(f, snowVar));
    cws = double(ncread(f, canopyVar));
    tws = sms + swe + cws;

    if size(tws,1) == numel(latG) && size(tws,2) == numel(lonG)
        tws = tws.';
    end

    F = griddedInterpolant({lonG, latG}, tws, 'linear', 'none');
    Gtws = F(LONQ, LATQ);

    for i = 1:nb
        gldas_tws(k,i) = basin_mean_one(Gtws, masks(:,:,i), latVec);
    end
end

% --- Window and anomalies (2004-2013)
idxWin = t >= datetime(2004,1,1) & t <= datetime(2013,12,1);
gldas_twsA = gldas_tws - mean(gldas_tws(idxWin,:), 'omitnan');

% --- Methods
methodNames = {'GAUSS','FAN','P4M6_GAUSS','P4M6_FAN','DDK','HSAF'};
stackPaths = containers.Map;
stackPaths('GAUSS') = fullfile(root,'output','local','stacks','GAUSS_stack_200204-201706.mat');
stackPaths('DDK') = fullfile(root,'output','local','stacks','DDK_stack_200204-201706.mat');
stackPaths('P4M6_GAUSS') = fullfile(root,'output','local','stacks','P4M6_GAUSS_stack_200204-201706.mat');
stackPaths('HSAF') = fullfile(root,'output','local','stacks','HSAF_stack_200204-201706.mat');
stackPaths('FAN') = fullfile(root,'output','remote','183543','stacks','FAN_stack_200204-201706.mat');
stackPaths('P4M6_FAN') = fullfile(root,'output','remote','183543','stacks','P4M6_FAN_stack_200204-201706.mat');

% --- Metrics table
T = table();
for m = 1:numel(methodNames)
    key = methodNames{m};
    S = load(stackPaths(key));
    Stack = S.Stack;
    data = double(Stack.ewh);
    % ensure [nLon x nLat x Nt]
    if size(data,1) == numel(latVec) && size(data,2) == numel(lonVec)
        data = permute(data, [2 1 3]);
    end

    ts = nan(Nt, nb);
    for i = 1:nb
        ts(:,i) = basin_mean_ts(data, masks(:,:,i), latVec, true);
    end
    tsa = ts - mean(ts(idxWin,:), 'omitnan');

    for i = 1:nb
        x = tsa(idxWin,i);
        g = gldas_twsA(idxWin,i);
        r = corr(x,g,'Rows','complete');
        e = sqrt(mean((x-g).^2, 'omitnan'));
        row = table(basinNames(i), string(key), r, e, ...
            'VariableNames', {'Basin','Method','Corr','RMSE'});
        T = [T; row]; %#ok<AGROW>
    end
end

fullCsv = fullfile(outDir,'gldas_allmethods_metrics_2004_2013.csv');
writetable(T, fullCsv);

% --- Top 40 per method (by Corr)
for m = 1:numel(methodNames)
    key = methodNames{m};
    sub = T(strcmp(T.Method, key), :);
    sub = sortrows(sub, 'Corr', 'descend');
    topN = min(40, height(sub));
    outCsv = fullfile(outDir, sprintf('gldas_top40_%s_corr.csv', key));
    writetable(sub(1:topN,:), outCsv);
end

save(fullfile(outDir,'gldas_allmethods_metrics_2004_2013.mat'), ...
    't','basinNames','methodNames','gldas_twsA');

fprintf('Saved: %s\n', fullCsv);

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

