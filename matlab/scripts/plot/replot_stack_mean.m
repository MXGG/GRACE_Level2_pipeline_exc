% Replot stack mean maps using RMS/ABS for more informative signal.
clear; clc;
thisFile = mfilename('fullpath');
groupDir = fileparts(thisFile);
scriptsDir = fileparts(groupDir);
matlabRoot = fileparts(scriptsDir);
root = fileparts(matlabRoot);
addpath(genpath(fullfile(matlabRoot,'src')));

runRoot = fullfile(root,'output','local','global_nogia_mascon_undo','local');
% runRoot = fullfile(root,'output','local','adaptive_nogia_mascon_undo','local');

meanMode = 'rms';  % 'mean' | 'abs' | 'rms'
colormapName = 'redblue';
caxis_cm = [-30 30];

stackDir = fullfile(runRoot,'stacks');
plotDir = fullfile(runRoot,'plots');
if ~exist(plotDir,'dir'); mkdir(plotDir); end

stackFiles = dir(fullfile(stackDir, '*_stack_*.mat'));
if isempty(stackFiles)
    error('No stacks found in %s', stackDir);
end

for i = 1:numel(stackFiles)
    fp = fullfile(stackFiles(i).folder, stackFiles(i).name);
    S = load(fp);
    Stack = S.Stack;
    tag = Stack.tag;

    ewh = double(Stack.ewh);
    switch lower(meanMode)
        case 'mean'
            map = mean(ewh, 3, 'omitnan');
            titleStr = sprintf('%s mean', tag);
        case 'abs'
            map = mean(abs(ewh), 3, 'omitnan');
            titleStr = sprintf('%s mean(|EWH|)', tag);
        otherwise
            map = sqrt(mean(ewh.^2, 3, 'omitnan'));
            titleStr = sprintf('%s RMS', tag);
    end
    map = map / 10; % mm -> cm

    fig = plot_map_global(map, Stack.lon, Stack.lat, struct( ...
        'title', titleStr, 'caxis', caxis_cm, 'cbar_label', 'EWH (cm)', ...
        'colormap', colormapName));
    outPng = fullfile(plotDir, sprintf('stack_mean_%s.png', tag));
    saveas(fig, outPng);
    close(fig);
end

fprintf('Replotted stack mean maps in %s\n', plotDir);

