function [Dc_f, Ds_f, meta] = filter_sh_fan(Dc, Ds, Lmax, radius1_km, radius2_km)
%FILTER_SH_FAN Fan filter (anisotropic Gaussian):
%  - Gaussian smoothing along DEGREE (radius1_km)
%  - Gaussian smoothing along ORDER  (radius2_km)
%
% This is consistent with the common Fan filter implementation used in many GRACE toolchains.

    % 1) Degree smoothing
    [Dc1, Ds1] = apply_gaussian_filter(radius1_km, Lmax, Dc, Ds);

    % 2) Order smoothing (apply weights across columns)
    % Build order weights w2 (same recurrence, but applied on order dimension)
    persistent orderWeightCache
    if isempty(orderWeightCache)
        orderWeightCache = containers.Map('KeyType','char','ValueType','any');
    end

    if radius2_km <= 0
        Dc_f = Dc1; Ds_f = Ds1;
        w2 = ones(1, Lmax+1);
    else
        cacheKey = sprintf('L%d_R%.8f', Lmax, radius2_km);
        if isKey(orderWeightCache, cacheKey)
            w2 = orderWeightCache(cacheKey);
        else
            a  = 6.378136460e6;
            r2 = radius2_km * 1000;
            b2 = log(2) / (1 - cos(r2/a));

            w2 = zeros(1, Lmax+1);
            w2(1) = 1;
            if Lmax >= 1
                w2(2) = (1 + exp(-2*b2)) / (1 - exp(-2*b2)) - 1/b2;
            end
            for l = 1:(Lmax-1)
                w2(l+2) = -(2*l+1)/b2 * w2(l+1) + w2(l);
            end
            orderWeightCache(cacheKey) = w2;
        end
    end

    % 使用 size 检查而非 ndims，因为 ndims 对于 2D 数组始终返回 2
    is3D = (numel(size(Dc1)) >= 3 && size(Dc1,3) > 1);
    if ~is3D
        Dc_f = Dc1 .* w2;
        Ds_f = Ds1 .* w2;
    else
        Dc_f = Dc1 .* reshape(w2, [1, Lmax+1, 1]);
        Ds_f = Ds1 .* reshape(w2, [1, Lmax+1, 1]);
    end

    meta = struct();
    meta.type = 'Fan';
    meta.radius1_km = radius1_km;
    meta.radius2_km = radius2_km;
    meta.w_order = w2(:);
end
