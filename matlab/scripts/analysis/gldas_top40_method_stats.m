% Summarize method performance over top-40 basins (by area)
% Outputs: method stats CSV + bar chart (median Corr/RMSE).
clear; clc;
thisFile = mfilename('fullpath');
groupDir = fileparts(thisFile);
scriptsDir = fileparts(groupDir);
matlabRoot = fileparts(scriptsDir);
root = fileparts(matlabRoot);
addpath(genpath(fullfile(matlabRoot,'src')));

outDir = fullfile(root,'output','local','gldas_ext');
if ~exist(outDir,'dir'); mkdir(outDir); end

% Read top-40 tables
fc = fullfile(outDir,'gldas_top40_corr_byarea.csv');
fr = fullfile(outDir,'gldas_top40_rmse_byarea.csv');
CorrTab = readtable(fc);
RMSETab = readtable(fr);

methodNames = CorrTab.Properties.VariableNames(2:end);
nm = numel(methodNames);

stats = table(methodNames(:), 'VariableNames', {'Method'});
stats.MeanCorr = nan(nm,1);
stats.MedianCorr = nan(nm,1);
stats.MeanRMSE = nan(nm,1);
stats.MedianRMSE = nan(nm,1);

for i = 1:nm
    key = methodNames{i};
    c = CorrTab.(key);
    r = RMSETab.(key);
    stats.MeanCorr(i) = mean(c, 'omitnan');
    stats.MedianCorr(i) = median(c, 'omitnan');
    stats.MeanRMSE(i) = mean(r, 'omitnan');
    stats.MedianRMSE(i) = median(r, 'omitnan');
end

% Save table
writetable(stats, fullfile(outDir,'gldas_top40_method_stats.csv'));

% Plot bar chart (median Corr & RMSE)
fig = figure('Color','w','Position',[100 100 1200 500]);
subplot(1,2,1);
bar(stats.MedianCorr, 'FaceColor',[0.2 0.5 0.8]); grid on;
set(gca,'XTickLabel',stats.Method,'XTickLabelRotation',30);
ylabel('Median Corr'); title('Top-40 Basins: Median Corr vs GLDAS');

subplot(1,2,2);
bar(stats.MedianRMSE, 'FaceColor',[0.8 0.4 0.2]); grid on;
set(gca,'XTickLabel',stats.Method,'XTickLabelRotation',30);
ylabel('Median RMSE (mm)'); title('Top-40 Basins: Median RMSE vs GLDAS');

saveas(fig, fullfile(outDir,'gldas_top40_method_stats.png'));
close(fig);

fprintf('Saved method stats to: %s\n', outDir);

