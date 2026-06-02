function fp = io_build_product_paths(paths, tag, Tk)
%IO_BUILD_PRODUCT_PATHS Build standard file paths for a monthly product (.mat/.txt).

    if isfield(Tk,'yyyymm')
        yyyymm = Tk.yyyymm;
    elseif isfield(Tk,'ym')
        yyyymm = strrep(Tk.ym,'-','');
    else
        yyyymm = datestr(Tk.dt,'yyyymm');
    end

    matDir = fullfile(paths.monthly_mat, tag);
    txtDir = fullfile(paths.monthly_txt, tag);
    ensure_dir(matDir);
    ensure_dir(txtDir);

    fp = struct();
    fp.mat = fullfile(matDir, sprintf('%s_%s.mat', tag, yyyymm));
    fp.txt = fullfile(txtDir, sprintf('%s_%s.txt', tag, yyyymm));
end
