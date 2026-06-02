% Caspian HIS leakage visualization (Mascon truth vs Gaussian filter)
% Outputs:
%   1) Spatial comparison map set (truth / filtered / difference / leakage)
%   2) Basin-mean time-series leakage effect
%   3) 1D profile schematic (similar to leakage concept figure)
%
% Saved under:
%   output/local/caspian_his_leakage/

clear; clc;

thisFile = mfilename('fullpath');
plotDir = fileparts(thisFile);
scriptsDir = fileparts(plotDir);
matlabRoot = fileparts(scriptsDir);
root = fileparts(matlabRoot);
addpath(genpath(fullfile(matlabRoot, 'src')));

% ---------------- User settings ----------------
dataFile = 'G:\HSAF\Data\Drawing Data\Griddata\HIS_EWH_Hankel_Filtered_Statistics.mat';
shpFile = 'G:\HSAF\Data\zb452vm0926\XCA_adm0.shp';
outputDir = fullfile(root, 'output', 'local', 'caspian_his_leakage');
monthToPlot = [];  % [] => auto-pick strongest truth month
profilePadDeg = 8;
mapPadDeg = 3;
inspectTopNMonths = 6;
% -----------------------------------------------

if ~exist(outputDir, 'dir')
    mkdir(outputDir);
end

assert(isfile(dataFile), 'Data file not found: %s', dataFile);
assert(isfile(shpFile), 'Shapefile not found: %s', shpFile);

S = load(dataFile, 'HIS_EWH', 'csr_lon', 'csr_lat', 'years');
assert(isfield(S, 'HIS_EWH'), 'HIS_EWH is missing in MAT file.');
assert(isfield(S.HIS_EWH, 'Mascon'), 'HIS_EWH.Mascon is missing.');
assert(isfield(S.HIS_EWH, 'Gaussian'), 'HIS_EWH.Gaussian is missing.');
assert(isfield(S, 'csr_lon') && isfield(S, 'csr_lat'), 'csr_lon/csr_lat are missing.');

HIS_EWH = S.HIS_EWH;
csr_lon = S.csr_lon(:)';
csr_lat = S.csr_lat(:)';
years = [];
if isfield(S, 'years')
    years = S.years(:)';
end

% Build Caspian mask
cap = shaperead(shpFile);
dLon = median(diff(csr_lon), 'omitnan');
dLon = abs(dLon);
[cap_x, cap_y, cap_mk] = mkmask(cap, dLon);

% Basin window (for averaged series)
i1b = nearest_idx(csr_lon, cap_x(1));
i2b = nearest_idx(csr_lon, cap_x(end));
j1b = nearest_idx(csr_lat, cap_y(1));
j2b = nearest_idx(csr_lat, cap_y(end));
if i1b > i2b
    tmp = i1b; i1b = i2b; i2b = tmp;
end
if j1b > j2b
    tmp = j1b; j1b = j2b; j2b = tmp;
end

lon_basin = csr_lon(i1b:i2b);
lat_basin = csr_lat(j1b:j2b);
mask_basin = build_mask_lonlat(cap, lon_basin, lat_basin, cap_mk);

% Expanded map window (to retain surrounding values)
lonMinM = min(cap_x) - mapPadDeg;
lonMaxM = max(cap_x) + mapPadDeg;
latMinM = min(cap_y) - mapPadDeg;
latMaxM = max(cap_y) + mapPadDeg;
i1m = nearest_idx(csr_lon, lonMinM);
i2m = nearest_idx(csr_lon, lonMaxM);
j1m = nearest_idx(csr_lat, latMinM);
j2m = nearest_idx(csr_lat, latMaxM);
if i1m > i2m
    tmp = i1m; i1m = i2m; i2m = tmp;
end
if j1m > j2m
    tmp = j1m; j1m = j2m; j2m = tmp;
end
lon_map = csr_lon(i1m:i2m);
lat_map = csr_lat(j1m:j2m);

truth_basin = HIS_EWH.Mascon(i1b:i2b, j1b:j2b, :);
filt_basin = HIS_EWH.Gaussian(i1b:i2b, j1b:j2b, :);
truth_map = HIS_EWH.Mascon(i1m:i2m, j1m:j2m, :);
filt_map = HIS_EWH.Gaussian(i1m:i2m, j1m:j2m, :);

Nt = min([size(truth_basin, 3), size(filt_basin, 3), size(truth_map, 3), size(filt_map, 3)]);
truth_basin = truth_basin(:, :, 1:Nt);
filt_basin = filt_basin(:, :, 1:Nt);
truth_map = truth_map(:, :, 1:Nt);
filt_map = filt_map(:, :, 1:Nt);

if ~isempty(years)
    years = years(1:Nt);
else
    years = 1:Nt;
end

truth_basin = truth_basin .* repmat(mask_basin, 1, 1, Nt);
filt_basin = filt_basin .* repmat(mask_basin, 1, 1, Nt);

% Basin-mean series and leakage decomposition
latW = cosd(lat_basin);
truth_ts = nan(Nt, 1);
filt_ts = nan(Nt, 1);
atten_ts = nan(Nt, 1);
leak_out_ts = nan(Nt, 1);
leak_in_ts = nan(Nt, 1);
truth_rms_ts = nan(Nt, 1);

for k = 1:Nt
    T = truth_basin(:, :, k);
    F = filt_basin(:, :, k);
    A = abs(T);
    B = abs(F);

    truth_ts(k) = weighted_mean_2d(T, latW);
    filt_ts(k) = weighted_mean_2d(F, latW);
    atten_ts(k) = truth_ts(k) - filt_ts(k);
    truth_rms_ts(k) = sqrt(mean(T(:).^2, 'omitnan'));

    leak_out_map = max(A - B, 0); % Signal attenuation (leakage-out style)
    leak_in_map = max(B - A, 0);  % Contamination amplification (leakage-in style)

    leak_out_ts(k) = weighted_mean_2d(leak_out_map, latW);
    leak_in_ts(k) = weighted_mean_2d(leak_in_map, latW);
end

if isempty(monthToPlot)
    [~, month_idx] = max(truth_rms_ts);
else
    month_idx = max(1, min(Nt, round(monthToPlot)));
end

% Select months to inspect (best + top-N by truth RMS)
[~, ord_rms] = sort(truth_rms_ts, 'descend');
inspect_months = unique([month_idx; ord_rms(1:min(inspectTopNMonths, Nt))], 'stable');
spatial_files = strings(numel(inspect_months), 1);

for mm = 1:numel(inspect_months)
    m = inspect_months(mm);
    map_true = truth_map(:, :, m);
    map_filt = filt_map(:, :, m);
    map_out = max(abs(map_true) - abs(map_filt), 0);
    map_in = max(abs(map_filt) - abs(map_true), 0);

    % Per-month color limits
    cMain = prctile(abs([map_true(:); map_filt(:)]), 98);
    cMain = max(cMain, 1);
    cLeak = prctile([map_out(:); map_in(:)], 98);
    cLeak = max(cLeak, 0.2);

    fig1 = figure('Color', 'w', 'Position', [60, 60, 1360, 980]);
    tlo = tiledlayout(2, 2, 'TileSpacing', 'compact', 'Padding', 'compact');

    ax = nexttile(tlo, 1);
    plot_panel(ax, lon_map, lat_map, map_true, cap, [-cMain, cMain], ...
        sprintf('(a) Mascon Truth (month %d)', m), 'redblue');

    ax = nexttile(tlo, 2);
    plot_panel(ax, lon_map, lat_map, map_filt, cap, [-cMain, cMain], ...
        sprintf('(b) Gaussian Filtered (month %d)', m), 'redblue');

    ax = nexttile(tlo, 3);
    plot_panel(ax, lon_map, lat_map, map_in, cap, [0, cLeak], ...
        sprintf('(c) Leakage-In (month %d)', m), 'parula');

    ax = nexttile(tlo, 4);
    plot_panel(ax, lon_map, lat_map, map_out, cap, [0, cLeak], ...
        sprintf('(d) Leakage-Out (month %d)', m), 'parula');

    spatial_files(mm) = string(fullfile(outputDir, sprintf('caspian_his_leakage_spatial_m%02d.png', m)));
    exportgraphics(fig1, spatial_files(mm), 'Resolution', 400);
    close(fig1);
end

rms_truth = sqrt(mean(truth_ts.^2, 'omitnan'));
rms_filt = sqrt(mean(filt_ts.^2, 'omitnan'));
rms_ratio_percent = 100 * safe_div(rms_filt, rms_truth);
out1 = fullfile(outputDir, 'caspian_his_leakage_spatial.png');
copyfile(char(spatial_files(1)), out1, 'f');

% ---------- Figure 2: time-series leakage ----------
fig2 = figure('Color', 'w', 'Position', [80, 80, 1250, 820]);
tlo2 = tiledlayout(2, 1, 'TileSpacing', 'compact', 'Padding', 'compact');

ax1 = nexttile(tlo2, 1);
hold(ax1, 'on');
fill_x = [years, fliplr(years)];
fill_y = [truth_ts', fliplr(filt_ts')];
patch('Parent', ax1, 'XData', fill_x, 'YData', fill_y, ...
    'FaceColor', [0.82, 0.82, 0.82], 'FaceAlpha', 0.35, 'EdgeColor', 'none', ...
    'DisplayName', 'Attenuation Gap');
plot(ax1, years, truth_ts, 'g-', 'LineWidth', 2.0, 'DisplayName', 'Truth (Mascon)');
plot(ax1, years, filt_ts, 'r-', 'LineWidth', 2.0, 'DisplayName', 'Filtered (Gaussian)');
plot(ax1, years, atten_ts, 'k--', 'LineWidth', 1.3, 'DisplayName', 'Truth - Filtered');
grid(ax1, 'on');
box(ax1, 'on');
xlabel(ax1, 'Year');
ylabel(ax1, 'EWH (cm)');
title(ax1, 'Basin-Mean Time Series and Signal Attenuation', ...
    'FontName', 'Times New Roman', 'FontWeight', 'bold');
legend(ax1, 'Location', 'best');
set(ax1, 'FontName', 'Times New Roman', 'FontSize', 11);

ax2 = nexttile(tlo2, 2);
b = bar(ax2, years, [leak_out_ts, leak_in_ts], 1.0, 'grouped');
b(1).FaceColor = [0.95, 0.55, 0.20];
b(2).FaceColor = [0.25, 0.55, 0.90];
b(1).DisplayName = 'Leakage-Out Component';
b(2).DisplayName = 'Leakage-In Component';
ylabel(ax2, 'Component Magnitude (cm)');
xlabel(ax2, 'Year');
grid(ax2, 'on');
box(ax2, 'on');
title(ax2, 'Leakage-Out / Leakage-In Decomposition', ...
    'FontName', 'Times New Roman', 'FontWeight', 'bold');
set(ax2, 'FontName', 'Times New Roman', 'FontSize', 11);
ylim(ax2, [0, max([leak_out_ts; leak_in_ts], [], 'omitnan') * 1.25 + 0.1]);

legend(ax2, 'Location', 'best');

out2 = fullfile(outputDir, 'caspian_his_leakage_timeseries.png');
exportgraphics(fig2, out2, 'Resolution', 400);
close(fig2);

% ---------- Figure 3: profile schematic ----------
% Build a zonal profile near basin center latitude for visual leakage concept.
lat_center = mean(lat_basin, 'omitnan');
j_center = nearest_idx(csr_lat, lat_center);
j0 = max(1, j_center - 1);
j1p = min(numel(csr_lat), j_center + 1);

lon_min = min(cap_x) - profilePadDeg;
lon_max = max(cap_x) + profilePadDeg;
iL = nearest_idx(csr_lon, lon_min);
iR = nearest_idx(csr_lon, lon_max);
if iL > iR
    tmp = iL; iL = iR; iR = tmp;
end

lon_prof = csr_lon(iL:iR);
truth_prof = squeeze(mean(HIS_EWH.Mascon(iL:iR, j0:j1p, month_idx), 2, 'omitnan'));
filt_prof = squeeze(mean(HIS_EWH.Gaussian(iL:iR, j0:j1p, month_idx), 2, 'omitnan'));

fig3 = figure('Color', 'w', 'Position', [120, 120, 1180, 420]);
ax3 = axes(fig3); hold(ax3, 'on');

yl = [min([truth_prof; filt_prof], [], 'omitnan'), max([truth_prof; filt_prof], [], 'omitnan')];
ypad = max(0.5, 0.1 * (yl(2) - yl(1)));
yl = [yl(1) - ypad, yl(2) + ypad];

roiL = min(cap_x);
roiR = max(cap_x);
patch(ax3, [roiL roiR roiR roiL], [yl(1) yl(1) yl(2) yl(2)], ...
    [0.87 0.95 0.87], 'FaceAlpha', 0.35, 'EdgeColor', 'none', 'DisplayName', 'Region of Interest');
plot(ax3, lon_prof, truth_prof, 'g-', 'LineWidth', 2.2, 'DisplayName', 'Signal Original (Mascon)');
plot(ax3, lon_prof, filt_prof, 'r-', 'LineWidth', 2.2, 'DisplayName', 'Signal After Filter (Gaussian)');
plot(ax3, lon_prof, truth_prof - filt_prof, 'k--', 'LineWidth', 1.5, 'DisplayName', 'Signal Attenuation (Mascon-Gaussian)');
xline(ax3, roiL, 'k--', 'LineWidth', 1.2, 'HandleVisibility', 'off');
xline(ax3, roiR, 'k--', 'LineWidth', 1.2, 'HandleVisibility', 'off');

grid(ax3, 'on');
box(ax3, 'on');
ylim(ax3, yl);
xlabel(ax3, 'Longitude (deg)');
ylabel(ax3, 'EWH (cm)');
title(ax3, sprintf('Leakage Schematic Profile (month %d, lat %.2f deg)', month_idx, csr_lat(j_center)), ...
    'FontName', 'Times New Roman', 'FontWeight', 'bold');
legend(ax3, 'Location', 'best');
set(ax3, 'FontName', 'Times New Roman', 'FontSize', 11);

out3 = fullfile(outputDir, 'caspian_his_leakage_profile.png');
exportgraphics(fig3, out3, 'Resolution', 400);
close(fig3);

% Save metrics for downstream reuse
summary = struct();
summary.month_idx = month_idx;
summary.years = years;
summary.truth_ts = truth_ts;
summary.filtered_ts = filt_ts;
summary.atten_ts = atten_ts;
summary.leak_out_ts = leak_out_ts;
summary.leak_in_ts = leak_in_ts;
summary.truth_rms_ts = truth_rms_ts;
summary.rms_truth = rms_truth;
summary.rms_filtered = rms_filt;
summary.rms_ratio_percent = rms_ratio_percent;
summary.mean_leak_out = mean(leak_out_ts, 'omitnan');
summary.mean_leak_in = mean(leak_in_ts, 'omitnan');
summary.inspect_months = inspect_months;
summary.spatial_files = spatial_files;

save(fullfile(outputDir, 'caspian_his_leakage_metrics.mat'), 'summary');

fprintf('Done.\n');
fprintf('Outputs:\n');
fprintf('  %s\n', out1);
fprintf('  %s\n', out2);
fprintf('  %s\n', out3);
fprintf('  %s\n', fullfile(outputDir, 'caspian_his_leakage_metrics.mat'));
fprintf('Spatial months (high to low truth RMS): %s\n', mat2str(inspect_months'));

% ---------- local functions ----------
function idx = nearest_idx(vec, val)
    [~, idx] = min(abs(vec - val));
end

function m = build_mask_lonlat(cap, lon_sub, lat_sub, cap_mk)
    % Try direct mask from mkmask first, otherwise rebuild by inpolygon.
    m = cap_mk';
    expectedSz = [numel(lon_sub), numel(lat_sub)];
    if ~isequal(size(m), expectedSz)
        [LON, LAT] = meshgrid(lon_sub, lat_sub);
        mLatLon = false(size(LON));
        for ii = 1:numel(cap)
            mLatLon = mLatLon | inpolygon(LON, LAT, cap(ii).X, cap(ii).Y);
        end
        m = double(mLatLon');
    end
    m(m == 0) = NaN;
end

function v = weighted_mean_2d(Z, latW)
    % Z is [nLon x nLat], latW is [1 x nLat]
    W = repmat(latW, size(Z, 1), 1);
    valid = isfinite(Z) & isfinite(W);
    if ~any(valid, 'all')
        v = NaN;
        return;
    end
    v = sum(Z(valid) .* W(valid), 'omitnan') / sum(W(valid), 'omitnan');
end

function plot_panel(ax, lon, lat, Z, cap, cax, ttl, cmapName)
    imagesc(ax, lon, lat, Z');
    set(ax, 'YDir', 'normal');
    axis(ax, 'tight');
    axis(ax, 'equal');
    hold(ax, 'on');
    for ii = 1:numel(cap)
        plot(ax, cap(ii).X, cap(ii).Y, 'k-', 'LineWidth', 1.0);
    end
    grid(ax, 'on');
    box(ax, 'on');
    colormap(ax, get_cmap(cmapName));
    caxis(ax, cax);
    cb = colorbar(ax);
    cb.Label.String = 'EWH (cm)';
    xlabel(ax, 'Lon');
    ylabel(ax, 'Lat');
    title(ax, ttl, 'FontName', 'Times New Roman', 'FontWeight', 'bold', 'FontSize', 11);
    text(ax, 0.02, 0.98, ttl, 'Units', 'normalized', ...
        'HorizontalAlignment', 'left', 'VerticalAlignment', 'top', ...
        'FontName', 'Times New Roman', 'FontWeight', 'bold', 'FontSize', 11, ...
        'BackgroundColor', [1 1 1], 'Margin', 1);
    set(ax, 'FontName', 'Times New Roman', 'FontSize', 10);
end

function cmap = get_cmap(name)
    switch lower(name)
        case 'redblue'
            n = 256; n2 = floor(n / 2);
            r = [(0:n2-1)' / max(n2-1, 1); ones(n-n2, 1)];
            g = [(0:n2-1)' / max(n2-1, 1); (n-n2-1:-1:0)' / max(n-n2-1, 1)];
            b = [ones(n2, 1); (n-n2-1:-1:0)' / max(n-n2-1, 1)];
            cmap = [r g b];
        case 'parula'
            cmap = parula(256);
        otherwise
            cmap = jet(256);
    end
end

function y = safe_div(a, b)
    if abs(b) < eps
        y = NaN;
    else
        y = a / b;
    end
end
