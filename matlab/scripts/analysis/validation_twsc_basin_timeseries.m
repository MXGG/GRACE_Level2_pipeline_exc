% Build basin-scale TWSC time series from monthly validation grids
% Outputs: monthly global maps + multi-panel basin time series figure.
clear; clc;

thisFile = mfilename('fullpath');
groupDir = fileparts(thisFile);
scriptsDir = fileparts(groupDir);
matlabRoot = fileparts(scriptsDir);
root = fileparts(matlabRoot);
addpath(genpath(fullfile(matlabRoot,'src')));

dataDir = fullfile(root,'data','Validation','TWSC_monthly');
outDir = fullfile(root,'output','local','validation_twsc');
mapDir = fullfile(outDir,'maps');
if ~exist(outDir,'dir'); mkdir(outDir); end
saveMaps = false;
if saveMaps && ~exist(mapDir,'dir'); mkdir(mapDir); end

% --- Grid definition (input files: lon 0-360, lat 89.75:-0.5:-89.75)
lon0 = 0.25:0.5:359.75;
lat0 = 89.75:-0.5:-89.75;
nLon = numel(lon0); nLat = numel(lat0);
lonWrap = wrapTo180(lon0);
[lonVec, lonOrder] = sort(lonWrap); % -180..180
latVec = fliplr(lat0); % ascending -89.75..89.75

% --- Basin boundaries
shp = fullfile(root,'data','Boundary','LargeBasin.shp');
Sbasin = shaperead(shp,'UseGeoCoords',true);

% Desired basins (with aliases)
basinList = { ...
    {'AMAZONAS','AMAZON'}, ...
    {'ARAL DRAINAGE','ARAL'}, ...
    {'BRAHMAPUTRA','BRAH MAPU TRA','BRAHMAPUTRA RIVER'}, ...
    {'COLORADO RIVER (PACIFIC OCEAN)','COLORADO RIVER'}, ...
    {'COLUMBIA RIVER','COLUMBIA'}, ...
    {'GANGES'}, ...
    {'INDUS'}, ...
    {'KOLYMA'}, ...
    {'LAKE CHAD'}, ...
    {'LENA','CENA'}, ...
    {'MACKENZIE RIVER','MACKENZIE'}, ...
    {'MEKONG'}, ...
    {'NIGER'}, ...
    {'OB'}, ...
    {'ORINOCO'}, ...
    {'ZAMBEZI','ZAMBEII'}, ...
    {'SHEBELLE'} ...
};

basins = struct('name',{},'B',{});
for i = 1:numel(basinList)
    B = pick_basin(Sbasin, basinList{i});
    if ~isempty(B)
        basins(end+1).name = pretty_name(string(strtrim(B(1).whymap_riv))); %#ok<AGROW>
        basins(end).B = B;
    end
end
nBasins = numel(basins);

% Basin masks
masks = false(numel(lonVec), numel(latVec), nBasins);
for i = 1:nBasins
    masks(:,:,i) = basin_make_mask(lonVec, latVec, basins(i).B);
end

% --- Files
files = dir(fullfile(dataDir,'val_twsc_*.txt'));
[~, idx] = sort({files.name});
files = files(idx);
Nt = numel(files);
t = datetime(zeros(Nt,1),1,1);

obs_ts = nan(Nt, nBasins);
pred_ts = nan(Nt, nBasins);
glob_obs = nan(Nt,1);
glob_pred = nan(Nt,1);

% --- Loop months
for k = 1:Nt
    f = fullfile(files(k).folder, files(k).name);
    tok = regexp(files(k).name,'val_twsc_(\d{6})','tokens','once');
    if ~isempty(tok)
        t(k) = datetime(tok{1},'InputFormat','yyyyMM');
    end

    M = readmatrix(f, 'FileType','text', 'NumHeaderLines', 2);
    if size(M,2) < 4
        warning('Unexpected columns in %s', files(k).name);
        continue;
    end

    obs = M(:,3);
    pred = M(:,4);

    if numel(obs) ~= nLon*nLat
        warning('Unexpected grid size in %s', files(k).name);
        continue;
    end

    % reshape to [nLon x nLat], lat descending
    ObsG = reshape(obs, [nLon, nLat]);
    PredG = reshape(pred, [nLon, nLat]);

    % flip to lat ascending
    ObsG = ObsG(:, end:-1:1);
    PredG = PredG(:, end:-1:1);

    % reorder lon to -180..180
    ObsG = ObsG(lonOrder, :);
    PredG = PredG(lonOrder, :);

    % basin means
    for i = 1:nBasins
        obs_ts(k,i) = basin_mean_one(ObsG, masks(:,:,i), latVec);
        pred_ts(k,i) = basin_mean_one(PredG, masks(:,:,i), latVec);
    end

    % global land mean (area-weighted by latitude)
    glob_obs(k) = global_mean(ObsG, latVec);
    glob_pred(k) = global_mean(PredG, latVec);

    if saveMaps
        % save global maps
        opt = struct('title', sprintf('Observed TWSC %s', datestr(t(k),'yyyy-mm')), ...
                     'caxis', [-30 30], 'show_colorbar', true);
        fig = plot_map_global(ObsG, lonVec, latVec, opt);
        saveas(fig, fullfile(mapDir, sprintf('obs_twsc_%s.png', datestr(t(k),'yyyymm'))));
        close(fig);

        opt.title = sprintf('Predicted TWSC %s', datestr(t(k),'yyyy-mm'));
        fig = plot_map_global(PredG, lonVec, latVec, opt);
        saveas(fig, fullfile(mapDir, sprintf('pred_twsc_%s.png', datestr(t(k),'yyyymm'))));
        close(fig);
    end
end

% --- Multi-panel figure: 10 basins + center (map)
fig = figure('Color','w','Position',[100 100 1800 1000]);
tl = tiledlayout(4,4,'TileSpacing','compact','Padding','compact');

% choose 10 basins for side panels
pickIdx = 1:min(12, nBasins);
smallTiles = [1 2 3 4 5 8 9 12 13 14 15 16];

% center map panel (span 2x2 for larger map)
axMap = nexttile(tl, 6, [2 2]);
basinsSel = basins(pickIdx);
plot_basin_map(axMap, basinsSel, lonVec, latVec);

% plot 10 basins around with index labels
rowLabelTiles = [1 5 9 13];
for ii = 1:numel(pickIdx)
    i = pickIdx(ii);
    ax = nexttile(tl, smallTiles(ii));
    plot(ax, t, obs_ts(:,i), 'k-', 'LineWidth', 1.6); hold on;
    plot(ax, t, pred_ts(:,i), 'r-', 'LineWidth', 1.6);
    grid(ax,'on');
    title(ax, sprintf('%d. %s', ii, basins(i).name), 'Interpreter','none');
    if any(smallTiles(ii) == rowLabelTiles)
        ylabel(ax, 'TWSC (cm)');
    end
    if ii == 1
        legend(ax, {'Observed','Predicted'}, 'Location','best');
    end
    style_axes(ax, false);
end

% Apply Times New Roman font
set(findall(fig,'-property','FontName'),'FontName','Times New Roman');

saveas(fig, fullfile(outDir,'twsc_basin_timeseries_with_map.png'));
savefig(fig, fullfile(outDir,'twsc_basin_timeseries_with_map.fig'));
close(fig);

save(fullfile(outDir,'twsc_basin_timeseries.mat'), ...
    't','basins','obs_ts','pred_ts','glob_obs','glob_pred','lonVec','latVec');

fprintf('Outputs saved to: %s\\n', outDir);

% ---- helpers ----
function B = pick_basin(S, keys)
    names = string({S.whymap_riv});
    for k = 1:numel(keys)
        key = keys{k};
        idx = find(strcmpi(strtrim(names), key), 1);
        if isempty(idx)
            idx = find(contains(upper(names), upper(key)), 1);
        end
        if ~isempty(idx)
            B = S(idx);
            return;
        end
    end
    B = struct([]);
end

function m = basin_mean_one(G, mask, latVec)
    if all(isnan(G(:))) || nnz(mask)==0
        m = NaN; return;
    end
    w = cosd(latVec(:))';
    W = mask .* w;
    v = isfinite(G) & mask;
    if ~any(v(:))
        m = NaN; return;
    end
    W(~v) = 0;
    m = nansum(G(:).*W(:)) / (nansum(W(:)) + eps);
end

function m = global_mean(G, latVec)
    w = cosd(latVec(:))';
    W = repmat(w, size(G,1), 1);
    v = isfinite(G);
    if ~any(v(:))
        m = NaN; return;
    end
    W(~v) = 0;
    m = nansum(G(:).*W(:)) / (nansum(W(:)) + eps);
end

function plot_basin_map(ax, basins, lonVec, latVec)
    axes(ax); %#ok<LAXES>
    hold(ax,'on');
    if exist('m_proj','file') == 2
        m_proj('robinson','lon',[-180 180],'lat',[-90 90]);
        % DEM-like background (light)
        try
            m_elev('shadedrelief');
            cm = gray(256);
            cm = cm*0.6 + 0.4; % lighten
            colormap(ax, cm);
        catch
            m_coast('patch',[0.90 0.94 0.90],'edgecolor',[0.6 0.6 0.6]);
        end
        m_coast('color',[0.4 0.4 0.4],'linewidth',0.6);
        xtk = -180:90:180;
        ytk = -90:45:90;
        m_grid('box','on','tickdir','in','linewidth',1,'fontsize',10,'xtick',xtk,'ytick',ytk);

        % plot basin boundaries and index labels
        for i = 1:numel(basins)
            B = basins(i).B;
            for k = 1:numel(B)
                lon = wrapTo180(B(k).Lon(:));
                lat = B(k).Lat(:);
                m_plot(lon, lat, 'b-', 'LineWidth', 1.8);
            end
            [lonc, latc] = basin_centroid(B);
            if isfinite(lonc) && isfinite(latc)
                m_text(lonc, latc, sprintf('%d', i), 'Color','r', ...
                    'FontWeight','bold','FontSize',10, 'HorizontalAlignment','center');
            end
        end
        ax.Visible = 'off';
        % reduce inner margins to better fill tile
        ti = get(ax,'TightInset');
        set(ax,'LooseInset',ti);
    else
        % fallback
        plot(ax, 0, 0);
        title(ax, 'Watershed Locations', 'Interpreter','none');
        axis(ax,'off');
    end
end

function [lonc, latc] = basin_centroid(B)
    lonAll = []; latAll = [];
    for k = 1:numel(B)
        lonAll = [lonAll; B(k).Lon(:)]; %#ok<AGROW>
        latAll = [latAll; B(k).Lat(:)]; %#ok<AGROW>
    end
    good = isfinite(lonAll) & isfinite(latAll);
    lonAll = lonAll(good); latAll = latAll(good);
    if isempty(lonAll)
        lonc = NaN; latc = NaN; return;
    end
    lonc = mean(wrapTo180(lonAll));
    latc = mean(latAll);
end

function name = pretty_name(nameIn)
    % Convert to title case for readability
    s = lower(char(nameIn));
    chars = s;
    cap = true;
    for i = 1:numel(chars)
        if cap && isletter(chars(i))
            chars(i) = upper(chars(i));
            cap = false;
        elseif any(chars(i) == [' ' '-' '(' '/' '&'])
            cap = true;
        end
    end
    name = string(strtrim(chars));
end

function style_axes(ax, isGlobal)
    ax.FontSize = 12;
    ax.LineWidth = 1.0;
    ax.GridLineWidth = 1.2;
    ax.XMinorGrid = 'off';
    ax.YMinorGrid = 'off';
    ax.GridAlpha = 0.35;
    ax.Title.FontSize = 12;
    ax.XLabel.FontSize = 12;
    ax.YLabel.FontSize = 12;
    if ~isGlobal
        yrs = year(ax.XLim);
        if ~isempty(yrs)
            yt = year(datetime(yrs(1),1,1)):2:year(datetime(yrs(2),1,1));
            ax.XTick = datetime(yt,1,1);
        end
    end
end


