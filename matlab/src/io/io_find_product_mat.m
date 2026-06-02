function fp = io_find_product_mat(paths, tag, Tk)
%IO_FIND_PRODUCT_MAT Return expected MAT path; does not check existence.
    if isfield(Tk,'yyyymm')
        yyyymm = Tk.yyyymm;
    elseif isfield(Tk,'ym')
        yyyymm = strrep(Tk.ym,'-','');
    else
        yyyymm = datestr(Tk.dt,'yyyymm');
    end

    matDir = fullfile(paths.monthly_mat, tag);
    fp = fullfile(matDir, sprintf('%s_%s.mat', tag, yyyymm));
end
