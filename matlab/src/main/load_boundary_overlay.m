function B = load_boundary_overlay(cfg)
%LOAD_BOUNDARY_OVERLAY Load shared basin boundary overlay for plotting.

    B = [];
    if ~isfield(cfg, 'plot') || ~isfield(cfg.plot, 'basin_overlay') || ~cfg.plot.basin_overlay
        return;
    end
    if ~isfield(cfg, 'path') || ~isfield(cfg.path, 'BOUNDARY')
        return;
    end

    shp = fullfile(cfg.path.BOUNDARY, 'LargeBasin.shp');
    if ~isfile(shp)
        return;
    end

    try
        B = basin_read_boundary(shp);
    catch
        B = [];
    end
end
