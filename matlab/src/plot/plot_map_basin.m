function [fig, ax] = plot_map_basin(G, lonVec, latVec, B, opt)
%PLOT_MAP_BASIN Plot basin map with boundary overlay.
% B: boundary struct array from basin_read_boundary()

    if nargin < 5; opt = struct(); end
    if ~isfield(opt,'show_colorbar'); opt.show_colorbar = true; end
    if ~isfield(opt,'pad_deg'); opt.pad_deg = 2; end
    if ~isfield(opt,'grid_style'); opt.grid_style = 'dotted'; end
    if ~isfield(opt,'grid_color'); opt.grid_color = [0.6 0.6 0.6]; end
    if ~isfield(opt,'show_grid'); opt.show_grid = true; end
    if ~isfield(opt,'coast_res'); opt.coast_res = 'high'; end
    if ~isfield(opt,'coast_color'); opt.coast_color = 'k'; end
    if ~isfield(opt,'coast_linewidth'); opt.coast_linewidth = 0.6; end
    if ~isfield(opt,'coast_shp'); opt.coast_shp = ''; end
    if ~isfield(opt,'font'); opt.font = 'Times New Roman'; end
    if ~isfield(opt,'fontsize'); opt.fontsize = 10; end
    if ~isfield(opt,'shading'); opt.shading = 'interp'; end

    if isfield(opt,'ax') && ~isempty(opt.ax) && isgraphics(opt.ax)
        ax = opt.ax;
        fig = ancestor(ax, 'figure');
        axes(ax);
        cla(ax);
        hold(ax,'on');
    else
        fig = figure('Color','w');
        ax = axes(fig);
        hold(ax,'on');
    end

    Gplot = align_grid_for_plot(G, lonVec, latVec);

    lonAll = vertcat(B(:).Lon); latAll = vertcat(B(:).Lat);
    lonAll = lonAll(isfinite(lonAll)); latAll = latAll(isfinite(latAll));
    if isempty(lonAll) || isempty(latAll)
        lonlim = [min(lonVec) max(lonVec)];
        latlim = [min(latVec) max(latVec)];
    else
        lonlim = [min(lonAll)-opt.pad_deg, max(lonAll)+opt.pad_deg];
        latlim = [min(latAll)-opt.pad_deg, max(latAll)+opt.pad_deg];
    end

    if exist('m_proj','file') == 2
        [LON, LAT] = meshgrid(lonVec, latVec);
        proj = select_region_proj(latlim, lonlim);
        if isfield(opt,'proj') && ~isempty(opt.proj)
            proj = opt.proj;
        end
        try
            m_proj(proj,'lon',lonlim,'lat',latlim);
            m_pcolor(LON, LAT, Gplot);
            shading(opt.shading);
            cmap = resolve_colormap(opt);
            if ~isempty(cmap); colormap(ax, cmap); end
            draw_coastline(opt, true);
            for i = 1:numel(B)
                m_plot(B(i).Lon, B(i).Lat, 'k-', 'LineWidth', 1.0);
            end
            if opt.show_grid
                m_grid('box','fancy','tickdir','out', ...
                    'fontsize',opt.fontsize,'fontname',opt.font, ...
                    'linestyle',grid_linestyle(opt.grid_style), ...
                    'linewidth',0.8,'color',opt.grid_color);
            end
        catch
            % fallback to simple axes if projection fails
            imagesc(ax, lonVec, latVec, Gplot);
            set(ax,'YDir','normal');
            if opt.show_grid; grid(ax,'on'); end
            box(ax,'on');
            for i = 1:numel(B)
                plot(B(i).Lon, B(i).Lat, 'k-', 'LineWidth', 1.0);
            end
            cmap = resolve_colormap(opt);
            if ~isempty(cmap); colormap(ax, cmap); end
            xlim(ax, lonlim);
            ylim(ax, latlim);
        end
    else
        imagesc(ax, lonVec, latVec, Gplot);
        set(ax,'YDir','normal');
        if opt.show_grid
            grid(ax,'on');
        end
        box(ax,'on');
        draw_coastline(opt, false);
        for i = 1:numel(B)
            plot(B(i).Lon, B(i).Lat, 'k-', 'LineWidth', 1.0);
        end
        xlim(ax, lonlim);
        ylim(ax, latlim);
        cmap = resolve_colormap(opt);
        if ~isempty(cmap); colormap(ax, cmap); end
    end

    if isfield(opt,'caxis') && ~isempty(opt.caxis)
        caxis(ax, opt.caxis);
    elseif isfield(opt,'auto_caxis') && opt.auto_caxis
        vals = Gplot(isfinite(Gplot));
        if ~isempty(vals)
            prcRange = [2 98];
            if isfield(opt,'auto_caxis_prc') && ~isempty(opt.auto_caxis_prc)
                prcRange = opt.auto_caxis_prc;
            end
            prc = prctile(vals, prcRange);
            if prc(1) == prc(2)
                prc = prc + [-1 1] * max(abs(prc(1)), 1e-6);
            end
            caxis(ax, prc);
        end
    end
    if isfield(opt,'title'); title(ax, opt.title, 'Interpreter','none','FontName',opt.font,'FontSize',opt.fontsize); end
    if opt.show_colorbar; colorbar(ax); end
    set(ax,'FontName',opt.font,'FontSize',opt.fontsize);

    % auto zoom
    lonAll = vertcat(B(:).Lon); latAll = vertcat(B(:).Lat);
    lonAll = lonAll(isfinite(lonAll)); latAll = latAll(isfinite(latAll));
    if ~isempty(lonAll)
        xlim(ax, [min(lonAll)-opt.pad_deg, max(lonAll)+opt.pad_deg]);
        ylim(ax, [min(latAll)-opt.pad_deg, max(latAll)+opt.pad_deg]);
    end
end

function draw_coastline(opt, use_mmap)
    if nargin < 2; use_mmap = true; end
    [coastLon, coastLat, hasShp] = load_coastline_vectors(opt);
    if hasShp
        if use_mmap && exist('m_plot','file') == 2
            m_plot(coastLon, coastLat, 'Color', opt.coast_color, 'LineWidth', opt.coast_linewidth);
        else
            plot(coastLon, coastLat, 'Color', opt.coast_color, 'LineWidth', opt.coast_linewidth);
        end
        return;
    end

    try
        if exist('m_gshhs','file') == 2
            dataDir = fileparts(which('m_gshhs'));
            dataDir = fullfile(dataDir, 'data');
            if ~isfolder(dataDir)
                dataDir = fullfile(fileparts(fileparts(which('m_gshhs'))), 'data');
            end
            wantFile = '';
            switch lower(opt.coast_res)
                case 'full'
                    wantFile = 'gshhs_f.b';
                case 'high'
                    wantFile = 'gshhs_h.b';
                case 'intermediate'
                    wantFile = 'gshhs_i.b';
                otherwise
                    wantFile = 'gshhs_l.b';
            end
            if isempty(dataDir) || ~isfolder(dataDir)
                m_coast('color',opt.coast_color,'linewidth',opt.coast_linewidth);
                return;
            end
            if ~isempty(wantFile) && ~isfile(fullfile(dataDir, wantFile))
                m_coast('color',opt.coast_color,'linewidth',opt.coast_linewidth);
                return;
            end
            switch lower(opt.coast_res)
                case 'full'
                    m_gshhs_f('color',opt.coast_color,'linewidth',opt.coast_linewidth);
                case 'high'
                    m_gshhs_h('color',opt.coast_color,'linewidth',opt.coast_linewidth);
                case 'intermediate'
                    m_gshhs_i('color',opt.coast_color,'linewidth',opt.coast_linewidth);
                otherwise
                    m_gshhs_l('color',opt.coast_color,'linewidth',opt.coast_linewidth);
            end
            return;
        end
    catch
    end
    m_coast('color',opt.coast_color,'linewidth',opt.coast_linewidth);
end

function [lonVec, latVec, ok] = load_coastline_vectors(opt)
    persistent coastLon coastLat coastFile
    lonVec = []; latVec = []; ok = false;

    shp = '';
    if isfield(opt,'coast_shp') && ~isempty(opt.coast_shp)
        shp = opt.coast_shp;
    else
        shp = default_coast_shp();
    end
    if isempty(shp) || ~isfile(shp) || exist('shaperead','file') ~= 2
        return;
    end

    if isempty(coastFile) || ~strcmp(coastFile, shp)
        try
            S = shaperead(shp, 'UseGeoCoords', true);
        catch
            return;
        end
        lonAll = [];
        latAll = [];
        for k = 1:numel(S)
            lon = S(k).Lon(:);
            lat = S(k).Lat(:);
            lonAll = [lonAll; lon; NaN]; %#ok<AGROW>
            latAll = [latAll; lat; NaN]; %#ok<AGROW>
        end
        coastLon = lonAll;
        coastLat = latAll;
        coastFile = shp;
    end

    lonVec = coastLon;
    latVec = coastLat;
    ok = true;
end

function shp = default_coast_shp()
    shp = '';
    try
        p = fileparts(mfilename('fullpath')); % .../src/plot
        root = fileparts(fileparts(p));       % project root
        base = fullfile(root, 'data', 'Boundary', 'ne_admin_0');
        if ~isfolder(base)
            return;
        end
        cand = { ...
            fullfile(base, 'ne_10m_admin_0_countries.shp'), ...
            fullfile(base, 'ne_50m_admin_0_countries.shp'), ...
            fullfile(base, 'ne_110m_admin_0_countries.shp')};
        for i = 1:numel(cand)
            if isfile(cand{i})
                shp = cand{i};
                return;
            end
        end
        d = dir(fullfile(base, '*.shp'));
        if ~isempty(d)
            shp = fullfile(d(1).folder, d(1).name);
        end
    catch
        shp = '';
    end
end

function ls = grid_linestyle(style)
    switch lower(style)
        case {'dot','dotted',':'}
            ls = ':';
        case {'dash','dashed','--'}
            ls = '--';
        otherwise
            ls = '-';
    end
end

function proj = select_region_proj(latlim, lonlim)
    latSpan = abs(diff(latlim));
    latMean = mean(latlim);
    if latSpan > 80
        proj = 'mercator';
        return;
    end
    if abs(latMean) >= 50 && latSpan <= 40
        proj = 'stereographic';
        return;
    end
    proj = 'lambert';
end

function cmap = resolve_colormap(opt)
    cmap = [];
    if isfield(opt,'colormap') && ~isempty(opt.colormap)
        if ischar(opt.colormap)
            switch lower(opt.colormap)
                case 'jet'
                    cmap = jet(256);
                case {'bwr','redblue','rdblu'}
                    cmap = redblue_cmap(256);
                otherwise
                    try
                        cmap = feval(opt.colormap, 256);
                    catch
                        cmap = [];
                    end
            end
        elseif isnumeric(opt.colormap)
            cmap = opt.colormap;
        end
    end
end

function cmap = redblue_cmap(n)
    if nargin < 1; n = 256; end
    n = max(2, n);
    n2 = floor(n/2);
    r = [(0:n2-1)'/max(n2-1,1); ones(n-n2,1)];
    g = [(0:n2-1)'/max(n2-1,1); (n-n2-1:-1:0)'/max(n-n2-1,1)];
    b = [ones(n2,1); (n-n2-1:-1:0)'/max(n-n2-1,1)];
    cmap = [r g b];
end

function Gout = align_grid_for_plot(G, lonVec, latVec)
    nLon = numel(lonVec);
    nLat = numel(latVec);
    sz = size(G);
    if isequal(sz, [nLat, nLon])
        Gout = G;
    elseif isequal(sz, [nLon, nLat])
        Gout = G.';
    else
        error('Grid size does not match lon/lat vectors.');
    end
end
