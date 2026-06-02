function fp = io_save_product(cfg, paths, P)
%IO_SAVE_PRODUCT Save a monthly product to MAT and optional TXT.
% Respects cfg.io.save_monthly_mat and cfg.io.export_txt.

    tag = P.tag;
    Tk  = P.time;

    fp = io_build_product_paths(paths, tag, Tk);

    if ~isfield(cfg,'io'); cfg.io = struct(); end

    saveMat = true;
    if isfield(cfg.io,'save_monthly_mat'); saveMat = cfg.io.save_monthly_mat; end

    exportTxt = false;
    if isfield(cfg.io,'export_txt'); exportTxt = cfg.io.export_txt; end

    if saveMat
        safe_save_mat(fp.mat, P);
    end

    if exportTxt
        fmt = 'lonlatval';
        if isfield(cfg.io,'txt_format'); fmt = cfg.io.txt_format; end
        if strcmpi(fmt,'lonlatval')
            io_write_grid_xyz(fp.txt, P.grid.ewh, P.grid.lon, P.grid.lat, 'asc');
        else
            % fallback: lon lat val
            io_write_grid_xyz(fp.txt, P.grid.ewh, P.grid.lon, P.grid.lat, 'asc');
        end
    end
end

function safe_save_mat(fp, P)
%SAFE_SAVE_MAT Write MAT file via temp file to avoid corruption on failure.
    tmp = [fp '.tmp'];
    if exist(tmp,'file'); delete(tmp); end
    try
        save(tmp, 'P', '-v7.3');
        movefile(tmp, fp, 'f');
    catch ME
        if exist(tmp,'file'); delete(tmp); end
        rethrow(ME);
    end
end
