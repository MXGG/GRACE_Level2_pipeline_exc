% Build top-40 (by basin area) tables of Corr/RMSE for all methods.
clear; clc;

thisFile = mfilename('fullpath');
groupDir = fileparts(thisFile);
scriptsDir = fileparts(groupDir);
matlabRoot = fileparts(scriptsDir);
root = fileparts(matlabRoot);
addpath(genpath(fullfile(matlabRoot,'src')));

outDir = fullfile(root,'output','local','gldas_ext');
if ~exist(outDir,'dir'); mkdir(outDir); end

% --- Top 40 basins by area
shp = fullfile(root,'data','Boundary','LargeBasin.shp');
Sbasin = shaperead(shp,'UseGeoCoords',true);
areas = [Sbasin.Sheet1__AR];
[~, order] = sort(areas,'descend');
topN = 40;
Sbasin = Sbasin(order(1:topN));
basinNames = strtrim(string({Sbasin.whymap_riv})).';

% --- Load metrics (all methods)
metricsCsv = fullfile(outDir,'gldas_allmethods_metrics_2004_2013.csv');
T = readtable(metricsCsv);
T.Basin = strtrim(string(T.Basin));

methodNames = {'GAUSS','FAN','P4M6_GAUSS','P4M6_FAN','DDK','HSAF'};

% --- Build wide tables
CorrTab = table(basinNames, 'VariableNames', {'Basin'});
RMSETab = table(basinNames, 'VariableNames', {'Basin'});

for m = 1:numel(methodNames)
    key = methodNames{m};
    sub = T(strcmp(T.Method, key), :);
    sub.Basin = strtrim(string(sub.Basin));
    Corr = nan(topN,1);
    RMSE = nan(topN,1);
    for i = 1:topN
        idx = find(sub.Basin == basinNames(i), 1);
        if ~isempty(idx)
            Corr(i) = sub.Corr(idx);
            RMSE(i) = sub.RMSE(idx);
        end
    end
    CorrTab.(key) = Corr;
    RMSETab.(key) = RMSE;
end

% --- Save
writetable(CorrTab, fullfile(outDir,'gldas_top40_corr_byarea.csv'));
writetable(RMSETab, fullfile(outDir,'gldas_top40_rmse_byarea.csv'));

fprintf('Saved: %s\n', outDir);

