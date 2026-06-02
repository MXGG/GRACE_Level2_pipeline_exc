function SH = inv_read_gsm_month(cfg, Tk)
%INV_READ_GSM_MONTH Read monthly GSM coefficients and return SH struct.

    Lmax = cfg.inversion.Lmax;
    gfcFile = inv_find_gfc_file(cfg, Tk);
    SH = inv_read_gfc(gfcFile, Lmax);

    % attach time tag
    SH.meta.ym = Tk.ym;
    SH.meta.yyyymm = Tk.yyyymm;
end
