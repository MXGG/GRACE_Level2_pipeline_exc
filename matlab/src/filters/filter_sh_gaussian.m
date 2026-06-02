function [Dc_f, Ds_f, meta] = filter_sh_gaussian(Dc, Ds, Lmax, radius_km)
%FILTER_SH_GAUSSIAN Apply Gaussian filter (degree smoothing) to SH coefficients.

    [Dc_f, Ds_f, w1] = apply_gaussian_filter(radius_km, Lmax, Dc, Ds);

    meta = struct();
    meta.type = 'Gaussian';
    meta.radius_km = radius_km;
    meta.w_degree = w1;
end
