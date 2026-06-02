% Plot mosaic of top-N basins (mean map) in WSDI-like style.
clear; clc;
thisFile = mfilename('fullpath');
groupDir = fileparts(thisFile);
scriptsDir = fileparts(groupDir);
matlabRoot = fileparts(scriptsDir);
root = fileparts(matlabRoot);
addpath(genpath(fullfile(matlabRoot,'src')));

% ---- User settings ----
runRoot = fullfile(root,'output','local','global_nogia_mascon_undo','local');
% runRoot = fullfile(root,'output','local','adaptive_nogia_mascon_undo','local');

basinShp = fullfile(root,'data','Boundary','boundary_cache','LargeBasin.shp');

methodTags = {'P4M6_FAN','DDK','HSAF','Mascon'};   % which filter stacks to plot
nBasins = 10;                                    % number of basins to plot

plotMode = 'rms';             % 'mean' | 'month' | 'rms'
month_ym = '2012-06';          % used when plotMode='month'

caxis_cm = [-30 30];           % unified EWH colorbar
colormapName = 'redblue';      % 'redblue' or 'jet'

coastShp = fullfile(root,'data','Boundary','ne_admin_0','ne_50m_admin_0_countries.shp');
if ~isfile(coastShp)
    coastShp = '';
end

plotDir = fullfile(runRoot,'plots');
if ~exist(plotDir,'dir'); mkdir(plotDir); end

% ---- Read basin boundaries ----
B = basin_read_boundary(basinShp);
[areas, names] = basin_areas(B);
[~, idx] = sort(areas, 'descend');
idx = idx(1:min(nBasins, numel(idx)));

% ---- Loop methods ----
for mt = 1:numel(methodTags)
    methodTag = methodTags{mt};
    stackDir = fullfile(runRoot,'stacks');
    stackFile = find_latest_stack(stackDir, methodTag);
    if isempty(stackFile)
        fprintf('Skip %s (stack not found)\n', methodTag);
        continue;
    end
    S = load(stackFile);
    Stack = S.Stack;
    lonVec = Stack.lon; latVec = Stack.lat;

    if strcmpi(plotMode, 'mean')
        map = mean(double(Stack.ewh), 3, 'omitnan') / 10; % mm->cm
        map = align_lonlat(map, lonVec, latVec);
    else
        if strcmpi(plotMode, 'month')
            t = Stack.t;
            if iscell(t); t = string(t); end
            idxMonth = find(strcmp(t, month_ym), 1);
            if isempty(idxMonth)
                warning('Month %s not found in stack, using first month.', month_ym);
                idxMonth = 1;
            end
            map = double(Stack.ewh(:,:,idxMonth)) / 10; % mm->cm
            map = align_lonlat(map, lonVec, latVec);
        else
            map = sqrt(mean(double(Stack.ewh).^2, 3, 'omitnan')) / 10; % RMS in cm
            map = align_lonlat(map, lonVec, latVec);
        end
    end

    rows = 2; cols = ceil(numel(idx)/rows);
    fig = figure('Color','w','Position',[100 100 1600 900]);
    tiledlayout(rows, cols, 'TileSpacing','compact','Padding','compact');

    for i = 1:numel(idx)
        bi = idx(i);
        nexttile; hold on;

        [lonlim, latlim] = basin_bounds(B(bi), 1.5);
        lonMask = lonVec >= lonlim(1) & lonVec <= lonlim(2);
        latMask = latVec >= latlim(1) & latVec <= latlim(2);
        Z = map(lonMask, latMask);
        lonSub = lonVec(lonMask);
        latSub = latVec(latMask);
        [LONR, LATR] = meshgrid(lonSub, latSub);

        try
            m_proj('lambert','lon',lonlim,'lat',latlim);
            h = m_pcolor(LONR, LATR, Z.');
            set(h,'EdgeColor','none'); shading flat;
            colormap(get_cmap(colormapName)); caxis(caxis_cm);
            draw_coast(coastShp);
            if ~isempty(B(bi).Lon)
                m_line(B(bi).Lon, B(bi).Lat, 'Color',[0.2 0.2 0.2], 'LineWidth',0.5);
            end
            m_grid('box','fancy','tickdir','out','fontsize',9,'linestyle',':','linewidth',0.7);
        catch
            imagesc(lonSub, latSub, Z.');
            set(gca,'YDir','normal');
            colormap(get_cmap(colormapName)); caxis(caxis_cm);
            if ~isempty(B(bi).Lon)
                plot(B(bi).Lon, B(bi).Lat, 'Color',[0.2 0.2 0.2], 'LineWidth',0.5);
            end
            grid on; box on;
        end

        title(names{bi}, 'FontName','Times New Roman','FontSize',9);
    end

    cb = colorbar;
    cb.Layout.Tile = 'east';
    cb.Label.String = 'EWH (cm)';
    cb.Label.FontName = 'Times New Roman';

    set(findall(fig,'-property','FontName'),'FontName','Times New Roman');

    outPng = fullfile(plotDir, sprintf('basin_mosaic_%s_%s.png', methodTag, plotMode));
    saveas(fig, outPng);
    close(fig);

    fprintf('Saved: %s\n', outPng);
end

% ---- helpers ----
function f = find_latest_stack(stackDir, tag)
    f = '';
    d = dir(fullfile(stackDir, sprintf('%s_stack_*.mat', tag)));
    if isempty(d); return; end
    [~, idx] = max([d.datenum]);
    f = fullfile(d(idx).folder, d(idx).name);
end

function [areas, names] = basin_areas(B)
    areas = zeros(numel(B),1);
    names = cell(numel(B),1);
    for i = 1:numel(B)
        lon = B(i).Lon(:); lat = B(i).Lat(:);
        good = isfinite(lon) & isfinite(lat);
        lon = lon(good); lat = lat(good);
        names{i} = B(i).Name;
        if isempty(lon)
            areas(i) = 0; continue;
        end
        areas(i) = abs(polyarea(lon, lat));
    end
end

function [lonlim, latlim] = basin_bounds(B, padDeg)
    lon = B.Lon(:); lat = B.Lat(:);
    good = isfinite(lon) & isfinite(lat);
    lon = lon(good); lat = lat(good);
    lonlim = [min(lon)-padDeg, max(lon)+padDeg];
    latlim = [min(lat)-padDeg, max(lat)+padDeg];
end

function Gout = align_lonlat(G, lonVec, latVec)
    nLon = numel(lonVec); nLat = numel(latVec);
    if isequal(size(G), [nLon, nLat])
        Gout = G;
    elseif isequal(size(G), [nLat, nLon])
        Gout = G.';
    else
        error('Grid size mismatch with lon/lat.');
    end
end

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
            cmap = jet(256);
    end
end

function draw_coast(coastShp)
    if isempty(coastShp) || exist('shaperead','file') ~= 2
        m_coast('color',[0.2 0.2 0.2],'linewidth',0.8);
        return;
    end
    try
        S = shaperead(coastShp, 'UseGeoCoords', true);
        for k = 1:numel(S)
            m_line(S(k).Lon, S(k).Lat, 'Color',[0.2 0.2 0.2], 'LineWidth',0.5);
        end
    catch
        m_coast('color',[0.2 0.2 0.2],'linewidth',0.8);
    end
end

